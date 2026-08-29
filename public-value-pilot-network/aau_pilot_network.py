"""Privacy-bounded public-value pilot and reproduction contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


PILOT_VERSION = "aau-public-value-pilot/0.1"
ASSESSMENT_VERSION = "aau-public-value-pilot-assessment/0.1"
PACK_VERSION = "aau-public-value-pilot-pack/0.1"
MAX_BYTES = 1_000_000


class PilotError(ValueError):
    """Raised when a public-value pilot record overstates or under-specifies evidence."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise PilotError(f"invalid, symbolic, or oversized input: {source}")
    try:
        value = json.loads(source.read_bytes())
    except json.JSONDecodeError as exc:
        raise PilotError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise PilotError(f"expected one JSON object in {source}")
    return value


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise PilotError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _list(value: Any, label: str, *, allow_empty: bool = False) -> list[Any]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise PilotError(f"{label} must be a list")
    return value


def validate_pilot(pilot: dict[str, Any]) -> None:
    if set(pilot) != {
        "pilot_version",
        "pilot_id",
        "title",
        "beneficiaries",
        "accountable_owner",
        "task_contract",
        "pre_registration",
        "human_protection",
        "field_observation",
        "reproduction",
        "sources",
        "limitations",
        "claims",
    }:
        raise PilotError("pilot fields differ from the 0.1 contract")
    if pilot["pilot_version"] != PILOT_VERSION:
        raise PilotError(f"pilot_version must be {PILOT_VERSION}")
    for key in ("pilot_id", "title", "accountable_owner"):
        _text(pilot[key], key)
    if not pilot["accountable_owner"].startswith("human:"):
        raise PilotError("accountable_owner must identify a human role")
    if any(not isinstance(item, str) or not item for item in _list(pilot["beneficiaries"], "beneficiaries")):
        raise PilotError("beneficiaries must contain text")

    task = pilot["task_contract"]
    if not isinstance(task, dict) or set(task) != {
        "reviewed_suite_ref",
        "suite_sha256",
        "agent_receipt_ref",
        "human_baseline_ref",
        "protected_human_authority",
        "transfer_conditions",
    }:
        raise PilotError("task_contract fields differ")
    for key in ("reviewed_suite_ref", "suite_sha256", "agent_receipt_ref", "protected_human_authority"):
        _text(task[key], f"task_contract.{key}")
    if len(task["suite_sha256"]) != 64 or any(char not in "0123456789abcdef" for char in task["suite_sha256"]):
        raise PilotError("task_contract.suite_sha256 must be lowercase SHA-256")
    if task["human_baseline_ref"] is not None:
        _text(task["human_baseline_ref"], "task_contract.human_baseline_ref")
    if any(not isinstance(item, str) or not item for item in _list(task["transfer_conditions"], "task_contract.transfer_conditions")):
        raise PilotError("task transfer conditions must contain text")

    prereg = pilot["pre_registration"]
    if not isinstance(prereg, dict) or set(prereg) != {
        "registered_on",
        "observation_window",
        "measures",
        "analysis_plan",
        "stop_conditions",
    }:
        raise PilotError("pre_registration fields differ")
    _text(prereg["registered_on"], "pre_registration.registered_on", 20)
    _text(prereg["observation_window"], "pre_registration.observation_window")
    _text(prereg["analysis_plan"], "pre_registration.analysis_plan")
    if any(not isinstance(item, str) or not item for item in _list(prereg["stop_conditions"], "pre_registration.stop_conditions")):
        raise PilotError("stop_conditions must contain text")
    measures = _list(prereg["measures"], "pre_registration.measures")
    measure_ids: set[str] = set()
    for index, measure in enumerate(measures):
        if not isinstance(measure, dict) or set(measure) != {
            "measure_id",
            "title",
            "unit",
            "direction",
            "baseline_source",
            "claim_boundary",
        }:
            raise PilotError(f"measures[{index}] fields differ")
        measure_id = _text(measure["measure_id"], f"measures[{index}].measure_id", 100)
        if measure_id in measure_ids:
            raise PilotError(f"duplicate measure_id: {measure_id}")
        measure_ids.add(measure_id)
        for key in ("title", "unit", "baseline_source", "claim_boundary"):
            _text(measure[key], f"measures[{index}].{key}")
        if measure["direction"] not in {"increase", "decrease", "maintain"}:
            raise PilotError(f"measures[{index}].direction is unsupported")

    protection = pilot["human_protection"]
    if not isinstance(protection, dict) or set(protection) != {
        "institutional_determination",
        "data_mode",
        "collection_owner",
        "public_artifact_excludes",
    }:
        raise PilotError("human_protection fields differ")
    if protection["institutional_determination"] not in {"not_determined", "not_required", "approved"}:
        raise PilotError("institutional_determination is unsupported")
    if protection["data_mode"] not in {"synthetic", "aggregate_public", "organization_controlled_private"}:
        raise PilotError("human_protection.data_mode is unsupported")
    _text(protection["collection_owner"], "human_protection.collection_owner")
    excludes = _list(protection["public_artifact_excludes"], "human_protection.public_artifact_excludes")
    required_excludes = {"personal identifiers", "individual responses", "free text", "credentials"}
    if not required_excludes.issubset(set(excludes)):
        raise PilotError("public artifact exclusions are incomplete")

    field = pilot["field_observation"]
    if not isinstance(field, dict) or set(field) != {
        "status",
        "artifact_ref",
        "suite_sha256",
        "started_on",
        "ended_on",
        "causal_claim",
    }:
        raise PilotError("field_observation fields differ")
    if field["status"] not in {"not_started", "in_progress", "complete"}:
        raise PilotError("field observation status is unsupported")
    if field["causal_claim"] is not False:
        raise PilotError("the public pilot contract does not permit a causal claim")
    if field["status"] == "complete":
        for key in ("artifact_ref", "suite_sha256", "started_on", "ended_on"):
            _text(field[key], f"field_observation.{key}")
        if field["suite_sha256"] != task["suite_sha256"]:
            raise PilotError("field observation suite hash differs from the task contract")
    elif any(field[key] is not None for key in ("artifact_ref", "suite_sha256", "started_on", "ended_on")):
        raise PilotError("incomplete field observation must not imply completed artifacts")

    reproduction = pilot["reproduction"]
    if not isinstance(reproduction, dict) or set(reproduction) != {
        "status",
        "independent",
        "organization",
        "artifact_ref",
        "suite_sha256",
        "reviewed_on",
    }:
        raise PilotError("reproduction fields differ")
    if reproduction["status"] not in {"not_started", "submitted", "verified"}:
        raise PilotError("reproduction status is unsupported")
    if reproduction["status"] == "verified":
        if reproduction["independent"] is not True:
            raise PilotError("verified reproduction must attest independence")
        for key in ("organization", "artifact_ref", "suite_sha256", "reviewed_on"):
            _text(reproduction[key], f"reproduction.{key}")
        if reproduction["suite_sha256"] != task["suite_sha256"]:
            raise PilotError("reproduction suite hash differs from the task contract")
    elif reproduction["independent"] is not False or any(
        reproduction[key] is not None for key in ("organization", "artifact_ref", "suite_sha256", "reviewed_on")
    ):
        raise PilotError("unverified reproduction must not imply independence or artifacts")

    sources = _list(pilot["sources"], "sources")
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"publisher", "title", "url", "reviewed_on"}:
            raise PilotError(f"sources[{index}] fields differ")
        if not _text(source["url"], f"sources[{index}].url").startswith("https://"):
            raise PilotError("source URLs must use HTTPS")
        for key in ("publisher", "title", "reviewed_on"):
            _text(source[key], f"sources[{index}].{key}")
    if any(not isinstance(item, str) or not item for item in _list(pilot["limitations"], "limitations")):
        raise PilotError("limitations must contain text")
    claims = pilot["claims"]
    if not isinstance(claims, dict) or set(claims) != {
        "not_production_approval",
        "not_certification",
        "not_government_endorsement",
        "no_unverified_savings_claim",
    } or any(value is not True for value in claims.values()):
        raise PilotError("all public pilot claim boundaries must be true")


