import copy
import json
import sys
from pathlib import Path

import pytest

from aau_harness.evaluate import command_adapter, mock_adapter
from aau_harness.release_gate import (
    ReleaseGateError,
    assess_release,
    build_pack,
    capture_manifest,
    diff_snapshots,
    load_json,
    run_impacted_suites,
    verify_pack,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "agent-release-gate" / "examples"
BASELINE = EXAMPLES / "baseline" / "release-manifest.json"
CANDIDATE = EXAMPLES / "candidate" / "release-manifest.json"
POLICY = EXAMPLES / "release-policy.json"
PLAN = EXAMPLES / "evidence-plan.json"
APPROVAL = EXAMPLES / "approval.json"
ADAPTER = EXAMPLES / "reference_adapter.py"


def _inputs(adapter_kind="command"):
    baseline = capture_manifest(BASELINE)
    candidate = capture_manifest(CANDIDATE)
    policy = load_json(POLICY)
    plan = load_json(PLAN)
    change = diff_snapshots(baseline, candidate)
    invoke = (
        command_adapter(f"{sys.executable} {ADAPTER}", 2)
        if adapter_kind == "command"
        else mock_adapter
    )
    receipts = run_impacted_suites(
        plan, PLAN, set(change["impacted_tags"]), invoke, adapter_kind
    )
    return baseline, candidate, policy, plan, receipts


def test_reference_change_is_exact_change_specific_and_human_owned():
    baseline, candidate, policy, plan, receipts = _inputs()
    decision, change = assess_release(
        baseline, candidate, policy, plan, receipts, "command", load_json(APPROVAL)
    )
    assert decision["status"] == "release_ready"
    assert change["impacted_tags"] == ["authority", "policy", "tools"]
    assert len(change["changes"]) == 3
    assert all(row["passes"] for row in decision["evidence"])
    assert decision["review"]["approval_identity_verified"] is False


def test_mock_self_test_can_never_authorize_release():
    baseline, candidate, policy, plan, receipts = _inputs("mock")
    decision, _ = assess_release(
        baseline, candidate, policy, plan, receipts, "mock", load_json(APPROVAL)
    )
    assert decision["status"] == "human_review_required"
    assert "MOCK_PROTOCOL_SELF_TEST_ONLY" in decision["reason_codes"]


def test_missing_approval_preserves_protected_human_boundary():
    baseline, candidate, policy, plan, receipts = _inputs()
    decision, _ = assess_release(
        baseline, candidate, policy, plan, receipts, "command", None
    )
    assert decision["status"] == "human_review_required"
    assert "PROTECTED_HUMAN_APPROVAL_REQUIRED" in decision["reason_codes"]


def test_failed_suite_blocks_even_when_approval_exists():
    baseline, candidate, policy, plan, receipts = _inputs()
    broken = copy.deepcopy(receipts)
    broken["aau-agent-release-conformance-v1"]["metrics"]["exact_rate"] = 0.5
    decision, _ = assess_release(
        baseline, candidate, policy, plan, broken, "command", load_json(APPROVAL)
    )
    assert decision["status"] == "release_blocked"
    assert any(code.startswith("SUITE_THRESHOLD_FAILED") for code in decision["reason_codes"])


def test_complete_pack_recomputes_and_tampering_fails(tmp_path):
    baseline, candidate, policy, plan, receipts = _inputs()
    pack = tmp_path / "pack"
    decision = build_pack(
        baseline,
        candidate,
        policy,
        plan,
        receipts,
        "command",
        load_json(APPROVAL),
        pack,
    )
    assert verify_pack(pack) == decision
    (pack / "release-decision.json").write_text("{}")
    with pytest.raises(ReleaseGateError, match="integrity mismatch"):
        verify_pack(pack)


def test_component_symlink_and_path_escape_are_rejected(tmp_path):
    source = json.loads(BASELINE.read_text())
    next(
        item for item in source["components"] if item["component_id"] == "authority-policy"
    )["source_path"] = "../outside.json"
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(json.dumps(source))
    with pytest.raises(ReleaseGateError, match="stay below"):
        capture_manifest(manifest)


def test_required_component_removal_fails_closed():
    baseline, candidate, policy, plan, receipts = _inputs()
    candidate = copy.deepcopy(candidate)
    candidate["components"] = [
        item for item in candidate["components"] if item["kind"] != "monitoring"
    ]
    unsigned = {key: value for key, value in candidate.items() if key != "snapshot_sha256"}
    from aau_harness.release_gate import digest

    candidate["snapshot_sha256"] = digest(unsigned)
    decision, _ = assess_release(
        baseline, candidate, policy, plan, receipts, "command", load_json(APPROVAL)
    )
    assert decision["status"] == "release_blocked"
    assert "REQUIRED_COMPONENT_MISSING:monitoring" in decision["reason_codes"]
