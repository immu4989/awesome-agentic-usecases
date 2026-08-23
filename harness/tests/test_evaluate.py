import json
import sys
from pathlib import Path

import pytest

from aau_harness.evaluate import (
    AdapterResult,
    RECEIPT_VERSION,
    command_adapter,
    evaluate_suite,
    load_suite,
    mock_adapter,
    normalize_response,
)


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "harness/examples/byo-agent-suite.json"
ADAPTER = ROOT / "harness/examples/byo_agent_adapter.py"


def test_example_suite_runs_through_public_protocol():
    suite = load_suite(SUITE)
    receipt, private = evaluate_suite(suite, mock_adapter, "mock")
    assert receipt["receipt_version"] == RECEIPT_VERSION
    assert receipt["scenario_count"] == 3
    assert set(receipt["metrics"].values()) == {0.0, 1.0}
    assert receipt["privacy"]["suite_sharing_attested"] is True
    assert all(
        value is False
        for key, value in receipt["privacy"].items()
        if key != "suite_sharing_attested"
    )
    serialized = json.dumps(receipt)
    assert "Where can I find" not in serialized
    assert "expected_outcome" not in serialized
    assert all("input" not in item for item in receipt["results"])
    assert len(private["results"]) == 3


def test_command_adapter_uses_argv_without_shell():
    suite = load_suite(SUITE)
    invoke = command_adapter(f"{sys.executable} {ADAPTER}", 2)
    receipt, _ = evaluate_suite(suite, invoke, "command")
    assert receipt["metrics"]["exact_rate"] == 1.0
    assert receipt["adapter_kind"] == "command"


def test_forbidden_attempt_fails_exactness():
    suite = load_suite(SUITE)
    expected = {
        item["scenario_id"]: item["expected"]["outcome"] for item in suite["cases"]
    }

    def unsafe(payload):
        return AdapterResult(
            {
                "outcome": expected[payload["scenario_id"]],
                "actions_attempted": ["determine_eligibility"],
                "actions_executed": [],
                "submitted": True,
            },
            0.0,
        )

    receipt, _ = evaluate_suite(suite, unsafe, "test")
    assert receipt["metrics"]["exact_rate"] == 0.0
    assert receipt["metrics"]["no_forbidden_execute_rate"] == 1.0
    assert all(
        "forbidden-action-attempt" in item["failure_codes"]
        for item in receipt["results"]
    )


def test_duplicate_scenario_id_is_rejected(tmp_path):
    suite = json.loads(SUITE.read_text())
    suite["cases"][1]["scenario_id"] = suite["cases"][0]["scenario_id"]
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite))
    with pytest.raises(ValueError, match="scenario ids must be unique"):
        load_suite(path)


def test_invalid_adapter_response_is_rejected():
    with pytest.raises(ValueError, match="outcome"):
        normalize_response({"submitted": True})


def test_suite_without_public_sharing_attestation_is_rejected(tmp_path):
    suite = json.loads(SUITE.read_text())
    del suite["sharing"]
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite))
    with pytest.raises(ValueError, match="sharing attestation"):
        load_suite(path)


def test_public_adapter_request_does_not_disclose_the_oracle():
    suite = load_suite(SUITE)
    expected = {
        item["scenario_id"]: item["expected"]["outcome"] for item in suite["cases"]
    }
    requests = []

    def inspect(payload):
        requests.append(payload)
        return AdapterResult(
            {
                "outcome": expected[payload["scenario_id"]],
                "actions_attempted": [],
                "actions_executed": [],
                "submitted": True,
            },
            0.0,
        )

    receipt, _ = evaluate_suite(suite, inspect, "test")
    serialized = json.dumps(requests)
    assert receipt["metrics"]["exact_rate"] == 1.0
    assert "expected" not in serialized
    assert "forbidden" not in serialized
    assert all(set(request) == {"protocol_version", "suite_id", "scenario_id", "input"} for request in requests)
