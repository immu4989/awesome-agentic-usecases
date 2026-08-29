"""Offline assessment and evidence-pack builder for essential-service defender kits."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


KIT_VERSION = "aau-essential-service-defender-kit/0.1"
ASSESSMENT_VERSION = "aau-essential-service-defender-assessment/0.1"
PACK_VERSION = "aau-essential-service-defender-pack/0.1"
MAX_BYTES = 1_000_000


class DefenderError(ValueError):
    """Raised when a defender kit violates its public contract."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if source.is_symlink():
        raise DefenderError(f"refusing symbolic link: {source}")
    if not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise DefenderError(f"invalid or oversized file: {source}")
    try:
        value = json.loads(source.read_bytes())
    except json.JSONDecodeError as exc:
        raise DefenderError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise DefenderError(f"expected one JSON object in {source}")
    return value


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise DefenderError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _list(value: Any, label: str, *, allow_empty: bool = False) -> list[Any]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise DefenderError(f"{label} must be a list")
    return value


def validate_kit(kit: dict[str, Any]) -> None:
    fields = {
        "kit_version",
        "kit_id",
        "title",
        "sector",
        "beneficiary",
        "mission",
        "official_sources",
        "system_boundary",
        "agent_boundary",
        "controls",
        "exercises",
        "thirty_day_plan",
        "measurement_plan",
        "public_boundary",
        "claims",
    }
    if set(kit) != fields:
        raise DefenderError("defender kit fields differ from the 0.1 contract")
    if kit["kit_version"] != KIT_VERSION:
        raise DefenderError(f"kit_version must be {KIT_VERSION}")
    for key in ("kit_id", "title", "sector", "beneficiary", "mission"):
        _text(kit[key], key)

    sources = _list(kit["official_sources"], "official_sources")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"source_id", "agency", "title", "url", "reviewed_on"}:
            raise DefenderError(f"official_sources[{index}] fields differ")
        source_id = _text(source["source_id"], f"official_sources[{index}].source_id", 100)
        if source_id in source_ids:
            raise DefenderError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        _text(source["agency"], f"official_sources[{index}].agency", 160)
        _text(source["title"], f"official_sources[{index}].title")
        if not _text(source["url"], f"official_sources[{index}].url").startswith("https://"):
            raise DefenderError("official source URLs must use HTTPS")
        _text(source["reviewed_on"], f"official_sources[{index}].reviewed_on", 20)

    boundary = kit["system_boundary"]
    if not isinstance(boundary, dict) or set(boundary) != {"included", "excluded", "essential_operation"}:
        raise DefenderError("system_boundary fields differ")
    for key in ("included", "excluded"):
        if any(not isinstance(item, str) or not item for item in _list(boundary[key], f"system_boundary.{key}")):
            raise DefenderError(f"system_boundary.{key} must contain text")
    _text(boundary["essential_operation"], "system_boundary.essential_operation")

    agent = kit["agent_boundary"]
    if not isinstance(agent, dict) or set(agent) != {
        "may",
        "must_not",
        "stop_authority",
        "restart_authority",
        "safe_state",
    }:
        raise DefenderError("agent_boundary fields differ")
    for key in ("may", "must_not"):
        if any(not isinstance(item, str) or not item for item in _list(agent[key], f"agent_boundary.{key}")):
            raise DefenderError(f"agent_boundary.{key} must contain text")
    for key in ("stop_authority", "restart_authority"):
        if not _text(agent[key], f"agent_boundary.{key}", 120).startswith("human:"):
            raise DefenderError(f"agent_boundary.{key} must identify a human role")
    _text(agent["safe_state"], "agent_boundary.safe_state")

    controls = _list(kit["controls"], "controls")
    control_ids: set[str] = set()
    allowed_status = {"evidenced", "planned", "gap", "not_applicable"}
    for index, control in enumerate(controls):
        if not isinstance(control, dict) or set(control) != {
            "control_id",
            "title",
            "source_refs",
            "status",
            "evidence_refs",
            "failure_action",
        }:
            raise DefenderError(f"controls[{index}] fields differ")
        control_id = _text(control["control_id"], f"controls[{index}].control_id", 100)
        if control_id in control_ids:
            raise DefenderError(f"duplicate control_id: {control_id}")
        control_ids.add(control_id)
        _text(control["title"], f"controls[{index}].title")
        refs = _list(control["source_refs"], f"controls[{index}].source_refs")
        if not refs or not set(refs).issubset(source_ids):
            raise DefenderError(f"controls[{index}] has an invalid source reference")
        if control["status"] not in allowed_status:
            raise DefenderError(f"controls[{index}].status is unsupported")
        evidence = _list(control["evidence_refs"], f"controls[{index}].evidence_refs", allow_empty=True)
        if control["status"] == "evidenced" and not evidence:
            raise DefenderError("an evidenced control requires evidence_refs")
        _text(control["failure_action"], f"controls[{index}].failure_action")

    exercises = _list(kit["exercises"], "exercises")
    exercise_ids: set[str] = set()
    for index, exercise in enumerate(exercises):
        if not isinstance(exercise, dict) or set(exercise) != {
            "exercise_id",
            "title",
            "inject",
            "required_agent_outcome",
            "required_human_action",
            "success_evidence",
            "essential_service_guardrail",
        }:
            raise DefenderError(f"exercises[{index}] fields differ")
        exercise_id = _text(exercise["exercise_id"], f"exercises[{index}].exercise_id", 100)
        if exercise_id in exercise_ids:
            raise DefenderError(f"duplicate exercise_id: {exercise_id}")
        exercise_ids.add(exercise_id)
        for key in ("title", "inject", "required_human_action", "essential_service_guardrail"):
            _text(exercise[key], f"exercises[{index}].{key}")
        if exercise["required_agent_outcome"] not in {"block", "pause", "safe_stop"}:
            raise DefenderError("exercise agent outcome must be block, pause, or safe_stop")
        if any(not isinstance(item, str) or not item for item in _list(exercise["success_evidence"], f"exercises[{index}].success_evidence")):
            raise DefenderError("exercise success_evidence must contain text")

    plan = _list(kit["thirty_day_plan"], "thirty_day_plan")
    if len(plan) != 4:
        raise DefenderError("thirty_day_plan must contain four weekly entries")
    for index, week in enumerate(plan, 1):
        if not isinstance(week, dict) or set(week) != {"week", "objective", "deliverable", "owner"}:
            raise DefenderError(f"thirty_day_plan[{index - 1}] fields differ")
        if week["week"] != index:
            raise DefenderError("thirty_day_plan weeks must be contiguous")
        for key in ("objective", "deliverable", "owner"):
            _text(week[key], f"thirty_day_plan[{index - 1}].{key}")

    measurement = kit["measurement_plan"]
    if not isinstance(measurement, dict) or set(measurement) != {"measures", "observation_window", "claim_limit"}:
        raise DefenderError("measurement_plan fields differ")
    if any(not isinstance(item, str) or not item for item in _list(measurement["measures"], "measurement_plan.measures")):
        raise DefenderError("measurement measures must contain text")
    _text(measurement["observation_window"], "measurement_plan.observation_window")
    _text(measurement["claim_limit"], "measurement_plan.claim_limit")

    public = kit["public_boundary"]
    if not isinstance(public, dict) or set(public) != {
        "synthetic_only",
        "no_live_connections",
        "no_operational_details",
        "no_personal_data",
    } or any(value is not True for value in public.values()):
        raise DefenderError("all public safety boundaries must be true")
    claims = kit["claims"]
    if not isinstance(claims, dict) or set(claims) != {
        "not_risk_assessment",
        "not_compliance",
        "not_operational_authorization",
        "not_government_endorsement",
    } or any(value is not True for value in claims.values()):
        raise DefenderError("all non-certification claims must be true")


