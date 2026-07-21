import json

import pytest

from aau_harness import CostTracker, run_tool_agent
from oncall_watch_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from oncall_watch_agent.evaluate import evaluate, score_run
from oncall_watch_agent.tools import TOOL_SCHEMAS, WatchSession
from oncall_watch_agent.world import (
    SLO_ERROR_RATE,
    WINDOW_TICKS,
    generate_scenarios,
    search_runbook,
)


def test_generator_is_deterministic():
    a = [s.as_dict() for s in generate_scenarios(n=30, seed=29)]
    b = [s.as_dict() for s in generate_scenarios(n=30, seed=29)]
    assert a == b


def test_gold_covers_all_severities():
    sc = generate_scenarios(n=60, seed=29)
    assert {s.gold_severity for s in sc} == {"page", "ticket", "none"}


def test_every_window_is_full_length():
    for s in generate_scenarios(n=30, seed=29):
        assert len(s.ticks) == WINDOW_TICKS
        assert [t["tick"] for t in s.ticks] == list(range(WINDOW_TICKS))


def test_blip_recovers_and_regression_does_not():
    """The two archetypes must be indistinguishable at onset and divergent after."""
    scen = generate_scenarios(n=30, seed=29)
    blip = next(s for s in scen if s.archetype == "UPSTREAM_BLIP")
    reg = next(s for s in scen if s.archetype == "DEPLOY_REGRESSION")

    # both breach at onset
    assert blip.ticks[blip.onset_tick]["error_rate"] > SLO_ERROR_RATE
    assert reg.ticks[reg.onset_tick + 2]["error_rate"] > SLO_ERROR_RATE
    # the blip is back under SLO a few ticks later; the regression is not
    assert blip.ticks[blip.onset_tick + 3]["error_rate"] < SLO_ERROR_RATE
    assert reg.ticks[-1]["error_rate"] > SLO_ERROR_RATE


def test_slow_burn_never_spikes_but_ends_in_breach():
    s = next(x for x in generate_scenarios(n=30, seed=29) if x.archetype == "SLOW_BURN")
    assert s.ticks[0]["error_rate"] < SLO_ERROR_RATE
    assert s.ticks[-1]["error_rate"] > SLO_ERROR_RATE
    # no single early sample looks alarming
    assert all(t["error_rate"] < SLO_ERROR_RATE for t in s.ticks[:8])


def test_capacity_trend_keeps_slos_healthy():
    s = next(x for x in generate_scenarios(n=30, seed=29) if x.archetype == "CAPACITY_TREND")
    assert s.gold_severity == "ticket"
    assert all(t["error_rate"] < SLO_ERROR_RATE for t in s.ticks)
    assert s.ticks[-1]["saturation"] > s.ticks[0]["saturation"]


def test_next_tick_cannot_see_the_future():
    s = generate_scenarios(n=1, seed=29)[0]
    sess = WatchSession(s)
    first = json.loads(sess("next_tick", {"service_id": s.service_id}))
    assert first["tick"] == 0
    assert sess.ticks_seen == 1
    second = json.loads(sess("next_tick", {"service_id": s.service_id}))
    assert second["tick"] == 1
    assert "error_rate" in second and "ticks_remaining" in second


def test_stream_exhausts_cleanly():
    s = generate_scenarios(n=1, seed=29)[0]
    sess = WatchSession(s)
    for _ in range(WINDOW_TICKS):
        sess("next_tick", {"service_id": s.service_id})
    end = json.loads(sess("next_tick", {"service_id": s.service_id}))
    assert end["end_of_window"] is True
    assert sess.ticks_seen == WINDOW_TICKS


def test_runbook_finds_transient_guidance():
    docs = search_runbook("transient blip recovers alert fatigue")
    assert any(d["id"] == "OC-BLIP-01" for d in docs)


def test_tool_schemas_are_strict():
    for schema in TOOL_SCHEMAS:
        assert schema["strict"] is True
        assert schema["input_schema"]["additionalProperties"] is False
        assert set(schema["input_schema"]["required"]) == set(
            schema["input_schema"]["properties"]
        )


def test_mock_suppresses_during_maintenance():
    s = next(x for x in generate_scenarios(n=30, seed=29)
             if x.archetype == "MAINTENANCE_WINDOW")
    sess = WatchSession(s)
    cost = CostTracker(model="mock")
    run = run_tool_agent(MockBackend(), SYSTEM_PROMPT, TOOL_SCHEMAS, s.alert_text,
                         sess, SUBMIT_TOOL, cost, max_turns=28)
    assert run.submitted
    assert run.submission["severity"] == "none"


def test_mock_commits_the_engineered_impatience():
    """The mock pages on the first breaching sample, so it must cry wolf on the
    upstream blip. That keeps the alert-fatigue metric exercised in CI."""
    s = next(x for x in generate_scenarios(n=30, seed=29) if x.archetype == "UPSTREAM_BLIP")
    sess = WatchSession(s)
    cost = CostTracker(model="mock")
    run = run_tool_agent(MockBackend(), SYSTEM_PROMPT, TOOL_SCHEMAS, s.alert_text,
                         sess, SUBMIT_TOOL, cost, max_turns=28)
    m = score_run(s, run, sess)
    assert run.submission["severity"] == "page"
    assert m["no_false_page"] == 0.0
    assert m["severity_correct"] == 0.0


def test_mock_eval_separates_fatigue_from_correctness():
    scenarios = generate_scenarios(n=30, seed=29)
    agg = evaluate(scenarios, backend_kind="mock", repeats=2)
    m = agg.metric_means
    assert m["submitted"] == 1.0
    assert m["no_false_page"] < 1.0, "impatience gap must produce false pages"
    assert m["caught_incident"] > 0.0
    assert agg.total_cost_usd == 0.0


def test_score_run_unsubmitted_is_zero():
    s = generate_scenarios(n=1, seed=29)[0]
    sess = WatchSession(s)

    class Dead:
        submitted = False
        submission = None

    m = score_run(s, Dead(), sess)
    assert m["severity_correct"] == 0.0 and m["submitted"] == 0.0
    assert m["no_false_page"] == 1.0, "silence is not a false page"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
