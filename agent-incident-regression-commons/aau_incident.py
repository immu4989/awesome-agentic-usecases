"""Safe, deterministic Agent Incident Regression Commons reference tool."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


INCIDENT_VERSION = "aau-agent-incident-regression/0.1"
RECEIPT_VERSION = "aau-agent-incident-regression-receipt/0.1"
PACK_VERSION = "aau-agent-incident-regression-pack/0.1"
MAX_BYTES = 1_000_000
MAX_REGRESSIONS = 100
TEXT_LIMIT = 600
FORBIDDEN_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "email_address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "ipv4_address": re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
}


class IncidentError(ValueError):
    """Raised when an incident regression artifact crosses the public boundary."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _read(path: Path) -> bytes:
    if path.is_symlink():
        raise IncidentError(f"refusing symbolic link: {path}")
    if not path.is_file():
        raise IncidentError(f"not a regular file: {path}")
    if path.stat().st_size > MAX_BYTES:
        raise IncidentError(f"file exceeds {MAX_BYTES} bytes: {path}")
    return path.read_bytes()


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(_read(source))
    except json.JSONDecodeError as exc:
        raise IncidentError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise IncidentError(f"expected one JSON object in {source}")
    return value


def _text(value: Any, label: str, limit: int = TEXT_LIMIT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise IncidentError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _text_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise IncidentError(f"{label} must be a string list")
    if any(not isinstance(item, str) or not item.strip() or len(item) > TEXT_LIMIT for item in value):
        raise IncidentError(f"{label} contains invalid text")
    if len(set(value)) != len(value):
        raise IncidentError(f"{label} must not contain duplicates")
    return value


def scan_public_text(value: Any) -> list[str]:
    """Return finding labels only; never echo a possible secret or identifier."""

    serialized = json.dumps(value, ensure_ascii=True)
    return sorted(label for label, pattern in FORBIDDEN_PATTERNS.items() if pattern.search(serialized))


def validate_incident(record: dict[str, Any]) -> None:
    expected = {
        "incident_version",
        "incident_id",
        "title",
        "published_at",
        "public_sources",
        "classification",
        "failure",
        "timeline",
        "regressions",
        "recovery",
        "limitations",
        "claims",
    }
    if set(record) != expected:
        raise IncidentError("incident fields differ from the public 0.1 contract")
    if record["incident_version"] != INCIDENT_VERSION:
        raise IncidentError(f"incident_version must be {INCIDENT_VERSION}")
    _text(record["incident_id"], "incident_id", 120)
    _text(record["title"], "title", 200)
    _text(record["published_at"], "published_at", 40)
    sources = record["public_sources"]
    if not isinstance(sources, list) or not sources:
        raise IncidentError("public_sources must be a non-empty list")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"source_id", "publisher", "title", "url", "reviewed_on"}:
            raise IncidentError(f"public_sources[{index}] fields differ")
        source_id = _text(source["source_id"], f"public_sources[{index}].source_id", 80)
        if source_id in source_ids:
            raise IncidentError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        _text(source["publisher"], f"public_sources[{index}].publisher", 120)
        _text(source["title"], f"public_sources[{index}].title", 240)
        url = _text(source["url"], f"public_sources[{index}].url", 500)
        if not url.startswith("https://"):
            raise IncidentError("public source URLs must use HTTPS")
        _text(source["reviewed_on"], f"public_sources[{index}].reviewed_on", 20)

    classification = record["classification"]
    if not isinstance(classification, dict) or set(classification) != {
        "mode",
        "contains_real_credentials",
        "contains_personal_data",
        "contains_nonpublic_telemetry",
        "contains_exploit_instructions",
        "contains_live_targets",
    }:
        raise IncidentError("classification fields differ")
    if classification["mode"] != "public_synthetic_abstraction":
        raise IncidentError("classification.mode must be public_synthetic_abstraction")
    if any(classification[key] is not False for key in classification if key != "mode"):
        raise IncidentError("all public incident sensitive-content flags must be false")

    failure = record["failure"]
    if not isinstance(failure, dict) or set(failure) != {
        "summary",
        "failure_shapes",
        "authority_boundary",
        "public_facts_only",
    }:
        raise IncidentError("failure fields differ")
    _text(failure["summary"], "failure.summary")
    _text_list(failure["failure_shapes"], "failure.failure_shapes")
    _text(failure["authority_boundary"], "failure.authority_boundary")
    if failure["public_facts_only"] is not True:
        raise IncidentError("failure.public_facts_only must be true")

    timeline = record["timeline"]
    if not isinstance(timeline, list) or not timeline:
        raise IncidentError("timeline must be non-empty")
    allowed_stages = {"signal", "detection", "containment", "eradication", "recovery", "lesson"}
    timeline_ids: set[str] = set()
    for index, item in enumerate(timeline):
        if not isinstance(item, dict) or set(item) != {"event_id", "stage", "order", "description", "source_refs"}:
            raise IncidentError(f"timeline[{index}] fields differ")
        event_id = _text(item["event_id"], f"timeline[{index}].event_id", 80)
        if event_id in timeline_ids:
            raise IncidentError(f"duplicate timeline event_id: {event_id}")
        timeline_ids.add(event_id)
        if item["stage"] not in allowed_stages:
            raise IncidentError(f"timeline[{index}].stage is unsupported")
        if item["order"] != index + 1:
            raise IncidentError("timeline order must be contiguous and one-based")
        _text(item["description"], f"timeline[{index}].description")
        refs = _text_list(item["source_refs"], f"timeline[{index}].source_refs")
        if not set(refs).issubset(source_ids):
            raise IncidentError(f"timeline[{index}] references an unknown source")

    regressions = record["regressions"]
    if not isinstance(regressions, list) or not 1 <= len(regressions) <= MAX_REGRESSIONS:
        raise IncidentError(f"regressions must contain 1 to {MAX_REGRESSIONS} cases")
    case_ids: set[str] = set()
    outcomes = {"allow", "block", "pause", "safe_stop"}
    for index, case in enumerate(regressions):
        if not isinstance(case, dict) or set(case) != {
            "case_id",
            "title",
            "synthetic_trigger",
            "required_outcome",
            "pre_fix_outcome",
            "post_fix_outcome",
            "control_change",
            "evidence_refs",
            "non_transfer_conditions",
        }:
            raise IncidentError(f"regressions[{index}] fields differ")
        case_id = _text(case["case_id"], f"regressions[{index}].case_id", 80)
        if case_id in case_ids:
            raise IncidentError(f"duplicate regression case_id: {case_id}")
        case_ids.add(case_id)
        for key in ("title", "synthetic_trigger", "control_change", "non_transfer_conditions"):
            _text(case[key], f"regressions[{index}].{key}")
        for key in ("required_outcome", "pre_fix_outcome", "post_fix_outcome"):
            if case[key] not in outcomes:
                raise IncidentError(f"regressions[{index}].{key} is unsupported")
        _text_list(case["evidence_refs"], f"regressions[{index}].evidence_refs")

    recovery = record["recovery"]
    if not isinstance(recovery, dict) or set(recovery) != {
        "stop_authority",
        "restart_authority",
        "restoration_evidence",
        "unresolved_questions",
    }:
        raise IncidentError("recovery fields differ")
    if not _text(recovery["stop_authority"], "recovery.stop_authority", 120).startswith("human:"):
        raise IncidentError("recovery.stop_authority must identify a human role")
    if not _text(recovery["restart_authority"], "recovery.restart_authority", 120).startswith("human:"):
        raise IncidentError("recovery.restart_authority must identify a human role")
    _text_list(recovery["restoration_evidence"], "recovery.restoration_evidence")
    _text_list(recovery["unresolved_questions"], "recovery.unresolved_questions", allow_empty=True)
    _text_list(record["limitations"], "limitations")

    claims = record["claims"]
    if not isinstance(claims, dict) or set(claims) != {
        "not_original_incident_reproduction",
        "not_attribution",
        "not_verified_production_fix",
        "not_security_certification",
    } or any(value is not True for value in claims.values()):
        raise IncidentError("all incident claim boundaries must be true")
    findings = scan_public_text(record)
    if findings:
        raise IncidentError(f"public incident scan found prohibited categories: {findings}")


