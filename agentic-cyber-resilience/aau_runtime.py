"""Stateful AAU Agent Boundary Protocol 0.2 conformance gateway.

The gateway is an offline policy decision point. It normalizes recorded framework
events, evaluates them against an ABP authority profile, and models run state across
pause, safe-stop, revocation, delegation, and human-controlled restart. It never
executes a tool, accepts a credential, opens a socket, or connects to a live system.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aau_boundary import (
    BoundaryError,
    ZERO_HASH,
    _digest,
    _read_bytes,
    _text,
    _timestamp,
    decide,
    load_json,
    validate_profile,
)


RUNTIME_VERSION = "aau-agent-boundary-runtime/0.2"
SUITE_VERSION = "aau-agent-boundary-runtime-suite/0.2"
RECEIPT_VERSION = "aau-agent-boundary-runtime-receipt/0.2"
PACK_VERSION = "aau-agent-boundary-runtime-pack/0.2"
MAX_RUNS = 200
MAX_EVENTS = 2_000


@dataclass
class RuntimeState:
    status: str = "active"
    policy_epoch: int = 1
    sequence: int = 0
    pause_reason: str | None = None
    delegations: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeDecision:
    outcome: str
    reason_codes: tuple[str, ...]
    status_after: str
    policy_epoch_after: int


def _split_tool(name: Any) -> tuple[str, str]:
    value = _text(name, "tool name", 160)
    if "." not in value:
        raise BoundaryError("tool name must use '<tool>.<action>'")
    tool, action = value.rsplit(".", 1)
    if not tool or not action:
        raise BoundaryError("tool name must use '<tool>.<action>'")
    return tool, action


def _context(envelope: dict[str, Any]) -> dict[str, Any]:
    context = envelope.get("context")
    if not isinstance(context, dict):
        raise BoundaryError("adapter envelope.context must be an object")
    required = {
        "event_id",
        "occurred_at",
        "agent_id",
        "task_id",
        "authority_ref",
        "policy_epoch",
    }
    missing = sorted(required - set(context))
    if missing:
        raise BoundaryError(f"adapter context is missing {missing}")
    return copy.deepcopy(context)


def normalize_framework_event(adapter: str, envelope: dict[str, Any]) -> dict[str, Any]:
    """Normalize recorded framework-shaped tool calls without importing a framework."""

    if adapter == "generic":
        event = copy.deepcopy(envelope)
        if not isinstance(event, dict):
            raise BoundaryError("generic event must be an object")
        return event

    supported = {"mcp", "openai-agents", "langgraph", "crewai", "autogen"}
    if adapter not in supported:
        raise BoundaryError(f"unsupported adapter: {adapter}")

    context = _context(envelope)
    arguments: dict[str, Any]
    tool_name: Any

    if adapter == "mcp":
        if envelope.get("jsonrpc") != "2.0" or envelope.get("method") != "tools/call":
            raise BoundaryError("MCP adapter accepts only recorded JSON-RPC tools/call envelopes")
        params = envelope.get("params")
        if not isinstance(params, dict):
            raise BoundaryError("MCP params must be an object")
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
    elif adapter == "openai-agents":
        if envelope.get("type") not in {"function_call", "tool_call"}:
            raise BoundaryError("OpenAI adapter expects a recorded function_call or tool_call")
        tool_name = envelope.get("name")
        arguments = envelope.get("arguments", {})
    elif adapter == "langgraph":
        tool_name = envelope.get("tool")
        arguments = envelope.get("tool_input", {})
    elif adapter == "crewai":
        tool_name = envelope.get("tool")
        arguments = envelope.get("input", {})
    elif adapter == "autogen":
        function = envelope.get("function")
        if not isinstance(function, dict):
            raise BoundaryError("AutoGen adapter expects function metadata")
        tool_name = function.get("name")
        arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise BoundaryError("adapter arguments string must contain one JSON object") from exc
    if not isinstance(arguments, dict):
        raise BoundaryError("adapter arguments must be an object")
    tool, action = _split_tool(tool_name)
    event = {
        **context,
        "kind": "tool_call",
        "tool": tool,
        "action": action,
        "resource": str(arguments.get("resource", "")),
        "destination": str(arguments.get("destination", "")),
    }
    for key in (
        "approval_ref",
        "authority_basis",
        "control_evidence",
        "token_audience",
        "resource_uri",
        "token_passthrough",
    ):
        if key in arguments:
            event[key] = copy.deepcopy(arguments[key])
    return event


def _base_violations(profile: dict[str, Any], event: dict[str, Any], state: RuntimeState) -> list[str]:
    violations: list[str] = []
    if event.get("sequence") != state.sequence + 1:
        violations.append("SEQUENCE_INVALID")
    if event.get("policy_epoch") != state.policy_epoch:
        violations.append("STALE_POLICY_EPOCH")
    if event.get("agent_id") != profile["authority"]["agent_id"]:
        violations.append("IDENTITY_MISMATCH")
    if event.get("task_id") != profile["authority"]["task_id"]:
        violations.append("TASK_MISMATCH")
    if event.get("authority_ref") != profile["authority"]["lease_id"]:
        violations.append("AUTHORITY_REF_INVALID")
    _timestamp(event.get("occurred_at"), "event.occurred_at")
    return violations


def _boundary_event(event: dict[str, Any], event_type: str) -> dict[str, Any]:
    translated = {
        "event_id": event["event_id"],
        "type": event_type,
        "occurred_at": event["occurred_at"],
        "agent_id": event["agent_id"],
        "task_id": event["task_id"],
        "authority_ref": event["authority_ref"],
    }
    for key in (
        "tool",
        "action",
        "resource",
        "destination",
        "authority_basis",
        "approval_ref",
        "control_evidence",
        "source_agent",
        "state",
        "severity",
        "operation",
    ):
        if key in event:
            translated[key] = copy.deepcopy(event[key])
    return translated


def _allowed_action_keys(profile: dict[str, Any]) -> set[str]:
    return {
        f"{item['tool']}.{item['action']}"
        for item in profile["authority"]["allowed_actions"]
    }


def evaluate_event(
    profile: dict[str, Any], event: dict[str, Any], state: RuntimeState
) -> RuntimeDecision:
    """Evaluate one normalized event and update the supplied state."""

    if not isinstance(event, dict):
        raise BoundaryError("runtime event must be an object")
    for field_name in (
        "event_id",
        "kind",
        "occurred_at",
        "agent_id",
        "task_id",
        "authority_ref",
        "sequence",
        "policy_epoch",
    ):
        if field_name not in event:
            raise BoundaryError(f"runtime event is missing {field_name}")
    _text(event["event_id"], "event.event_id", 160)
    kind = _text(event["kind"], "event.kind", 80)
    if not isinstance(event["sequence"], int) or event["sequence"] < 1:
        raise BoundaryError("event.sequence must be a positive integer")
    if not isinstance(event["policy_epoch"], int) or event["policy_epoch"] < 1:
        raise BoundaryError("event.policy_epoch must be a positive integer")

    violations = _base_violations(profile, event, state)
    if state.status == "revoked":
        violations.append("RUN_REVOKED")
    elif state.status in {"paused", "safe_stopped"} and kind != "resume":
        violations.append("RUN_NOT_ACTIVE")

    outcome = "block" if violations else "allow"
    next_status = state.status
    next_epoch = state.policy_epoch

    if not violations and kind == "tool_call":
        if event.get("token_passthrough") is True:
            violations.append("TOKEN_PASSTHROUGH_FORBIDDEN")
        audience = event.get("token_audience")
        resource_uri = event.get("resource_uri")
        if audience is not None or resource_uri is not None:
            if not audience or not resource_uri or audience != resource_uri:
                violations.append("TOKEN_AUDIENCE_MISMATCH")
        boundary = decide(profile, _boundary_event(event, "action_request"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
    elif not violations and kind == "network_request":
        boundary = decide(profile, _boundary_event(event, "network_request"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
    elif not violations and kind == "peer_instruction":
        boundary = decide(profile, _boundary_event(event, "peer_instruction"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
    elif not violations and kind == "delegate":
        target = _text(event.get("target_agent"), "event.target_agent", 120)
        requested = event.get("allowed_actions")
        if not isinstance(requested, list) or not requested or any(
            not isinstance(item, str) or not item for item in requested
        ):
            raise BoundaryError("delegate.allowed_actions must be a non-empty string list")
        if target not in profile["authority"]["allowed_peers"]:
            violations.append("UNAUTHORIZED_PEER")
        if not set(requested).issubset(_allowed_action_keys(profile)):
            violations.append("DELEGATION_SCOPE_EXPANSION")
        if not violations:
            state.delegations[target] = tuple(sorted(set(requested)))
    elif not violations and kind == "revoke":
        if event.get("actor") != profile["authority"]["issued_by"]:
            violations.append("REVOCATION_AUTHORITY_INVALID")
        else:
            next_status = "revoked"
            next_epoch += 1
            outcome = "pause"
            violations.append("LEASE_REVOKED")
    elif not violations and kind == "pause":
        if not str(event.get("actor", "")).startswith("human:"):
            violations.append("PAUSE_AUTHORITY_INVALID")
        else:
            next_status = "paused"
            outcome = "pause"
            violations.append("HUMAN_PAUSE")
    elif not violations and kind == "resume":
        boundary = decide(profile, _boundary_event(event, "restart_request"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
        if outcome == "allow":
            next_status = "active"
            next_epoch += 1
    elif not violations and kind == "monitor_state":
        boundary = decide(profile, _boundary_event(event, "monitor_state"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
        if outcome == "pause":
            next_status = "paused"
    elif not violations and kind == "critical_alert":
        boundary = decide(profile, _boundary_event(event, "critical_alert"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
        if outcome == "pause":
            next_status = "paused"
    elif not violations and kind == "task_state":
        boundary = decide(profile, _boundary_event(event, "task_state"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
        if outcome == "safe_stop":
            next_status = "safe_stopped"
    elif not violations and kind == "record_mutation":
        boundary = decide(profile, _boundary_event(event, "record_mutation"))
        violations.extend(boundary.violation_codes)
        outcome = boundary.outcome
        if outcome == "pause":
            next_status = "paused"
    elif not violations:
        violations.append("RUNTIME_EVENT_UNSUPPORTED")

    unique = tuple(sorted(set(violations)))
    if unique and outcome == "allow":
        outcome = "block"
    if "RUN_REVOKED" in unique or "RUN_NOT_ACTIVE" in unique:
        outcome = "block"
    state.sequence = event["sequence"]
    state.status = next_status
    state.policy_epoch = next_epoch
    state.pause_reason = unique[0] if next_status in {"paused", "safe_stopped", "revoked"} else None
    return RuntimeDecision(outcome, unique, next_status, next_epoch)


def _normalized_suite_event(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = item.get("expected")
    if not isinstance(expected, dict) or set(expected) != {"outcome", "reason_codes", "status_after"}:
        raise BoundaryError("suite event expected must contain outcome, reason_codes, and status_after")
    if expected["outcome"] not in {"allow", "block", "pause", "safe_stop"}:
        raise BoundaryError("suite expected outcome is unsupported")
    if expected["status_after"] not in {"active", "paused", "safe_stopped", "revoked"}:
        raise BoundaryError("suite expected status_after is unsupported")
    if not isinstance(expected["reason_codes"], list) or any(
        not isinstance(code, str) or not code for code in expected["reason_codes"]
    ):
        raise BoundaryError("suite expected reason_codes must be a string list")
    adapter = item.get("adapter", "generic")
    payload = item.get("event") if adapter == "generic" else item.get("envelope")
    if not isinstance(payload, dict):
        raise BoundaryError("suite event payload must be an object")
    event = normalize_framework_event(adapter, payload)
    return event, expected


def validate_suite(suite: dict[str, Any]) -> None:
    if set(suite) != {"suite_version", "suite_id", "title", "boundary", "runs"}:
        raise BoundaryError("runtime suite fields differ from the 0.2 contract")
    if suite["suite_version"] != SUITE_VERSION:
        raise BoundaryError(f"suite_version must be {SUITE_VERSION}")
    _text(suite["suite_id"], "suite_id", 120)
    _text(suite["title"], "title", 200)
    boundary = suite["boundary"]
    if not isinstance(boundary, dict) or set(boundary) != {
        "synthetic_only",
        "no_live_targets",
        "no_real_credentials",
        "not_certification",
    }:
        raise BoundaryError("suite boundary fields differ from the 0.2 contract")
    if any(value is not True for value in boundary.values()):
        raise BoundaryError("all runtime suite safety boundaries must be true")
    runs = suite["runs"]
    if not isinstance(runs, list) or not 1 <= len(runs) <= MAX_RUNS:
        raise BoundaryError(f"runs must contain between 1 and {MAX_RUNS} entries")
    seen_runs: set[str] = set()
    event_count = 0
    for index, run in enumerate(runs):
        if not isinstance(run, dict) or set(run) != {"run_id", "title", "events"}:
            raise BoundaryError(f"run[{index}] fields differ")
        run_id = _text(run["run_id"], f"run[{index}].run_id", 120)
        if run_id in seen_runs:
            raise BoundaryError(f"duplicate run_id: {run_id}")
        seen_runs.add(run_id)
        _text(run["title"], f"run[{index}].title", 200)
        if not isinstance(run["events"], list) or not run["events"]:
            raise BoundaryError(f"run[{index}].events must be a non-empty list")
        for item in run["events"]:
            _normalized_suite_event(item)
            event_count += 1
    if event_count > MAX_EVENTS:
        raise BoundaryError(f"suite exceeds {MAX_EVENTS} events")


def evaluate_suite(profile: dict[str, Any], suite: dict[str, Any]) -> dict[str, Any]:
    validate_profile(profile)
    validate_suite(suite)
    previous = ZERO_HASH
    run_rows: list[dict[str, Any]] = []
    totals = {
        "exact_outcome": 0,
        "exact_reason_codes": 0,
        "exact_state": 0,
        "unsafe_allow": 0,
        "legitimate_allow_preserved": 0,
        "legitimate_allow_total": 0,
        "pause_or_stop_required": 0,
        "pause_or_stop_success": 0,
    }
    event_count = 0
    for run in suite["runs"]:
        state = RuntimeState()
        event_rows: list[dict[str, Any]] = []
        for item in run["events"]:
            event, expected = _normalized_suite_event(item)
            decision = evaluate_event(profile, event, state)
            expected_codes = tuple(sorted(expected["reason_codes"]))
            exact_outcome = decision.outcome == expected["outcome"]
            exact_reasons = decision.reason_codes == expected_codes
            exact_state = decision.status_after == expected["status_after"]
            unsafe_allow = decision.outcome == "allow" and expected["outcome"] != "allow"
            legitimate = expected["outcome"] == "allow"
            stop_required = expected["outcome"] in {"pause", "safe_stop"}
            metrics = {
                "exact_outcome": int(exact_outcome),
                "exact_reason_codes": int(exact_reasons),
                "exact_state": int(exact_state),
                "unsafe_allow": int(unsafe_allow),
                "legitimate_allow_preserved": int(legitimate and decision.outcome == "allow"),
                "legitimate_allow_total": int(legitimate),
                "pause_or_stop_required": int(stop_required),
                "pause_or_stop_success": int(stop_required and decision.outcome == expected["outcome"]),
            }
            for key, value in metrics.items():
                totals[key] += value
            material = {
                "event_id": event["event_id"],
                "event_sha256": _digest(event),
                "decision": decision.outcome,
                "reason_codes": list(decision.reason_codes),
                "status_after": decision.status_after,
                "policy_epoch_after": decision.policy_epoch_after,
                "metrics": metrics,
                "previous_event_sha256": previous,
            }
            event_hash = _digest(material)
            event_rows.append({**material, "event_result_sha256": event_hash})
            previous = event_hash
            event_count += 1
        run_rows.append(
            {
                "run_id": run["run_id"],
                "event_count": len(event_rows),
                "final_status": state.status,
                "final_policy_epoch": state.policy_epoch,
                "events": event_rows,
            }
        )
    summary = {
        "exact_outcome": round(totals["exact_outcome"] / event_count, 6),
        "exact_reason_codes": round(totals["exact_reason_codes"] / event_count, 6),
        "exact_state": round(totals["exact_state"] / event_count, 6),
        "unsafe_allow": round(totals["unsafe_allow"] / event_count, 6),
        "legitimate_allow_preservation": round(
            totals["legitimate_allow_preserved"] / totals["legitimate_allow_total"], 6
        ) if totals["legitimate_allow_total"] else 0.0,
        "pause_or_stop_success": round(
            totals["pause_or_stop_success"] / totals["pause_or_stop_required"], 6
        ) if totals["pause_or_stop_required"] else 0.0,
    }
    return {
        "receipt_version": RECEIPT_VERSION,
        "suite_id": suite["suite_id"],
        "profile_id": profile["profile_id"],
        "profile_sha256": _digest(profile),
        "suite_sha256": _digest(suite),
        "run_count": len(run_rows),
        "event_count": event_count,
        "summary": summary,
        "runs": run_rows,
        "chain_head_sha256": previous,
        "boundary": copy.deepcopy(suite["boundary"]),
    }


def verify_runtime_receipt(
    receipt: dict[str, Any],
    profile: dict[str, Any] | None = None,
    suite: dict[str, Any] | None = None,
) -> None:
    required = {
        "receipt_version",
        "suite_id",
        "profile_id",
        "profile_sha256",
        "suite_sha256",
        "run_count",
        "event_count",
        "summary",
        "runs",
        "chain_head_sha256",
        "boundary",
    }
    if set(receipt) != required or receipt.get("receipt_version") != RECEIPT_VERSION:
        raise BoundaryError("runtime receipt fields or version are invalid")
    previous = ZERO_HASH
    count = 0
    for run_index, run in enumerate(receipt.get("runs", [])):
        if run.get("event_count") != len(run.get("events", [])):
            raise BoundaryError(f"runtime run[{run_index}] event count differs")
        for event_index, row in enumerate(run["events"]):
            if row.get("previous_event_sha256") != previous:
                raise BoundaryError(f"runtime event[{run_index}:{event_index}] breaks the chain")
            material = {key: value for key, value in row.items() if key != "event_result_sha256"}
            expected_hash = _digest(material)
            if row.get("event_result_sha256") != expected_hash:
                raise BoundaryError(f"runtime event[{run_index}:{event_index}] digest mismatch")
            previous = expected_hash
            count += 1
    if count != receipt.get("event_count") or len(receipt.get("runs", [])) != receipt.get("run_count"):
        raise BoundaryError("runtime receipt aggregate counts differ")
    if previous != receipt.get("chain_head_sha256"):
        raise BoundaryError("runtime receipt chain head differs")
    if (profile is None) != (suite is None):
        raise BoundaryError("full runtime verification requires profile and suite")
    if profile is not None and suite is not None and receipt != evaluate_suite(profile, suite):
        raise BoundaryError("runtime receipt does not recompute from profile and suite")


def write_json(value: dict[str, Any], target: Path) -> None:
    if target.exists():
        raise BoundaryError(f"refusing to overwrite: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n")


def build_runtime_pack(profile_path: Path, suite_path: Path, receipt_path: Path, out: Path) -> None:
    if out.exists():
        raise BoundaryError(f"refusing to overwrite existing runtime pack: {out}")
    profile = load_json(profile_path)
    suite = load_json(suite_path)
    receipt = load_json(receipt_path)
    verify_runtime_receipt(receipt, profile, suite)
    out.mkdir(parents=True)
    for name, source in {
        "profile.json": profile_path,
        "suite.json": suite_path,
        "receipt.json": receipt_path,
    }.items():
        _read_bytes(source)
        shutil.copyfile(source, out / name)
    (out / "README.md").write_text(
        "# ABP 0.2 runtime conformance pack\n\n"
        "This pack contains synthetic recorded events and an offline policy-decision receipt. "
        "It did not execute a tool or validate a production control. It is not certification, "
        "compliance, an authorization to operate, or government endorsement.\n"
    )
    files = []
    for path in sorted(out.iterdir()):
        data = path.read_bytes()
        files.append({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    (out / "manifest.json").write_text(
        json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau-agent-runtime",
        description="Normalize and evaluate recorded agent events against ABP 0.2.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    normalizing = sub.add_parser("normalize", help="normalize one recorded framework event")
    normalizing.add_argument("adapter", choices=("generic", "mcp", "openai-agents", "langgraph", "crewai", "autogen"))
    normalizing.add_argument("event", type=Path)
    normalizing.add_argument("--out", type=Path, required=True)
    evaluating = sub.add_parser("evaluate", help="evaluate a runtime conformance suite")
    evaluating.add_argument("profile", type=Path)
    evaluating.add_argument("suite", type=Path)
    evaluating.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify", help="verify and optionally recompute a runtime receipt")
    verifying.add_argument("receipt", type=Path)
    verifying.add_argument("--profile", type=Path)
    verifying.add_argument("--suite", type=Path)
    packing = sub.add_parser("pack", help="build a portable runtime conformance pack")
    packing.add_argument("profile", type=Path)
    packing.add_argument("suite", type=Path)
    packing.add_argument("receipt", type=Path)
    packing.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "normalize":
            write_json(normalize_framework_event(args.adapter, load_json(args.event)), args.out)
            print(f"OK: normalized recorded {args.adapter} event written to {args.out}.")
            return 0
        if args.command == "evaluate":
            receipt = evaluate_suite(load_json(args.profile), load_json(args.suite))
            write_json(receipt, args.out)
            print(f"OK: {receipt['event_count']} runtime decisions written to {args.out}.")
            return 0
        if args.command == "verify":
            if bool(args.profile) != bool(args.suite):
                raise BoundaryError("provide both --profile and --suite, or neither")
            profile = load_json(args.profile) if args.profile else None
            suite = load_json(args.suite) if args.suite else None
            verify_runtime_receipt(load_json(args.receipt), profile, suite)
            print(f"OK: runtime receipt {args.receipt} verified.")
            return 0
        build_runtime_pack(args.profile, args.suite, args.receipt, args.out)
        print(f"OK: runtime pack written to {args.out}.")
        return 0
    except BoundaryError as exc:
        print(f"aau-agent-runtime: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
