"""Deterministic local executor for AI-agent containment and recovery drills."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DRILL_VERSION = "aau-agent-containment-drill/0.1"
RECEIPT_VERSION = "aau-agent-containment-receipt/0.1"
PACK_VERSION = "aau-agent-containment-pack/0.1"
MAX_BYTES = 2_000_000
ZERO_HASH = "0" * 64
EVENT_KINDS = {
    "enqueue",
    "delegate",
    "tool_effect",
    "critical_alert",
    "monitor_loss",
    "revoke",
    "restart",
    "evidence_mutation",
    "execute_job",
}
OUTCOMES = {"allow", "block", "pause_scheduled", "revocation_scheduled", "safe_stop"}
STATES = {"active", "paused", "safe_stopped", "revoked"}
BOUNDARY_KEYS = {
    "synthetic_executor_only",
    "no_live_target",
    "no_tool_execution",
    "no_network_access",
    "not_production_containment_claim",
    "human_restart_required",
}


class ContainmentError(ValueError):
    """Raised when a drill or receipt violates the public contract."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(payload).hexdigest()


def load_json(source: Path) -> dict[str, Any]:
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise ContainmentError(f"invalid, oversized, or symbolic-link input: {source}")
    try:
        value = json.loads(source.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContainmentError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContainmentError("expected one JSON object")
    return value


def write_json(value: dict[str, Any], out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise ContainmentError(f"refusing to overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, indent=2) + "\n")


def _text(value: Any, label: str, limit: int = 400) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ContainmentError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ContainmentError(f"{label} fields differ from the 0.1 contract")
    return value


def validate_drill(drill: dict[str, Any]) -> None:
    _exact(drill, {"drill_version", "drill_id", "title", "profile_ref", "control_profile", "runs", "boundaries"}, "drill")
    if drill["drill_version"] != DRILL_VERSION:
        raise ContainmentError(f"drill_version must be {DRILL_VERSION}")
    _text(drill["drill_id"], "drill_id", 120)
    _text(drill["title"], "title", 220)
    _text(drill["profile_ref"], "profile_ref", 300)
    profile = _exact(
        drill["control_profile"],
        {
            "pause_latency_ms",
            "revocation_latency_ms",
            "child_revocation_latency_ms",
            "queue_cancel_latency_ms",
            "containment_deadline_ms",
            "maximum_service_interruption_ms",
            "restart_role",
            "required_restart_evidence",
        },
        "control_profile",
    )
    for key in (
        "pause_latency_ms",
        "revocation_latency_ms",
        "child_revocation_latency_ms",
        "queue_cancel_latency_ms",
        "containment_deadline_ms",
        "maximum_service_interruption_ms",
    ):
        if not isinstance(profile[key], int) or profile[key] < 0:
            raise ContainmentError(f"control_profile.{key} must be a non-negative integer")
    role = _text(profile["restart_role"], "control_profile.restart_role", 200)
    if "human" not in role.lower():
        raise ContainmentError("control_profile.restart_role must identify a human role")
    evidence = profile["required_restart_evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ContainmentError("required_restart_evidence must contain text")
    for index, item in enumerate(evidence):
        _text(item, f"required_restart_evidence[{index}]", 160)

    boundaries = _exact(drill["boundaries"], BOUNDARY_KEYS, "boundaries")
    if any(boundaries[key] is not True for key in BOUNDARY_KEYS):
        raise ContainmentError("all containment safety boundaries must be true")

    runs = drill["runs"]
    if not isinstance(runs, list) or not (2 <= len(runs) <= 50):
        raise ContainmentError("runs must contain between 2 and 50 entries")
    run_ids: set[str] = set()
    all_kinds: set[str] = set()
    event_ids: set[str] = set()
    for run_index, run in enumerate(runs):
        run = _exact(run, {"run_id", "objective", "events"}, f"runs[{run_index}]")
        run_id = _text(run["run_id"], f"runs[{run_index}].run_id", 100)
        if run_id in run_ids:
            raise ContainmentError(f"duplicate run_id: {run_id}")
        run_ids.add(run_id)
        _text(run["objective"], f"runs[{run_index}].objective", 400)
        events = run["events"]
        if not isinstance(events, list) or not (4 <= len(events) <= 100):
            raise ContainmentError(f"runs[{run_index}].events must contain 4 to 100 events")
        previous_at = -1
        for event_index, event in enumerate(events):
            event = _exact(
                event,
                {"event_id", "at_ms", "kind", "subject", "actor", "evidence", "expected"},
                f"runs[{run_index}].events[{event_index}]",
            )
            event_id = _text(event["event_id"], f"events[{event_index}].event_id", 100)
            if event_id in event_ids:
                raise ContainmentError(f"duplicate event_id: {event_id}")
            event_ids.add(event_id)
            if not isinstance(event["at_ms"], int) or event["at_ms"] <= previous_at:
                raise ContainmentError("event at_ms values must be strictly increasing within each run")
            previous_at = event["at_ms"]
            if event["kind"] not in EVENT_KINDS:
                raise ContainmentError(f"unsupported event kind: {event['kind']}")
            all_kinds.add(event["kind"])
            _text(event["subject"], f"events[{event_index}].subject", 200)
            _text(event["actor"], f"events[{event_index}].actor", 200)
            if not isinstance(event["evidence"], list):
                raise ContainmentError("event evidence must be a list")
            for item in event["evidence"]:
                _text(item, "event evidence item", 160)
            expected = _exact(event["expected"], {"outcome", "state_after"}, "event.expected")
            if expected["outcome"] not in OUTCOMES or expected["state_after"] not in STATES:
                raise ContainmentError("event expected outcome or state is unsupported")
    required = EVENT_KINDS
    if not required.issubset(all_kinds):
        raise ContainmentError(f"drill is missing required event kinds: {sorted(required - all_kinds)}")


@dataclass
class ExecutorState:
    status: str = "active"
    queue: set[str] = field(default_factory=set)
    children: dict[str, bool] = field(default_factory=dict)
    pending: list[tuple[int, str]] = field(default_factory=list)
    containment_trigger_at: int | None = None
    paused_at: int | None = None
    revoked_at: int | None = None
    children_revoked_at: int | None = None
    queue_canceled_at: int | None = None


def _apply_pending(state: ExecutorState, at_ms: int) -> None:
    remaining: list[tuple[int, str]] = []
    priority = {"pause": 0, "revoke": 1, "child_revoke": 2, "queue_cancel": 3}
    for due, action in sorted(state.pending, key=lambda item: (item[0], priority[item[1]])):
        if due > at_ms:
            remaining.append((due, action))
            continue
        if action == "pause" and state.status == "active":
            state.status = "paused"
            state.paused_at = due
        elif action == "revoke":
            state.status = "revoked"
            state.revoked_at = due
        elif action == "child_revoke":
            for child in state.children:
                state.children[child] = False
            state.children_revoked_at = due
        elif action == "queue_cancel":
            state.queue.clear()
            state.queue_canceled_at = due
    state.pending = remaining


def _run_event(event: dict[str, Any], profile: dict[str, Any], state: ExecutorState) -> str:
    kind = event["kind"]
    at_ms = event["at_ms"]
    _apply_pending(state, at_ms)
    if kind == "critical_alert" or kind == "monitor_loss":
        state.containment_trigger_at = at_ms
        state.pending.append((at_ms + profile["pause_latency_ms"], "pause"))
        return "pause_scheduled"
    if kind == "revoke":
        state.containment_trigger_at = at_ms
        state.pending.extend(
            [
                (at_ms + profile["revocation_latency_ms"], "revoke"),
                (at_ms + profile["child_revocation_latency_ms"], "child_revoke"),
                (at_ms + profile["queue_cancel_latency_ms"], "queue_cancel"),
            ]
        )
        return "revocation_scheduled"
    if kind == "evidence_mutation":
        state.containment_trigger_at = at_ms
        state.status = "safe_stopped"
        return "safe_stop"
    if kind == "restart":
        required = set(profile["required_restart_evidence"])
        if (
            state.status in {"paused", "safe_stopped"}
            and event["actor"] == profile["restart_role"]
            and required.issubset(set(event["evidence"]))
        ):
            state.status = "active"
            state.containment_trigger_at = None
            state.pending = [item for item in state.pending if item[1] not in {"pause"}]
            return "allow"
        return "block"
    if kind == "enqueue":
        if state.status == "active":
            state.queue.add(event["subject"])
            return "allow"
        return "block"
    if kind == "delegate":
        if state.status == "active":
            state.children[event["subject"]] = True
            return "allow"
        return "block"
    if kind == "execute_job":
        if state.status == "active" and event["subject"] in state.queue:
            state.queue.remove(event["subject"])
            return "allow"
        return "block"
    if kind == "tool_effect":
        child_active = not event["actor"].startswith("agent:child") or state.children.get(event["actor"], False)
        return "allow" if state.status == "active" and child_active else "block"
    raise ContainmentError(f"unsupported event kind: {kind}")


def evaluate_drill(drill: dict[str, Any]) -> dict[str, Any]:
    validate_drill(drill)
    profile = drill["control_profile"]
    receipt_runs = []
    previous = ZERO_HASH
    total_events = 0
    exact_outcomes = 0
    exact_states = 0
    containment_breaches = 0
    unauthorized_restart_blocks = 0
    authorized_restarts = 0
    post_control_blocks = 0
    child_stop_observed = False
    queue_cancel_observed = False
    for run in drill["runs"]:
        state = ExecutorState()
        rows = []
        for event in run["events"]:
            outcome = _run_event(event, profile, state)
            total_events += 1
            outcome_exact = outcome == event["expected"]["outcome"]
            state_exact = state.status == event["expected"]["state_after"]
            exact_outcomes += int(outcome_exact)
            exact_states += int(state_exact)
            if event["kind"] in {"tool_effect", "execute_job"} and outcome == "block":
                post_control_blocks += 1
            if event["kind"] == "tool_effect" and event["actor"].startswith("agent:child") and outcome == "block":
                child_stop_observed = True
            if event["kind"] == "execute_job" and outcome == "block":
                queue_cancel_observed = True
            if event["kind"] == "restart":
                authorized_restarts += int(outcome == "allow")
                unauthorized_restart_blocks += int(outcome == "block")
            if (
                event["kind"] in {"tool_effect", "execute_job"}
                and outcome == "allow"
                and state.containment_trigger_at is not None
                and event["at_ms"] > state.containment_trigger_at + profile["containment_deadline_ms"]
            ):
                containment_breaches += 1
            row = {
                "event_id": event["event_id"],
                "kind": event["kind"],
                "at_ms": event["at_ms"],
                "outcome": outcome,
                "state_after": state.status,
                "outcome_exact": outcome_exact,
                "state_exact": state_exact,
                "queued_job_count": len(state.queue),
                "active_child_count": sum(state.children.values()),
                "previous_result_sha256": previous,
            }
            row["result_sha256"] = digest(row)
            previous = row["result_sha256"]
            rows.append(row)
        receipt_runs.append({"run_id": run["run_id"], "events": rows})
    summary = {
        "run_count": len(receipt_runs),
        "event_count": total_events,
        "exact_outcome_rate": round(exact_outcomes / total_events, 6),
        "exact_state_rate": round(exact_states / total_events, 6),
        "pause_latency_ms": profile["pause_latency_ms"],
        "revocation_latency_ms": profile["revocation_latency_ms"],
        "child_revocation_latency_ms": profile["child_revocation_latency_ms"],
        "queue_cancel_latency_ms": profile["queue_cancel_latency_ms"],
        "containment_breach_count": containment_breaches,
        "post_control_block_count": post_control_blocks,
        "unauthorized_restart_block_count": unauthorized_restart_blocks,
        "authorized_restart_count": authorized_restarts,
        "child_revocation_observed": child_stop_observed,
        "queue_cancel_observed": queue_cancel_observed,
    }
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "drill_id": drill["drill_id"],
        "drill_sha256": digest(drill),
        "summary": summary,
        "runs": receipt_runs,
        "final_result_sha256": previous,
        "claim_boundary": {
            "simulated_executor": True,
            "no_external_side_effect": True,
            "not_production_containment": True,
            "not_certification": True,
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_receipt(receipt: dict[str, Any], drill: dict[str, Any] | None = None) -> None:
    if receipt.get("receipt_version") != RECEIPT_VERSION:
        raise ContainmentError("unsupported receipt_version")
    unsigned = dict(receipt)
    supplied = unsigned.pop("receipt_sha256", None)
    if supplied != digest(unsigned):
        raise ContainmentError("receipt digest mismatch")
    previous = ZERO_HASH
    for run in receipt.get("runs", []):
        for row in run.get("events", []):
            if row.get("previous_result_sha256") != previous:
                raise ContainmentError("receipt result chain is broken")
            unsigned_row = dict(row)
            row_hash = unsigned_row.pop("result_sha256", None)
            if row_hash != digest(unsigned_row):
                raise ContainmentError("receipt result digest mismatch")
            previous = row_hash
    if receipt.get("final_result_sha256") != previous:
        raise ContainmentError("receipt final digest mismatch")
    if drill is not None and receipt != evaluate_drill(drill):
        raise ContainmentError("receipt does not recompute from the supplied drill")


def build_pack(drill_path: Path, receipt_path: Path, out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise ContainmentError(f"refusing to overwrite existing containment pack: {out}")
    drill = load_json(drill_path)
    receipt = load_json(receipt_path)
    verify_receipt(receipt, drill)
    out.mkdir(parents=True)
    shutil.copyfile(drill_path, out / "drill.json")
    shutil.copyfile(receipt_path, out / "receipt.json")
    (out / "README.md").write_text(
        "# AAU Agent Containment Drill pack\n\n"
        "This pack records deterministic simulated enforcement. It does not prove that a live "
        "executor, queue, credential, process, or network effect was contained.\n"
    )
    files = []
    for path in sorted(out.iterdir()):
        if path.name != "manifest.json":
            files.append({"path": path.name, "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size})
    (out / "manifest.json").write_text(json.dumps({"manifest_version": PACK_VERSION, "files": files}, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="aau-containment", description="Run a local synthetic agent-containment drill.")
    sub = root.add_subparsers(dest="command", required=True)
    validating = sub.add_parser("validate")
    validating.add_argument("drill", type=Path)
    evaluating = sub.add_parser("evaluate")
    evaluating.add_argument("drill", type=Path)
    evaluating.add_argument("--out", type=Path, required=True)
    verifying = sub.add_parser("verify")
    verifying.add_argument("receipt", type=Path)
    verifying.add_argument("--drill", type=Path)
    packing = sub.add_parser("pack")
    packing.add_argument("drill", type=Path)
    packing.add_argument("receipt", type=Path)
    packing.add_argument("--out", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "validate":
            validate_drill(load_json(args.drill))
            print(f"OK: {args.drill} is a valid synthetic containment drill.")
            return 0
        if args.command == "evaluate":
            receipt = evaluate_drill(load_json(args.drill))
            write_json(receipt, args.out)
            print(f"OK: {receipt['summary']['event_count']} containment events written to {args.out}.")
            return 0
        if args.command == "verify":
            drill = load_json(args.drill) if args.drill else None
            verify_receipt(load_json(args.receipt), drill)
            print(f"OK: {args.receipt} verified.")
            return 0
        build_pack(args.drill, args.receipt, args.out)
        print(f"OK: containment pack written to {args.out}.")
        return 0
    except ContainmentError as exc:
        print(f"aau-containment: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
