"""Zero-upload, deterministic fix-route planner for essential-service defenders."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any


CAMPAIGN_VERSION = "aau-essential-service-campaign/0.1"
ASSESSMENT_VERSION = "aau-essential-service-campaign-assessment/0.1"
PACK_VERSION = "aau-essential-service-campaign-pack/0.1"
MAX_BYTES = 2_000_000
BOUNDARIES = {
    "synthetic_or_authorized_inventory",
    "no_live_scanning",
    "no_network_access",
    "no_exploit_payloads",
    "no_automatic_changes",
    "human_approval_required",
    "not_risk_assessment",
    "not_compliance_claim",
}


class DefenderBoxError(ValueError):
    """Raised when a campaign violates the public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise DefenderBoxError(f"invalid, oversized, or symbolic-link input: {path}")
    try:
        value = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DefenderBoxError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DefenderBoxError("expected one JSON object")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise DefenderBoxError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def _text(value: Any, label: str, limit: int = 400) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise DefenderBoxError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise DefenderBoxError(f"{label} fields differ from the 0.1 contract")
    return value


def _iso_date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(_text(value, label, 10))
    except ValueError as exc:
        raise DefenderBoxError(f"{label} must be an ISO date") from exc


def validate_campaign(campaign: dict[str, Any]) -> None:
    _exact(
        campaign,
        {
            "campaign_version", "campaign_id", "title", "sector", "as_of", "official_sources",
            "assets", "vulnerabilities", "continuity_tests", "decisions", "boundaries",
        },
        "campaign",
    )
    if campaign["campaign_version"] != CAMPAIGN_VERSION:
        raise DefenderBoxError(f"campaign_version must be {CAMPAIGN_VERSION}")
    for key, limit in (("campaign_id", 120), ("title", 220), ("sector", 160)):
        _text(campaign[key], key, limit)
    _iso_date(campaign["as_of"], "as_of")

    sources = campaign["official_sources"]
    if not isinstance(sources, list) or not sources:
        raise DefenderBoxError("official_sources must contain at least one source")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        _exact(source, {"source_id", "publisher", "title", "url", "retrieved_on"}, f"official_sources[{index}]")
        source_id = _text(source["source_id"], f"official_sources[{index}].source_id", 100)
        if source_id in source_ids:
            raise DefenderBoxError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        _text(source["publisher"], "source publisher", 160)
        _text(source["title"], "source title")
        if not _text(source["url"], "source URL").startswith("https://"):
            raise DefenderBoxError("official source URLs must use HTTPS")
        _iso_date(source["retrieved_on"], "source retrieved_on")

    assets = campaign["assets"]
    if not isinstance(assets, list) or not (1 <= len(assets) <= 500):
        raise DefenderBoxError("assets must contain between 1 and 500 entries")
    asset_ids: set[str] = set()
    patchability: dict[str, str] = {}
    for index, asset in enumerate(assets):
        _exact(
            asset,
            {"asset_id", "system", "product", "version_evidence", "service_criticality", "patchability", "owner_role"},
            f"assets[{index}]",
        )
        asset_id = _text(asset["asset_id"], f"assets[{index}].asset_id", 100)
        if asset_id in asset_ids:
            raise DefenderBoxError(f"duplicate asset_id: {asset_id}")
        asset_ids.add(asset_id)
        for key in ("system", "product", "version_evidence", "owner_role"):
            _text(asset[key], f"assets[{index}].{key}", 220)
        if asset["service_criticality"] not in {"low", "moderate", "high", "essential"}:
            raise DefenderBoxError("unsupported service_criticality")
        if asset["patchability"] not in {"now", "window_only", "unavailable"}:
            raise DefenderBoxError("unsupported patchability")
        patchability[asset_id] = asset["patchability"]

    vulnerabilities = campaign["vulnerabilities"]
    if not isinstance(vulnerabilities, list) or not (1 <= len(vulnerabilities) <= 500):
        raise DefenderBoxError("vulnerabilities must contain between 1 and 500 entries")
    vulnerability_ids: set[str] = set()
    affected_pairs: set[tuple[str, str]] = set()
    for index, vulnerability in enumerate(vulnerabilities):
        _exact(
            vulnerability,
            {"vulnerability_id", "source_ref", "known_exploited", "due_date", "affected_asset_ids", "required_action"},
            f"vulnerabilities[{index}]",
        )
        vuln_id = _text(vulnerability["vulnerability_id"], "vulnerability_id", 100)
        if vuln_id in vulnerability_ids:
            raise DefenderBoxError(f"duplicate vulnerability_id: {vuln_id}")
        vulnerability_ids.add(vuln_id)
        if vulnerability["source_ref"] not in source_ids:
            raise DefenderBoxError(f"unknown source_ref for {vuln_id}")
        if not isinstance(vulnerability["known_exploited"], bool):
            raise DefenderBoxError("known_exploited must be boolean")
        _iso_date(vulnerability["due_date"], "vulnerability due_date")
        _text(vulnerability["required_action"], "required_action")
        affected = vulnerability["affected_asset_ids"]
        if not isinstance(affected, list) or not affected or not set(affected).issubset(asset_ids):
            raise DefenderBoxError(f"invalid affected_asset_ids for {vuln_id}")
        affected_pairs.update((vuln_id, asset_id) for asset_id in affected)

    tests = campaign["continuity_tests"]
    if not isinstance(tests, list) or not tests:
        raise DefenderBoxError("continuity_tests must contain entries")
    test_ids: set[str] = set()
    test_assets: dict[str, str] = {}
    for index, test in enumerate(tests):
        _exact(
            test,
            {"test_id", "asset_id", "service_available", "observed_interruption_minutes", "max_interruption_minutes", "rollback_ready", "evidence_ref"},
            f"continuity_tests[{index}]",
        )
        test_id = _text(test["test_id"], "test_id", 100)
        if test_id in test_ids:
            raise DefenderBoxError(f"duplicate test_id: {test_id}")
        test_ids.add(test_id)
        if test["asset_id"] not in asset_ids:
            raise DefenderBoxError(f"unknown continuity-test asset: {test['asset_id']}")
        test_assets[test_id] = test["asset_id"]
        if not isinstance(test["service_available"], bool) or not isinstance(test["rollback_ready"], bool):
            raise DefenderBoxError("continuity boolean fields must be boolean")
        for key in ("observed_interruption_minutes", "max_interruption_minutes"):
            if not isinstance(test[key], int) or test[key] < 0:
                raise DefenderBoxError(f"{key} must be a non-negative integer")
        _text(test["evidence_ref"], "continuity evidence_ref", 240)

    decisions = campaign["decisions"]
    if not isinstance(decisions, list) or len(decisions) != len(affected_pairs):
        raise DefenderBoxError("decisions must cover every affected asset exactly once")
    decision_pairs: set[tuple[str, str]] = set()
    for index, decision in enumerate(decisions):
        _exact(
            decision,
            {"vulnerability_id", "asset_id", "applicability", "route", "continuity_test_id", "evidence_refs", "human_approved"},
            f"decisions[{index}]",
        )
        pair = (decision["vulnerability_id"], decision["asset_id"])
        if pair not in affected_pairs or pair in decision_pairs:
            raise DefenderBoxError(f"invalid or duplicate decision pair: {pair}")
        decision_pairs.add(pair)
        if decision["applicability"] not in {"confirmed", "not_affected", "unknown"}:
            raise DefenderBoxError("unsupported applicability")
        if decision["route"] not in {"patch", "compensating_control", "investigate", "no_action"}:
            raise DefenderBoxError("unsupported route")
        test_id = decision["continuity_test_id"]
        if test_id is not None and (test_id not in test_ids or test_assets[test_id] != decision["asset_id"]):
            raise DefenderBoxError("continuity_test_id must refer to the same asset")
        if not isinstance(decision["evidence_refs"], list):
            raise DefenderBoxError("decision evidence_refs must be a list")
        for evidence in decision["evidence_refs"]:
            _text(evidence, "decision evidence_ref", 240)
        if not isinstance(decision["human_approved"], bool):
            raise DefenderBoxError("human_approved must be boolean")
    if decision_pairs != affected_pairs:
        raise DefenderBoxError("decision coverage differs from affected assets")

    boundary = _exact(campaign["boundaries"], BOUNDARIES, "boundaries")
    if any(boundary[key] is not True for key in BOUNDARIES):
        raise DefenderBoxError("all campaign safety boundaries must be true")


