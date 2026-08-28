"""AAU Agent Boundary Protocol reference verifier.

The protocol turns an agent's temporary authority into a machine-checkable lease and
evaluates synthetic boundary events against it.  It is deliberately standard-library
only, offline, deterministic, and defensive.  It never connects to a model, network,
credential store, production system, or security scanner.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROFILE_VERSION = "aau-agent-boundary-profile/0.1"
SCENARIO_VERSION = "aau-agent-boundary-scenario/0.1"
RECEIPT_VERSION = "aau-agent-boundary-receipt/0.1"
MAX_JSON_BYTES = 2_000_000
MAX_SCENARIOS = 1_000
ZERO_HASH = "0" * 64


class BoundaryError(ValueError):
    """Raised when a profile, scenario, or receipt violates the public contract."""


@dataclass(frozen=True)
class Decision:
    outcome: str
    violation_codes: tuple[str, ...]
    authority_preserved: bool


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read_bytes(path: Path) -> bytes:
    if path.is_symlink():
        raise BoundaryError(f"refusing symbolic link: {path}")
    if not path.is_file():
        raise BoundaryError(f"not a regular file: {path}")
    size = path.stat().st_size
    if size > MAX_JSON_BYTES:
        raise BoundaryError(f"file exceeds {MAX_JSON_BYTES} bytes: {path}")
    return path.read_bytes()


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(_read_bytes(source))
    except json.JSONDecodeError as exc:
        raise BoundaryError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise BoundaryError(f"expected one JSON object in {source}")
    return value


def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    raw = _read_bytes(source).decode("utf-8")
    scenarios: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BoundaryError(f"invalid JSON on {source}:{line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise BoundaryError(f"expected an object on {source}:{line_number}")
        scenarios.append(item)
    if not scenarios or len(scenarios) > MAX_SCENARIOS:
        raise BoundaryError(f"scenario count must be between 1 and {MAX_SCENARIOS}")
    return scenarios


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    found = set(value)
    if found != expected:
        missing = sorted(expected - found)
        extra = sorted(found - expected)
        raise BoundaryError(f"{label} fields differ; missing={missing}, extra={extra}")


def _text(value: Any, label: str, limit: int = 240) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise BoundaryError(f"{label} must be a non-empty string of at most {limit} characters")
    return value


def _text_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise BoundaryError(f"{label} must be {'a' if allow_empty else 'a non-empty'} string list")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 240 for item in value):
        raise BoundaryError(f"{label} contains an invalid string")
    if len(value) != len(set(value)):
        raise BoundaryError(f"{label} must not contain duplicates")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    text = _text(value, label, 40)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BoundaryError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise BoundaryError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_profile(profile: dict[str, Any]) -> None:
    _exact_keys(
        profile,
        {
            "profile_version",
            "profile_id",
            "organization",
            "authority",
            "safe_stop",
            "response",
            "logging",
            "data_boundary",
            "claims",
        },
        "profile",
    )
    if profile["profile_version"] != PROFILE_VERSION:
        raise BoundaryError(f"profile_version must be {PROFILE_VERSION}")
    _text(profile["profile_id"], "profile_id", 120)

    organization = profile["organization"]
    if not isinstance(organization, dict):
        raise BoundaryError("organization must be an object")
    _exact_keys(organization, {"name", "sector", "environment"}, "organization")
    _text(organization["name"], "organization.name", 120)
    _text(organization["sector"], "organization.sector", 120)
    if organization["environment"] != "synthetic":
        raise BoundaryError("the public reference profile is synthetic-only")

    authority = profile["authority"]
    if not isinstance(authority, dict):
        raise BoundaryError("authority must be an object")
    _exact_keys(
        authority,
        {
            "lease_id",
            "agent_id",
            "task_id",
            "issued_by",
            "valid_from",
            "valid_until",
            "allowed_actions",
            "blocked_actions",
            "allowed_peers",
            "allowed_egress",
            "human_approval_actions",
            "approvals",
        },
        "authority",
    )
    for key in ("lease_id", "agent_id", "task_id", "issued_by"):
        _text(authority[key], f"authority.{key}", 120)
    if not authority["agent_id"].startswith("agent:"):
        raise BoundaryError("authority.agent_id must start with 'agent:'")
    if not authority["issued_by"].startswith("human:"):
        raise BoundaryError("authority.issued_by must name an accountable human role")
    valid_from = _timestamp(authority["valid_from"], "authority.valid_from")
    valid_until = _timestamp(authority["valid_until"], "authority.valid_until")
    if valid_until <= valid_from:
        raise BoundaryError("authority.valid_until must be after valid_from")
    _text_list(authority["blocked_actions"], "authority.blocked_actions")
    _text_list(authority["allowed_peers"], "authority.allowed_peers", allow_empty=True)
    _text_list(authority["allowed_egress"], "authority.allowed_egress", allow_empty=True)
    _text_list(authority["human_approval_actions"], "authority.human_approval_actions")

    actions = authority["allowed_actions"]
    if not isinstance(actions, list) or not actions:
        raise BoundaryError("authority.allowed_actions must be a non-empty list")
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise BoundaryError(f"allowed_actions[{index}] must be an object")
        _exact_keys(action, {"tool", "action", "resources", "destinations"}, f"allowed_actions[{index}]")
        _text(action["tool"], f"allowed_actions[{index}].tool", 80)
        _text(action["action"], f"allowed_actions[{index}].action", 80)
        _text_list(action["resources"], f"allowed_actions[{index}].resources")
        _text_list(action["destinations"], f"allowed_actions[{index}].destinations", allow_empty=True)

    approvals = authority["approvals"]
    if not isinstance(approvals, list):
        raise BoundaryError("authority.approvals must be a list")
    approval_ids: set[str] = set()
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            raise BoundaryError(f"approvals[{index}] must be an object")
        _exact_keys(
            approval,
            {"approval_id", "actor", "actions", "issued_at", "expires_at", "evidence_refs"},
            f"approvals[{index}]",
        )
        approval_id = _text(approval["approval_id"], f"approvals[{index}].approval_id", 120)
        if approval_id in approval_ids:
            raise BoundaryError("approval_id values must be unique")
        approval_ids.add(approval_id)
        actor = _text(approval["actor"], f"approvals[{index}].actor", 120)
        if not actor.startswith("human:"):
            raise BoundaryError("approval.actor must name a human role")
        _text_list(approval["actions"], f"approvals[{index}].actions")
        issued = _timestamp(approval["issued_at"], f"approvals[{index}].issued_at")
        expires = _timestamp(approval["expires_at"], f"approvals[{index}].expires_at")
        if expires <= issued:
            raise BoundaryError("approval.expires_at must be after issued_at")
        _text_list(approval["evidence_refs"], f"approvals[{index}].evidence_refs")

    safe_stop = profile["safe_stop"]
    if not isinstance(safe_stop, dict):
        raise BoundaryError("safe_stop must be an object")
    _exact_keys(safe_stop, {"states", "report_to"}, "safe_stop")
    _text_list(safe_stop["states"], "safe_stop.states")
    if not _text(safe_stop["report_to"], "safe_stop.report_to", 120).startswith("human:"):
        raise BoundaryError("safe_stop.report_to must name a human role")

    response = profile["response"]
    if not isinstance(response, dict):
        raise BoundaryError("response must be an object")
    _exact_keys(
        response,
        {"critical_alert_sla_minutes", "pause_on_critical_alert", "restart_requires_human"},
        "response",
    )
    if not isinstance(response["critical_alert_sla_minutes"], int) or not 1 <= response["critical_alert_sla_minutes"] <= 1440:
        raise BoundaryError("critical_alert_sla_minutes must be an integer from 1 to 1440")
    if response["pause_on_critical_alert"] is not True or response["restart_requires_human"] is not True:
        raise BoundaryError("the reference profile must preserve human pause and restart authority")

    logging = profile["logging"]
    if not isinstance(logging, dict):
        raise BoundaryError("logging must be an object")
    _exact_keys(logging, {"hash_algorithm", "required_event_fields", "tamper_response"}, "logging")
    if logging["hash_algorithm"] != "sha256":
        raise BoundaryError("logging.hash_algorithm must be sha256")
    required_fields = _text_list(logging["required_event_fields"], "logging.required_event_fields")
    mandatory = {"event_id", "type", "occurred_at", "agent_id", "task_id", "authority_ref"}
    if not mandatory.issubset(required_fields):
        raise BoundaryError(f"logging.required_event_fields must include {sorted(mandatory)}")
    if logging["tamper_response"] != "pause":
        raise BoundaryError("logging.tamper_response must be pause")

    data_boundary = profile["data_boundary"]
    if not isinstance(data_boundary, dict):
        raise BoundaryError("data_boundary must be an object")
    _exact_keys(
        data_boundary,
        {
            "classification",
            "contains_real_credentials",
            "contains_personal_data",
            "contains_controlled_data",
            "contains_classified_data",
        },
        "data_boundary",
    )
    if data_boundary["classification"] != "synthetic":
        raise BoundaryError("data_boundary.classification must be synthetic")
    for key in (
        "contains_real_credentials",
        "contains_personal_data",
        "contains_controlled_data",
        "contains_classified_data",
    ):
        if data_boundary[key] is not False:
            raise BoundaryError(f"data_boundary.{key} must be false")

    claims = profile["claims"]
    if not isinstance(claims, dict):
        raise BoundaryError("claims must be an object")
    _exact_keys(
        claims,
        {"not_certification", "not_authorization_to_operate", "not_compliance_finding"},
        "claims",
    )
    if any(value is not True for value in claims.values()):
        raise BoundaryError("all non-certification claim boundaries must be true")


def validate_scenarios(scenarios: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for index, scenario in enumerate(scenarios):
        label = f"scenario[{index}]"
        _exact_keys(
            scenario,
            {"scenario_version", "scenario_id", "title", "failure_shape", "event", "expected"},
            label,
        )
        if scenario["scenario_version"] != SCENARIO_VERSION:
            raise BoundaryError(f"{label}.scenario_version must be {SCENARIO_VERSION}")
        scenario_id = _text(scenario["scenario_id"], f"{label}.scenario_id", 120)
        if scenario_id in seen:
            raise BoundaryError(f"duplicate scenario_id: {scenario_id}")
        seen.add(scenario_id)
        _text(scenario["title"], f"{label}.title", 160)
        _text(scenario["failure_shape"], f"{label}.failure_shape", 160)
        event = scenario["event"]
        if not isinstance(event, dict):
            raise BoundaryError(f"{label}.event must be an object")
        for field in ("event_id", "type", "occurred_at", "agent_id", "task_id", "authority_ref"):
            if field not in event:
                raise BoundaryError(f"{label}.event is missing {field}")
            _text(event[field], f"{label}.event.{field}", 240)
        _timestamp(event["occurred_at"], f"{label}.event.occurred_at")
        expected = scenario["expected"]
        if not isinstance(expected, dict):
            raise BoundaryError(f"{label}.expected must be an object")
        _exact_keys(expected, {"decision", "violation_codes"}, f"{label}.expected")
        if expected["decision"] not in {"allow", "block", "safe_stop", "pause"}:
            raise BoundaryError(f"{label}.expected.decision is unsupported")
        _text_list(expected["violation_codes"], f"{label}.expected.violation_codes", allow_empty=True)


def _matches(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(value, pattern) for pattern in patterns)


def _active_approval(profile: dict[str, Any], event: dict[str, Any], action_key: str) -> bool:
    approval_ref = event.get("approval_ref")
    evidence_refs = event.get("control_evidence", [])
    if not approval_ref or not isinstance(evidence_refs, list):
        return False
    occurred_at = _timestamp(event["occurred_at"], "event.occurred_at")
    for approval in profile["authority"]["approvals"]:
        if approval["approval_id"] != approval_ref or action_key not in approval["actions"]:
            continue
        issued = _timestamp(approval["issued_at"], "approval.issued_at")
        expires = _timestamp(approval["expires_at"], "approval.expires_at")
        required = set(approval["evidence_refs"])
        return issued <= occurred_at <= expires and required.issubset(evidence_refs)
    return False


def _action_violations(profile: dict[str, Any], event: dict[str, Any]) -> list[str]:
    tool = str(event.get("tool", ""))
    action = str(event.get("action", ""))
    resource = str(event.get("resource", ""))
    destination = str(event.get("destination", ""))
    action_key = f"{tool}.{action}"
    authority = profile["authority"]
    violations: list[str] = []

    if event.get("authority_basis") == "discovered_credential":
        violations.append("CREDENTIAL_IS_NOT_AUTHORITY")
    if action_key in authority["blocked_actions"]:
        violations.append("ACTION_EXPLICITLY_BLOCKED")

    matching_rules = [
        rule
        for rule in authority["allowed_actions"]
        if rule["tool"] == tool and rule["action"] == action and _matches(resource, rule["resources"])
    ]
    if not matching_rules:
        violations.append("ACTION_OUT_OF_SCOPE")
    elif destination:
        rule_destinations = [pattern for rule in matching_rules for pattern in rule["destinations"]]
        globally_allowed = _matches(destination, authority["allowed_egress"])
        locally_allowed = bool(rule_destinations) and _matches(destination, rule_destinations)
        if not globally_allowed or not locally_allowed:
            violations.append("EGRESS_NOT_ALLOWED")

    if action_key in authority["human_approval_actions"] and not _active_approval(profile, event, action_key):
        violations.append("HUMAN_APPROVAL_MISSING")
    return violations


def decide(profile: dict[str, Any], event: dict[str, Any]) -> Decision:
    """Derive one decision from the profile.  Event text is never executed."""

    authority = profile["authority"]
    violations: list[str] = []
    required_fields = profile["logging"]["required_event_fields"]
    if any(field not in event or event[field] in (None, "") for field in required_fields):
        violations.append("PROVENANCE_INCOMPLETE")
    if event.get("agent_id") != authority["agent_id"]:
        violations.append("IDENTITY_MISMATCH")
    if event.get("task_id") != authority["task_id"]:
        violations.append("TASK_MISMATCH")
    if event.get("authority_ref") != authority["lease_id"]:
        violations.append("AUTHORITY_REF_INVALID")

    occurred_at = _timestamp(event.get("occurred_at"), "event.occurred_at")
    valid_from = _timestamp(authority["valid_from"], "authority.valid_from")
    valid_until = _timestamp(authority["valid_until"], "authority.valid_until")
    if not valid_from <= occurred_at <= valid_until:
        violations.append("LEASE_INACTIVE")

    event_type = event.get("type")
    if event_type == "task_state":
        state = event.get("state")
        if state in profile["safe_stop"]["states"]:
            violations.append("SAFE_STOP_REQUIRED")
            return Decision("safe_stop", tuple(sorted(set(violations))), True)
        return Decision("block" if violations else "allow", tuple(sorted(set(violations))), not violations)

    if event_type == "peer_instruction":
        if event.get("source_agent") not in authority["allowed_peers"]:
            violations.append("UNAUTHORIZED_PEER")
        violations.extend(_action_violations(profile, event))
    elif event_type in {"action_request", "network_request"}:
        violations.extend(_action_violations(profile, event))
    elif event_type == "monitor_state":
        if event.get("state") != "operational":
            violations.append("MONITORING_LOST")
            return Decision("pause", tuple(sorted(set(violations))), True)
    elif event_type == "critical_alert":
        if event.get("severity") == "critical" and profile["response"]["pause_on_critical_alert"]:
            violations.append("CRITICAL_ALERT_PAUSE")
            return Decision("pause", tuple(sorted(set(violations))), True)
    elif event_type == "restart_request":
        action_key = "run.restart"
        if not _active_approval(profile, event, action_key):
            violations.append("HUMAN_RESTART_APPROVAL_MISSING")
    elif event_type == "record_mutation":
        if event.get("operation") in {"delete", "rewrite", "truncate"}:
            violations.append("AUDIT_TAMPERING")
            return Decision(profile["logging"]["tamper_response"], tuple(sorted(set(violations))), True)
    else:
        violations.append("EVENT_TYPE_UNSUPPORTED")

    unique = tuple(sorted(set(violations)))
    return Decision("block" if unique else "allow", unique, True)


def evaluate(profile: dict[str, Any], scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    validate_profile(profile)
    validate_scenarios(scenarios)
    previous = ZERO_HASH
    results: list[dict[str, Any]] = []
    metric_totals = {
        "exact_decision": 0.0,
        "exact_violations": 0.0,
        "unsafe_allow": 0.0,
        "boundary_containment": 0.0,
        "safe_stop_required": 0.0,
        "safe_stop_success": 0.0,
        "provenance_complete": 0.0,
        "human_control_preserved": 0.0,
    }

    for scenario in scenarios:
        event = scenario["event"]
        expected = scenario["expected"]
        decision = decide(profile, event)
        expected_codes = tuple(sorted(expected["violation_codes"]))
        exact_decision = decision.outcome == expected["decision"]
        exact_violations = decision.violation_codes == expected_codes
        unsafe_allow = decision.outcome == "allow" and expected["decision"] != "allow"
        provenance_complete = "PROVENANCE_INCOMPLETE" not in decision.violation_codes
        safe_stop_required = expected["decision"] == "safe_stop"
        metrics = {
            "exact_decision": float(exact_decision),
            "exact_violations": float(exact_violations),
            "unsafe_allow": float(unsafe_allow),
            "boundary_containment": float(not unsafe_allow),
            "safe_stop_required": float(safe_stop_required),
            "safe_stop_success": float(safe_stop_required and decision.outcome == "safe_stop"),
            "provenance_complete": float(provenance_complete),
            "human_control_preserved": float(decision.authority_preserved and not unsafe_allow),
        }
        for key, value in metrics.items():
            metric_totals[key] += value

        material = {
            "scenario_id": scenario["scenario_id"],
            "event_sha256": _digest(event),
            "decision": decision.outcome,
            "violation_codes": list(decision.violation_codes),
            "metrics": metrics,
            "previous_result_sha256": previous,
        }
        result_hash = _digest(material)
        results.append({**material, "result_sha256": result_hash})
        previous = result_hash

    count = len(results)
    summary = {key: round(total / count, 6) for key, total in metric_totals.items()}
    safe_stop_count = metric_totals["safe_stop_required"]
    summary["safe_stop_success"] = round(
        metric_totals["safe_stop_success"] / safe_stop_count, 6
    ) if safe_stop_count else 0.0
    generated_at = max(
        scenarios,
        key=lambda item: _timestamp(item["event"]["occurred_at"], "event.occurred_at"),
    )["event"]["occurred_at"]
    return {
        "receipt_version": RECEIPT_VERSION,
        "generated_at": generated_at,
        "profile_id": profile["profile_id"],
        "profile_sha256": _digest(profile),
        "scenario_set_sha256": _digest(scenarios),
        "scenario_count": count,
        "summary": summary,
        "results": results,
        "chain_head_sha256": previous,
        "boundary": {
            "synthetic_only": True,
            "not_certification": True,
            "not_authorization_to_operate": True,
            "no_live_offensive_activity": True,
        },
    }


def verify_receipt(
    receipt: dict[str, Any],
    profile: dict[str, Any] | None = None,
    scenarios: list[dict[str, Any]] | None = None,
) -> None:
    required = {
        "receipt_version",
        "generated_at",
        "profile_id",
        "profile_sha256",
        "scenario_set_sha256",
        "scenario_count",
        "summary",
        "results",
        "chain_head_sha256",
        "boundary",
    }
    _exact_keys(receipt, required, "receipt")
    if receipt["receipt_version"] != RECEIPT_VERSION:
        raise BoundaryError(f"receipt_version must be {RECEIPT_VERSION}")
    if not isinstance(receipt["results"], list) or len(receipt["results"]) != receipt["scenario_count"]:
        raise BoundaryError("receipt result count does not match scenario_count")
    previous = ZERO_HASH
    totals: dict[str, float] = {}
    for index, result in enumerate(receipt["results"]):
        if result.get("previous_result_sha256") != previous:
            raise BoundaryError(f"result[{index}] breaks the hash chain")
        material = {key: value for key, value in result.items() if key != "result_sha256"}
        expected_hash = _digest(material)
        if result.get("result_sha256") != expected_hash:
            raise BoundaryError(f"result[{index}] digest mismatch")
        previous = expected_hash
        metrics = result.get("metrics")
        if not isinstance(metrics, dict):
            raise BoundaryError(f"result[{index}].metrics must be an object")
        for key, value in metrics.items():
            if value not in (0.0, 1.0):
                raise BoundaryError(f"result[{index}].metrics.{key} must be 0.0 or 1.0")
            totals[key] = totals.get(key, 0.0) + value
    if receipt["chain_head_sha256"] != previous:
        raise BoundaryError("chain_head_sha256 does not match the final result")
    count = receipt["scenario_count"]
    derived_summary = {key: round(total / count, 6) for key, total in totals.items()}
    safe_stop_count = totals.get("safe_stop_required", 0.0)
    derived_summary["safe_stop_success"] = round(
        totals.get("safe_stop_success", 0.0) / safe_stop_count, 6
    ) if safe_stop_count else 0.0
    if receipt["summary"] != derived_summary:
        raise BoundaryError("receipt summary is not derived from result metrics")

    if (profile is None) != (scenarios is None):
        raise BoundaryError("full verification requires both profile and scenarios")
    if profile is not None and scenarios is not None:
        expected = evaluate(profile, scenarios)
        if receipt != expected:
            raise BoundaryError("receipt does not recompute from the supplied profile and scenarios")


def write_receipt(receipt: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    if target.exists():
        raise BoundaryError(f"refusing to overwrite existing receipt: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2) + "\n")


def build_pack(profile_path: Path, scenarios_path: Path, receipt_path: Path, out: Path) -> None:
    if out.exists():
        raise BoundaryError(f"refusing to overwrite existing pack: {out}")
    profile = load_json(profile_path)
    scenarios = load_scenarios(scenarios_path)
    receipt = load_json(receipt_path)
    verify_receipt(receipt, profile, scenarios)
    out.mkdir(parents=True)
    copies = {
        "profile.json": profile_path,
        "scenarios.jsonl": scenarios_path,
        "receipt.json": receipt_path,
    }
    for name, source in copies.items():
        _read_bytes(source)
        shutil.copyfile(source, out / name)
    readme = (
        "# Agent Boundary evidence pack\n\n"
        "This pack contains a synthetic authority profile, defensive scenario set, and a "
        "recomputed tamper-evident receipt. It is not certification, an authorization to "
        "operate, a compliance finding, or evidence about a production deployment.\n"
    )
    (out / "README.md").write_text(readme)
    rows = []
    for path in sorted(out.iterdir()):
        if path.name == "manifest.json":
            continue
        data = path.read_bytes()
        rows.append({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {"manifest_version": "aau-agent-boundary-pack/0.1", "files": rows}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau-agent-boundary",
        description="Validate and evaluate synthetic AI-agent authority boundaries.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validating = sub.add_parser("validate", help="validate a synthetic boundary profile")
    validating.add_argument("profile", type=Path)
    evaluating = sub.add_parser("evaluate", help="evaluate a profile against JSONL scenarios")
    evaluating.add_argument("profile", type=Path)
    evaluating.add_argument("scenarios", type=Path)
    evaluating.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify", help="verify a receipt hash chain and optionally recompute it")
    verifying.add_argument("receipt", type=Path)
    verifying.add_argument("--profile", type=Path)
    verifying.add_argument("--scenarios", type=Path)
    packing = sub.add_parser("pack", help="create a non-overwriting portable evidence pack")
    packing.add_argument("profile", type=Path)
    packing.add_argument("scenarios", type=Path)
    packing.add_argument("receipt", type=Path)
    packing.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "validate":
            validate_profile(load_json(args.profile))
            print(f"OK: {args.profile} is a valid synthetic Agent Boundary profile.")
            return 0
        if args.command == "evaluate":
            profile = load_json(args.profile)
            scenarios = load_scenarios(args.scenarios)
            receipt = evaluate(profile, scenarios)
            write_receipt(receipt, args.out)
            print(
                f"OK: {receipt['scenario_count']} boundary scenarios evaluated; "
                f"receipt written to {args.out}."
            )
            return 0
        if args.command == "verify":
            if bool(args.profile) != bool(args.scenarios):
                raise BoundaryError("provide both --profile and --scenarios, or neither")
            profile = load_json(args.profile) if args.profile else None
            scenarios = load_scenarios(args.scenarios) if args.scenarios else None
            verify_receipt(load_json(args.receipt), profile, scenarios)
            mode = "recomputed" if profile is not None else "hash-chain"
            print(f"OK: {args.receipt} passed {mode} verification.")
            return 0
        build_pack(args.profile, args.scenarios, args.receipt, args.out)
        print(f"OK: portable evidence pack written to {args.out}.")
        return 0
    except BoundaryError as exc:
        print(f"aau-agent-boundary: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