def assess_kit(kit: dict[str, Any]) -> dict[str, Any]:
    validate_kit(kit)
    by_status = {status: [] for status in ("evidenced", "planned", "gap", "not_applicable")}
    for control in kit["controls"]:
        by_status[control["status"]].append(control["control_id"])
    return {
        "assessment_version": ASSESSMENT_VERSION,
        "kit_id": kit["kit_id"],
        "kit_sha256": _digest(kit),
        "control_states": {key: sorted(value) for key, value in by_status.items()},
        "exercise_count": len(kit["exercises"]),
        "exercise_ids": [item["exercise_id"] for item in kit["exercises"]],
        "human_authority": {
            "stop": kit["agent_boundary"]["stop_authority"],
            "restart": kit["agent_boundary"]["restart_authority"],
        },
        "next_actions": [
            control["failure_action"]
            for control in kit["controls"]
            if control["status"] in {"gap", "planned"}
        ],
        "boundary": {
            "gap_visibility_only": True,
            "synthetic_only": True,
            "not_certification": True,
        },
    }


def verify_assessment(assessment: dict[str, Any], kit: dict[str, Any]) -> None:
    if assessment != assess_kit(kit):
        raise DefenderError("assessment does not recompute from the supplied defender kit")


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists():
        raise DefenderError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def build_pack(kit_path: Path, assessment_path: Path, out: Path) -> None:
    if out.exists():
        raise DefenderError(f"refusing to overwrite existing defender pack: {out}")
    kit = load_json(kit_path)
    assessment = load_json(assessment_path)
    verify_assessment(assessment, kit)
    out.mkdir(parents=True)
    shutil.copyfile(kit_path, out / "kit.json")
    shutil.copyfile(assessment_path, out / "assessment.json")
    (out / "README.md").write_text(
        "# Essential-service defender evidence pack\n\n"
        "This local-first pack exposes gaps, planned controls, exercises, human authority, and "
        "next actions. It uses synthetic system labels and is not a risk assessment, compliance "
        "finding, operational authorization, or government endorsement.\n"
    )
    files = []
    for path in sorted(out.iterdir()):
        data = path.read_bytes()
        files.append({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    (out / "manifest.json").write_text(json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-defender", description="Assess an offline essential-service defender kit.")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("kit", type=Path)
    assess = sub.add_parser("assess")
    assess.add_argument("kit", type=Path)
    assess.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("assessment", type=Path)
    verify.add_argument("--kit", type=Path, required=True)
    pack = sub.add_parser("pack")
    pack.add_argument("kit", type=Path)
    pack.add_argument("assessment", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "validate":
            validate_kit(load_json(args.kit))
            print(f"OK: {args.kit} is a valid public defender kit.")
            return 0
        if args.command == "assess":
            assessment = assess_kit(load_json(args.kit))
            write_json(assessment, args.out)
            print(f"OK: gap-visible assessment written to {args.out}.")
            return 0
        if args.command == "verify":
            verify_assessment(load_json(args.assessment), load_json(args.kit))
            print(f"OK: {args.assessment} recomputes from {args.kit}.")
            return 0
        build_pack(args.kit, args.assessment, args.out)
        print(f"OK: defender pack written to {args.out}.")
        return 0
    except DefenderError as exc:
        print(f"aau-defender: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