def evaluate_incident(record: dict[str, Any]) -> dict[str, Any]:
    validate_incident(record)
    rows = []
    previous = "0" * 64
    for case in record["regressions"]:
        pre_exact = case["pre_fix_outcome"] == case["required_outcome"]
        post_exact = case["post_fix_outcome"] == case["required_outcome"]
        unsafe_before = case["pre_fix_outcome"] == "allow" and case["required_outcome"] != "allow"
        legitimate_preserved = case["required_outcome"] == "allow" and case["post_fix_outcome"] == "allow"
        material = {
            "case_id": case["case_id"],
            "case_sha256": digest(case),
            "required_outcome": case["required_outcome"],
            "pre_fix_outcome": case["pre_fix_outcome"],
            "post_fix_outcome": case["post_fix_outcome"],
            "pre_fix_exact": int(pre_exact),
            "post_fix_exact": int(post_exact),
            "unsafe_allow_before": int(unsafe_before),
            "legitimate_allow_preserved": int(legitimate_preserved),
            "previous_result_sha256": previous,
        }
        result_hash = digest(material)
        rows.append({**material, "result_sha256": result_hash})
        previous = result_hash
    count = len(rows)
    legitimate_total = sum(row["required_outcome"] == "allow" for row in rows)
    summary = {
        "regression_count": count,
        "unsafe_allow_before_count": sum(row["unsafe_allow_before"] for row in rows),
        "pre_fix_exact_rate": round(sum(row["pre_fix_exact"] for row in rows) / count, 6),
        "post_fix_exact_rate": round(sum(row["post_fix_exact"] for row in rows) / count, 6),
        "legitimate_allow_preservation": round(
            sum(row["legitimate_allow_preserved"] for row in rows) / legitimate_total, 6
        ) if legitimate_total else None,
        "unresolved_question_count": len(record["recovery"]["unresolved_questions"]),
    }
    return {
        "receipt_version": RECEIPT_VERSION,
        "incident_id": record["incident_id"],
        "incident_sha256": digest(record),
        "summary": summary,
        "results": rows,
        "chain_head_sha256": previous,
        "boundary": {
            "public_synthetic_abstraction": True,
            "no_sensitive_incident_data": True,
            "not_verified_production_fix": True,
            "not_certification": True,
        },
    }


