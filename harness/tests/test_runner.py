"""Guards that keep a provider outage from being published as a model score."""

import pytest
from aau_harness.runner import ScenarioResult, run_eval


def _agg_with_errors(n_bad: int, n_total: int = 10):
    """An aggregate where `n_bad` runs died at the transport layer."""
    from aau_harness.runner import EvalAggregate, ScenarioResult

    rows = []
    for i in range(n_total):
        err = "RuntimeError: HTTP 401 from mistral: Unauthorized" if i < n_bad else None
        rows.append(ScenarioResult(f"sc-{i:03d}", 0, {"acc": 0.0}, 0.0, 0.1, 0,
                                   detail={"error": err}))
    return EvalAggregate(n_total, 1, {"acc": 0.0}, {"acc": (0.0, 0.0)}, 0.0, 0.0, 0.1, rows)


def test_provider_error_rate_separates_transport_failures_from_wrong_answers():
    from aau_harness import provider_error_rate

    assert provider_error_rate(_agg_with_errors(0)) == 0.0
    assert provider_error_rate(_agg_with_errors(10)) == 1.0
    assert provider_error_rate(_agg_with_errors(3)) == pytest.approx(0.3)


def test_a_task_failure_is_not_a_provider_failure():
    """"ended turn without submitting" is the model's fault and must still count as data."""
    from aau_harness import provider_error_rate
    from aau_harness.runner import EvalAggregate, ScenarioResult

    rows = [ScenarioResult("sc-000", 0, {"acc": 0.0}, 0.0, 0.1, 3,
                           detail={"error": "ended turn without submitting a decision"})]
    agg = EvalAggregate(1, 1, {"acc": 0.0}, {"acc": (0.0, 0.0)}, 0.0, 0.0, 0.1, rows)
    assert provider_error_rate(agg) == 0.0


def test_check_refuses_an_eval_that_never_reached_the_model():
    from aau_harness import ProviderUnavailable, check_results_are_measurements

    check_results_are_measurements(_agg_with_errors(2))          # 20% — noisy but real
    with pytest.raises(ProviderUnavailable, match="transport layer"):
        check_results_are_measurements(_agg_with_errors(9))       # 90% — not a measurement


@pytest.mark.parametrize("err", [
    "RuntimeError: HTTP 401 from mistral: {\"detail\":\"Unauthorized\"}",   # native backend
    "HTTPError: HTTP Error 402: Payment Required",                            # urllib / OpenAI-compat
    "HTTPError: HTTP Error 429: Too Many Requests",
    "HTTPError: HTTP Error 503: Service Unavailable",
    "RemoteDisconnected: Remote end closed connection without response",
])
def test_real_provider_failures_are_all_recognised(err):
    """Every string here was produced by an actual provider outage during a real eval."""
    from aau_harness import provider_error_rate
    from aau_harness.runner import EvalAggregate, ScenarioResult

    rows = [ScenarioResult("sc-000", 0, {"acc": 0.0}, 0.0, 0.1, 0, detail={"error": err})]
    agg = EvalAggregate(1, 1, {"acc": 0.0}, {"acc": (0.0, 0.0)}, 0.0, 0.0, 0.1, rows)
    assert provider_error_rate(agg) == 1.0


def test_a_metric_that_applies_to_only_some_scenarios_is_not_diluted():
    """`aau_harness.reporting` omits its omission rate where nothing consequential was done.

    Scenarios that do not report a metric must be dropped from it, not counted as zero --
    otherwise the inapplicable runs dilute the very rate the caller declined to fake.
    """
    from aau_harness import ScenarioResult, run_eval

    def run_one(scenario, repeat):
        # only the odd-numbered scenarios report `sometimes`
        metrics = {"always": 1.0}
        if scenario % 2:
            metrics["sometimes"] = 1.0
        return ScenarioResult(scenario_id=f"s{scenario}", repeat=repeat, metrics=metrics,
                              cost_usd=0.0, latency_s=0.0, n_api_calls=0, detail={})

    agg = run_eval([0, 1, 2, 3], run_one, repeats=1)
    assert agg.metric_means["always"] == 1.0
    assert agg.metric_means["sometimes"] == 1.0, "must average over the 2 that reported it"


