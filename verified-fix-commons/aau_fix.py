"""Offline evaluator and evidence-pack builder for the AAU Verified Fix Commons."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "aau-verified-fix-contract/0.1"
RECEIPT_VERSION = "aau-verified-fix-receipt/0.1"
PACK_VERSION = "aau-verified-fix-pack/0.1"
MAX_BYTES = 2_000_000
ZERO_HASH = "0" * 64
CASE_KINDS = {
    "vulnerability_regression",
    "legitimate_twin",
    "service_continuity",
    "rollback_readiness",
    "compensating_control",
}
CHANGE_KINDS = {"patch", "upgrade", "configuration", "compensating_control"}
BOUNDARY_KEYS = {
    "public_or_synthetic_only",
    "no_live_target",
    "no_exploit_payload",
    "not_organizational_security_claim",
    "not_compliance_or_certification",
    "human_approved_change_required",
}
STATE_KEYS = {
    "vulnerable",
    "legitimate_allowed",
    "service_available",
    "interruption_ms",
    "rollback_ready",
    "control_active",
    "evidence_present",
}


class FixError(ValueError):
    """Raised when a fix contract or receipt violates the public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def load_json(source: Path) -> dict[str, Any]:
    if source.is_symlink():
        raise FixError(f"refusing symbolic link: {source}")
    if not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise FixError(f"invalid or oversized file: {source}")
    try:
        value = json.loads(source.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FixError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise FixError("expected one JSON object")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise FixError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def _text(value: Any, label: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise FixError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _date(value: Any, label: str) -> str:
    value = _text(value, label, 10)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise FixError(f"{label} must use YYYY-MM-DD") from exc
    return value


def _exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise FixError(f"{label} fields differ from the 0.1 contract")
    return value


def _state(value: Any, label: str) -> dict[str, Any]:
    state = _exact_keys(value, STATE_KEYS, label)
    for key in STATE_KEYS - {"interruption_ms"}:
        if not isinstance(state[key], bool):
            raise FixError(f"{label}.{key} must be boolean")
    if not isinstance(state["interruption_ms"], int) or state["interruption_ms"] < 0:
        raise FixError(f"{label}.interruption_ms must be a non-negative integer")
    return state


def validate_contract(contract: dict[str, Any]) -> None:
    _exact_keys(
        contract,
        {
            "contract_version",
            "fix_id",
            "title",
            "vulnerability",
            "change",
            "protected_service",
            "public_sources",
            "cases",
            "evidence",
            "boundaries",
        },
        "contract",
    )
    if contract["contract_version"] != CONTRACT_VERSION:
        raise FixError(f"contract_version must be {CONTRACT_VERSION}")
    _text(contract["fix_id"], "fix_id", 120)
    _text(contract["title"], "title", 200)

    vulnerability = _exact_keys(
        contract["vulnerability"],
        {"identifier", "affected_component", "affected_range", "exploitation_basis", "fixture_scope"},
        "vulnerability",
    )
    for key in vulnerability:
        _text(vulnerability[key], f"vulnerability.{key}", 400)

    change = _exact_keys(
        contract["change"],
        {"kind", "description", "implementation_ref", "rollback_ref", "accountable_owner"},
        "change",
    )
    if change["kind"] not in CHANGE_KINDS:
        raise FixError("change.kind is unsupported")
    for key in change:
        _text(change[key], f"change.{key}", 500)
    if "human" not in change["accountable_owner"].lower():
        raise FixError("change.accountable_owner must identify a human role")

    service = _exact_keys(
        contract["protected_service"],
        {"name", "continuity_owner", "maximum_interruption_ms", "prohibited_actions"},
        "protected_service",
    )
    _text(service["name"], "protected_service.name", 200)
    _text(service["continuity_owner"], "protected_service.continuity_owner", 200)
    if "human" not in service["continuity_owner"].lower():
        raise FixError("protected_service.continuity_owner must identify a human role")
    if not isinstance(service["maximum_interruption_ms"], int) or service["maximum_interruption_ms"] < 0:
        raise FixError("protected_service.maximum_interruption_ms must be non-negative")
    prohibited = service["prohibited_actions"]
    if not isinstance(prohibited, list) or not prohibited:
        raise FixError("protected_service.prohibited_actions must contain text")
    for index, item in enumerate(prohibited):
        _text(item, f"protected_service.prohibited_actions[{index}]", 200)

    sources = contract["public_sources"]
    if not isinstance(sources, list) or not sources:
        raise FixError("public_sources must be a non-empty list")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        source = _exact_keys(source, {"source_id", "url", "role", "reviewed_on"}, f"public_sources[{index}]")
        source_id = _text(source["source_id"], f"public_sources[{index}].source_id", 100)
        if source_id in source_ids:
            raise FixError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        url = _text(source["url"], f"public_sources[{index}].url", 800)
        if not url.startswith("https://"):
            raise FixError("public source URLs must use HTTPS")
        _text(source["role"], f"public_sources[{index}].role", 300)
        _date(source["reviewed_on"], f"public_sources[{index}].reviewed_on")

    evidence = _exact_keys(contract["evidence"], {"tested_on", "environment", "runner", "producer", "run_id"}, "evidence")
    _date(evidence["tested_on"], "evidence.tested_on")
    for key in ("environment", "runner", "producer", "run_id"):
        _text(evidence[key], f"evidence.{key}", 300)

    boundaries = _exact_keys(contract["boundaries"], BOUNDARY_KEYS, "boundaries")
    if any(boundaries[key] is not True for key in BOUNDARY_KEYS):
        raise FixError("all public safety boundaries must be true")

    cases = contract["cases"]
    if not isinstance(cases, list) or not (4 <= len(cases) <= 100):
        raise FixError("cases must contain between 4 and 100 entries")
    case_ids: set[str] = set()
    observed_kinds: set[str] = set()
    for index, case in enumerate(cases):
        case = _exact_keys(
            case,
            {"case_id", "title", "case_kind", "source_refs", "before", "after", "expected"},
            f"cases[{index}]",
        )
        case_id = _text(case["case_id"], f"cases[{index}].case_id", 100)
        if case_id in case_ids:
            raise FixError(f"duplicate case_id: {case_id}")
        case_ids.add(case_id)
        _text(case["title"], f"cases[{index}].title", 240)
        if case["case_kind"] not in CASE_KINDS:
            raise FixError(f"cases[{index}].case_kind is unsupported")
        observed_kinds.add(case["case_kind"])
        refs = case["source_refs"]
        if not isinstance(refs, list) or not refs or any(ref not in source_ids for ref in refs):
            raise FixError(f"cases[{index}].source_refs must name public sources")
        _state(case["before"], f"cases[{index}].before")
        _state(case["after"], f"cases[{index}].after")
        expected = _exact_keys(case["expected"], {"before", "after"}, f"cases[{index}].expected")
        if expected["before"] not in {"pass", "fail"} or expected["after"] != "pass":
            raise FixError("each case must declare pass/fail before and pass after")

    required = {"vulnerability_regression", "legitimate_twin", "service_continuity", "rollback_readiness"}
    if not required.issubset(observed_kinds):
        raise FixError(f"cases are missing required kinds: {sorted(required - observed_kinds)}")
    if change["kind"] == "compensating_control" and "compensating_control" not in observed_kinds:
        raise FixError("a compensating control change requires a compensating_control case")


def simulate_case(kind: str, state: dict[str, Any], maximum_interruption_ms: int) -> str:
    if kind == "vulnerability_regression":
        passed = not state["vulnerable"]
    elif kind == "legitimate_twin":
        passed = state["legitimate_allowed"]
    elif kind == "service_continuity":
        passed = state["service_available"] and state["interruption_ms"] <= maximum_interruption_ms
    elif kind == "rollback_readiness":
        passed = state["rollback_ready"]
    elif kind == "compensating_control":
        passed = state["control_active"] and state["evidence_present"]
    else:
        raise FixError(f"unsupported case kind: {kind}")
    return "pass" if passed else "fail"


def evaluate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    validate_contract(contract)
    maximum = contract["protected_service"]["maximum_interruption_ms"]
    rows: list[dict[str, Any]] = []
    previous = ZERO_HASH
    exact = 0
    after_pass = 0
    for case in contract["cases"]:
        before = simulate_case(case["case_kind"], case["before"], maximum)
        after = simulate_case(case["case_kind"], case["after"], maximum)
        before_exact = before == case["expected"]["before"]
        after_exact = after == case["expected"]["after"]
        exact += int(before_exact) + int(after_exact)
        after_pass += int(after == "pass")
        row = {
            "case_id": case["case_id"],
            "case_kind": case["case_kind"],
            "before": before,
            "after": after,
            "before_exact": before_exact,
            "after_exact": after_exact,
            "after_safe": after == "pass",
            "source_refs": case["source_refs"],
            "previous_result_sha256": previous,
        }
        row["result_sha256"] = digest(row)
        previous = row["result_sha256"]
        rows.append(row)

    count = len(rows)

    def kind_rows(name: str) -> list[dict[str, Any]]:
        return [row for row in rows if row["case_kind"] == name]

    def rate(selected: list[dict[str, Any]]) -> float | None:
        if not selected:
            return None
        return round(sum(row["after"] == "pass" for row in selected) / len(selected), 6)

    summary = {
        "case_count": count,
        "pre_fix_failure_count": sum(row["before"] == "fail" for row in rows),
        "exact_phase_rate": round(exact / (count * 2), 6),
        "after_pass_rate": round(after_pass / count, 6),
        "vulnerability_closed_rate": rate(kind_rows("vulnerability_regression")),
        "legitimate_preservation_rate": rate(kind_rows("legitimate_twin")),
        "continuity_preservation_rate": rate(kind_rows("service_continuity")),
        "rollback_readiness_rate": rate(kind_rows("rollback_readiness")),
        "unsafe_after_count": sum(not row["after_safe"] for row in rows),
    }
    evidence_level = "reference_exact" if summary["exact_phase_rate"] == 1.0 and summary["unsafe_after_count"] == 0 else "designed"
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "fix_id": contract["fix_id"],
        "contract_sha256": digest(contract),
        "producer": contract["evidence"]["producer"],
        "run_id": contract["evidence"]["run_id"],
        "tested_on": contract["evidence"]["tested_on"],
        "evidence_level": evidence_level,
        "summary": summary,
        "cases": rows,
        "final_result_sha256": previous,
        "claim_boundary": {
            "synthetic_reference_result": True,
            "not_production_validation": True,
            "not_compliance_or_certification": True,
            "not_independent_reproduction": True,
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_receipt(receipt: dict[str, Any], contract: dict[str, Any] | None = None) -> None:
    if receipt.get("receipt_version") != RECEIPT_VERSION:
        raise FixError("unsupported receipt_version")
    supplied = receipt.get("receipt_sha256")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    if supplied != digest(unsigned):
        raise FixError("receipt digest mismatch")
    previous = ZERO_HASH
    rows = receipt.get("cases")
    if not isinstance(rows, list) or not rows:
        raise FixError("receipt cases are missing")
    for row in rows:
        if row.get("previous_result_sha256") != previous:
            raise FixError("receipt result chain is broken")
        unsigned_row = dict(row)
        result_hash = unsigned_row.pop("result_sha256", None)
        if result_hash != digest(unsigned_row):
            raise FixError("receipt result digest mismatch")
        previous = result_hash
    if receipt.get("final_result_sha256") != previous:
        raise FixError("receipt final digest mismatch")
    if contract is not None and receipt != evaluate_contract(contract):
        raise FixError("receipt does not recompute from the supplied contract")


def build_openvex(contract: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    status = "fixed" if receipt["summary"]["vulnerability_closed_rate"] == 1.0 else "under_investigation"
    return {
        "@context": "https://openvex.dev/ns/v0.2.0",
        "@id": f"https://immu4989.github.io/awesome-agentic-usecases/fixes/{contract['fix_id']}/{receipt['receipt_sha256']}",
        "author": contract["evidence"]["producer"],
        "role": "Document Creator",
        "timestamp": f"{contract['evidence']['tested_on']}T00:00:00Z",
        "version": 1,
        "statements": [
            {
                "vulnerability": {"name": contract["vulnerability"]["identifier"]},
                "products": [{"@id": contract["vulnerability"]["affected_component"]}],
                "status": status,
                "status_notes": "Derived from an AAU safe-fixture receipt; not a production exploitability determination.",
                "action_statement": contract["change"]["description"],
            }
        ],
    }


def build_sarif(contract: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    results = []
    for row in receipt["cases"]:
        results.append(
            {
                "ruleId": row["case_kind"],
                "level": "none" if row["after"] == "pass" else "error",
                "message": {"text": f"{row['case_id']}: after-fix outcome {row['after']}"},
                "properties": {
                    "before": row["before"],
                    "after": row["after"],
                    "syntheticReference": True,
                },
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "AAU Verified Fix Commons", "version": "0.1"}},
                "results": results,
                "properties": {"fixId": contract["fix_id"], "receiptSha256": receipt["receipt_sha256"]},
            }
        ],
    }


def build_pack(contract_path: Path, receipt_path: Path, out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise FixError(f"refusing to overwrite existing fix pack: {out}")
    contract = load_json(contract_path)
    receipt = load_json(receipt_path)
    validate_contract(contract)
    verify_receipt(receipt, contract)
    out.mkdir(parents=True)
    shutil.copyfile(contract_path, out / "fix-contract.json")
    shutil.copyfile(receipt_path, out / "fix-receipt.json")
    (out / "openvex.json").write_text(json.dumps(build_openvex(contract, receipt), indent=2) + "\n")
    (out / "results.sarif.json").write_text(json.dumps(build_sarif(contract, receipt), indent=2) + "\n")
    (out / "README.md").write_text(
        "# AAU Verified Fix evidence pack\n\n"
        "This pack contains public or synthetic fixture evidence, an OpenVEX-style statement, "
        "and SARIF results. It is not a production exploitability determination, certification, "
        "compliance finding, or authorization to change a system.\n"
    )
    files = []
    for path in sorted(out.iterdir()):
        if path.name == "manifest.json":
            continue
        files.append({"path": path.name, "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size})
    (out / "manifest.json").write_text(json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-fix", description="Build reproducible safe-fixture fix evidence.")
    sub = root.add_subparsers(dest="command", required=True)
    validating = sub.add_parser("validate")
    validating.add_argument("contract", type=Path)
    evaluating = sub.add_parser("evaluate")
    evaluating.add_argument("contract", type=Path)
    evaluating.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify")
    verifying.add_argument("receipt", type=Path)
    verifying.add_argument("--contract", type=Path)
    packing = sub.add_parser("pack")
    packing.add_argument("contract", type=Path)
    packing.add_argument("receipt", type=Path)
    packing.add_argument("--out", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "validate":
            validate_contract(load_json(args.contract))
            print(f"OK: {args.contract} is a valid safe-fixture fix contract.")
            return 0
        if args.command == "evaluate":
            receipt = evaluate_contract(load_json(args.contract))
            write_json(receipt, args.out)
            print(f"OK: {receipt['summary']['case_count']} fix cases written to {args.out}.")
            return 0
        if args.command == "verify":
            contract = load_json(args.contract) if args.contract else None
            verify_receipt(load_json(args.receipt), contract)
            print(f"OK: {args.receipt} verified.")
            return 0
        build_pack(args.contract, args.receipt, args.out)
        print(f"OK: verified fix pack written to {args.out}.")
        return 0
    except FixError as exc:
        print(f"aau-fix: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
