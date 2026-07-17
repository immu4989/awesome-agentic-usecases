import json

import pytest

from aau_harness import CostTracker, run_tool_agent
from exception_triage_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from exception_triage_agent.evaluate import evaluate, score_run
from exception_triage_agent.tools import TOOL_SCHEMAS, execute_tool
from exception_triage_agent.world import (
    generate_scenarios,
    gold_triage,
    search_policy,
)


def test_generator_is_deterministic():
    a = [s.as_dict() for s in generate_scenarios(n=30, seed=7)]
    b = [s.as_dict() for s in generate_scenarios(n=30, seed=7)]
    assert a == b
    assert [s["scenario_id"] for s in a] != [
        s.scenario_id for s in generate_scenarios(n=30, seed=8)
    ] or a != [s.as_dict() for s in generate_scenarios(n=30, seed=8)]


def test_gold_rules_cover_all_actions():
    scenarios = generate_scenarios(n=60, seed=7)
    actions = {s.gold_action for s in scenarios}
    assert actions == {"auto_resolve", "route_to_queue", "escalate_to_human"}
    queues = {s.gold_queue for s in scenarios}
    assert len(queues) == 5


def test_gold_platinum_sla_escalation():
    shipment = {
        "exception_code": "WEATHER_DELAY",
        "value_usd": 100.0,
        "customer_tier": "platinum",
        "sla_hours_remaining": 5,
        "has_validated_address_candidate": False,
    }
    queue, action = gold_triage(shipment)
    assert queue == "customer-notification"
    assert action == "escalate_to_human"


def test_tools_answer_only_for_this_scenario():
    sc = generate_scenarios(n=1, seed=7)[0]
    ok = json.loads(execute_tool("lookup_shipment", {"tracking_id": sc.tracking_id}, sc))
    assert ok["exception_code"] == sc.shipment["exception_code"]
    miss = json.loads(execute_tool("lookup_shipment", {"tracking_id": "XX000"}, sc))
    assert "error" in miss


def test_policy_search_finds_escalation_thresholds():
    docs = search_policy("escalation value threshold")
    assert any(d["id"] == "POL-ESC-01" for d in docs)


def test_tool_schemas_are_strict():
    for schema in TOOL_SCHEMAS:
        assert schema["strict"] is True
        assert schema["input_schema"]["additionalProperties"] is False
        assert set(schema["input_schema"]["required"]) == set(
            schema["input_schema"]["properties"]
        )


def test_mock_agent_end_to_end_submits():
    sc = generate_scenarios(n=6, seed=7)[0]
    cost = CostTracker(model="mock")
    run = run_tool_agent(
        MockBackend(), SYSTEM_PROMPT, TOOL_SCHEMAS, sc.ticket_text,
        lambda n, i: execute_tool(n, i, sc), SUBMIT_TOOL, cost,
    )
    assert run.submitted
    assert run.submission["queue"] == sc.gold_queue
    assert cost.api_calls == run.n_turns
    assert [c["name"] for c in run.tool_calls][:3] == [
        "lookup_shipment",
        "get_carrier_status",
        "search_policy",
    ]


def test_mock_eval_accuracy_band():
    scenarios = generate_scenarios(n=30, seed=7)
    agg = evaluate(scenarios, backend_kind="mock", repeats=2)
    # queue mapping is exact for the mock; the deliberate policy gap only hurts action
    assert agg.metric_means["queue_accuracy"] == 1.0
    assert 0.6 <= agg.metric_means["action_accuracy"] < 1.0
    assert agg.metric_means["submitted"] == 1.0
    assert agg.total_cost_usd == 0.0


def test_score_run_unsubmitted_is_zero():
    sc = generate_scenarios(n=1, seed=7)[0]

    class Dead:
        submitted = False
        submission = None

    metrics = score_run(sc, Dead())
    assert metrics == {
        "queue_accuracy": 0.0,
        "action_accuracy": 0.0,
        "exact_match": 0.0,
        "submitted": 0.0,
    }


def test_generator_includes_platinum_sla_cases():
    scenarios = generate_scenarios(n=30, seed=7)
    gap_cases = [
        s
        for s in scenarios
        if s.gold_action == "escalate_to_human" and s.shipment["value_usd"] <= 2000
    ]
    assert gap_cases, "need at least one platinum/SLA escalation to exercise the policy gap"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
