"""Provider-neutral gateway for evaluating an existing agent.

An adapter receives one JSON object and returns one JSON object. Public receipts
contain aggregate measurements and scenario ids, never scenario inputs, expected
answers, adapter responses, environment variables, headers, or reasoning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SUITE_VERSION = "aau-byo-agent-suite/1.0"
RECEIPT_VERSION = "aau-byo-agent-receipt/1.0"
MAX_SUITE_BYTES = 2_000_000
MAX_RESPONSE_BYTES = 1_000_000
SAFE_CLASSIFICATIONS = {"public", "synthetic", "public_synthetic"}
SHARING_EXCLUSIONS = (
    "contains_personally_identifiable_information",
    "contains_procurement_sensitive_information",
    "contains_controlled_unclassified_information",
    "contains_classified_information",
    "contains_secrets_or_credentials",
)


@dataclass(frozen=True)
class AdapterResult:
    response: dict[str, Any]
    latency_s: float
    error: str | None = None


def load_suite(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_SUITE_BYTES:
        raise ValueError("suite exceeds the 2 MB limit")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("suite root must be an object")
    if value.get("suite_version") != SUITE_VERSION:
        raise ValueError(f"suite_version must be {SUITE_VERSION}")
    if not isinstance(value.get("suite_id"), str) or not value["suite_id"].strip():
        raise ValueError("suite_id is required")
    sharing = value.get("sharing")
    if not isinstance(sharing, dict):
        raise ValueError("sharing attestation is required")
    if sharing.get("classification") not in SAFE_CLASSIFICATIONS:
        raise ValueError("sharing.classification must be public or synthetic")
    if sharing.get("human_review_complete") is not True:
        raise ValueError("sharing.human_review_complete must be true")
    if any(sharing.get(field) is not False for field in SHARING_EXCLUSIONS):
        raise ValueError("all public sharing exclusions must be explicitly false")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("suite needs at least one case")
    ids = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{index}] must be an object")
        scenario_id = case.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ValueError(f"cases[{index}].scenario_id is required")
        ids.append(scenario_id)
        if not isinstance(case.get("input"), dict):
            raise ValueError(f"cases[{index}].input must be an object")
        expected = case.get("expected")
        if not isinstance(expected, dict) or not isinstance(
            expected.get("outcome"), str
        ):
            raise ValueError(f"cases[{index}].expected.outcome is required")
        forbidden = case.get("forbidden_actions", [])
        if not isinstance(forbidden, list) or not all(
            isinstance(item, str) for item in forbidden
        ):
            raise ValueError(
                f"cases[{index}].forbidden_actions must be a string list"
            )
    if len(ids) != len(set(ids)):
        raise ValueError("scenario ids must be unique")
    return value


def normalize_response(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("adapter response must be an object")
    outcome = value.get("outcome")
    if not isinstance(outcome, str) or not outcome:
        raise ValueError("adapter response needs a non-empty outcome")
    normalized = {
        "outcome": outcome,
        "actions_attempted": value.get("actions_attempted", []),
        "actions_executed": value.get("actions_executed", []),
        "submitted": value.get("submitted", True),
    }
    for field in ("actions_attempted", "actions_executed"):
        if not isinstance(normalized[field], list) or not all(
            isinstance(item, str) for item in normalized[field]
        ):
            raise ValueError(f"adapter response {field} must be a string list")
    if not isinstance(normalized["submitted"], bool):
        raise ValueError("adapter response submitted must be boolean")
    return normalized


def command_adapter(command: str, timeout_s: float) -> Callable[[dict], AdapterResult]:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("--command cannot be empty")

    def invoke(payload: dict) -> AdapterResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                argv,
                input=(json.dumps(payload) + "\n").encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s,
                check=False,
                shell=False,
            )
            if len(completed.stdout) > MAX_RESPONSE_BYTES:
                raise ValueError("adapter response exceeds the 1 MB limit")
            if completed.returncode != 0:
                return AdapterResult(
                    {},
                    time.monotonic() - started,
                    f"adapter-exit-{completed.returncode}",
                )
            return AdapterResult(
                normalize_response(json.loads(completed.stdout)),
                time.monotonic() - started,
            )
        except subprocess.TimeoutExpired:
            return AdapterResult(
                {}, time.monotonic() - started, "adapter-timeout"
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return AdapterResult(
                {}, time.monotonic() - started, "adapter-invalid-response"
            )

    return invoke


def endpoint_adapter(endpoint: str, timeout_s: float) -> Callable[[dict], AdapterResult]:
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("--endpoint must use http:// or https://")

    def invoke(payload: dict) -> AdapterResult:
        started = time.monotonic()
        request = urllib.request.Request(
            endpoint,
            data=(json.dumps(payload) + "\n").encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("adapter response exceeds the 1 MB limit")
            return AdapterResult(
                normalize_response(json.loads(raw)),
                time.monotonic() - started,
            )
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            ValueError,
        ):
            return AdapterResult(
                {}, time.monotonic() - started, "adapter-invalid-response"
            )

    return invoke


def mock_adapter(payload: dict) -> AdapterResult:
    expected = payload["_expected_outcome_for_protocol_self_test"]
    return AdapterResult(
        {
            "outcome": expected,
            "actions_attempted": [],
            "actions_executed": [],
            "submitted": True,
        },
        0.0,
    )


def evaluate_suite(
    suite: dict[str, Any],
    invoke: Callable[[dict], AdapterResult],
    adapter_kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    results = []
    private = []
    for case in suite["cases"]:
        payload = {
            "protocol_version": "aau-byo-agent-request/1.0",
            "suite_id": suite["suite_id"],
            "scenario_id": case["scenario_id"],
            "input": case["input"],
        }
        if invoke is mock_adapter:
            result = invoke(
                {
                    **payload,
                    "_expected_outcome_for_protocol_self_test": case["expected"][
                        "outcome"
                    ],
                }
            )
        else:
            result = invoke(payload)
        forbidden = set(case.get("forbidden_actions", []))
        response = result.response
        submitted = bool(response.get("submitted")) if not result.error else False
        outcome_exact = bool(
            submitted
            and response.get("outcome") == case["expected"]["outcome"]
        )
        no_forbidden_attempt = not bool(
            forbidden & set(response.get("actions_attempted", []))
        )
        no_forbidden_execute = not bool(
            forbidden & set(response.get("actions_executed", []))
        )
        exact = (
            outcome_exact
            and no_forbidden_attempt
            and no_forbidden_execute
        )
        failure_codes = []
        if result.error:
            failure_codes.append(result.error)
        if not submitted:
            failure_codes.append("not-submitted")
        if submitted and not outcome_exact:
            failure_codes.append("outcome-mismatch")
        if not no_forbidden_attempt:
            failure_codes.append("forbidden-action-attempt")
        if not no_forbidden_execute:
            failure_codes.append("forbidden-action-executed")
        results.append(
            {
                "scenario_id": case["scenario_id"],
                "submitted": submitted,
                "outcome_exact": outcome_exact,
                "no_forbidden_attempt": no_forbidden_attempt,
                "no_forbidden_execute": no_forbidden_execute,
                "exact": exact,
                "latency_s": round(result.latency_s, 6),
                "failure_codes": failure_codes,
            }
        )
        private.append(
            {
                "scenario_id": case["scenario_id"],
                "input": case["input"],
                "expected": case["expected"],
                "forbidden_actions": case.get("forbidden_actions", []),
                "response": response,
                "error": result.error,
            }
        )
    count = len(results)

    def mean(field: str) -> float:
        return sum(bool(item[field]) for item in results) / count

    public = {
        "receipt_version": RECEIPT_VERSION,
        "suite_id": suite["suite_id"],
        "suite_sha256": hashlib.sha256(
            (json.dumps(suite, sort_keys=True, separators=(",", ":")) + "\n").encode()
        ).hexdigest(),
        "adapter_kind": adapter_kind,
        "scenario_count": count,
        "metrics": {
            "submitted_rate": round(mean("submitted"), 6),
            "outcome_exact_rate": round(mean("outcome_exact"), 6),
            "no_forbidden_attempt_rate": round(
                mean("no_forbidden_attempt"), 6
            ),
            "no_forbidden_execute_rate": round(
                mean("no_forbidden_execute"), 6
            ),
            "exact_rate": round(mean("exact"), 6),
            "mean_latency_s": round(
                sum(item["latency_s"] for item in results) / count, 6
            ),
        },
        "results": results,
        "privacy": {
            "scenario_inputs_included": False,
            "expected_answers_included": False,
            "adapter_responses_included": False,
            "reasoning_included": False,
            "credentials_included": False,
            "suite_sharing_attested": True,
        },
        "boundary": (
            "This receipt measures the declared suite and adapter response "
            "contract. It is not production validation, certification, model "
            "ranking, legal advice, or permission to automate protected decisions."
        ),
    }
    private_record = {
        "private_receipt_version": "aau-byo-agent-private-detail/1.0",
        "suite_id": suite["suite_id"],
        "results": private,
        "warning": (
            "Private details may contain sensitive adapter inputs or outputs. "
            "Do not commit or publish without authorized review."
        ),
    }
    return public, private_record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aau evaluate",
        description="Evaluate an existing agent through a JSON command or endpoint adapter.",
    )
    parser.add_argument("suite", type=Path)
    adapter = parser.add_mutually_exclusive_group(required=True)
    adapter.add_argument("--command", help="argv string; JSON request on stdin, JSON response on stdout")
    adapter.add_argument("--endpoint", help="HTTP endpoint accepting a JSON POST request")
    adapter.add_argument("--mock", action="store_true", help="deterministic protocol self-test")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out", type=Path, help="write aggregate public receipt")
    parser.add_argument(
        "--private-out",
        type=Path,
        help="write unredacted local detail; never publish without review",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        suite = load_suite(args.suite)
        if args.command:
            invoke = command_adapter(args.command, args.timeout)
            kind = "command"
        elif args.endpoint:
            invoke = endpoint_adapter(args.endpoint, args.timeout)
            kind = "endpoint"
        else:
            invoke = mock_adapter
            kind = "mock"
        receipt, private = evaluate_suite(suite, invoke, kind)
        rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered)
        else:
            print(rendered, end="")
        if args.private_out:
            args.private_out.parent.mkdir(parents=True, exist_ok=True)
            args.private_out.write_text(
                json.dumps(private, indent=2, sort_keys=True) + "\n"
            )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"aau evaluate: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
