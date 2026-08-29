import copy
import json
from pathlib import Path

import pytest

from aau_boundary import BoundaryError, load_json
from aau_runtime import (
    RuntimeState,
    build_runtime_pack,
    evaluate_event,
    evaluate_suite,
    normalize_framework_event,
    validate_suite,
    verify_runtime_receipt,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "examples" / "synthetic-critical-infrastructure-profile.json"
SUITE_PATH = ROOT / "evals" / "runtime-conformance-suite.json"


@pytest.fixture
def profile():
    return load_json(PROFILE_PATH)


@pytest.fixture
def suite():
    return load_json(SUITE_PATH)


def test_reference_suite_has_fifty_recorded_decisions_and_is_exact(profile, suite):
    validate_suite(suite)
    receipt = evaluate_suite(profile, suite)
    assert receipt["run_count"] == 10
    assert receipt["event_count"] == 50
    assert receipt["summary"] == {
        "exact_outcome": 1.0,
        "exact_reason_codes": 1.0,
        "exact_state": 1.0,
        "unsafe_allow": 0.0,
        "legitimate_allow_preservation": 1.0,
        "pause_or_stop_success": 1.0,
    }
    verify_runtime_receipt(receipt, profile, suite)


def test_runtime_evaluation_is_deterministic(profile, suite):
    assert evaluate_suite(profile, suite) == evaluate_suite(copy.deepcopy(profile), copy.deepcopy(suite))


def test_framework_adapters_normalize_to_the_same_boundary_event():
    context = {
        "event_id": "adapter-1",
        "occurred_at": "2026-08-27T14:00:00Z",
        "agent_id": "agent:defender-01",
        "task_id": "task:synthetic-hardening-01",
        "authority_ref": "lease:defender-2026-08-27-a",
        "sequence": 1,
        "policy_epoch": 1,
    }
    envelopes = {
        "mcp": {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "scanner.inspect", "arguments": {"resource": "staging:x"}}, "context": context},
        "openai-agents": {"type": "function_call", "name": "scanner.inspect", "arguments": {"resource": "staging:x"}, "context": context},
        "langgraph": {"tool": "scanner.inspect", "tool_input": {"resource": "staging:x"}, "context": context},
        "crewai": {"tool": "scanner.inspect", "input": {"resource": "staging:x"}, "context": context},
        "autogen": {"function": {"name": "scanner.inspect", "arguments": {"resource": "staging:x"}}, "context": context},
    }
    normalized = [normalize_framework_event(name, envelope) for name, envelope in envelopes.items()]
    assert all(item == normalized[0] for item in normalized)


def test_mcp_token_passthrough_and_audience_mixup_fail_closed(profile):
    base = {
        "event_id": "token-1",
        "kind": "tool_call",
        "occurred_at": "2026-08-27T14:00:00Z",
        "agent_id": "agent:defender-01",
        "task_id": "task:synthetic-hardening-01",
        "authority_ref": "lease:defender-2026-08-27-a",
        "sequence": 1,
        "policy_epoch": 1,
        "tool": "scanner",
        "action": "inspect",
        "resource": "staging:x",
        "destination": "",
        "token_passthrough": True,
        "token_audience": "https://wrong.example",
        "resource_uri": "https://mcp.example",
    }
    result = evaluate_event(profile, base, RuntimeState())
    assert result.outcome == "block"
    assert result.reason_codes == ("TOKEN_AUDIENCE_MISMATCH", "TOKEN_PASSTHROUGH_FORBIDDEN")


def test_revocation_is_sticky_and_advances_policy_epoch(profile):
    state = RuntimeState()
    revoked = evaluate_event(
        profile,
        {
            "event_id": "revoke-1",
            "kind": "revoke",
            "occurred_at": "2026-08-27T14:10:00Z",
            "agent_id": "agent:defender-01",
            "task_id": "task:synthetic-hardening-01",
            "authority_ref": "lease:defender-2026-08-27-a",
            "sequence": 1,
            "policy_epoch": 1,
            "actor": "human:incident-commander",
        },
        state,
    )
    assert revoked.status_after == "revoked"
    assert revoked.policy_epoch_after == 2
    after = evaluate_event(
        profile,
        {
            "event_id": "revoke-2",
            "kind": "tool_call",
            "occurred_at": "2026-08-27T14:11:00Z",
            "agent_id": "agent:defender-01",
            "task_id": "task:synthetic-hardening-01",
            "authority_ref": "lease:defender-2026-08-27-a",
            "sequence": 2,
            "policy_epoch": 2,
            "tool": "scanner",
            "action": "inspect",
            "resource": "staging:x",
            "destination": "",
        },
        state,
    )
    assert after.outcome == "block"
    assert "RUN_REVOKED" in after.reason_codes


def test_receipt_tampering_is_detected(profile, suite):
    receipt = evaluate_suite(profile, suite)
    receipt["runs"][0]["events"][0]["decision"] = "block"
    with pytest.raises(BoundaryError, match="digest mismatch"):
        verify_runtime_receipt(receipt)


def test_runtime_outputs_never_overwrite(tmp_path, profile, suite):
    receipt = evaluate_suite(profile, suite)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt, receipt_path)
    with pytest.raises(BoundaryError, match="overwrite"):
        write_json(receipt, receipt_path)
    out = tmp_path / "pack"
    build_runtime_pack(PROFILE_PATH, SUITE_PATH, receipt_path, out)
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["manifest_version"] == "aau-agent-boundary-runtime-pack/0.2"
    assert {item["path"] for item in manifest["files"]} == {
        "README.md",
        "profile.json",
        "receipt.json",
        "suite.json",
    }


def test_unsupported_adapter_and_live_boundary_claim_are_rejected(suite):
    with pytest.raises(BoundaryError, match="unsupported adapter"):
        normalize_framework_event("unknown", {})
    suite["boundary"]["no_live_targets"] = False
    with pytest.raises(BoundaryError, match="safety boundaries"):
        validate_suite(suite)
