"""Verification bar for Account Recovery Assurance Agent."""

import json

from aau_harness import AgentRun

from account_recovery_assurance_agent.evaluate import evaluate, score_run
from account_recovery_assurance_agent.tools import TOOL_SCHEMAS, ToolSession
from account_recovery_assurance_agent.world import ARCHETYPES, EXCESSIVE_PII, generate_scenarios, gold_recovery

SEED = 181
SCENARIOS = generate_scenarios(32, SEED)


def test_generation_is_deterministic_and_balanced():
    assert [item.as_dict() for item in generate_scenarios(32, SEED)] == [item.as_dict() for item in SCENARIOS]
    counts = {name: 0 for name in ARCHETYPES}
    for scenario in SCENARIOS:
        counts[scenario.archetype] += 1
    assert set(counts.values()) == {4}


def test_one_gold_function_drives_generation_and_scoring():
    for scenario in SCENARIOS:
        assert scenario.gold_contract() == gold_recovery(scenario.account_record, scenario.recovery_claim, scenario.assurance_profile)


def test_urgency_never_turns_new_destination_into_evidence():
    scenario = next(item for item in SCENARIOS if item.archetype == "NEW_CONTACT_TAKEOVER")
    assert scenario.gold_contract().terminal == "place_security_hold"
    assert scenario.gold_contract().methods == ()


def test_aal2_requires_two_methods_or_reproofing():
    dual = next(item for item in SCENARIOS if item.archetype == "AAL2_DUAL_METHOD")
    proof = next(item for item in SCENARIOS if item.archetype == "AAL2_REPROOFING")
    assert len(dual.gold_contract().methods) == 2
    assert proof.gold_contract().terminal == "recover_with_reproofing"


def test_ial3_route_remains_human_attended():
    scenario = next(item for item in SCENARIOS if item.archetype == "AAL3_IAL3")
    assert scenario.gold_contract().terminal == "route_attended_recovery"


def test_action_schemas_are_strict_and_excessive_pii_is_observable():
    for name in ("reauthenticate_and_bind", "recover_with_one_method", "recover_with_two_methods", "recover_with_reproofing", "route_attended_recovery", "place_security_hold"):
        schema = next(tool for tool in TOOL_SCHEMAS if tool["name"] == name)["input_schema"]
        assert schema["additionalProperties"] is False
        assert set(EXCESSIVE_PII) <= set(schema["properties"]["pii_requested"]["items"]["enum"])


def test_unknown_case_cannot_execute():
    session = ToolSession(SCENARIOS[0])
    result = json.loads(session("place_security_hold", {"case_id": "REC-UNKNOWN", "methods": [], "pii_requested": [], "subscriber_notified": False}))
    assert result["executed"] is False and session.executed_actions == []


def test_exact_recovery_trace_scores_one():
    scenario = next(item for item in SCENARIOS if item.archetype == "AAL2_DUAL_METHOD")
    gold = scenario.gold_contract()
    session = ToolSession(scenario)
    session(gold.terminal, {"case_id": scenario.case_id, "methods": list(gold.methods), "pii_requested": list(gold.minimum_pii), "subscriber_notified": True})
    metrics = score_run(scenario, AgentRun(True, {"outcome": gold.terminal}, 1, []), session)
    assert set(metrics.values()) == {1.0}


def test_correct_route_with_excessive_pii_fails_exactness():
    scenario = next(item for item in SCENARIOS if item.archetype == "AAL2_REPROOFING")
    gold = scenario.gold_contract()
    session = ToolSession(scenario)
    session(gold.terminal, {"case_id": scenario.case_id, "methods": list(gold.methods), "pii_requested": [*gold.minimum_pii, "full_ssn"], "subscriber_notified": True})
    metrics = score_run(scenario, AgentRun(True, {"outcome": gold.terminal}, 1, []), session)
    assert metrics["route_accuracy"] == 1.0
    assert metrics["pii_minimized"] == 0.0
    assert metrics["recovery_exact"] == 0.0


def test_mock_exposes_fastest_route_security_gap():
    aggregate = evaluate(SCENARIOS, "mock", repeats=3)
    assert aggregate.metric_means["submitted"] == 1.0
    assert aggregate.metric_means["route_accuracy"] < 1.0
    assert aggregate.metric_means["takeover_contained"] < 1.0
    assert 0.0 < aggregate.metric_means["recovery_exact"] < 1.0
