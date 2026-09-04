"""Public-synthetic two-process adapter for the ASEL crash lab."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from aau_crash_lab import CRASH_EXIT, PROTOCOL_VERSION  # noqa: E402


def _require_runtime_policy() -> None:
    policy = json.loads(Path(__file__).with_name("reference-runtime-policy.json").read_text())
    if policy != {
        "policy_id": "public-synthetic-side-effect-staging-v1",
        "environment": "public_synthetic",
        "live_targets_allowed": False,
    }:
        raise ValueError("runtime policy does not permit the public-synthetic adapter")


ORDER = {
    "prepare_durable": 1,
    "approval_durable": 2,
    "dispatch_recorded": 3,
    "target_resolved": 4,
    "result_durable": 5,
    "response_returned": 6,
}


def _contains_oracle(value: object) -> bool:
    if isinstance(value, dict):
        return "expected" in value or any(_contains_oracle(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_oracle(item) for item in value)
    return False


def _durable_write(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("x") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if os.name == "posix":
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _inject(request: dict[str, object], state_dir: Path) -> None:
    case = request["case"]
    profile = request["profile"]
    assert isinstance(case, dict) and isinstance(profile, dict)
    point = case["crash_after"]
    journal_status = "prepared"
    if ORDER[point] >= ORDER["approval_durable"]:
        journal_status = "approved"
    if ORDER[point] >= ORDER["dispatch_recorded"]:
        journal_status = "unknown"
    target_outcome = case["target_outcome"]
    if ORDER[point] >= ORDER["target_resolved"]:
        _durable_write(
            state_dir / "target.json",
            {
                "idempotency_key": profile["idempotency_key"],
                "intent_sha256": profile["intent_sha256"],
                "status": target_outcome,
                "effect_count": 1 if target_outcome == "committed" else 0,
            },
        )
    if ORDER[point] >= ORDER["result_durable"]:
        journal_status = target_outcome
    if case["local_journal_available"]:
        _durable_write(
            state_dir / "journal.json",
            {
                "idempotency_key": profile["idempotency_key"],
                "intent_sha256": profile["intent_sha256"],
                "status": journal_status,
                "response_returned": point == "response_returned",
            },
        )
    os._exit(CRASH_EXIT)


def _absent_recovery(case: dict[str, object]) -> tuple[str, str, int, list[str]]:
    now = case["recovery_at_ms"]
    assert isinstance(now, int)
    reasons = ["TARGET_CONFIRMED_ABSENT"]
    if now >= case["authority_expires_at_ms"]:
        reasons.append("AUTHORITY_EXPIRED")
        return "recovery_held", "reauthorize", 0, sorted(reasons)
    if now >= case["approval_expires_at_ms"]:
        reasons.append("APPROVAL_EXPIRED")
        return "recovery_held", "request_approval", 0, sorted(reasons)
    return "reconciled_absent", "retry_once", 0, reasons


def _recover(request: dict[str, object], state_dir: Path) -> dict[str, object]:
    case = request["case"]
    profile = request["profile"]
    assert isinstance(case, dict) and isinstance(profile, dict)
    journal_path = state_dir / "journal.json"
    if not journal_path.is_file():
        result = (
            "manual_recovery_required",
            "hold_manual",
            None,
            ["LOCAL_JOURNAL_UNAVAILABLE"],
        )
    else:
        journal = json.loads(journal_path.read_text())
        if (
            journal.get("idempotency_key") != profile["idempotency_key"]
            or journal.get("intent_sha256") != profile["intent_sha256"]
        ):
            result = (
                "manual_recovery_required",
                "hold_manual",
                None,
                ["LOCAL_JOURNAL_BINDING_MISMATCH"],
            )
        elif journal["status"] == "prepared":
            result = "recovery_held", "request_approval", 0, ["APPROVAL_REQUIRED"]
        elif journal["status"] == "approved":
            now = case["recovery_at_ms"]
            if now >= case["authority_expires_at_ms"]:
                result = "recovery_held", "reauthorize", 0, ["AUTHORITY_EXPIRED"]
            elif now >= case["approval_expires_at_ms"]:
                result = "recovery_held", "request_approval", 0, ["APPROVAL_EXPIRED"]
            else:
                result = "recovery_ready", "dispatch_once", 0, []
        elif journal["status"] == "committed":
            result = "replay_committed", "replay", 1, ["DURABLE_RESULT_REPLAY"]
        elif journal["status"] == "absent":
            result = _absent_recovery(case)
        elif not case["target_lookup_available"]:
            result = (
                "manual_recovery_required",
                "hold_manual",
                None,
                ["TARGET_LOOKUP_UNAVAILABLE"],
            )
        elif case["recovery_at_ms"] >= case["retention_expires_at_ms"]:
            result = (
                "manual_recovery_required",
                "hold_manual",
                None,
                ["IDEMPOTENCY_RETENTION_EXPIRED"],
            )
        else:
            target_path = state_dir / "target.json"
            if target_path.is_file() and json.loads(target_path.read_text())["status"] == "committed":
                result = (
                    "reconciled_committed",
                    "replay",
                    1,
                    ["TARGET_CONFIRMED_COMMITTED"],
                )
            else:
                result = _absent_recovery(case)
    outcome, action, effect_count, reasons = result
    return {
        "case_id": case["case_id"],
        "recovered_outcome": outcome,
        "next_action": action,
        "known_effect_count": effect_count,
        "reason_codes": reasons,
    }


def main() -> int:
    _require_runtime_policy()
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "phase", "suite_id", "state_dir", "profile", "case"}:
        raise ValueError("crash adapter request fields changed")
    if request["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError("unsupported crash adapter protocol")
    if _contains_oracle(request):
        raise ValueError("crash adapter request leaked expected evidence")
    state_dir = Path(request["state_dir"])
    if state_dir.is_symlink() or not state_dir.is_dir():
        raise ValueError("state_dir must be an existing non-symbolic directory")
    if request["phase"] == "inject":
        _inject(request, state_dir)
    if request["phase"] != "recover":
        raise ValueError("unsupported crash adapter phase")
    json.dump(_recover(request, state_dir), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
