"""Multi-process race lab for intent-bound side-effect deduplication."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from aau_side_effect import SideEffectError, canonical, digest, load_json, write_json


SUITE_VERSION = "aau-agent-side-effect-race-suite/0.1"
RECEIPT_VERSION = "aau-agent-side-effect-race-receipt/0.1"
PROTOCOL_VERSION = "aau-agent-side-effect-race-adapter/0.1"
MAX_ADAPTER_BYTES = 1_000_000
OUTCOMES = {"committed", "replayed", "conflict", "blocked"}
BOUNDARY_KEYS = {
    "public_synthetic_only",
    "oracle_withheld_from_adapter",
    "fresh_process_per_attempt",
    "post_race_state_inspection",
    "no_production_target",
    "concurrent_launch_is_not_scheduler_proof",
    "adapter_scoped_not_exactly_once",
}


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SideEffectError(f"{label} fields differ from the 0.1 contract")
    return value


def _text(value: Any, label: str, limit: int = 240) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise SideEffectError(f"{label} must be non-empty text of at most {limit} characters")
    return value


def _digest_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value != value.lower():
        raise SideEffectError(f"{label} must be a lowercase SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SideEffectError(f"{label} must be a lowercase SHA-256 digest") from exc
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
        "race suite",
    )
    if suite["suite_version"] != SUITE_VERSION:
        raise SideEffectError(f"race suite_version must be {SUITE_VERSION}")
    _text(suite["suite_id"], "suite_id", 120)
    _text(suite["title"], "title")
    profile = _exact(suite["profile"], {"operation_id"}, "race profile")
    _text(profile["operation_id"], "profile.operation_id", 160)
    boundaries = _exact(suite["boundaries"], BOUNDARY_KEYS, "race boundaries")
    if any(boundaries[key] is not True for key in BOUNDARY_KEYS):
        raise SideEffectError("every race-lab boundary must be true")
    cases = suite["cases"]
    if not isinstance(cases, list) or not (8 <= len(cases) <= 30):
        raise SideEffectError("race suite must contain 8 to 30 cases")
    case_ids: set[str] = set()
    global_attempt_ids: set[str] = set()
    for case_index, case in enumerate(cases):
        case = _exact(case, {"case_id", "title", "attempts", "expected"}, f"cases[{case_index}]")
        case_id = _text(case["case_id"], f"cases[{case_index}].case_id", 100)
        if case_id in case_ids:
            raise SideEffectError(f"duplicate race case_id: {case_id}")
        case_ids.add(case_id)
        _text(case["title"], f"cases[{case_index}].title", 220)
        attempts = case["attempts"]
        if not isinstance(attempts, list) or not (2 <= len(attempts) <= 32):
            raise SideEffectError(f"cases[{case_index}].attempts must contain 2 to 32 entries")
        for attempt_index, attempt in enumerate(attempts):
            attempt = _exact(
                attempt,
                {
                    "attempt_id",
                    "idempotency_key",
                    "intent_sha256",
                    "authority_valid",
                    "approval_valid",
                },
                f"cases[{case_index}].attempts[{attempt_index}]",
            )
            attempt_id = _text(attempt["attempt_id"], "attempt_id", 100)
            if attempt_id in global_attempt_ids:
                raise SideEffectError(f"duplicate race attempt_id: {attempt_id}")
            global_attempt_ids.add(attempt_id)
            _text(attempt["idempotency_key"], "idempotency_key", 200)
            _digest_text(attempt["intent_sha256"], "intent_sha256")
            for key in ("authority_valid", "approval_valid"):
                if not isinstance(attempt[key], bool):
                    raise SideEffectError(f"attempt.{key} must be boolean")
        expected = _exact(
            case["expected"],
            {
                "effect_count",
                "key_count",
                "committed_count",
                "replayed_count",
                "conflict_count",
                "blocked_count",
            },
            f"cases[{case_index}].expected",
        )
        for key, value in expected.items():
            if not isinstance(value, int) or value < 0:
                raise SideEffectError(f"cases[{case_index}].expected.{key} must be non-negative")
        response_total = sum(expected[key] for key in ("committed_count", "replayed_count", "conflict_count", "blocked_count"))
        if response_total != len(attempts):
            raise SideEffectError(f"cases[{case_index}].expected response counts must cover attempts")
        if expected["effect_count"] != expected["committed_count"]:
            raise SideEffectError(f"cases[{case_index}] must bind committed and inspected effects")


def attempt_request(
    suite: dict[str, Any], case: dict[str, Any], attempt: dict[str, Any], state_dir: Path
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "phase": "attempt",
        "suite_id": suite["suite_id"],
        "case_id": case["case_id"],
        "worker_count": len(case["attempts"]),
        "state_dir": str(state_dir),
        "profile": suite["profile"],
        "attempt": attempt,
    }


def inspect_request(suite: dict[str, Any], case: dict[str, Any], state_dir: Path) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "phase": "inspect",
        "suite_id": suite["suite_id"],
        "case_id": case["case_id"],
        "state_dir": str(state_dir),
        "profile": suite["profile"],
    }


def _invoke(argv: list[str], request: dict[str, Any], timeout: float) -> dict[str, Any]:
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
        raise SideEffectError(f"race adapter execution failed: {exc}") from exc
    if completed.returncode != 0:
        raise SideEffectError(f"race adapter exited with status {completed.returncode}")
    if len(completed.stdout) > MAX_ADAPTER_BYTES:
        raise SideEffectError(f"race adapter response exceeds {MAX_ADAPTER_BYTES} bytes")
    try:
        value = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SideEffectError("race adapter returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise SideEffectError("race adapter response must be an object")
    return value


def _validate_attempt_response(value: Any, attempt_id: str) -> dict[str, Any]:
    response = _exact(value, {"attempt_id", "outcome", "reason_codes"}, "race attempt response")
    if response["attempt_id"] != attempt_id:
        raise SideEffectError("race attempt response identity mismatch")
    if response["outcome"] not in OUTCOMES:
        raise SideEffectError("race attempt response outcome is unsupported")
    _reason_codes(response["reason_codes"], "race attempt reason_codes")
    return response


def _validate_inspection(value: Any, case_id: str) -> dict[str, Any]:
    result = _exact(value, {"case_id", "effect_count", "key_count"}, "race inspection")
    if result["case_id"] != case_id:
        raise SideEffectError("race inspection identity mismatch")
    for key in ("effect_count", "key_count"):
        if not isinstance(result[key], int) or result[key] < 0:
            raise SideEffectError(f"race inspection {key} must be non-negative")
    return result


def _run_case(
    suite: dict[str, Any], case: dict[str, Any], argv: list[str], timeout: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attempts = case["attempts"]
    barrier = threading.Barrier(len(attempts))
    with tempfile.TemporaryDirectory(prefix="aau-race-") as directory:
        state_dir = Path(directory)

        def run_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
            barrier.wait(timeout=timeout)
            response = _invoke(argv, attempt_request(suite, case, attempt, state_dir), timeout)
            return _validate_attempt_response(response, attempt["attempt_id"])

        with ThreadPoolExecutor(max_workers=len(attempts)) as executor:
            futures = [executor.submit(run_attempt, attempt) for attempt in attempts]
            responses = [future.result() for future in futures]
        inspection = _validate_inspection(
            _invoke(argv, inspect_request(suite, case, state_dir), timeout), case["case_id"]
        )
    return sorted(responses, key=lambda row: row["attempt_id"]), inspection


def run_suite(suite: dict[str, Any], command: str, timeout: float = 15.0) -> dict[str, Any]:
    validate_suite(suite)
    argv = shlex.split(command)
    if not argv:
        raise SideEffectError("race adapter command is empty")
    if not 0 < timeout <= 300:
        raise SideEffectError("race adapter timeout must be greater than 0 and at most 300 seconds")
    previous = "0" * 64
    rows = []
    exact_count = 0
    duplicate_effect_count = 0
    missing_effect_count = 0
    response_state_mismatch_count = 0
    attempt_count = 0
    for case in suite["cases"]:
        responses, inspection = _run_case(suite, case, argv, timeout)
        counts = {outcome: 0 for outcome in OUTCOMES}
        grouped: dict[tuple[str, tuple[str, ...]], int] = {}
        for response in responses:
            counts[response["outcome"]] += 1
            group_key = (response["outcome"], tuple(response["reason_codes"]))
            grouped[group_key] = grouped.get(group_key, 0) + 1
        response_groups = [
            {"outcome": outcome, "reason_codes": list(reasons), "count": count}
            for (outcome, reasons), count in sorted(grouped.items())
        ]
        actual = {
            "effect_count": inspection["effect_count"],
            "key_count": inspection["key_count"],
            "committed_count": counts["committed"],
            "replayed_count": counts["replayed"],
            "conflict_count": counts["conflict"],
            "blocked_count": counts["blocked"],
        }
        expected = case["expected"]
        exact = actual == expected
        exact_count += int(exact)
        attempt_count += len(responses)
        duplicate_effect_count += max(actual["effect_count"] - expected["effect_count"], 0)
        missing_effect_count += max(expected["effect_count"] - actual["effect_count"], 0)
        response_state_mismatch_count += int(
            actual["committed_count"] != actual["effect_count"]
        )
        row = {
            "case_id": case["case_id"],
            "attempt_count": len(responses),
            "actual": actual,
            "response_groups": response_groups,
            "exact": exact,
            "previous_result_sha256": previous,
        }
        row["result_sha256"] = digest(row)
        previous = row["result_sha256"]
        rows.append(row)
    summary = {
        "case_count": len(rows),
        "attempt_count": attempt_count,
        "exact_count": exact_count,
        "exact_rate": round(exact_count / len(rows), 6),
        "duplicate_effect_count": duplicate_effect_count,
        "missing_effect_count": missing_effect_count,
        "response_state_mismatch_count": response_state_mismatch_count,
    }
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "adapter_protocol_version": PROTOCOL_VERSION,
        "suite_id": suite["suite_id"],
        "suite_sha256": digest(suite),
        "adapter_kind": "multi_process_command",
        "status": "evidence_passed" if exact_count == len(rows) else "evidence_failed",
        "summary": summary,
        "results": rows,
        "final_result_sha256": previous,
        "claim_boundary": {
            "oracle_withheld_from_adapter": True,
            "post_race_state_inspected": True,
            "public_synthetic_state_only": True,
            "concurrent_launch_not_scheduler_overlap_proof": True,
            "adapter_command_is_trusted_local_code": True,
            "passing_not_linearizability_exactly_once_or_production_evidence": True,
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_receipt(receipt: dict[str, Any], suite: dict[str, Any]) -> None:
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
            "results",
            "final_result_sha256",
            "claim_boundary",
            "receipt_sha256",
        },
        "race receipt",
    )
    unsigned = dict(receipt)
    supplied = unsigned.pop("receipt_sha256")
    if supplied != digest(unsigned):
        raise SideEffectError("race receipt digest mismatch")
    if receipt["receipt_version"] != RECEIPT_VERSION:
        raise SideEffectError("unsupported race receipt_version")
    if receipt["suite_id"] != suite["suite_id"] or receipt["suite_sha256"] != digest(suite):
        raise SideEffectError("race receipt suite binding mismatch")
    cases = {case["case_id"]: case for case in suite["cases"]}
    if not isinstance(receipt["results"], list):
        raise SideEffectError("race receipt results must be a list")
    if [row.get("case_id") for row in receipt["results"] if isinstance(row, dict)] != list(cases):
        raise SideEffectError("race receipt case coverage or order is invalid")
    previous = "0" * 64
    exact_count = 0
    duplicate = 0
    missing = 0
    mismatch = 0
    attempt_count = 0
    for row in receipt["results"]:
        row = _exact(
            row,
            {
                "case_id",
                "attempt_count",
                "actual",
                "response_groups",
                "exact",
                "previous_result_sha256",
                "result_sha256",
            },
            "race result",
        )
        source = cases[row["case_id"]]
        if row["previous_result_sha256"] != previous:
            raise SideEffectError("race receipt result chain is broken")
        unsigned_row = dict(row)
        row_hash = unsigned_row.pop("result_sha256")
        if row_hash != digest(unsigned_row):
            raise SideEffectError("race receipt result digest mismatch")
        previous = row_hash
        if row["attempt_count"] != len(source["attempts"]):
            raise SideEffectError("race receipt attempt count is invalid")
        groups = row["response_groups"]
        if not isinstance(groups, list) or not groups:
            raise SideEffectError("race receipt response groups are invalid")
        counts = {outcome: 0 for outcome in OUTCOMES}
        group_keys = []
        for group in groups:
            group = _exact(group, {"outcome", "reason_codes", "count"}, "race response group")
            if group["outcome"] not in OUTCOMES:
                raise SideEffectError("race response group outcome is unsupported")
            reasons = _reason_codes(group["reason_codes"], "race response group reason_codes")
            if not isinstance(group["count"], int) or group["count"] <= 0:
                raise SideEffectError("race response group count must be positive")
            group_keys.append((group["outcome"], tuple(reasons)))
            counts[group["outcome"]] += group["count"]
        if group_keys != sorted(set(group_keys)) or sum(counts.values()) != row["attempt_count"]:
            raise SideEffectError("race response groups are duplicated, unsorted, or incomplete")
        actual = _exact(
            row["actual"],
            {"effect_count", "key_count", "committed_count", "replayed_count", "conflict_count", "blocked_count"},
            "race actual aggregate",
        )
        for key, value in actual.items():
            if not isinstance(value, int) or value < 0:
                raise SideEffectError(f"race actual {key} is invalid")
        recomputed_counts = {
            "committed_count": counts["committed"],
            "replayed_count": counts["replayed"],
            "conflict_count": counts["conflict"],
            "blocked_count": counts["blocked"],
        }
        if any(actual[key] != value for key, value in recomputed_counts.items()):
            raise SideEffectError("race response counts do not recompute")
        exact = actual == source["expected"]
        if row["exact"] is not exact:
            raise SideEffectError("race receipt exactness does not recompute")
        exact_count += int(exact)
        attempt_count += row["attempt_count"]
        duplicate += max(actual["effect_count"] - source["expected"]["effect_count"], 0)
        missing += max(source["expected"]["effect_count"] - actual["effect_count"], 0)
        mismatch += int(actual["committed_count"] != actual["effect_count"])
    summary = {
        "case_count": len(cases),
        "attempt_count": attempt_count,
        "exact_count": exact_count,
        "exact_rate": round(exact_count / len(cases), 6),
        "duplicate_effect_count": duplicate,
        "missing_effect_count": missing,
        "response_state_mismatch_count": mismatch,
    }
    if receipt["summary"] != summary:
        raise SideEffectError("race receipt summary does not recompute")
    status = "evidence_passed" if exact_count == len(cases) else "evidence_failed"
    boundary = {
        "oracle_withheld_from_adapter": True,
        "post_race_state_inspected": True,
        "public_synthetic_state_only": True,
        "concurrent_launch_not_scheduler_overlap_proof": True,
        "adapter_command_is_trusted_local_code": True,
        "passing_not_linearizability_exactly_once_or_production_evidence": True,
    }
    if (
        receipt["status"] != status
        or receipt["final_result_sha256"] != previous
        or receipt["adapter_protocol_version"] != PROTOCOL_VERSION
        or receipt["adapter_kind"] != "multi_process_command"
        or receipt["claim_boundary"] != boundary
    ):
        raise SideEffectError("race receipt status, protocol, chain, or boundary is invalid")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="launch concurrent fresh-process attempts and inspect state")
    run.add_argument("suite", type=Path)
    run.add_argument("--command", dest="adapter_command", required=True)
    run.add_argument("--timeout", type=float, default=15.0)
    run.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify", help="verify a race-lab receipt against its suite")
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
                f"wrote {args.out}: {receipt['summary']['attempt_count']} attempts, "
                f"{receipt['summary']['duplicate_effect_count']} duplicate effects"
            )
        else:
            receipt = load_json(args.receipt)
            suite = load_json(args.suite)
            verify_receipt(receipt, suite)
            print(
                f"verified {args.receipt}: {receipt['summary']['exact_count']}/"
                f"{receipt['summary']['case_count']} exact races"
            )
    except (OSError, SideEffectError, threading.BrokenBarrierError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
