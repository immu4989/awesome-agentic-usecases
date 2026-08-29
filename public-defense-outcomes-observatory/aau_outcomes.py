"""Aggregate public defensive receipts without manufacturing effectiveness claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


INDEX_VERSION = "aau-cyber-defense-evidence-index/0.1"
REPORT_VERSION = "aau-public-defense-outcomes-report/0.1"
MAX_BYTES = 2_000_000
KINDS = {"verified_fix", "containment_drill", "defender_campaign", "defense_benchmark"}
LEVELS = {"designed", "synthetic_reference", "reference_exact", "independently_reproduced"}


class OutcomesError(ValueError):
    """Raised when public outcome data violates the aggregation boundary."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise OutcomesError(f"invalid, oversized, or symbolic-link input: {path}")
    try:
        value = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OutcomesError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OutcomesError("expected one JSON object")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise OutcomesError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def validate_index(index: dict[str, Any]) -> None:
    if index.get("index_version") != INDEX_VERSION:
        raise OutcomesError(f"index_version must be {INDEX_VERSION}")
    records = index.get("records")
    if not isinstance(records, list) or not records:
        raise OutcomesError("index records must contain entries")
    if index.get("record_count") != len(records):
        raise OutcomesError("record_count does not match records")
    ids: set[str] = set()
    for record in records:
        required = {
            "artifact_id", "kind", "artifact_version", "artifact_sha256", "evidence_level",
            "producer", "independent_reproduction", "measurements", "control_fingerprints",
        }
        if not isinstance(record, dict) or set(record) != required:
            raise OutcomesError("record fields differ from the evidence index contract")
        if record["artifact_id"] in ids:
            raise OutcomesError(f"duplicate artifact_id: {record['artifact_id']}")
        ids.add(record["artifact_id"])
        if record["kind"] not in KINDS or record["evidence_level"] not in LEVELS:
            raise OutcomesError("record has unsupported kind or evidence level")
        if not isinstance(record["artifact_sha256"], str) or len(record["artifact_sha256"]) != 64:
            raise OutcomesError("record artifact_sha256 is invalid")
        if not isinstance(record["independent_reproduction"], bool):
            raise OutcomesError("independent_reproduction must be boolean")
        if record["evidence_level"] == "independently_reproduced" and not record["independent_reproduction"]:
            raise OutcomesError("independent evidence label lacks reproduction flag")
        if not isinstance(record["measurements"], dict) or not isinstance(record["control_fingerprints"], list):
            raise OutcomesError("record measurements and fingerprints must use bounded containers")
    boundary = index.get("claim_boundary")
    if not isinstance(boundary, dict) or any(value is not True for value in boundary.values()):
        raise OutcomesError("index claim boundary must be present and true")


def evaluate(index: dict[str, Any]) -> dict[str, Any]:
    validate_index(index)
    records = index["records"]
    kinds = {kind: 0 for kind in sorted(KINDS)}
    levels = {level: 0 for level in sorted(LEVELS)}
    observations_by_kind = {kind: 0 for kind in sorted(KINDS)}
    observation_keys = {
        "verified_fix": "case_count",
        "containment_drill": "event_count",
        "defender_campaign": "decision_count",
        "defense_benchmark": "task_count",
    }
    fingerprints: set[str] = set()
    for record in records:
        kinds[record["kind"]] += 1
        levels[record["evidence_level"]] += 1
        key = observation_keys[record["kind"]]
        count = record["measurements"].get(key, 0)
        if not isinstance(count, int) or count < 0:
            raise OutcomesError(f"{record['artifact_id']} has an invalid {key}")
        observations_by_kind[record["kind"]] += count
        fingerprints.update(record["control_fingerprints"])
    gaps = []
    missing = [kind for kind, count in kinds.items() if count == 0]
    if missing:
        gaps.append(f"Missing artifact families: {', '.join(missing)}")
    if levels["independently_reproduced"] == 0:
        gaps.append("No independently reproduced artifact has been contributed yet.")
    report = {
        "report_version": REPORT_VERSION,
        "mesh_id": index["mesh_id"],
        "index_sha256": digest(index),
        "summary": {
            "artifact_count": len(records),
            "artifact_count_by_kind": kinds,
            "evidence_level_counts": levels,
            "observation_counts_by_kind": observations_by_kind,
            "control_fingerprint_count": len(fingerprints),
            "independent_reproduction_count": sum(record["independent_reproduction"] for record in records),
        },
        "visible_gaps": gaps,
        "claim_boundary": {
            "counts_artifacts_not_organizations": True,
            "heterogeneous_observations_not_summed": True,
            "no_vendor_or_agency_ranking": True,
            "no_field_effectiveness_claim": True,
            "not_certification_or_government_endorsement": True,
        },
    }
    report["report_sha256"] = digest(report)
    return report


def verify_report(report: dict[str, Any], index: dict[str, Any]) -> None:
    if report != evaluate(index):
        raise OutcomesError("report does not recompute from the supplied evidence index")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-defense-outcomes", description="Aggregate evidence without overstating outcomes.")
    sub = root.add_subparsers(dest="command", required=True)
    evaluating = sub.add_parser("evaluate")
    evaluating.add_argument("index", type=Path)
    evaluating.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify")
    verifying.add_argument("report", type=Path)
    verifying.add_argument("--index", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "evaluate":
            report = evaluate(load_json(args.index))
            write_json(report, args.out)
            print(f"OK: {report['summary']['artifact_count']} artifacts aggregated at {args.out}.")
        else:
            verify_report(load_json(args.report), load_json(args.index))
            print(f"OK: {args.report} verified.")
        return 0
    except OutcomesError as exc:
        print(f"aau-defense-outcomes: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