def assess_pilot(pilot: dict[str, Any]) -> dict[str, Any]:
    validate_pilot(pilot)
    gaps = []
    if pilot["task_contract"]["human_baseline_ref"] is None:
        gaps.append("human_baseline_missing")
    if pilot["human_protection"]["institutional_determination"] == "not_determined":
        gaps.append("institutional_determination_missing")
    if pilot["field_observation"]["status"] != "complete":
        gaps.append("field_observation_missing")
    if pilot["reproduction"]["status"] != "verified":
        gaps.append("independent_reproduction_missing")
    if pilot["reproduction"]["status"] == "verified":
        level = "independently_reproduced"
    elif pilot["field_observation"]["status"] == "complete":
        level = "observed"
    elif not set(gaps).intersection({"human_baseline_missing", "institutional_determination_missing"}):
        level = "review_ready"
    else:
        level = "designed"
    return {
        "assessment_version": ASSESSMENT_VERSION,
        "pilot_id": pilot["pilot_id"],
        "pilot_sha256": _digest(pilot),
        "evidence_level": level,
        "visible_gaps": gaps,
        "measure_ids": [item["measure_id"] for item in pilot["pre_registration"]["measures"]],
        "suite_sha256": pilot["task_contract"]["suite_sha256"],
        "field_status": pilot["field_observation"]["status"],
        "reproduction_status": pilot["reproduction"]["status"],
        "boundary": {
            "status_derived_from_artifacts": True,
            "no_causal_claim": True,
            "not_certification": True,
        },
    }