def verify_receipt(receipt: dict[str, Any], record: dict[str, Any] | None = None) -> None:
    expected_fields = {
        "receipt_version",
        "incident_id",
        "incident_sha256",
        "summary",
        "results",
        "chain_head_sha256",
        "boundary",
    }
    if set(receipt) != expected_fields or receipt.get("receipt_version") != RECEIPT_VERSION:
        raise IncidentError("incident receipt fields or version are invalid")
    previous = "0" * 64
    for index, row in enumerate(receipt.get("results", [])):
        if row.get("previous_result_sha256") != previous:
            raise IncidentError(f"result[{index}] breaks the hash chain")
        material = {key: value for key, value in row.items() if key != "result_sha256"}
        expected_hash = digest(material)
        if row.get("result_sha256") != expected_hash:
            raise IncidentError(f"result[{index}] digest mismatch")
        previous = expected_hash
    if previous != receipt.get("chain_head_sha256"):
        raise IncidentError("incident receipt chain head differs")
    if record is not None and receipt != evaluate_incident(record):
        raise IncidentError("incident receipt does not recompute from the supplied record")


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists():
        raise IncidentError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def build_pack(record_path: Path, receipt_path: Path, out: Path) -> None:
    if out.exists():
        raise IncidentError(f"refusing to overwrite existing pack: {out}")
    record = load_json(record_path)
    receipt = load_json(receipt_path)
    verify_receipt(receipt, record)
    out.mkdir(parents=True)
    shutil.copyfile(record_path, out / "incident.json")
    shutil.copyfile(receipt_path, out / "receipt.json")
    (out / "README.md").write_text(
        "# Agent incident regression pack\n\n"
        "This is a public synthetic abstraction backed by named public sources. It contains "
        "no live target, exploit instructions, credentials, personal data, or private telemetry. "
        "A passing post-fix regression is not proof that an original or production incident is fixed.\n"
    )
    files = []
    for path in sorted(out.iterdir()):
        data = path.read_bytes()
        files.append({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    (out / "manifest.json").write_text(json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aau-incident", description="Build safe agent incident regression evidence.")
    sub = parser.add_subparsers(dest="command", required=True)
    validating = sub.add_parser("validate")
    validating.add_argument("incident", type=Path)
    evaluating = sub.add_parser("evaluate")
    evaluating.add_argument("incident", type=Path)
    evaluating.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify")
    verifying.add_argument("receipt", type=Path)
    verifying.add_argument("--incident", type=Path)
    packing = sub.add_parser("pack")
    packing.add_argument("incident", type=Path)
    packing.add_argument("receipt", type=Path)
    packing.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "validate":
            validate_incident(load_json(args.incident))
            print(f"OK: {args.incident} is a safe public incident regression record.")
            return 0
        if args.command == "evaluate":
            receipt = evaluate_incident(load_json(args.incident))
            write_json(receipt, args.out)
            print(f"OK: {receipt['summary']['regression_count']} regressions written to {args.out}.")
            return 0
        if args.command == "verify":
            record = load_json(args.incident) if args.incident else None
            verify_receipt(load_json(args.receipt), record)
            print(f"OK: {args.receipt} verified.")
            return 0
        build_pack(args.incident, args.receipt, args.out)
        print(f"OK: incident regression pack written to {args.out}.")
        return 0
    except IncidentError as exc:
        print(f"aau-incident: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