def recommended_route(applicability: str, patchability: str) -> str:
    if applicability == "unknown":
        return "investigate"
    if applicability == "not_affected":
        return "no_action"
    return "patch" if patchability == "now" else "compensating_control"


def assess_campaign(campaign: dict[str, Any]) -> dict[str, Any]:
    validate_campaign(campaign)
    assets = {item["asset_id"]: item for item in campaign["assets"]}
    tests = {item["test_id"]: item for item in campaign["continuity_tests"]}
    vulnerabilities = {item["vulnerability_id"]: item for item in campaign["vulnerabilities"]}
    as_of = _iso_date(campaign["as_of"], "as_of")
    rows = []
    for decision in campaign["decisions"]:
        asset = assets[decision["asset_id"]]
        vulnerability = vulnerabilities[decision["vulnerability_id"]]
        expected = recommended_route(decision["applicability"], asset["patchability"])
        test = tests.get(decision["continuity_test_id"])
        continuity_pass = bool(
            test
            and test["service_available"]
            and test["rollback_ready"]
            and test["observed_interruption_minutes"] <= test["max_interruption_minutes"]
        )
        evidence_present = bool(decision["evidence_refs"])
        approval_required = decision["route"] in {"patch", "compensating_control", "no_action"}
        gate_pass = (
            decision["route"] == expected
            and evidence_present
            and (not approval_required or decision["human_approved"])
            and (decision["route"] not in {"patch", "compensating_control"} or continuity_pass)
        )
        row = {
            "vulnerability_id": decision["vulnerability_id"],
            "asset_id": decision["asset_id"],
            "known_exploited": vulnerability["known_exploited"],
            "days_to_due": (date.fromisoformat(vulnerability["due_date"]) - as_of).days,
            "declared_route": decision["route"],
            "recommended_route": expected,
            "route_exact": decision["route"] == expected,
            "continuity_pass": continuity_pass if decision["route"] in {"patch", "compensating_control"} else None,
            "human_approval_present": decision["human_approved"],
            "evidence_present": evidence_present,
            "gate_pass": gate_pass,
        }
        row["result_sha256"] = digest(row)
        rows.append(row)
    passing = sum(row["gate_pass"] for row in rows)
    return {
        "assessment_version": ASSESSMENT_VERSION,
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": digest(campaign),
        "evidence_scope": "declared_synthetic_or_authorized_local_input",
        "summary": {
            "asset_count": len(assets),
            "vulnerability_count": len(vulnerabilities),
            "decision_count": len(rows),
            "known_exploited_decision_count": sum(row["known_exploited"] for row in rows),
            "gate_pass_count": passing,
            "gate_fail_count": len(rows) - passing,
            "all_decisions_ready": passing == len(rows),
        },
        "decisions": rows,
        "claim_boundary": {
            "local_file_assessment": True,
            "no_live_scan_or_change": True,
            "not_field_effectiveness": True,
            "not_certification": True,
        },
    }


