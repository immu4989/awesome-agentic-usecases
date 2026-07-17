import json

import pytest

from aau_harness import CostTracker, run_tool_agent
from alert_triage_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from alert_triage_agent.evaluate import evaluate, score_run
from alert_triage_agent.tools import TOOL_SCHEMAS, execute_tool
from alert_triage_agent.world import (
    generate_scenarios,
    gold_triage,
    search_runbook,
)


def test_generator_is_deterministic():
    a = [s.as_dict() for s in generate_scenarios(n=30, seed=13)]
    b = [s.as_dict() for s in generate_scenarios(n=30, seed=13)]
    assert a == b


def test_gold_rules_cover_queues_and_dispositions():
    scenarios = generate_scenarios(n=90, seed=13)
    assert {s.gold_queue for s in scenarios} == {
        "phishing", "malware", "credential-abuse", "false-positive"
    }
    assert {s.gold_disposition for s in scenarios} == {
        "auto_close", "route_to_analyst", "escalate_to_incident"
    }


def test_benign_crown_jewel_exception():
    asset = {"criticality": "crown_jewel", "privilege": "standard"}
    events = {"known_benign_source": True}
    queue, disposition = gold_triage("SCANNER_NOISE", asset, events)
    assert queue == "false-positive"
    assert disposition == "route_to_analyst"  # NOT auto_close — RB-FP-02 exception

    asset_std = {"criticality": "standard", "privilege": "standard"}
    _, disposition_std = gold_triage("SCANNER_NOISE", asset_std, events)
    assert disposition_std == "auto_close"


def test_admin_identity_escalates_active_threat():
    asset = {"criticality": "standard", "privilege": "admin"}
    events = {"known_benign_source": False}
    queue, disposition = gold_triage("BRUTE_FORCE_SUCCESS", asset, events)
    assert queue == "credential-abuse"
    assert disposition == "escalate_to_incident"


def test_tools_answer_only_for_this_scenario():
    sc = generate_scenarios(n=1, seed=13)[0]
    ok = json.loads(execute_tool("lookup_entity", {"entity_id": sc.entity_id}, sc))
    assert ok["criticality"] == sc.asset["criticality"]
    miss = json.loads(execute_tool("lookup_entity", {"entity_id": "HST-0000"}, sc))
    assert "error" in miss


def test_runbook_search_finds_autoclose_exception():
    docs = search_runbook("auto-close benign scanner exception")
    assert any(d["id"] == "RB-FP-02" for d in docs)


def test_tool_schemas_are_strict():
    for schema in TOOL_SCHEMAS:
        assert schema["strict"] is True
        assert schema["input_schema"]["additionalProperties"] is False
        assert set(schema["input_schema"]["required"]) == set(
            schema["input_schema"]["properties"]
        )


def test_mock_agent_end_to_end_submits():
    sc = generate_scenarios(n=1, seed=13)[0]
    cost = CostTracker(model="mock")
    run = run_tool_agent(
        MockBackend(), SYSTEM_PROMPT, TOOL_SCHEMAS, sc.alert_text,
        lambda n, i: execute_tool(n, i, sc), SUBMIT_TOOL, cost,
    )
    assert run.submitted
    assert run.submission["queue"] == sc.gold_queue
    assert [c["name"] for c in run.tool_calls][:3] == [
        "lookup_entity",
        "query_events",
        "search_runbook",
    ]


def test_mock_eval_accuracy_band():
    scenarios = generate_scenarios(n=30, seed=13)
    agg = evaluate(scenarios, backend_kind="mock", repeats=2)
    assert agg.metric_means["queue_accuracy"] == 1.0
    assert 0.5 <= agg.metric_means["disposition_accuracy"] < 1.0
    assert agg.metric_means["submitted"] == 1.0
    assert agg.total_cost_usd == 0.0


def test_generator_includes_benign_highvalue_trap():
    scenarios = generate_scenarios(n=30, seed=13)
    trap = [
        s for s in scenarios
        if s.events["known_benign_source"] and s.gold_disposition == "route_to_analyst"
    ]
    assert trap, "need benign alerts on crown-jewel/privileged targets to exercise RB-FP-02"


def test_score_run_unsubmitted_is_zero():
    sc = generate_scenarios(n=1, seed=13)[0]

    class Dead:
        submitted = False
        submission = None

    metrics = score_run(sc, Dead())
    assert metrics == {
        "queue_accuracy": 0.0,
        "disposition_accuracy": 0.0,
        "exact_match": 0.0,
        "submitted": 0.0,
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
