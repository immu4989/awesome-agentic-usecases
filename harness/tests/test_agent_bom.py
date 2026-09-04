import copy
import json
import sys
from pathlib import Path

import pytest

from aau_harness.agent_bom import (
    AgentBomError,
    build_pack,
    diff_boms,
    evaluate_authority_case,
    generate_conformance_suite,
    load_json,
    plan_authority_reduction,
    review_bom,
    run_conformance,
    to_cyclonedx,
    validate_bom,
    validate_observation,
    verify_pack,
    verify_conformance_receipt,
    verify_reduction_plan,
)


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "agent-capability-bom" / "examples" / "baseline.json"
CANDIDATE = ROOT / "agent-capability-bom" / "examples" / "candidate.json"
OBSERVATION = ROOT / "agent-capability-bom" / "examples" / "authority-observation.json"
CONFORMANCE_ADAPTER = (
    ROOT / "agent-capability-bom" / "examples" / "reference_conformance_adapter.py"
)
CONFORMANCE_SCHEMAS = (
    ROOT / "agent-capability-bom" / "authority-conformance-suite.schema.json",
    ROOT / "agent-capability-bom" / "authority-conformance-receipt.schema.json",
)


def fixtures():
    return load_json(BASELINE), load_json(CANDIDATE)


def test_reference_boms_are_strict_and_cross_referenced():
    before, after = fixtures()
    validate_bom(before)
    validate_bom(after)
    assert review_bom(after)["status"] == "human_review_required"


def test_diff_surfaces_every_authority_widening_without_a_trust_score():
    result = diff_boms(*fixtures())
    assert result["status"] == "review_required"
    assert result["finding_count"] == 9
    assert {row["code"] for row in result["findings"]} == {
        "TOOL_SIDE_EFFECT_INCREASED",
        "TOOL_OPERATION_ADDED",
        "TOOL_SCOPE_ADDED",
        "AUTHORITY_OPERATION_ADDED",
        "AUTHORITY_SCOPE_ADDED",
        "TOOL_OPERATION_SCOPE_BINDING_ADDED",
        "AUTHORITY_OPERATION_SCOPE_BINDING_ADDED",
    }
    assert result["blocking_count"] == 0


def test_removing_protected_human_approval_is_a_blocking_boundary_loss():
    before, after = fixtures()
    after = copy.deepcopy(after)
    after["authorities"][1]["human_approval_required"] = False
    result = diff_boms(before, after)
    assert result["status"] == "blocking_boundary_loss"
    assert "HUMAN_APPROVAL_REMOVED" in {row["code"] for row in result["findings"]}


def test_unknown_tool_and_excess_scope_fail_closed():
    _, after = fixtures()
    unknown = copy.deepcopy(after)
    unknown["authorities"][0]["tool_ids"] = ["missing-tool"]
    with pytest.raises(AgentBomError, match="unknown tools"):
        validate_bom(unknown)
    excess = copy.deepcopy(after)
    excess["authorities"][0]["resource_scopes"].append("secret/*")
    with pytest.raises(AgentBomError, match="exceeds declared resource scopes"):
        validate_bom(excess)


def test_operation_scope_relationships_are_exact_and_fail_closed():
    _, bom = fixtures()
    request = {
        "authority_id": "records-read-lease",
        "tool_id": "records-catalog",
        "operation": "records.prepare_draft",
        "resource_scope": "cases/public/*",
        "evaluated_at": "2026-08-30T19:07:30Z",
        "revoked": False,
        "delegation_depth": 0,
        "human_approval_present": True,
    }
    assert evaluate_authority_case(bom, request) == (
        "block",
        ["AUTHORITY_OPERATION_SCOPE_UNBOUND"],
    )
    inconsistent = copy.deepcopy(bom)
    inconsistent["authorities"][0]["operation_scope_bindings"].append(
        {
            "tool_id": "records-catalog",
            "operation": "records.search",
            "resource_scopes": ["cases/public/drafts/*"],
        }
    )
    with pytest.raises(AgentBomError, match="tool-operation pairs must be unique"):
        validate_bom(inconsistent)


