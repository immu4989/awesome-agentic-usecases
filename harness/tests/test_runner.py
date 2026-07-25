"""Guards that keep a provider outage from being published as a model score."""

import pytest


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
