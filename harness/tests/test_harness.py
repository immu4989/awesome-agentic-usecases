import pytest

from aau_harness import CostTracker, ScenarioResult, render_report, run_eval


def test_cost_tracker_prices_all_token_classes():
    t = CostTracker(model="claude-opus-4-8")
    t.add_usage(
        {
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "cache_creation_input_tokens": 1_000_000,
            "cache_read_input_tokens": 1_000_000,
        }
    )
    # 5 (input) + 25 (output) + 5*1.25 (cache write) + 5*0.1 (cache read)
    assert t.cost_usd == pytest.approx(5 + 25 + 6.25 + 0.5)
    assert t.total_input_tokens == 3_000_000
    assert t.api_calls == 1


def test_cost_tracker_rejects_unknown_model():
    with pytest.raises(ValueError):
        CostTracker(model="claude-nonexistent")


def test_cost_tracker_accepts_object_usage():
    class Usage:
        input_tokens = 100
        output_tokens = 50
        cache_creation_input_tokens = 0
        cache_read_input_tokens = 0

    t = CostTracker(model="claude-haiku-4-5")
    t.add_usage(Usage())
    assert t.cost_usd == pytest.approx((100 * 1 + 50 * 5) / 1e6)


def test_run_eval_aggregates_paired_repeats():
    scenarios = ["a", "b", "c", "d"]

    def run_one(sc, rep):
        correct = 1.0 if sc in ("a", "b", "c") else 0.0
        return ScenarioResult(
            scenario_id=sc,
            repeat=rep,
            metrics={"accuracy": correct},
            cost_usd=0.01,
            latency_s=0.5,
            n_api_calls=3,
        )

    agg = run_eval(scenarios, run_one, repeats=3)
    assert agg.n_scenarios == 4
    assert agg.n_repeats == 3
    assert agg.metric_means["accuracy"] == pytest.approx(0.75)
    lo, hi = agg.metric_ci95["accuracy"]
    assert 0.0 <= lo <= 0.75 <= hi <= 1.0
    assert agg.total_cost_usd == pytest.approx(0.12)
    assert len(agg.results) == 12


def test_render_report_contains_metrics():
    scenarios = ["a"]
    agg = run_eval(
        scenarios,
        lambda sc, rep: ScenarioResult(sc, rep, {"accuracy": 1.0}, 0.0, 0.1, 1),
        repeats=3,
    )
    md = render_report(agg, model="mock")
    assert "| accuracy | 1.000" in md
    assert "`mock`" in md
