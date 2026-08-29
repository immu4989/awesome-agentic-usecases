"""Matched, deterministic control-effectiveness experiments for agent boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_VERSION = "aau-agent-control-experiment/0.1"
REPORT_VERSION = "aau-agent-control-report/0.1"
MAX_BYTES = 1_000_000


class ObservatoryError(ValueError):
    """Raised when a matched control experiment is invalid."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise ObservatoryError(f"invalid, symbolic, or oversized input: {source}")
    try:
        value = json.loads(source.read_bytes())
    except json.JSONDecodeError as exc:
        raise ObservatoryError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise ObservatoryError(f"expected one JSON object in {source}")
    return value


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ObservatoryError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def validate_experiment(experiment: dict[str, Any]) -> None:
    if set(experiment) != {
        "experiment_version",
        "experiment_id",
        "title",
        "controls",
        "arms",
        "cases",
        "sources",
        "boundary",
    }:
        raise ObservatoryError("experiment fields differ from the 0.1 contract")
    if experiment["experiment_version"] != EXPERIMENT_VERSION:
        raise ObservatoryError(f"experiment_version must be {EXPERIMENT_VERSION}")
    _text(experiment["experiment_id"], "experiment_id", 120)
    _text(experiment["title"], "title")
    controls = experiment["controls"]
    if not isinstance(controls, list) or not controls or any(
        not isinstance(item, dict) or set(item) != {"control_id", "title", "reason_codes"}
        for item in controls
    ):
        raise ObservatoryError("controls must contain control_id, title, and reason_codes")
    control_ids: set[str] = set()
    for index, control in enumerate(controls):
        control_id = _text(control["control_id"], f"controls[{index}].control_id", 100)
        if control_id in control_ids:
            raise ObservatoryError(f"duplicate control_id: {control_id}")
        control_ids.add(control_id)
        _text(control["title"], f"controls[{index}].title")
        if not isinstance(control["reason_codes"], list) or not control["reason_codes"]:
            raise ObservatoryError("each control requires at least one reason code")

    arms = experiment["arms"]
    if not isinstance(arms, list) or len(arms) < 2:
        raise ObservatoryError("at least two matched arms are required")
    arm_ids: set[str] = set()
    for index, arm in enumerate(arms):
        if not isinstance(arm, dict) or set(arm) != {"arm_id", "title", "active_controls", "limitations"}:
            raise ObservatoryError(f"arms[{index}] fields differ")
        arm_id = _text(arm["arm_id"], f"arms[{index}].arm_id", 100)
        if arm_id in arm_ids:
            raise ObservatoryError(f"duplicate arm_id: {arm_id}")
        arm_ids.add(arm_id)
        _text(arm["title"], f"arms[{index}].title")
        active = arm["active_controls"]
        if not isinstance(active, list) or not set(active).issubset(control_ids) or len(active) != len(set(active)):
            raise ObservatoryError(f"arms[{index}].active_controls are invalid")
        if not isinstance(arm["limitations"], list) or not arm["limitations"]:
            raise ObservatoryError("each arm requires limitations")

    cases = experiment["cases"]
    if not isinstance(cases, list) or len(cases) < 2:
        raise ObservatoryError("at least two matched cases are required")
    case_ids: set[str] = set()
    outcomes = {"allow", "block", "pause", "safe_stop"}
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != {
            "case_id",
            "title",
            "failure_shape",
            "required_outcome",
            "required_control",
        }:
            raise ObservatoryError(f"cases[{index}] fields differ")
        case_id = _text(case["case_id"], f"cases[{index}].case_id", 100)
        if case_id in case_ids:
            raise ObservatoryError(f"duplicate case_id: {case_id}")
        case_ids.add(case_id)
        _text(case["title"], f"cases[{index}].title")
        _text(case["failure_shape"], f"cases[{index}].failure_shape")
        if case["required_outcome"] not in outcomes:
            raise ObservatoryError(f"cases[{index}].required_outcome is unsupported")
        required_control = case["required_control"]
        if case["required_outcome"] == "allow":
            if required_control is not None:
                raise ObservatoryError("legitimate allow cases must not name a required control")
        elif required_control not in control_ids:
            raise ObservatoryError(f"cases[{index}] requires an unknown control")

    sources = experiment["sources"]
    if not isinstance(sources, list) or not sources:
        raise ObservatoryError("sources must be non-empty")
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"publisher", "title", "url", "reviewed_on"}:
            raise ObservatoryError(f"sources[{index}] fields differ")
        if not _text(source["url"], f"sources[{index}].url").startswith("https://"):
            raise ObservatoryError("source URLs must use HTTPS")
        for key in ("publisher", "title", "reviewed_on"):
            _text(source[key], f"sources[{index}].{key}")
    boundary = experiment["boundary"]
    if not isinstance(boundary, dict) or set(boundary) != {
        "synthetic_policy_arms",
        "not_product_benchmark",
        "not_model_benchmark",
        "no_universal_score",
    } or any(value is not True for value in boundary.values()):
        raise ObservatoryError("all experiment boundaries must be true")