def test_a_metric_no_scenario_reports_is_absent_rather_than_crashing():
    from aau_harness import ScenarioResult, run_eval

    def run_one(scenario, repeat):
        return ScenarioResult(scenario_id=f"s{scenario}", repeat=repeat,
                              metrics={"only": 0.5}, cost_usd=0.0, latency_s=0.0,
                              n_api_calls=0, detail={})

    agg = run_eval([0, 1], run_one, repeats=1)
    assert set(agg.metric_means) == {"only"}


def test_p50_latency_interpolates_the_middle_pair_for_an_even_run_count():
    from aau_harness import ScenarioResult, run_eval

    latencies = {"fast": 1.0, "slow": 3.0}

    def run_one(scenario, repeat):
        return ScenarioResult(
            scenario_id=scenario,
            repeat=repeat,
            metrics={"ok": 1.0},
            cost_usd=0.0,
            latency_s=latencies[scenario],
            n_api_calls=0,
        )

    agg = run_eval(["fast", "slow"], run_one, repeats=1)
    assert agg.p50_latency_s == 2.0


@pytest.mark.parametrize("scenarios,repeats", [([], 1), ([1], 0), ([1], -1), ([1], True), ([1], 1.5)])
def test_invalid_workload_is_rejected_before_any_invocation(scenarios, repeats):
    def never_run(*args):
        raise AssertionError("invalid workload executed a callback")
    with pytest.raises(ValueError):
        run_eval(scenarios, never_run, repeats=repeats)


@pytest.mark.parametrize("mode", ["duplicate", "drift", "repeat"])
def test_scenario_repeat_identity_cannot_silently_change_the_bootstrap_units(mode):
    def run_one(scenario, repeat):
        label = "same" if mode == "duplicate" else f"{scenario}-{repeat}" if mode == "drift" else scenario
        return ScenarioResult(label, 0 if mode == "repeat" else repeat, {"ok": 1.0}, 0, 0.1, 0)
    with pytest.raises(ValueError, match="duplicate|changed across|requested repeat"):
        run_eval(["one", "two"], run_one, repeats=2)


@pytest.mark.parametrize("field,value", [
    ("scenario_id", ""), ("repeat", False), ("metrics", {"x": float("nan")}),
    ("metrics", {"x": float("inf")}), ("metrics", {"x": "1"}),
    ("metrics", {"": 1.0}), ("metrics", {"x": True}),
    ("cost_usd", -1), ("cost_usd", float("inf")), ("latency_s", float("nan")),
    ("n_api_calls", 1.5), ("n_api_calls", -1),
])
def test_invalid_measurements_never_reach_aggregation(field, value):
    def run_one(scenario, repeat):
        result = ScenarioResult(scenario, repeat, {"ok": 1.0}, 0, 0.1, 0)
        setattr(result, field, value)
        return result
    with pytest.raises(ValueError):
        run_eval(["one"], run_one, repeats=1)


def test_mutable_callback_outputs_are_snapshotted_per_observation():
    shared = ScenarioResult("unset", 0, {}, 0, 0.1, 0, detail={"events": []})
    def run_one(scenario, repeat):
        shared.scenario_id, shared.repeat = scenario, repeat
        shared.metrics["score"] = float(scenario == "one")
        shared.detail["events"].append(scenario)
        return shared
    aggregate = run_eval(["one", "two"], run_one, repeats=2)
    assert aggregate.n_scenarios == 2
    assert aggregate.metric_means["score"] == 0.5
    assert [row.scenario_id for row in aggregate.results] == ["one", "two", "one", "two"]
    assert aggregate.results[0].detail["events"] == ["one"]
    shared.metrics["score"] = 99
    assert aggregate.results[-1].metrics["score"] == 0


def test_signed_unbounded_metrics_and_optional_metrics_remain_supported():
    def run_one(scenario, repeat):
        return ScenarioResult(scenario, repeat, {"difference": -5.0, "count": 12.0}, 0, 0.1, 0)
    assert run_eval(["one"], run_one, repeats=2).metric_means == {"count": 12.0, "difference": -5.0}
