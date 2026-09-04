"""Offline reference ledger for retry-safe, approval-bound agent side effects."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUITE_VERSION = "aau-agent-side-effect-suite/0.1"
RECEIPT_VERSION = "aau-agent-side-effect-receipt/0.1"
PACK_VERSION = "aau-agent-side-effect-pack/0.1"
CONFORMANCE_RECEIPT_VERSION = "aau-agent-side-effect-conformance-receipt/0.1"
ADAPTER_PROTOCOL_VERSION = "aau-agent-side-effect-adapter/0.1"
MAX_BYTES = 2_000_000
MAX_ADAPTER_BYTES = 1_000_000
ZERO_HASH = "0" * 64
TRACEPARENT = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
EVENT_KINDS = {"prepare", "approve", "commit", "reconcile", "compensate"}
OUTCOMES = {
    "prepared",
    "approved",
    "committed",
    "duplicate_replayed",
    "blocked",
    "reconcile_required",
    "reconciled_committed",
    "reconciled_absent",
    "compensated",
}
BOUNDARY_KEYS = {
    "synthetic_executor_only",
    "no_live_target",
    "no_tool_execution",
    "no_network_access",
    "not_exactly_once_claim",
    "compensation_does_not_erase_original",
    "human_approval_required",
}
CONTENT_FIELDS = {
    "prepare": {
        "tool_id",
        "operation",
        "target",
        "parameters",
        "agent_id",
        "task_id",
        "policy_epoch",
        "authority_expires_at_ms",
        "idempotency_key",
        "traceparent",
    },
    "approve": {"intent_ref", "purpose", "expires_at_ms"},
    "commit": {"intent_ref", "idempotency_key", "policy_epoch", "transport_outcome"},
    "reconcile": {"intent_ref", "idempotency_key", "observed_status"},
    "compensate": {
        "intent_ref",
        "approval_ref",
        "idempotency_key",
        "operation",
        "transport_outcome",
    },
}


class SideEffectError(ValueError):
    """Raised when an input or receipt violates the public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def load_json(source: Path) -> dict[str, Any]:
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise SideEffectError(f"invalid, oversized, or symbolic-link input: {source}")
    try:
        value = json.loads(source.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SideEffectError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise SideEffectError("expected one JSON object")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise SideEffectError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SideEffectError(f"{label} fields differ from the 0.1 contract")
    return value


def _text(value: Any, label: str, limit: int = 400) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise SideEffectError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def validate_suite(suite: dict[str, Any]) -> None:
    _exact(
        suite,
        {"suite_version", "suite_id", "title", "profile", "cases", "boundaries"},
        "suite",
    )
    if suite["suite_version"] != SUITE_VERSION:
        raise SideEffectError(f"suite_version must be {SUITE_VERSION}")
    _text(suite["suite_id"], "suite_id", 120)
    _text(suite["title"], "title", 240)
    profile = _exact(
        suite["profile"],
        {
            "agent_id",
            "task_id",
            "policy_epoch",
            "authority_expires_at_ms",
            "approval_role",
            "reconciler_role",
            "approval_ttl_ms",
            "idempotency_retention_ms",
            "tools",
        },
        "profile",
    )
    _text(profile["agent_id"], "profile.agent_id", 160)
    _text(profile["task_id"], "profile.task_id", 160)
    approval_role = _text(profile["approval_role"], "profile.approval_role", 160)
    if not approval_role.startswith("human:"):
        raise SideEffectError("profile.approval_role must name an accountable human role")
    _text(profile["reconciler_role"], "profile.reconciler_role", 160)
    for key in (
        "policy_epoch",
        "authority_expires_at_ms",
        "approval_ttl_ms",
        "idempotency_retention_ms",
    ):
        if not isinstance(profile[key], int) or profile[key] <= 0:
            raise SideEffectError(f"profile.{key} must be a positive integer")
    tools = profile["tools"]
    if not isinstance(tools, list) or not (1 <= len(tools) <= 30):
        raise SideEffectError("profile.tools must contain between 1 and 30 entries")
    tool_ids: set[str] = set()
    for index, tool in enumerate(tools):
        tool = _exact(
            tool,
            {"tool_id", "operation", "effect_class", "compensation_operation"},
            f"profile.tools[{index}]",
        )
        tool_id = _text(tool["tool_id"], f"profile.tools[{index}].tool_id", 120)
        if tool_id in tool_ids:
            raise SideEffectError(f"duplicate tool_id: {tool_id}")
        tool_ids.add(tool_id)
        _text(tool["operation"], f"profile.tools[{index}].operation", 160)
        if tool["effect_class"] not in {"reversible", "irreversible"}:
            raise SideEffectError("tool effect_class must be reversible or irreversible")
        compensation = tool["compensation_operation"]
        if compensation is not None:
            _text(compensation, f"profile.tools[{index}].compensation_operation", 160)

    boundaries = _exact(suite["boundaries"], BOUNDARY_KEYS, "boundaries")
    if any(boundaries[key] is not True for key in BOUNDARY_KEYS):
        raise SideEffectError("all side-effect safety boundaries must be true")
    cases = suite["cases"]
    if not isinstance(cases, list) or not (6 <= len(cases) <= 50):
        raise SideEffectError("cases must contain between 6 and 50 entries")
    case_ids: set[str] = set()
    event_ids: set[str] = set()
    observed_kinds: set[str] = set()
    for case_index, case in enumerate(cases):
        case = _exact(case, {"case_id", "title", "events"}, f"cases[{case_index}]")
        case_id = _text(case["case_id"], f"cases[{case_index}].case_id", 100)
        if case_id in case_ids:
            raise SideEffectError(f"duplicate case_id: {case_id}")
        case_ids.add(case_id)
        _text(case["title"], f"cases[{case_index}].title", 220)
        events = case["events"]
        if not isinstance(events, list) or not (2 <= len(events) <= 30):
            raise SideEffectError(f"cases[{case_index}].events must contain 2 to 30 entries")
        previous_at = -1
        local_ids: set[str] = set()
        for event_index, event in enumerate(events):
            label = f"cases[{case_index}].events[{event_index}]"
            event = _exact(event, {"event_id", "at_ms", "kind", "actor", "content", "expected"}, label)
            event_id = _text(event["event_id"], f"{label}.event_id", 100)
            if event_id in event_ids:
                raise SideEffectError(f"duplicate event_id: {event_id}")
            event_ids.add(event_id)
            if not isinstance(event["at_ms"], int) or event["at_ms"] <= previous_at:
                raise SideEffectError(f"{label}.at_ms must be strictly increasing")
            previous_at = event["at_ms"]
            kind = event["kind"]
            if kind not in EVENT_KINDS:
                raise SideEffectError(f"unsupported event kind: {kind}")
            observed_kinds.add(kind)
            _text(event["actor"], f"{label}.actor", 160)
            content = _exact(event["content"], CONTENT_FIELDS[kind], f"{label}.content")
            _validate_content(content, kind, local_ids, label)
            expected = _exact(event["expected"], {"outcome", "reason_codes"}, f"{label}.expected")
            if expected["outcome"] not in OUTCOMES:
                raise SideEffectError(f"unsupported expected outcome: {expected['outcome']}")
            if not isinstance(expected["reason_codes"], list):
                raise SideEffectError(f"{label}.expected.reason_codes must be a list")
            for code in expected["reason_codes"]:
                _text(code, f"{label}.expected.reason_codes", 100)
            if expected["reason_codes"] != sorted(set(expected["reason_codes"])):
                raise SideEffectError(f"{label}.expected.reason_codes must be sorted and unique")
            local_ids.add(event_id)
    if observed_kinds != EVENT_KINDS:
        raise SideEffectError(f"suite is missing event kinds: {sorted(EVENT_KINDS - observed_kinds)}")


def _validate_content(content: dict[str, Any], kind: str, local_ids: set[str], label: str) -> None:
    if kind == "prepare":
        for key in ("tool_id", "operation", "target", "agent_id", "task_id", "idempotency_key", "traceparent"):
            _text(content[key], f"{label}.content.{key}", 300)
        if not isinstance(content["parameters"], dict):
            raise SideEffectError(f"{label}.content.parameters must be an object")
        for key in ("policy_epoch", "authority_expires_at_ms"):
            if not isinstance(content[key], int):
                raise SideEffectError(f"{label}.content.{key} must be an integer")
        return
    intent_ref = _text(content["intent_ref"], f"{label}.content.intent_ref", 100)
    if intent_ref not in local_ids:
        raise SideEffectError(f"{label}.content.intent_ref must name an earlier event")
    if kind == "approve":
        if content["purpose"] not in {"primary", "compensation"}:
            raise SideEffectError(f"{label}.content.purpose is unsupported")
        if not isinstance(content["expires_at_ms"], int):
            raise SideEffectError(f"{label}.content.expires_at_ms must be an integer")
    elif kind == "commit":
        _text(content["idempotency_key"], f"{label}.content.idempotency_key", 200)
        if not isinstance(content["policy_epoch"], int):
            raise SideEffectError(f"{label}.content.policy_epoch must be an integer")
        if content["transport_outcome"] not in {"success", "timeout_unknown"}:
            raise SideEffectError(f"{label}.content.transport_outcome is unsupported")
    elif kind == "reconcile":
        _text(content["idempotency_key"], f"{label}.content.idempotency_key", 200)
        if content["observed_status"] not in {"committed", "absent"}:
            raise SideEffectError(f"{label}.content.observed_status is unsupported")
    elif kind == "compensate":
        approval_ref = _text(content["approval_ref"], f"{label}.content.approval_ref", 100)
        if approval_ref not in local_ids:
            raise SideEffectError(f"{label}.content.approval_ref must name an earlier event")
        _text(content["idempotency_key"], f"{label}.content.idempotency_key", 200)
        _text(content["operation"], f"{label}.content.operation", 160)
        if content["transport_outcome"] != "success":
            raise SideEffectError("compensation timeout is outside the 0.1 reference profile")


@dataclass
class CaseState:
    prepares: dict[str, dict[str, Any]] = field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    journal: dict[str, dict[str, Any]] = field(default_factory=dict)
    compensations: dict[str, dict[str, Any]] = field(default_factory=dict)
    known_primary_effects: int = 0
    compensation_effects: int = 0
    unresolved_effects: int = 0
    duplicate_effects_prevented: int = 0
    key_conflicts_blocked: int = 0
    unknown_retries_blocked: int = 0
    reconciliations: int = 0


def _tool_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {tool["tool_id"]: tool for tool in profile["tools"]}


def _prepare(event: dict[str, Any], profile: dict[str, Any], state: CaseState) -> tuple[str, list[str], str]:
    content = event["content"]
    reasons = []
    tool = _tool_map(profile).get(content["tool_id"])
    if tool is None or tool["operation"] != content["operation"]:
        reasons.append("TOOL_NOT_ALLOWED")
    if content["agent_id"] != profile["agent_id"]:
        reasons.append("AGENT_BINDING_MISMATCH")
    if content["task_id"] != profile["task_id"]:
        reasons.append("TASK_BINDING_MISMATCH")
    if content["policy_epoch"] != profile["policy_epoch"]:
        reasons.append("POLICY_EPOCH_MISMATCH")
    if content["authority_expires_at_ms"] != profile["authority_expires_at_ms"]:
        reasons.append("AUTHORITY_BINDING_MISMATCH")
    elif event["at_ms"] >= profile["authority_expires_at_ms"]:
        reasons.append("AUTHORITY_EXPIRED")
    traceparent = content["traceparent"]
    trace_parts = traceparent.split("-")
    if (
        not TRACEPARENT.fullmatch(traceparent)
        or set(trace_parts[1]) == {"0"}
        or set(trace_parts[2]) == {"0"}
    ):
        reasons.append("TRACE_CONTEXT_INVALID")
    intent_sha = digest(content)
    state.prepares[event["event_id"]] = {
        "content": content,
        "intent_sha256": intent_sha,
        "valid": not reasons,
    }
    return ("prepared" if not reasons else "blocked", sorted(reasons), intent_sha)


def _approve(event: dict[str, Any], profile: dict[str, Any], state: CaseState) -> tuple[str, list[str], str | None]:
    content = event["content"]
    prepared = state.prepares.get(content["intent_ref"])
    reasons = []
    if prepared is None or not prepared["valid"]:
        reasons.append("INTENT_NOT_PREPARED")
    if event["actor"] != profile["approval_role"]:
        reasons.append("APPROVER_ROLE_MISMATCH")
    if content["expires_at_ms"] <= event["at_ms"]:
        reasons.append("APPROVAL_EXPIRED")
    elif content["expires_at_ms"] - event["at_ms"] > profile["approval_ttl_ms"]:
        reasons.append("APPROVAL_TTL_EXCEEDED")
    if prepared is not None and content["purpose"] == "compensation":
        tool = _tool_map(profile).get(prepared["content"]["tool_id"])
        if tool is None or tool["compensation_operation"] is None:
            reasons.append("NO_COMPENSATION_AVAILABLE")
    state.approvals[event["event_id"]] = {
        "intent_ref": content["intent_ref"],
        "purpose": content["purpose"],
        "expires_at_ms": content["expires_at_ms"],
        "valid": not reasons,
    }
    intent_sha = None if prepared is None else prepared["intent_sha256"]
    return ("approved" if not reasons else "blocked", sorted(reasons), intent_sha)


def _current_approval(
    intent_ref: str,
    purpose: str,
    at_ms: int,
    state: CaseState,
) -> tuple[bool, bool]:
    matching = [
        approval
        for approval in state.approvals.values()
        if approval["intent_ref"] == intent_ref and approval["purpose"] == purpose and approval["valid"]
    ]
    if not matching:
        return False, False
    return any(at_ms <= approval["expires_at_ms"] for approval in matching), True


def _commit(event: dict[str, Any], profile: dict[str, Any], state: CaseState) -> tuple[str, list[str], str | None]:
    content = event["content"]
    prepared = state.prepares.get(content["intent_ref"])
    if prepared is None or not prepared["valid"]:
        return "blocked", ["INTENT_NOT_PREPARED"], None if prepared is None else prepared["intent_sha256"]
    reasons = []
    intent = prepared["content"]
    intent_sha = prepared["intent_sha256"]
    if event["actor"] != profile["agent_id"]:
        reasons.append("COMMIT_ACTOR_MISMATCH")
    if content["idempotency_key"] != intent["idempotency_key"]:
        reasons.append("IDEMPOTENCY_KEY_MISMATCH")
    if content["policy_epoch"] != profile["policy_epoch"]:
        reasons.append("POLICY_EPOCH_MISMATCH")
    if event["at_ms"] >= profile["authority_expires_at_ms"]:
        reasons.append("AUTHORITY_EXPIRED")
    approval_current, approval_seen = _current_approval(
        content["intent_ref"], "primary", event["at_ms"], state
    )
    if not approval_seen:
        reasons.append("EXACT_APPROVAL_MISSING")
    elif not approval_current:
        reasons.append("APPROVAL_EXPIRED")
    if reasons:
        return "blocked", sorted(reasons), intent_sha

    key = content["idempotency_key"]
    existing = state.journal.get(key)
    if existing is not None:
        if event["at_ms"] - existing["created_at_ms"] > profile["idempotency_retention_ms"]:
            return "blocked", ["IDEMPOTENCY_RETENTION_EXPIRED"], intent_sha
        if existing["intent_sha256"] != intent_sha:
            state.key_conflicts_blocked += 1
            return "blocked", ["IDEMPOTENCY_KEY_REUSED_FOR_DIFFERENT_INTENT"], intent_sha
        if existing["status"] == "committed":
            state.duplicate_effects_prevented += 1
            return "duplicate_replayed", ["IDEMPOTENT_RESULT_REPLAY"], intent_sha
        if existing["status"] == "unknown":
            state.unknown_retries_blocked += 1
            return "reconcile_required", ["OUTCOME_RECONCILIATION_REQUIRED"], intent_sha

    if content["transport_outcome"] == "timeout_unknown":
        state.journal[key] = {
            "intent_sha256": intent_sha,
            "status": "unknown",
            "created_at_ms": event["at_ms"],
            "effect_count": 0,
        }
        state.unresolved_effects += 1
        return "reconcile_required", ["TRANSPORT_OUTCOME_UNKNOWN"], intent_sha
    state.journal[key] = {
        "intent_sha256": intent_sha,
        "status": "committed",
        "created_at_ms": event["at_ms"],
        "effect_count": 1,
    }
    state.known_primary_effects += 1
    return "committed", [], intent_sha


def _reconcile(event: dict[str, Any], profile: dict[str, Any], state: CaseState) -> tuple[str, list[str], str | None]:
    content = event["content"]
    prepared = state.prepares.get(content["intent_ref"])
    intent_sha = None if prepared is None else prepared["intent_sha256"]
    reasons = []
    if event["actor"] != profile["reconciler_role"]:
        reasons.append("RECONCILER_ROLE_MISMATCH")
    entry = state.journal.get(content["idempotency_key"])
    if prepared is None or entry is None or entry["status"] != "unknown":
        reasons.append("NO_UNKNOWN_OUTCOME")
    elif entry["intent_sha256"] != intent_sha:
        reasons.append("INTENT_BINDING_MISMATCH")
    if reasons:
        return "blocked", sorted(reasons), intent_sha
    state.unresolved_effects -= 1
    state.reconciliations += 1
    if content["observed_status"] == "committed":
        entry["status"] = "committed"
        entry["effect_count"] = 1
        state.known_primary_effects += 1
        return "reconciled_committed", [], intent_sha
    entry["status"] = "absent"
    return "reconciled_absent", [], intent_sha


def _compensate(event: dict[str, Any], profile: dict[str, Any], state: CaseState) -> tuple[str, list[str], str | None]:
    content = event["content"]
    prepared = state.prepares.get(content["intent_ref"])
    if prepared is None or not prepared["valid"]:
        return "blocked", ["INTENT_NOT_PREPARED"], None if prepared is None else prepared["intent_sha256"]
    intent_sha = prepared["intent_sha256"]
    intent = prepared["content"]
    tool = _tool_map(profile)[intent["tool_id"]]
    reasons = []
    if event["actor"] != profile["agent_id"]:
        reasons.append("COMPENSATION_ACTOR_MISMATCH")
    primary = state.journal.get(intent["idempotency_key"])
    if primary is None or primary["status"] != "committed":
        reasons.append("PRIMARY_EFFECT_NOT_COMMITTED")
    if tool["compensation_operation"] is None:
        reasons.append("NO_COMPENSATION_AVAILABLE")
    elif content["operation"] != tool["compensation_operation"]:
        reasons.append("COMPENSATION_OPERATION_MISMATCH")
    approval = state.approvals.get(content["approval_ref"])
    if (
        approval is None
        or not approval["valid"]
        or approval["purpose"] != "compensation"
        or approval["intent_ref"] != content["intent_ref"]
    ):
        reasons.append("COMPENSATION_APPROVAL_MISSING")
    elif event["at_ms"] > approval["expires_at_ms"]:
        reasons.append("APPROVAL_EXPIRED")
    if reasons:
        return "blocked", sorted(reasons), intent_sha
    compensation_sha = digest(
        {"primary_intent_sha256": intent_sha, "operation": content["operation"]}
    )
    key = content["idempotency_key"]
    existing = state.compensations.get(key)
    if existing is not None:
        if existing["compensation_sha256"] != compensation_sha:
            state.key_conflicts_blocked += 1
            return "blocked", ["IDEMPOTENCY_KEY_REUSED_FOR_DIFFERENT_INTENT"], intent_sha
        state.duplicate_effects_prevented += 1
        return "duplicate_replayed", ["IDEMPOTENT_RESULT_REPLAY"], intent_sha
    state.compensations[key] = {"compensation_sha256": compensation_sha, "effect_count": 1}
    state.compensation_effects += 1
    return "compensated", [], intent_sha


def _run_event(event: dict[str, Any], profile: dict[str, Any], state: CaseState) -> tuple[str, list[str], str | None]:
    handlers = {
        "prepare": _prepare,
        "approve": _approve,
        "commit": _commit,
        "reconcile": _reconcile,
        "compensate": _compensate,
    }
    return handlers[event["kind"]](event, profile, state)


def evaluate_case(profile: dict[str, Any], case: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate one already-validated synthetic case without retaining its oracle."""
    state = CaseState()
    results = []
    for event in case["events"]:
        outcome, reason_codes, _intent_sha = _run_event(event, profile, state)
        results.append(
            {
                "event_id": event["event_id"],
                "outcome": outcome,
                "reason_codes": reason_codes,
            }
        )
    return results


def adapter_request(suite: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Build the complete adapter request while deliberately excluding expected answers."""
    return {
        "protocol_version": ADAPTER_PROTOCOL_VERSION,
        "suite_id": suite["suite_id"],
        "profile": suite["profile"],
        "case": {
            "case_id": case["case_id"],
            "title": case["title"],
            "events": [
                {key: value for key, value in event.items() if key != "expected"}
                for event in case["events"]
            ],
        },
    }


def _command_adapter(command: str, timeout: float):
    argv = shlex.split(command)
    if not argv:
        raise SideEffectError("adapter command is empty")
    if not 0 < timeout <= 300:
        raise SideEffectError("adapter timeout must be greater than 0 and at most 300 seconds")

    def invoke(request: dict[str, Any]) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                argv,
                input=canonical(request),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SideEffectError(f"adapter execution failed: {exc}") from exc
        if completed.returncode != 0:
            raise SideEffectError(f"adapter exited with status {completed.returncode}")
        if len(completed.stdout) > MAX_ADAPTER_BYTES:
            raise SideEffectError(f"adapter response exceeds {MAX_ADAPTER_BYTES} bytes")
        try:
            response = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SideEffectError("adapter returned invalid JSON") from exc
        return _validate_adapter_response(response, request["case"])

    return invoke


def _validate_adapter_response(response: Any, case: dict[str, Any]) -> dict[str, Any]:
    response = _exact(response, {"case_id", "results"}, "adapter response")
    if response["case_id"] != case["case_id"]:
        raise SideEffectError("adapter response case_id does not match the request")
    results = response["results"]
    if not isinstance(results, list) or len(results) != len(case["events"]):
        raise SideEffectError("adapter response must cover every event exactly once")
    expected_ids = [event["event_id"] for event in case["events"]]
    observed_ids = []
    for index, result in enumerate(results):
        result = _exact(
            result,
            {"event_id", "outcome", "reason_codes"},
            f"adapter response.results[{index}]",
        )
        observed_ids.append(_text(result["event_id"], "adapter result event_id", 100))
        if result["outcome"] not in OUTCOMES:
            raise SideEffectError("adapter result outcome is unsupported")
        reasons = result["reason_codes"]
        if not isinstance(reasons, list):
            raise SideEffectError("adapter result reason_codes must be a list")
        for reason in reasons:
            _text(reason, "adapter result reason code", 100)
        if reasons != sorted(set(reasons)):
            raise SideEffectError("adapter result reason_codes must be sorted and unique")
    if observed_ids != expected_ids:
        raise SideEffectError("adapter response event order or coverage differs from the request")
    return response


def run_conformance(suite: dict[str, Any], command: str, timeout: float = 10.0) -> dict[str, Any]:
    """Run oracle-free synthetic case sequences through a trusted local command adapter."""
    validate_suite(suite)
    invoke = _command_adapter(command, timeout)
    previous = ZERO_HASH
    case_rows = []
    event_count = 0
    exact_outcome_count = 0
    exact_reason_count = 0
    unsafe_effect_outcome_count = 0
    unknown_retry_violation_count = 0
    legitimate_effect_block_count = 0
    effect_outcomes = {"committed", "reconciled_committed", "compensated"}
    for case in suite["cases"]:
        request = adapter_request(suite, case)
        response = invoke(request)
        rows = []
        for event, actual in zip(case["events"], response["results"], strict=True):
            expected = event["expected"]
            outcome_exact = actual["outcome"] == expected["outcome"]
            reasons_exact = actual["reason_codes"] == expected["reason_codes"]
            event_count += 1
            exact_outcome_count += int(outcome_exact)
            exact_reason_count += int(reasons_exact)
            unsafe_effect_outcome_count += int(
                actual["outcome"] in effect_outcomes and expected["outcome"] not in effect_outcomes
            )
            unknown_retry_violation_count += int(
                expected["outcome"] == "reconcile_required"
                and actual["outcome"] in effect_outcomes
            )
            legitimate_effect_block_count += int(
                expected["outcome"] in effect_outcomes
                and actual["outcome"] in {"blocked", "reconcile_required"}
            )
            row = {
                "event_id": event["event_id"],
                "actual_outcome": actual["outcome"],
                "actual_reason_codes": actual["reason_codes"],
                "outcome_exact": outcome_exact,
                "reasons_exact": reasons_exact,
                "previous_result_sha256": previous,
            }
            row["result_sha256"] = digest(row)
            previous = row["result_sha256"]
            rows.append(row)
        case_rows.append({"case_id": case["case_id"], "results": rows})
    summary = {
        "case_count": len(case_rows),
        "event_count": event_count,
        "exact_outcome_count": exact_outcome_count,
        "exact_reason_count": exact_reason_count,
        "exact_outcome_rate": round(exact_outcome_count / event_count, 6),
        "exact_reason_rate": round(exact_reason_count / event_count, 6),
        "unsafe_effect_outcome_count": unsafe_effect_outcome_count,
        "unknown_retry_violation_count": unknown_retry_violation_count,
        "legitimate_effect_block_count": legitimate_effect_block_count,
    }
    receipt = {
        "receipt_version": CONFORMANCE_RECEIPT_VERSION,
        "adapter_protocol_version": ADAPTER_PROTOCOL_VERSION,
        "suite_id": suite["suite_id"],
        "suite_sha256": digest(suite),
        "adapter_kind": "command",
        "status": (
            "evidence_passed"
            if exact_outcome_count == event_count and exact_reason_count == event_count
            else "evidence_failed"
        ),
        "summary": summary,
        "cases": case_rows,
        "final_result_sha256": previous,
        "claim_boundary": {
            "oracle_withheld_from_adapter": True,
            "synthetic_case_data_only": True,
            "runner_does_not_invoke_declared_tools": True,
            "trusted_adapter_command_executes_locally": True,
            "adapter_behavior_not_target_system_evidence": True,
            "passing_not_production_safety_or_certification": True,
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_conformance_receipt(receipt: dict[str, Any], suite: dict[str, Any]) -> None:
    validate_suite(suite)
    receipt = _exact(
        receipt,
        {
            "receipt_version",
            "adapter_protocol_version",
            "suite_id",
            "suite_sha256",
            "adapter_kind",
            "status",
            "summary",
            "cases",
            "final_result_sha256",
            "claim_boundary",
            "receipt_sha256",
        },
        "conformance receipt",
    )
    if receipt["receipt_version"] != CONFORMANCE_RECEIPT_VERSION:
        raise SideEffectError("unsupported conformance receipt_version")
    if receipt["adapter_protocol_version"] != ADAPTER_PROTOCOL_VERSION:
        raise SideEffectError("unsupported adapter_protocol_version")
    if receipt["adapter_kind"] != "command":
        raise SideEffectError("conformance adapter_kind must be command")
    unsigned = dict(receipt)
    supplied = unsigned.pop("receipt_sha256", None)
    if supplied != digest(unsigned):
        raise SideEffectError("conformance receipt digest mismatch")
    if receipt.get("suite_id") != suite["suite_id"] or receipt.get("suite_sha256") != digest(suite):
        raise SideEffectError("conformance receipt suite binding mismatch")
    case_map = {case["case_id"]: case for case in suite["cases"]}
    if [row.get("case_id") for row in receipt.get("cases", [])] != list(case_map):
        raise SideEffectError("conformance receipt case coverage or order is invalid")
    previous = ZERO_HASH
    outcome_exact = 0
    reason_exact = 0
    unsafe = 0
    unknown_retry = 0
    legitimate_block = 0
    event_count = 0
    effect_outcomes = {"committed", "reconciled_committed", "compensated"}
    for case_row in receipt["cases"]:
        case_row = _exact(case_row, {"case_id", "results"}, "conformance case result")
        source_events = case_map[case_row["case_id"]]["events"]
        results = case_row.get("results")
        if not isinstance(results, list) or len(results) != len(source_events):
            raise SideEffectError("conformance receipt event coverage is invalid")
        for source, row in zip(source_events, results, strict=True):
            row = _exact(
                row,
                {
                    "event_id",
                    "actual_outcome",
                    "actual_reason_codes",
                    "outcome_exact",
                    "reasons_exact",
                    "previous_result_sha256",
                    "result_sha256",
                },
                "conformance result",
            )
            if row.get("event_id") != source["event_id"]:
                raise SideEffectError("conformance receipt event order is invalid")
            if row["actual_outcome"] not in OUTCOMES:
                raise SideEffectError("conformance receipt outcome is invalid")
            reasons = row["actual_reason_codes"]
            if not isinstance(reasons, list):
                raise SideEffectError("conformance receipt reason codes are invalid")
            for reason in reasons:
                _text(reason, "conformance receipt reason code", 100)
            if reasons != sorted(set(reasons)):
                raise SideEffectError("conformance receipt reason codes are invalid")
            if row.get("previous_result_sha256") != previous:
                raise SideEffectError("conformance receipt result chain is broken")
            unsigned_row = dict(row)
            row_hash = unsigned_row.pop("result_sha256", None)
            if row_hash != digest(unsigned_row):
                raise SideEffectError("conformance receipt result digest mismatch")
            previous = row_hash
            expected = source["expected"]
            expected_outcome_exact = row.get("actual_outcome") == expected["outcome"]
            expected_reasons_exact = row.get("actual_reason_codes") == expected["reason_codes"]
            if row.get("outcome_exact") is not expected_outcome_exact:
                raise SideEffectError("conformance outcome exactness does not recompute")
            if row.get("reasons_exact") is not expected_reasons_exact:
                raise SideEffectError("conformance reason exactness does not recompute")
            event_count += 1
            outcome_exact += int(expected_outcome_exact)
            reason_exact += int(expected_reasons_exact)
            unsafe += int(
                row["actual_outcome"] in effect_outcomes
                and expected["outcome"] not in effect_outcomes
            )
            unknown_retry += int(
                expected["outcome"] == "reconcile_required"
                and row["actual_outcome"] in effect_outcomes
            )
            legitimate_block += int(
                expected["outcome"] in effect_outcomes
                and row["actual_outcome"] in {"blocked", "reconcile_required"}
            )
    expected_summary = {
        "case_count": len(case_map),
        "event_count": event_count,
        "exact_outcome_count": outcome_exact,
        "exact_reason_count": reason_exact,
        "exact_outcome_rate": round(outcome_exact / event_count, 6),
        "exact_reason_rate": round(reason_exact / event_count, 6),
        "unsafe_effect_outcome_count": unsafe,
        "unknown_retry_violation_count": unknown_retry,
        "legitimate_effect_block_count": legitimate_block,
    }
    if receipt["summary"] != expected_summary:
        raise SideEffectError("conformance receipt summary does not recompute")
    expected_status = (
        "evidence_passed"
        if outcome_exact == event_count and reason_exact == event_count
        else "evidence_failed"
    )
    if receipt["status"] != expected_status:
        raise SideEffectError("conformance receipt status does not recompute")
    if receipt["final_result_sha256"] != previous:
        raise SideEffectError("conformance receipt final digest mismatch")
    expected_boundary = {
        "oracle_withheld_from_adapter": True,
        "synthetic_case_data_only": True,
        "runner_does_not_invoke_declared_tools": True,
        "trusted_adapter_command_executes_locally": True,
        "adapter_behavior_not_target_system_evidence": True,
        "passing_not_production_safety_or_certification": True,
    }
    if receipt["claim_boundary"] != expected_boundary:
        raise SideEffectError("conformance receipt claim boundary is invalid")


def evaluate_suite(suite: dict[str, Any]) -> dict[str, Any]:
    validate_suite(suite)
    profile = suite["profile"]
    previous = ZERO_HASH
    case_rows = []
    counters = {
        "event_count": 0,
        "exact_outcome_count": 0,
        "exact_reason_count": 0,
        "known_primary_effect_count": 0,
        "compensation_effect_count": 0,
        "unresolved_effect_count": 0,
        "duplicate_effects_prevented": 0,
        "key_conflicts_blocked": 0,
        "unknown_retries_blocked": 0,
        "reconciliation_count": 0,
        "at_most_one_breach_count": 0,
    }
    for case in suite["cases"]:
        state = CaseState()
        events = []
        for event in case["events"]:
            outcome, reason_codes, intent_sha = _run_event(event, profile, state)
            outcome_exact = outcome == event["expected"]["outcome"]
            reasons_exact = reason_codes == event["expected"]["reason_codes"]
            counters["event_count"] += 1
            counters["exact_outcome_count"] += int(outcome_exact)
            counters["exact_reason_count"] += int(reasons_exact)
            row = {
                "event_id": event["event_id"],
                "kind": event["kind"],
                "at_ms": event["at_ms"],
                "outcome": outcome,
                "reason_codes": reason_codes,
                "intent_sha256": intent_sha,
                "outcome_exact": outcome_exact,
                "reasons_exact": reasons_exact,
                "known_primary_effect_count": state.known_primary_effects,
                "compensation_effect_count": state.compensation_effects,
                "unresolved_effect_count": state.unresolved_effects,
                "previous_result_sha256": previous,
            }
            row["result_sha256"] = digest(row)
            previous = row["result_sha256"]
            events.append(row)
        counters["known_primary_effect_count"] += state.known_primary_effects
        counters["compensation_effect_count"] += state.compensation_effects
        counters["unresolved_effect_count"] += state.unresolved_effects
        counters["duplicate_effects_prevented"] += state.duplicate_effects_prevented
        counters["key_conflicts_blocked"] += state.key_conflicts_blocked
        counters["unknown_retries_blocked"] += state.unknown_retries_blocked
        counters["reconciliation_count"] += state.reconciliations
        counters["at_most_one_breach_count"] += sum(
            entry["effect_count"] > 1 for entry in state.journal.values()
        )
        counters["at_most_one_breach_count"] += sum(
            entry["effect_count"] > 1 for entry in state.compensations.values()
        )
        case_rows.append({"case_id": case["case_id"], "events": events})
    total = counters["event_count"]
    summary = {
        "case_count": len(case_rows),
        **counters,
        "exact_outcome_rate": round(counters["exact_outcome_count"] / total, 6),
        "exact_reason_rate": round(counters["exact_reason_count"] / total, 6),
    }
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "suite_id": suite["suite_id"],
        "suite_sha256": digest(suite),
        "summary": summary,
        "cases": case_rows,
        "final_result_sha256": previous,
        "claim_boundary": {
            "simulated_ledger": True,
            "no_external_side_effect": True,
            "at_most_one_is_adapter_scoped": True,
            "trace_context_is_not_authorization": True,
            "compensation_is_a_new_effect": True,
            "not_production_evidence": True,
            "not_certification": True,
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_receipt(receipt: dict[str, Any], suite: dict[str, Any] | None = None) -> None:
    if receipt.get("receipt_version") != RECEIPT_VERSION:
        raise SideEffectError("unsupported receipt_version")
    unsigned = dict(receipt)
    supplied = unsigned.pop("receipt_sha256", None)
    if supplied != digest(unsigned):
        raise SideEffectError("receipt digest mismatch")
    previous = ZERO_HASH
    for case in receipt.get("cases", []):
        for row in case.get("events", []):
            if row.get("previous_result_sha256") != previous:
                raise SideEffectError("receipt result chain is broken")
            unsigned_row = dict(row)
            row_hash = unsigned_row.pop("result_sha256", None)
            if row_hash != digest(unsigned_row):
                raise SideEffectError("receipt result digest mismatch")
            previous = row_hash
    if receipt.get("final_result_sha256") != previous:
        raise SideEffectError("receipt final digest mismatch")
    if suite is not None and receipt != evaluate_suite(suite):
        raise SideEffectError("receipt does not recompute from the supplied suite")


def build_pack(suite_path: Path, receipt_path: Path, out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise SideEffectError(f"refusing to overwrite: {out}")
    suite = load_json(suite_path)
    receipt = load_json(receipt_path)
    validate_suite(suite)
    verify_receipt(receipt, suite)
    out.mkdir(parents=True)
    shutil.copyfile(suite_path, out / "suite.json")
    shutil.copyfile(receipt_path, out / "receipt.json")
    readme = (
        "# Agent Side-Effect Ledger evidence pack\n\n"
        "Verify with `python3 aau_side_effect.py verify receipt.json --suite suite.json`.\n\n"
        "This is a synthetic, adapter-scoped state-machine result. It is not proof of exactly-once "
        "delivery, a production side effect, authorization, safety, certification, or an ATO.\n"
    )
    (out / "README.md").write_text(readme)
    files = []
    for path in sorted(out.iterdir(), key=lambda item: item.name):
        files.append({"path": path.name, "sha256": digest(path.read_bytes()), "size_bytes": path.stat().st_size})
    manifest = {"pack_version": PACK_VERSION, "files": files}
    manifest["manifest_sha256"] = digest(manifest)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate", help="evaluate a synthetic side-effect suite")
    evaluate.add_argument("suite", type=Path)
    evaluate.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="verify a receipt and optionally recompute it")
    verify.add_argument("receipt", type=Path)
    verify.add_argument("--suite", type=Path)
    conformance = sub.add_parser(
        "run-conformance", help="run oracle-free synthetic sequences through a command adapter"
    )
    conformance.add_argument("suite", type=Path)
    conformance.add_argument("--command", dest="adapter_command", required=True)
    conformance.add_argument("--timeout", type=float, default=10.0)
    conformance.add_argument("--out", type=Path, required=True)
    verify_conformance = sub.add_parser(
        "verify-conformance", help="verify a command-adapter conformance receipt"
    )
    verify_conformance.add_argument("receipt", type=Path)
    verify_conformance.add_argument("--suite", type=Path, required=True)
    pack = sub.add_parser("pack", help="build a non-overwriting portable evidence pack")
    pack.add_argument("suite", type=Path)
    pack.add_argument("receipt", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            receipt = evaluate_suite(load_json(args.suite))
            write_json(receipt, args.out)
            print(
                f"wrote {args.out}: {receipt['summary']['event_count']} events, "
                f"{receipt['summary']['duplicate_effects_prevented']} duplicate effects prevented"
            )
        elif args.command == "verify":
            suite = load_json(args.suite) if args.suite else None
            receipt = load_json(args.receipt)
            verify_receipt(receipt, suite)
            print(
                f"verified {args.receipt}: {receipt['summary']['case_count']} cases, "
                f"{receipt['summary']['at_most_one_breach_count']} at-most-one breaches"
            )
        elif args.command == "run-conformance":
            receipt = run_conformance(
                load_json(args.suite), args.adapter_command, timeout=args.timeout
            )
            write_json(receipt, args.out)
            print(
                f"wrote {args.out}: {receipt['summary']['event_count']} events, "
                f"{receipt['summary']['unsafe_effect_outcome_count']} unsafe effect outcomes"
            )
        elif args.command == "verify-conformance":
            receipt = load_json(args.receipt)
            suite = load_json(args.suite)
            verify_conformance_receipt(receipt, suite)
            print(
                f"verified {args.receipt}: {receipt['summary']['event_count']} events, "
                f"status {receipt['status']}"
            )
        else:
            build_pack(args.suite, args.receipt, args.out)
            print(f"wrote {args.out}")
    except (OSError, SideEffectError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
