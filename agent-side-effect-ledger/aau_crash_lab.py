"""Two-process fault-injection lab for side-effect recovery boundaries."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from aau_side_effect import SideEffectError, canonical, digest, load_json, write_json


SUITE_VERSION = "aau-agent-side-effect-crash-suite/0.1"
RECEIPT_VERSION = "aau-agent-side-effect-crash-receipt/0.1"
PROTOCOL_VERSION = "aau-agent-side-effect-crash-adapter/0.1"
CRASH_EXIT = 86
MAX_ADAPTER_BYTES = 1_000_000
CRASH_POINTS = {
    "prepare_durable",
    "approval_durable",
    "dispatch_recorded",
    "target_resolved",
    "result_durable",
    "response_returned",
}
TARGET_OUTCOMES = {"not_attempted", "committed", "absent"}
RECOVERED_OUTCOMES = {
    "recovery_ready",
    "recovery_held",
    "reconciled_committed",
    "reconciled_absent",
    "replay_committed",
    "manual_recovery_required",
}
NEXT_ACTIONS = {
    "request_approval",
    "reauthorize",
    "dispatch_once",
    "retry_once",
    "replay",
    "hold_manual",
}
BOUNDARY_KEYS = {
    "public_synthetic_only",
    "fresh_process_recovery",
    "oracle_withheld_from_adapter",
    "no_production_target",
    "crash_exit_is_not_power_loss",
    "fsync_is_not_storage_proof",
    "not_exactly_once_claim",
}


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SideEffectError(f"{label} fields differ from the 0.1 contract")
    return value


def _text(value: Any, label: str, limit: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise SideEffectError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _reason_codes(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise SideEffectError(f"{label} must be a list")
    for item in value:
        _text(item, label, 100)
    if value != sorted(set(value)):
        raise SideEffectError(f"{label} must be sorted and unique")
    return value


def validate_suite(suite: dict[str, Any]) -> None:
    _exact(
        suite,
        {"suite_version", "suite_id", "title", "profile", "cases", "boundaries"},
        "crash suite",
    )
    if suite["suite_version"] != SUITE_VERSION:
        raise SideEffectError(f"crash suite_version must be {SUITE_VERSION}")
    _text(suite["suite_id"], "suite_id", 120)
    _text(suite["title"], "title", 240)
    profile = _exact(
        suite["profile"],
        {"tool_id", "operation_id", "idempotency_key", "intent_sha256"},
        "crash profile",
    )
    _text(profile["tool_id"], "profile.tool_id", 120)
    _text(profile["operation_id"], "profile.operation_id", 160)
    _text(profile["idempotency_key"], "profile.idempotency_key", 200)
    if not isinstance(profile["intent_sha256"], str) or len(profile["intent_sha256"]) != 64:
        raise SideEffectError("profile.intent_sha256 must be a lowercase SHA-256 digest")
    try:
        int(profile["intent_sha256"], 16)
    except ValueError as exc:
        raise SideEffectError("profile.intent_sha256 must be a lowercase SHA-256 digest") from exc
    if profile["intent_sha256"] != profile["intent_sha256"].lower():
        raise SideEffectError("profile.intent_sha256 must be a lowercase SHA-256 digest")
    boundaries = _exact(suite["boundaries"], BOUNDARY_KEYS, "crash boundaries")
    if any(boundaries[key] is not True for key in BOUNDARY_KEYS):
        raise SideEffectError("every crash-lab boundary must be true")
    cases = suite["cases"]
    if not isinstance(cases, list) or not (8 <= len(cases) <= 40):
        raise SideEffectError("crash suite must contain 8 to 40 cases")
    case_ids: set[str] = set()
    observed_points: set[str] = set()
    for index, case in enumerate(cases):
        case = _exact(
            case,
            {
                "case_id",
                "title",
                "crash_after",
                "target_outcome",
                "recovery_at_ms",
                "approval_expires_at_ms",
                "authority_expires_at_ms",
                "retention_expires_at_ms",
                "local_journal_available",
                "target_lookup_available",
                "expected",
            },
            f"cases[{index}]",
        )
        case_id = _text(case["case_id"], f"cases[{index}].case_id", 100)
        if case_id in case_ids:
            raise SideEffectError(f"duplicate crash case_id: {case_id}")
        case_ids.add(case_id)
        _text(case["title"], f"cases[{index}].title", 220)
        if case["crash_after"] not in CRASH_POINTS:
            raise SideEffectError(f"cases[{index}].crash_after is unsupported")
        observed_points.add(case["crash_after"])
        if case["target_outcome"] not in TARGET_OUTCOMES:
            raise SideEffectError(f"cases[{index}].target_outcome is unsupported")
        if case["crash_after"] in {"target_resolved", "result_durable", "response_returned"}:
            if case["target_outcome"] == "not_attempted":
                raise SideEffectError(f"cases[{index}] requires a resolved target outcome")
        elif case["target_outcome"] != "not_attempted":
            raise SideEffectError(f"cases[{index}] resolves the target before its crash point")
        for key in (
            "recovery_at_ms",
            "approval_expires_at_ms",
            "authority_expires_at_ms",
            "retention_expires_at_ms",
        ):
            if not isinstance(case[key], int) or case[key] <= 0:
                raise SideEffectError(f"cases[{index}].{key} must be a positive integer")
        for key in ("local_journal_available", "target_lookup_available"):
            if not isinstance(case[key], bool):
                raise SideEffectError(f"cases[{index}].{key} must be boolean")
        expected = _exact(
            case["expected"],
            {"recovered_outcome", "next_action", "known_effect_count", "reason_codes"},
            f"cases[{index}].expected",
        )
        if expected["recovered_outcome"] not in RECOVERED_OUTCOMES:
            raise SideEffectError(f"cases[{index}].expected.recovered_outcome is unsupported")
        if expected["next_action"] not in NEXT_ACTIONS:
            raise SideEffectError(f"cases[{index}].expected.next_action is unsupported")
        if expected["known_effect_count"] not in {None, 0, 1}:
            raise SideEffectError(f"cases[{index}].expected.known_effect_count is invalid")
        _reason_codes(expected["reason_codes"], f"cases[{index}].expected.reason_codes")
    if observed_points != CRASH_POINTS:
        raise SideEffectError(f"crash suite is missing points: {sorted(CRASH_POINTS - observed_points)}")


def adapter_request(
    suite: dict[str, Any], case: dict[str, Any], phase: str, state_dir: Path
) -> dict[str, Any]:
    if phase not in {"inject", "recover"}:
        raise SideEffectError("crash adapter phase must be inject or recover")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "phase": phase,
        "suite_id": suite["suite_id"],
        "state_dir": str(state_dir),
        "profile": suite["profile"],
        "case": {key: value for key, value in case.items() if key != "expected"},
    }


def _validate_response(value: Any, case: dict[str, Any]) -> dict[str, Any]:
    response = _exact(
        value,
        {"case_id", "recovered_outcome", "next_action", "known_effect_count", "reason_codes"},
        "crash adapter response",
    )
    if response["case_id"] != case["case_id"]:
        raise SideEffectError("crash adapter response case_id mismatch")
    if response["recovered_outcome"] not in RECOVERED_OUTCOMES:
        raise SideEffectError("crash adapter recovered_outcome is unsupported")
    if response["next_action"] not in NEXT_ACTIONS:
        raise SideEffectError("crash adapter next_action is unsupported")
    if response["known_effect_count"] not in {None, 0, 1, 2}:
        raise SideEffectError("crash adapter known_effect_count is invalid")
    _reason_codes(response["reason_codes"], "crash adapter reason_codes")
    return response


def _invoke(
    argv: list[str],
    request: dict[str, Any],
    timeout: float,
    expect_crash: bool,
    adapter_env: dict[str, str] | None = None,
) -> bytes:
    try:
        completed = subprocess.run(
            argv,
            input=canonical(request),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=adapter_env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SideEffectError(f"crash adapter execution failed: {exc}") from exc
    expected_code = CRASH_EXIT if expect_crash else 0
    if completed.returncode != expected_code:
        raise SideEffectError(
            f"crash adapter exited with status {completed.returncode}; expected {expected_code}"
        )
    if len(completed.stdout) > MAX_ADAPTER_BYTES:
        raise SideEffectError(f"crash adapter response exceeds {MAX_ADAPTER_BYTES} bytes")
    return completed.stdout


def run_suite(
    suite: dict[str, Any],
    command: str,
    timeout: float = 10.0,
    adapter_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    validate_suite(suite)
    argv = shlex.split(command)
    if not argv:
        raise SideEffectError("crash adapter command is empty")
    if not 0 < timeout <= 300:
        raise SideEffectError("crash adapter timeout must be greater than 0 and at most 300 seconds")
    previous = "0" * 64
    rows = []
    exact_count = 0
    unsafe_resume_count = 0
    duplicate_effect_breach_count = 0
    unresolved_effect_count = 0
    for case in suite["cases"]:
        with tempfile.TemporaryDirectory(prefix="aau-crash-") as directory:
            state_dir = Path(directory)
            _invoke(
                argv,
                adapter_request(suite, case, "inject", state_dir),
                timeout,
                True,
                adapter_env,
            )
            raw = _invoke(
                argv,
                adapter_request(suite, case, "recover", state_dir),
                timeout,
                False,
                adapter_env,
            )
        try:
            actual = _validate_response(json.loads(raw), case)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SideEffectError("crash adapter returned invalid JSON") from exc
        expected = case["expected"]
        exact = actual == {"case_id": case["case_id"], **expected}
        exact_count += int(exact)
        expected_action = expected["next_action"]
        unsafe_resume_count += int(
            actual["next_action"] in {"dispatch_once", "retry_once"}
            and actual["next_action"] != expected_action
        )
        duplicate_effect_breach_count += int(
            isinstance(actual["known_effect_count"], int)
            and actual["known_effect_count"] > 1
        )
        unresolved_effect_count += int(actual["known_effect_count"] is None)
        row = {
            "case_id": case["case_id"],
            "crash_after": case["crash_after"],
            "actual_recovered_outcome": actual["recovered_outcome"],
            "actual_next_action": actual["next_action"],
            "actual_known_effect_count": actual["known_effect_count"],
            "actual_reason_codes": actual["reason_codes"],
            "exact": exact,
            "previous_result_sha256": previous,
        }
        row["result_sha256"] = digest(row)
        previous = row["result_sha256"]
        rows.append(row)
    summary = {
        "case_count": len(rows),
        "crash_point_count": len(CRASH_POINTS),
        "exact_count": exact_count,
        "exact_rate": round(exact_count / len(rows), 6),
        "unsafe_resume_count": unsafe_resume_count,
        "duplicate_effect_breach_count": duplicate_effect_breach_count,
        "unresolved_effect_count": unresolved_effect_count,
    }
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "adapter_protocol_version": PROTOCOL_VERSION,
        "suite_id": suite["suite_id"],
        "suite_sha256": digest(suite),
        "adapter_kind": "two_process_command",
        "status": "evidence_passed" if exact_count == len(rows) else "evidence_failed",
        "summary": summary,
        "results": rows,
        "final_result_sha256": previous,
        "claim_boundary": {
            "oracle_withheld_from_adapter": True,
            "fresh_process_used_for_recovery": True,
            "synthetic_state_only": True,
            "crash_exit_does_not_prove_power_loss_durability": True,
            "adapter_command_is_trusted_local_code": True,
            "passing_not_atomicity_exactly_once_or_production_evidence": True,
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_receipt(receipt: dict[str, Any], suite: dict[str, Any]) -> None:
    validate_suite(suite)
    expected_keys = {
        "receipt_version",
        "adapter_protocol_version",
        "suite_id",
        "suite_sha256",
        "adapter_kind",
        "status",
        "summary",
        "results",
        "final_result_sha256",
        "claim_boundary",
        "receipt_sha256",
    }
    receipt = _exact(receipt, expected_keys, "crash receipt")
    if receipt["receipt_version"] != RECEIPT_VERSION:
        raise SideEffectError("unsupported crash receipt_version")
    unsigned = dict(receipt)
    supplied = unsigned.pop("receipt_sha256")
    if supplied != digest(unsigned):
        raise SideEffectError("crash receipt digest mismatch")
    if receipt["suite_id"] != suite["suite_id"] or receipt["suite_sha256"] != digest(suite):
        raise SideEffectError("crash receipt suite binding mismatch")
    cases = {case["case_id"]: case for case in suite["cases"]}
    if not isinstance(receipt["results"], list):
        raise SideEffectError("crash receipt results must be a list")
    if [row.get("case_id") for row in receipt["results"] if isinstance(row, dict)] != list(cases):
        raise SideEffectError("crash receipt case coverage or order is invalid")
    previous = "0" * 64
    exact_count = 0
    unsafe = 0
    duplicate = 0
    unresolved = 0
    for row in receipt["results"]:
        row = _exact(
            row,
            {
                "case_id",
                "crash_after",
                "actual_recovered_outcome",
                "actual_next_action",
                "actual_known_effect_count",
                "actual_reason_codes",
                "exact",
                "previous_result_sha256",
                "result_sha256",
            },
            "crash result",
        )
        source = cases[row["case_id"]]
        if row["crash_after"] != source["crash_after"]:
            raise SideEffectError("crash receipt point binding mismatch")
        if row["actual_recovered_outcome"] not in RECOVERED_OUTCOMES:
            raise SideEffectError("crash receipt recovered outcome is invalid")
        if row["actual_next_action"] not in NEXT_ACTIONS:
            raise SideEffectError("crash receipt next action is invalid")
        if row["actual_known_effect_count"] not in {None, 0, 1, 2}:
            raise SideEffectError("crash receipt known effect count is invalid")
        if row["previous_result_sha256"] != previous:
            raise SideEffectError("crash receipt result chain is broken")
        unsigned_row = dict(row)
        row_hash = unsigned_row.pop("result_sha256")
        if row_hash != digest(unsigned_row):
            raise SideEffectError("crash receipt result digest mismatch")
        previous = row_hash
        _reason_codes(row["actual_reason_codes"], "crash receipt reason_codes")
        expected = source["expected"]
        recomputed_exact = (
            row["actual_recovered_outcome"] == expected["recovered_outcome"]
            and row["actual_next_action"] == expected["next_action"]
            and row["actual_known_effect_count"] == expected["known_effect_count"]
            and row["actual_reason_codes"] == expected["reason_codes"]
        )
        if row["exact"] is not recomputed_exact:
            raise SideEffectError("crash receipt exactness does not recompute")
        exact_count += int(recomputed_exact)
        unsafe += int(
            row["actual_next_action"] in {"dispatch_once", "retry_once"}
            and row["actual_next_action"] != expected["next_action"]
        )
        known = row["actual_known_effect_count"]
        duplicate += int(isinstance(known, int) and known > 1)
        unresolved += int(known is None)
    summary = {
        "case_count": len(cases),
        "crash_point_count": len(CRASH_POINTS),
        "exact_count": exact_count,
        "exact_rate": round(exact_count / len(cases), 6),
        "unsafe_resume_count": unsafe,
        "duplicate_effect_breach_count": duplicate,
        "unresolved_effect_count": unresolved,
    }
    if receipt["summary"] != summary:
        raise SideEffectError("crash receipt summary does not recompute")
    expected_status = "evidence_passed" if exact_count == len(cases) else "evidence_failed"
    if receipt["status"] != expected_status:
        raise SideEffectError("crash receipt status does not recompute")
    if receipt["final_result_sha256"] != previous:
        raise SideEffectError("crash receipt final digest mismatch")
    boundary = {
        "oracle_withheld_from_adapter": True,
        "fresh_process_used_for_recovery": True,
        "synthetic_state_only": True,
        "crash_exit_does_not_prove_power_loss_durability": True,
        "adapter_command_is_trusted_local_code": True,
        "passing_not_atomicity_exactly_once_or_production_evidence": True,
    }
    if (
        receipt["adapter_protocol_version"] != PROTOCOL_VERSION
        or receipt["adapter_kind"] != "two_process_command"
        or receipt["claim_boundary"] != boundary
    ):
        raise SideEffectError("crash receipt protocol or claim boundary is invalid")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="inject each crash and recover in a fresh adapter process")
    run.add_argument("suite", type=Path)
    run.add_argument("--command", dest="adapter_command", required=True)
    run.add_argument("--timeout", type=float, default=10.0)
    run.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="verify a crash-lab receipt against its suite")
    verify.add_argument("receipt", type=Path)
    verify.add_argument("--suite", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "run":
            receipt = run_suite(load_json(args.suite), args.adapter_command, args.timeout)
            write_json(receipt, args.out)
            print(
                f"wrote {args.out}: {receipt['summary']['case_count']} crashes, "
                f"{receipt['summary']['unsafe_resume_count']} unsafe resumes"
            )
        else:
            receipt = load_json(args.receipt)
            suite = load_json(args.suite)
            verify_receipt(receipt, suite)
            print(
                f"verified {args.receipt}: {receipt['summary']['exact_count']}/"
                f"{receipt['summary']['case_count']} exact recoveries"
            )
    except (OSError, SideEffectError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
