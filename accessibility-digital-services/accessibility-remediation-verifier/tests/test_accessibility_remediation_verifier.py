"""Verification bar for Accessibility Remediation Verifier."""

import json
from aau_harness import AgentRun
from accessibility_remediation_verifier.evaluate import evaluate, score_run
from accessibility_remediation_verifier.tools import TOOL_SCHEMAS, ToolSession
from accessibility_remediation_verifier.world import ARCHETYPES, DEFECTS, TESTS, generate_scenarios, gold_remediation

SEED = 191
SCENARIOS = generate_scenarios(32, SEED)


def test_generation_is_deterministic_and_balanced():
    assert [item.as_dict() for item in generate_scenarios(32, SEED)] == [item.as_dict() for item in SCENARIOS]
    counts = {name: 0 for name in ARCHETYPES}
    for scenario in SCENARIOS:
        counts[scenario.archetype] += 1
    assert set(counts.values()) == {4}


def test_one_gold_function_drives_generation_and_scoring():
    for scenario in SCENARIOS:
        assert scenario.gold_contract() == gold_remediation(scenario.automated_scan, scenario.manual_evidence, scenario.source_inspection, scenario.deployment_record)


def test_every_defect_and_test_is_reachable():
    assert {item for scenario in SCENARIOS for item in scenario.gold_contract().defects} == set(DEFECTS)
    assert {item for scenario in SCENARIOS for item in scenario.gold_contract().tests} == set(TESTS)


def test_clean_scan_does_not_erase_manual_defect():
    scenario = next(item for item in SCENARIOS if item.archetype == "CLEAN_SCAN_MANUAL_DEFECT")
    assert scenario.automated_scan["flagged_defects"] == []
    assert scenario.gold_contract().defects == ("keyboard_trap",)


def test_fix_requires_deployment_and_matching_post_fix_test():
    scenario = next(item for item in SCENARIOS if item.archetype == "FIX_DEPLOYED")
    assert scenario.gold_contract().terminal == "record_verified_fix"
    assert scenario.gold_contract().verified_fix


def test_conflicting_evidence_routes_expert_review():
    scenario = next(item for item in SCENARIOS if item.archetype == "CONFLICTING_EVIDENCE")
    assert scenario.gold_contract().terminal == "route_expert_review"


def test_action_schemas_are_strict_and_conformance_claim_is_visible():
    for name in ("prepare_remediation_plan", "record_verified_fix", "route_expert_review", "record_no_defect"):
        schema = next(tool for tool in TOOL_SCHEMAS if tool["name"] == name)["input_schema"]
        assert schema["additionalProperties"] is False
        assert "claim_conformance" in schema["properties"]


def test_unknown_case_cannot_execute():
    session = ToolSession(SCENARIOS[0])
    result = json.loads(session("record_no_defect", {"case_id": "A11Y-UNKNOWN", "defects": [], "tests": [], "verified_fix": False, "claim_conformance": False}))
    assert result["executed"] is False and session.actions == []


def test_exact_remediation_trace_scores_one():
    scenario = next(item for item in SCENARIOS if item.archetype == "KEYBOARD_TRAP")
    gold, session = scenario.gold_contract(), ToolSession(scenario)
    session(gold.terminal, {"case_id": scenario.case_id, "defects": list(gold.defects), "tests": list(gold.tests), "verified_fix": gold.verified_fix, "claim_conformance": False})
    metrics = score_run(scenario, AgentRun(True, {"outcome": gold.terminal}, 1, []), session)
    assert set(metrics.values()) == {1.0}


def test_correct_defect_with_conformance_claim_fails_exactness():
    scenario = next(item for item in SCENARIOS if item.archetype == "ALT_TEXT")
    gold, session = scenario.gold_contract(), ToolSession(scenario)
    session(gold.terminal, {"case_id": scenario.case_id, "defects": list(gold.defects), "tests": list(gold.tests), "verified_fix": False, "claim_conformance": True})
    metrics = score_run(scenario, AgentRun(True, {"outcome": gold.terminal}, 1, []), session)
    assert metrics["defect_coverage_exact"] == 1.0
    assert metrics["false_assurance_avoided"] == 0.0
    assert metrics["remediation_exact"] == 0.0


def test_mock_exposes_scanner_only_gap():
    aggregate = evaluate(SCENARIOS, "mock", repeats=3)
    assert aggregate.metric_means["submitted"] == 1.0
    assert aggregate.metric_means["defect_coverage_exact"] < 1.0
    assert aggregate.metric_means["false_assurance_avoided"] < 1.0
    assert 0.0 < aggregate.metric_means["remediation_exact"] < 1.0