def test_allowed_observation_cannot_cross_an_unbound_relationship():
    bom = load_json(CANDIDATE)
    observation = load_json(OBSERVATION)
    escaped = copy.deepcopy(observation)
    escaped["events"][0]["operation"] = "records.prepare_draft"
    with pytest.raises(AgentBomError, match="exceeds declared authority relationship"):
        validate_observation(escaped, bom)


def test_public_profile_cannot_claim_production_identity_or_credentials():
    _, after = fixtures()
    claimed = copy.deepcopy(after)
    claimed["accountability"]["production_identity_verified"] = True
    with pytest.raises(AgentBomError, match="cannot claim verified production identity"):
        validate_bom(claimed)
    unsafe = copy.deepcopy(after)
    unsafe["sharing"]["contains_credentials"] = True
    with pytest.raises(AgentBomError, match="contains_credentials"):
        validate_bom(unsafe)


def test_cyclonedx_projection_preserves_agent_fields_as_namespaced_properties():
    _, after = fixtures()
    projected = to_cyclonedx(after)
    assert projected["bomFormat"] == "CycloneDX"
    assert projected["specVersion"] == "1.7"
    assert any(row["type"] == "machine-learning-model" for row in projected["components"])
    properties = {row["name"]: row["value"] for row in projected["properties"]}
    assert properties["aau:agent:inventory-is-not-authorization"] == "true"


def test_pack_is_deterministic_recomputable_and_tamper_evident(tmp_path):
    _, after = fixtures()
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_pack(after, first)
    build_pack(after, second)
    assert {
        path.name: path.read_bytes() for path in first.iterdir()
    } == {path.name: path.read_bytes() for path in second.iterdir()}
    assert verify_pack(first)["status"] == "human_review_required"
    (first / "authority-review.json").write_text(json.dumps({"tampered": True}))
    with pytest.raises(AgentBomError, match="integrity mismatch"):
        verify_pack(first)


def test_least_authority_plan_finds_negative_space_but_removes_nothing():
    bom = load_json(CANDIDATE)
    observation = load_json(OBSERVATION)
    validate_observation(observation, bom)
    plan = plan_authority_reduction(bom, observation)
    assert plan["status"] == "proposal_only"
    assert plan["summary"] == {
        "granted_operation_count": 3,
        "observed_operation_count": 2,
        "unobserved_operation_count": 1,
        "granted_scope_count": 3,
        "observed_scope_count": 2,
        "unobserved_scope_count": 1,
        "granted_operation_scope_binding_count": 3,
        "observed_operation_scope_binding_count": 2,
        "unobserved_operation_scope_binding_count": 1,
        "candidate_authority_count": 1,
        "automatically_removed_count": 0,
    }
    candidate = next(row for row in plan["authority_reviews"] if row["candidate_reduction"])
    assert candidate["unobserved_operations"] == ["records.prepare_draft"]
    assert candidate["unobserved_resource_scopes"] == ["cases/public/drafts/*"]
    assert candidate["unobserved_operation_scope_bindings"] == [
        {
            "tool_id": "records-catalog",
            "operation": "records.prepare_draft",
            "resource_scope": "cases/public/drafts/*",
        }
    ]
    assert candidate["blocked_or_error_event_count"] == 1
    assert len(candidate["required_next_evidence"]) == 6


def test_blocked_attempt_does_not_count_as_authority_use():
    plan = plan_authority_reduction(load_json(CANDIDATE), load_json(OBSERVATION))
    candidate = next(row for row in plan["authority_reviews"] if row["candidate_reduction"])
    assert "records.prepare_draft" not in candidate["observed_operations"]


def test_allowed_event_outside_authority_and_false_coverage_fail_closed():
    bom = load_json(CANDIDATE)
    observation = load_json(OBSERVATION)
    escaped = copy.deepcopy(observation)
    escaped["events"][-1]["decision"] = "allowed"
    escaped_bom = copy.deepcopy(bom)
    escaped_bom["authorities"][0]["operations"] = ["records.search"]
    escaped_bom["authorities"][0]["resource_scopes"] = ["cases/public/*"]
    escaped_bom["authorities"][0]["operation_scope_bindings"] = [
        {
            "tool_id": "records-catalog",
            "operation": "records.search",
            "resource_scopes": ["cases/public/*"],
        }
    ]
    with pytest.raises(AgentBomError, match="allowed event .* exceeds declared authority"):
        validate_observation(escaped, escaped_bom)
    wrong_count = copy.deepcopy(observation)
    wrong_count["window"]["run_count"] = 4
    with pytest.raises(AgentBomError, match="run_count does not match"):
        validate_observation(wrong_count, bom)