def verify_assessment(assessment: dict[str, Any], campaign: dict[str, Any]) -> None:
    if assessment != assess_campaign(campaign):
        raise DefenderBoxError("assessment does not recompute from the supplied campaign")


def build_pack(campaign_path: Path, assessment_path: Path, out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise DefenderBoxError(f"refusing to overwrite existing campaign pack: {out}")
    campaign = load_json(campaign_path)
    assessment = load_json(assessment_path)
    verify_assessment(assessment, campaign)
    out.mkdir(parents=True)
    shutil.copyfile(campaign_path, out / "campaign.json")
    shutil.copyfile(assessment_path, out / "assessment.json")
    (out / "README.md").write_text(
        "# Essential-Service Defender-in-a-Box pack\n\n"
        "This pack is a local planning receipt. It is not a scan, risk assessment, "
        "compliance finding, operational authorization, or field-effectiveness claim.\n"
    )
    files = []
    for path in sorted(out.iterdir()):
        if path.name != "manifest.json":
            files.append({"path": path.name, "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size})
    (out / "manifest.json").write_text(json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-defender-box", description="Build a local continuity-aware fix plan.")
    sub = root.add_subparsers(dest="command", required=True)
    validating = sub.add_parser("validate")
    validating.add_argument("campaign", type=Path)
    assessing = sub.add_parser("assess")
    assessing.add_argument("campaign", type=Path)
    assessing.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify")
    verifying.add_argument("assessment", type=Path)
    verifying.add_argument("--campaign", type=Path, required=True)
    packing = sub.add_parser("pack")
    packing.add_argument("campaign", type=Path)
    packing.add_argument("assessment", type=Path)
    packing.add_argument("--out", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "validate":
            validate_campaign(load_json(args.campaign))
            print(f"OK: {args.campaign} is a valid local defense campaign.")
        elif args.command == "assess":
            result = assess_campaign(load_json(args.campaign))
            write_json(result, args.out)
            print(f"OK: {result['summary']['decision_count']} decisions written to {args.out}.")
        elif args.command == "verify":
            verify_assessment(load_json(args.assessment), load_json(args.campaign))
            print(f"OK: {args.assessment} verified.")
        else:
            build_pack(args.campaign, args.assessment, args.out)
            print(f"OK: campaign pack written to {args.out}.")
        return 0
    except DefenderBoxError as exc:
        print(f"aau-defender-box: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
