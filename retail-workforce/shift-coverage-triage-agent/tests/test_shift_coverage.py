import json

import pytest

from aau_harness import CostTracker, run_tool_agent
from shift_coverage_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from shift_coverage_agent.evaluate import evaluate, score_run
from shift_coverage_agent.tools import TOOL_SCHEMAS, execute_tool
from shift_coverage_agent.world import (
    generate_scenarios,
    gold_plan,
    ot_eligible,
    search_policy,
)


def test_generator_is_deterministic():
    a = [s.as_dict() for s in generate_scenarios(n=30, seed=11)]
    b = [s.as_dict() for s in generate_scenarios(n=30, seed=11)]
    assert a == b


def test_gold_rules_cover_all_strategies():
    scenarios = generate_scenarios(n=90, seed=11)
    strategies = {s.gold_strategy for s in scenarios}
    assert strategies == {
        "offer_overtime",
        "borrow_from_nearby",
        "run_reduced",
        "escalate_to_district",
    }


def test_ot_cap_clause():
    shift = {"end_hour": 14, "callouts": 1, "required_headcount": 8, "is_peak_day": False}
    at_cap = {"home_store": True, "is_minor": False, "weekly_hours_scheduled": 39,
              "distance_km": 0}
    under_cap = {**at_cap, "weekly_hours_scheduled": 38}
    assert not ot_eligible(at_cap, shift)  # 39 + 8 = 47 > 46
    assert ot_eligible(under_cap, shift)   # 38 + 8 = 46 <= 46


def test_minor_late_shift_clause():
    late_shift = {"end_hour": 23, "callouts": 2, "required_headcount": 8, "is_peak_day": True}
    minor = {"home_store": True, "is_minor": True, "weekly_hours_scheduled": 30,
             "distance_km": 0}
    assert gold_plan(late_shift, [minor]) == "escalate_to_district"


def test_peak_day_blocks_reduced():
    shift = {"end_hour": 14, "callouts": 1, "required_headcount": 10, "is_peak_day": True}
    assert gold_plan(shift, []) == "escalate_to_district"
    shift_off_peak = {**shift, "is_peak_day": False}
    assert gold_plan(shift_off_peak, []) == "run_reduced"


def test_tools_answer_only_for_this_scenario():
    sc = generate_scenarios(n=1, seed=11)[0]
    ok = json.loads(execute_tool("get_shift_status", {"store_id": sc.store_id}, sc))
    assert ok["required_headcount"] == sc.shift["required_headcount"]
    miss = json.loads(execute_tool("get_shift_status", {"store_id": "S000"}, sc))
    assert "error" in miss


def test_policy_search_finds_ot_cap():
    docs = search_policy("overtime weekly cap")
    assert any(d["id"] == "POL-OT-01" for d in docs)


def test_tool_schemas_are_strict():
    for schema in TOOL_SCHEMAS:
        assert schema["strict"] is True
        assert schema["input_schema"]["additionalProperties"] is False
        assert set(schema["input_schema"]["required"]) == set(
            schema["input_schema"]["properties"]
        )


def test_mock_agent_end_to_end_submits():
    sc = generate_scenarios(n=1, seed=11)[0]
    cost = CostTracker(model="mock")
    run = run_tool_agent(
        MockBackend(), SYSTEM_PROMPT, TOOL_SCHEMAS, sc.ticket_text,
        lambda n, i: execute_tool(n, i, sc), SUBMIT_TOOL, cost,
    )
    assert run.submitted
    assert run.submission["strategy"] in {
        "offer_overtime", "borrow_from_nearby", "run_reduced", "escalate_to_district"
    }
    assert [c["name"] for c in run.tool_calls][:3] == [
        "get_shift_status",
        "list_available_workers",
        "search_labor_policy",
    ]


def test_mock_eval_accuracy_band():
    scenarios = generate_scenarios(n=30, seed=11)
    agg = evaluate(scenarios, backend_kind="mock", repeats=2)
    assert 0.5 <= agg.metric_means["strategy_accuracy"] < 1.0
    assert agg.metric_means["submitted"] == 1.0
    assert agg.total_cost_usd == 0.0


def test_generator_includes_ot_cap_trap_cases():
    scenarios = generate_scenarios(n=30, seed=11)
    trap = [
        s for s in scenarios
        if s.gold_strategy != "offer_overtime"
        and any(w["home_store"] and not w["is_minor"] for w in s.workers)
    ]
    assert trap, "need scenarios where a home-store adult exists but the OT cap blocks overtime"


def test_score_run_unsubmitted_is_zero():
    sc = generate_scenarios(n=1, seed=11)[0]

    class Dead:
        submitted = False
        submission = None

    assert score_run(sc, Dead()) == {"strategy_accuracy": 0.0, "submitted": 0.0}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