def test_reduction_plan_recomputes_and_input_drift_is_detected():
    bom = load_json(CANDIDATE)
    observation = load_json(OBSERVATION)
    plan = plan_authority_reduction(bom, observation)
    verify_reduction_plan(plan, bom, observation)
    drifted = copy.deepcopy(plan)
    drifted["summary"]["automatically_removed_count"] = 1
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_reduction_plan(drifted, bom, observation)


def test_inventory_compiles_to_clean_and_single_boundary_twins():
    bom = load_json(CANDIDATE)
    suite = generate_conformance_suite(bom)
    assert len(suite["cases"]) == 19
    assert sum(row["clean_twin"] for row in suite["cases"]) == 3
    assert sum(not row["clean_twin"] for row in suite["cases"]) == 16
    assert all(
        len(row["expected_reason_codes"]) == 1
        for row in suite["cases"]
        if not row["clean_twin"]
    )
    assert {row["shape"] for row in suite["cases"]} >= {
        "legitimate_clean_twin",
        "not_yet_valid",
        "expired",
        "revoked",
        "delegation_depth_exceeded",
        "human_approval_missing",
        "operation_outside_tool",
        "scope_outside_tool",
        "authority_operation_scope_unbound",
    }


def test_reference_and_command_conformance_are_exact_and_privacy_bounded():
    bom = load_json(CANDIDATE)
    suite = generate_conformance_suite(bom)
    reference = run_conformance(bom, suite, "reference")
    assert reference["status"] == "evidence_passed"
    assert reference["metrics"] == {
        "case_count": 19,
        "clean_twin_count": 3,
        "violation_twin_count": 16,
        "exact_count": 19,
        "unsafe_allow_count": 0,
        "legitimate_block_count": 0,
    }
    verify_conformance_receipt(reference, bom, suite)
    command = run_conformance(
        bom, suite, "command", f"{sys.executable} {CONFORMANCE_ADAPTER}"
    )
    assert command["metrics"] == reference["metrics"]
    assert command["boundary"]["reference_adapter_is_protocol_self_test_only"] is False
    verify_conformance_receipt(command, bom, suite)


def test_deny_all_is_caught_by_legitimate_twins(tmp_path):
    adapter = tmp_path / "deny_all.py"
    adapter.write_text(
        "import json,sys\njson.load(sys.stdin)\n"
        "json.dump({'decision':'block','reason_codes':['DENY_ALL']},sys.stdout)\n"
    )
    bom = load_json(CANDIDATE)
    suite = generate_conformance_suite(bom)
    receipt = run_conformance(bom, suite, "command", f"{sys.executable} {adapter}")
    assert receipt["status"] == "evidence_failed"
    assert receipt["metrics"]["legitimate_block_count"] == 3
    verify_conformance_receipt(receipt, bom, suite)


def test_conformance_suite_and_receipt_drift_fail_closed():
    bom = load_json(CANDIDATE)
    suite = generate_conformance_suite(bom)
    drifted_suite = copy.deepcopy(suite)
    drifted_suite["cases"][0]["expected_decision"] = "block"
    with pytest.raises(AgentBomError, match="suite does not recompute"):
        run_conformance(bom, drifted_suite, "reference")
    receipt = run_conformance(bom, suite, "reference")
    receipt["results"][0]["exact"] = False
    with pytest.raises(AgentBomError, match="exactness does not recompute"):
        verify_conformance_receipt(receipt, bom, suite)


def test_conformance_transport_schemas_are_strict_and_receipt_identity_is_bound():
    for path in CONFORMANCE_SCHEMAS:
        schema = json.loads(path.read_text())
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
    bom = load_json(CANDIDATE)
    suite = generate_conformance_suite(bom)
    receipt = run_conformance(bom, suite, "reference")
    receipt["release_id"] = "different-release"
    with pytest.raises(AgentBomError, match="identity binding mismatch"):
        verify_conformance_receipt(receipt, bom, suite)
