import json

import pytest

from aau_harness import CostTracker, run_tool_agent
from fraud_alert_triage_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from fraud_alert_triage_agent.evaluate import evaluate, score_run
from fraud_alert_triage_agent.tools import TOOL_SCHEMAS, execute_tool
from fraud_alert_triage_agent.world import (
    generate_scenarios,
    gold_triage,
    search_policy,
)


def test_generator_is_deterministic():
    a = [s.as_dict() for s in generate_scenarios(n=30, seed=17)]
    b = [s.as_dict() for s in generate_scenarios(n=30, seed=17)]
    assert a == b


def test_gold_rules_cover_queues_and_dispositions():
    scenarios = generate_scenarios(n=120, seed=17)
    assert {s.gold_queue for s in scenarios} == {
        "card-fraud", "account-takeover", "app-scam", "false-positive"
    }
    assert {s.gold_disposition for s in scenarios} == {
        "allow", "hold_for_review", "block_and_notify", "escalate_to_fraud_ops"
    }


def test_benign_private_banking_exception():
    customer_pb = {"segment": "private_banking"}
    customer_retail = {"segment": "retail"}
    txn = {"known_benign_source": True, "amount_usd": 500}
    assert gold_triage("TRAVEL_BENIGN", customer_pb, txn)[1] == "hold_for_review"
    assert gold_triage("TRAVEL_BENIGN", customer_retail, txn)[1] == "allow"


def test_app_scam_is_active_fraud_not_benign():
    # customer authorized it, but it is not a benign source — must not be cleared
    customer = {"segment": "retail"}
    txn = {"known_benign_source": False, "amount_usd": 4000, "customer_authorized": True}
    queue, disposition = gold_triage("APP_SCAM", customer, txn)
    assert queue == "app-scam"
    assert disposition == "block_and_notify"


def test_reg_threshold_forces_high_value_path():
    customer = {"segment": "retail"}
    txn = {"known_benign_source": False, "amount_usd": 25000}
    assert gold_triage("CARD_FRAUD", customer, txn)[1] == "escalate_to_fraud_ops"


def test_tools_answer_only_for_this_scenario():
    sc = generate_scenarios(n=1, seed=17)[0]
    ok = json.loads(execute_tool("lookup_customer", {"entity_id": sc.entity_id}, sc))
    assert ok["segment"] == sc.customer["segment"]
    miss = json.loads(execute_tool("lookup_customer", {"entity_id": "acct-0"}, sc))
    assert "error" in miss


def test_policy_search_finds_app_scam_clause():
    docs = search_policy("app scam authorized push payment beneficiary")
    assert any(d["id"] == "FP-APP-05" for d in docs)


def test_tool_schemas_are_strict():
    for schema in TOOL_SCHEMAS:
        assert schema["strict"] is True
        assert schema["input_schema"]["additionalProperties"] is False
        assert set(schema["input_schema"]["required"]) == set(
            schema["input_schema"]["properties"]
        )


def test_mock_agent_end_to_end_submits():
    sc = generate_scenarios(n=1, seed=17)[0]
    cost = CostTracker(model="mock")
    run = run_tool_agent(
        MockBackend(), SYSTEM_PROMPT, TOOL_SCHEMAS, sc.alert_text,
        lambda n, i: execute_tool(n, i, sc), SUBMIT_TOOL, cost,
    )
    assert run.submitted
    assert [c["name"] for c in run.tool_calls][:3] == [
        "lookup_customer",
        "query_transaction",
        "search_fraud_policy",
    ]


def test_mock_eval_has_nonzero_error_from_app_scam_gap():
    scenarios = generate_scenarios(n=30, seed=17)
    agg = evaluate(scenarios, backend_kind="mock", repeats=2)
    # the mock clears customer-authorized APP scams — queue accuracy must drop below 1
    assert agg.metric_means["queue_accuracy"] < 1.0
    assert agg.metric_means["submitted"] == 1.0
    assert agg.total_cost_usd == 0.0


def test_generator_includes_app_scam_deception():
    scenarios = generate_scenarios(n=30, seed=17)
    app = [s for s in scenarios if s.fraud_type == "APP_SCAM"]
    assert app, "need APP-scam scenarios (authorized-but-fraud) to exercise the deception"
    assert all(s.transaction["customer_authorized"] for s in app)
    assert all(not s.transaction["known_benign_source"] for s in app)


def test_score_run_unsubmitted_is_zero():
    sc = generate_scenarios(n=1, seed=17)[0]

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