def _outcome_for(case: dict[str, Any], active_controls: set[str]) -> str:
    if case["required_outcome"] == "allow":
        return "allow"
    if case["required_control"] in active_controls:
        return case["required_outcome"]
    return "allow"


def evaluate_experiment(experiment: dict[str, Any]) -> dict[str, Any]:
    validate_experiment(experiment)
    control_map = {item["control_id"]: item for item in experiment["controls"]}
    arm_rows = []
    for arm in experiment["arms"]:
        active = set(arm["active_controls"])
        case_rows = []
        for case in experiment["cases"]:
            observed = _outcome_for(case, active)
            required = case["required_outcome"]
            exact = observed == required
            unsafe_allow = observed == "allow" and required != "allow"
            legitimate = required == "allow"
            reason_codes = []
            if exact and case["required_control"]:
                reason_codes = control_map[case["required_control"]]["reason_codes"]
            case_rows.append(
                {
                    "case_id": case["case_id"],
                    "required_outcome": required,
                    "observed_outcome": observed,
                    "required_control": case["required_control"],
                    "reason_codes": sorted(reason_codes),
                    "exact_outcome": int(exact),
                    "unsafe_allow": int(unsafe_allow),
                    "legitimate_allow_preserved": int(legitimate and observed == "allow"),
                }
            )
        count = len(case_rows)
        legitimate_count = sum(row["required_outcome"] == "allow" for row in case_rows)
        unsafe_required = sum(row["required_outcome"] != "allow" for row in case_rows)
        arm_rows.append(
            {
                "arm_id": arm["arm_id"],
                "active_controls": sorted(active),
                "measurements": {
                    "exact_outcome": round(sum(row["exact_outcome"] for row in case_rows) / count, 6),
                    "unsafe_allow_rate": round(sum(row["unsafe_allow"] for row in case_rows) / unsafe_required, 6),
                    "legitimate_allow_preservation": round(
                        sum(row["legitimate_allow_preserved"] for row in case_rows) / legitimate_count, 6
                    ) if legitimate_count else None,
                    "control_coverage": round(len(active) / len(control_map), 6),
                },
                "cases": case_rows,
                "limitations": arm["limitations"],
            }
        )
    return {
        "report_version": REPORT_VERSION,
        "experiment_id": experiment["experiment_id"],
        "experiment_sha256": _digest(experiment),
        "case_count": len(experiment["cases"]),
        "control_count": len(experiment["controls"]),
        "arms": arm_rows,
        "boundary": experiment["boundary"],
    }


def verify_report(report: dict[str, Any], experiment: dict[str, Any]) -> None:
    if report != evaluate_experiment(experiment):
        raise ObservatoryError("report does not recompute from the supplied experiment")


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists():
        raise ObservatoryError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-controls", description="Run a matched synthetic agent-control experiment.")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("experiment", type=Path)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("experiment", type=Path)
    evaluate.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("report", type=Path)
    verify.add_argument("--experiment", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "validate":
            validate_experiment(load_json(args.experiment))
            print(f"OK: {args.experiment} is a valid matched control experiment.")
            return 0
        if args.command == "evaluate":
            report = evaluate_experiment(load_json(args.experiment))
            write_json(report, args.out)
            print(f"OK: {len(report['arms'])} matched control arms written to {args.out}.")
            return 0
        verify_report(load_json(args.report), load_json(args.experiment))
        print(f"OK: {args.report} recomputes from {args.experiment}.")
        return 0
    except ObservatoryError as exc:
        print(f"aau-controls: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