def verify_assessment(assessment: dict[str, Any], pilot: dict[str, Any]) -> None:
    if assessment != assess_pilot(pilot):
        raise PilotError("assessment does not recompute from the supplied pilot")


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists():
        raise PilotError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def build_pack(pilot_path: Path, assessment_path: Path, out: Path) -> None:
    if out.exists():
        raise PilotError(f"refusing to overwrite existing pilot pack: {out}")
    pilot = load_json(pilot_path)
    assessment = load_json(assessment_path)
    verify_assessment(assessment, pilot)
    out.mkdir(parents=True)
    shutil.copyfile(pilot_path, out / "pilot.json")
    shutil.copyfile(assessment_path, out / "assessment.json")
    (out / "README.md").write_text(
        "# Public-value pilot contribution pack\n\n"
        "Evidence levels and gaps are derived from artifacts. This pack is not certification, "
        "production approval, causal evidence, a savings claim, or government endorsement. "
        "Independent reproduction is shown only after a different organization supplies a "
        "same-suite artifact and the record is reviewed.\n"
    )
    files = []
    for path in sorted(out.iterdir()):
        data = path.read_bytes()
        files.append({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    (out / "manifest.json").write_text(json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-pilot-network", description="Validate a public-value pilot contribution.")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("pilot", type=Path)
    assess = sub.add_parser("assess")
    assess.add_argument("pilot", type=Path)
    assess.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("assessment", type=Path)
    verify.add_argument("--pilot", type=Path, required=True)
    pack = sub.add_parser("pack")
    pack.add_argument("pilot", type=Path)
    pack.add_argument("assessment", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "validate":
            validate_pilot(load_json(args.pilot))
            print(f"OK: {args.pilot} is a valid public-value pilot record.")
            return 0
        if args.command == "assess":
            assessment = assess_pilot(load_json(args.pilot))
            write_json(assessment, args.out)
            print(f"OK: {assessment['evidence_level']} assessment written to {args.out}.")
            return 0
        if args.command == "verify":
            verify_assessment(load_json(args.assessment), load_json(args.pilot))
            print(f"OK: {args.assessment} recomputes from {args.pilot}.")
            return 0
        build_pack(args.pilot, args.assessment, args.out)
        print(f"OK: pilot pack written to {args.out}.")
        return 0
    except PilotError as exc:
        print(f"aau-pilot-network: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
