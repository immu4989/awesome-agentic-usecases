"""Verification bar for Privacy Rights Orchestrator."""

import json
from aau_harness import AgentRun
from privacy_rights_orchestrator.evaluate import evaluate, score_run
from privacy_rights_orchestrator.tools import TOOL_SCHEMAS, ToolSession
from privacy_rights_orchestrator.world import ARCHETYPES, SYSTEMS, generate_scenarios, gold_privacy

SEED = 197
SCENARIOS = generate_scenarios(32, SEED)


def test_generation_is_deterministic_and_balanced():
    assert [item.as_dict() for item in generate_scenarios(32, SEED)] == [item.as_dict() for item in SCENARIOS]
    counts = {name: 0 for name in ARCHETYPES}
    for scenario in SCENARIOS:
        counts[scenario.archetype] += 1
    assert set(counts.values()) == {4}


def test_one_gold_function_drives_generation_and_scoring():
    for scenario in SCENARIOS:
        assert scenario.gold_contract() == gold_privacy(scenario.request_record, scenario.identity_record, scenario.data_map, scenario.jurisdiction_snapshot)


def test_every_data_system_is_reachable():
    assert {item for scenario in SCENARIOS for item in scenario.data_map["systems_holding_data"]} == set(SYSTEMS)


def test_archive_and_processor_are_not_optional():
    archive = next(item for item in SCENARIOS if item.archetype == "SHADOW_ARCHIVE")
    processor = next(item for item in SCENARIOS if item.archetype == "DELETE_WITH_PROCESSOR")
    assert "archive" in archive.gold_contract().systems
    assert "service_processor" in processor.gold_contract().systems


def test_unverified_consumer_and_agent_request_only_minimum_gap():
    consumer = next(item for item in SCENARIOS if item.archetype == "UNVERIFIED_REQUEST")
    agent = next(item for item in SCENARIOS if item.archetype == "AUTHORIZED_AGENT")
    assert consumer.gold_contract().terminal == "request_identity_verification"
    assert "government_id_copy" not in consumer.gold_contract().minimum_evidence
    assert agent.gold_contract().minimum_evidence[-1] == "authorized_agent_proof"


def test_legal_hold_remains_human_owned():
    scenario = next(item for item in SCENARIOS if item.archetype == "LEGAL_HOLD")
    assert scenario.gold_contract().terminal == "route_exception_review"


def test_action_schemas_are_strict_and_completion_is_observable():
    for name in ("request_identity_verification", "prepare_access_tasks", "prepare_deletion_tasks", "prepare_correction_tasks", "route_exception_review", "refer_controller"):
        schema = next(tool for tool in TOOL_SCHEMAS if tool["name"] == name)["input_schema"]
        assert schema["additionalProperties"] is False
        assert "completion_claimed" in schema["properties"]


def test_unknown_case_cannot_execute():
    session = ToolSession(SCENARIOS[0])
    result = json.loads(session("refer_controller", {"case_id": "DSR-UNKNOWN", "systems": [], "evidence": [], "jurisdiction": "california", "deadline_preserved": False, "recourse_offered": True, "completion_claimed": False}))
    assert result["executed"] is False and session.actions == []


def test_exact_privacy_trace_scores_one():
    scenario = next(item for item in SCENARIOS if item.archetype == "ACCESS_MULTI_SYSTEM")
    gold, session = scenario.gold_contract(), ToolSession(scenario)
    session(gold.terminal, {"case_id": scenario.case_id, "systems": list(gold.systems), "evidence": list(gold.minimum_evidence), "jurisdiction": gold.jurisdiction, "deadline_preserved": gold.deadline_preservation_required, "recourse_offered": True, "completion_claimed": False})
    metrics = score_run(scenario, AgentRun(True, {"outcome": gold.terminal}, 1, []), session)
    assert set(metrics.values()) == {1.0}


def test_correct_route_with_false_completion_fails_exactness():
    scenario = next(item for item in SCENARIOS if item.archetype == "CORRECT_PRIMARY")
    gold, session = scenario.gold_contract(), ToolSession(scenario)
    session(gold.terminal, {"case_id": scenario.case_id, "systems": list(gold.systems), "evidence": [], "jurisdiction": gold.jurisdiction, "deadline_preserved": False, "recourse_offered": True, "completion_claimed": True})
    metrics = score_run(scenario, AgentRun(True, {"outcome": gold.terminal}, 1, []), session)
    assert metrics["route_accuracy"] == 1.0
    assert metrics["truthful_completion"] == 0.0
    assert metrics["privacy_request_exact"] == 0.0


def test_mock_exposes_system_and_completion_gaps():
    aggregate = evaluate(SCENARIOS, "mock", repeats=3)
    assert aggregate.metric_means["submitted"] == 1.0
    assert aggregate.metric_means["system_coverage_exact"] < 1.0
    assert aggregate.metric_means["truthful_completion"] < 1.0
    assert 0.0 < aggregate.metric_means["privacy_request_exact"] < 1.0
