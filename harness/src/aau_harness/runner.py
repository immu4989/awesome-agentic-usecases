"""Repeated-run evaluation with paired bootstrap confidence intervals.

Agent runs are stochastic, so the runner treats "repeat the whole eval n times"
as the default shape, not an option. Metrics are aggregated per repeat and the
CI is bootstrapped over scenarios (paired: resampling scenario indices, keeping
each scenario's repeats together).
"""

from __future__ import annotations

import random
import math
import re
import statistics
import time
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Callable, Sequence

# Errors that mean "the eval never ran" rather than "the model got it wrong". An expired
# key or a dead endpoint produces a full sweep of zeros that is indistinguishable, in the
# saved JSON, from a model that failed every scenario — and would then be charted and
# published as a real score. Runs like that are not measurements and must not be saved.
# The status code may be adjacent to "HTTP" (the native backend) or separated by "Error"
# (urllib, which every OpenAI-compatible provider goes through), so allow a short gap.
_TRANSPORT_ERROR = re.compile(
    r"HTTP[^0-9]{0,12}(4\d\d|5\d\d)"
    r"|Unauthorized|Forbidden|Payment\s*Required|RemoteDisconnected|ConnectionError"
    r"|Timed?\s*out|Too\s*Many\s*Requests|SSLError|NameResolution|Quota",
    re.IGNORECASE,
)


class ProviderUnavailable(RuntimeError):
    """Raised when an eval's runs failed at the transport layer instead of on the task."""


@dataclass
class ScenarioResult:
    scenario_id: str
    repeat: int
    metrics: dict[str, float]  # e.g. {"queue_correct": 1.0, "action_correct": 0.0}
    cost_usd: float
    latency_s: float
    n_api_calls: int
    detail: dict = field(default_factory=dict)


@dataclass
class EvalAggregate:
    n_scenarios: int
    n_repeats: int
    metric_means: dict[str, float]
    metric_ci95: dict[str, tuple[float, float]]
    mean_cost_per_scenario_usd: float
    total_cost_usd: float
    p50_latency_s: float
    results: list[ScenarioResult]

    def metric_coverage(self) -> dict[str, dict[str, int]]:
        """Describe reported metric availability, not applicability or independent sample size."""
        coverage = {}
        for name in sorted(self.metric_means):
            rows = [row for row in self.results if name in row.metrics]
            per_scenario = {row.scenario_id for row in rows}
            complete = sum(
                {row.repeat for row in rows if row.scenario_id == scenario_id} == set(range(self.n_repeats))
                for scenario_id in per_scenario
            )
            coverage[name] = {
                "reporting_scenarios": len(per_scenario),
                "reporting_observations": len(rows),
                "complete_repeat_scenarios": complete,
                "declared_scenarios": self.n_scenarios,
                "declared_observations": self.n_scenarios * self.n_repeats,
            }
        return coverage

    def as_dict(self) -> dict:
        from .provenance import snapshot

        return {
            # Stamped here rather than in each use case's save_results, so every result
            # in the repo carries its provenance whether or not its author thought about it.
            "provenance": snapshot(),
            "n_scenarios": self.n_scenarios,
            "n_repeats": self.n_repeats,
            "metric_coverage": self.metric_coverage(),
            "metric_means": {k: round(v, 4) for k, v in self.metric_means.items()},
            "metric_ci95": {
                k: [round(lo, 4), round(hi, 4)] for k, (lo, hi) in self.metric_ci95.items()
            },
            "mean_cost_per_scenario_usd": round(self.mean_cost_per_scenario_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "p50_latency_s": round(self.p50_latency_s, 3),
            "results": [
                {
                    "scenario_id": r.scenario_id,
                    "repeat": r.repeat,
                    "metrics": r.metrics,
                    "cost_usd": round(r.cost_usd, 6),
                    "latency_s": round(r.latency_s, 3),
                    "n_api_calls": r.n_api_calls,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


def _bootstrap_ci(
    per_scenario_values: Sequence[float], n_boot: int = 2000, seed: int = 0
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(per_scenario_values)
    if n == 0:
        return (0.0, 0.0)
    boots = []
    for _ in range(n_boot):
        sample = [per_scenario_values[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(sample) / n)
    boots.sort()
    return (boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)])


def run_eval(
    scenarios: Sequence,
    run_one: Callable[[object, int], ScenarioResult],
    repeats: int = 3,
    progress: Callable[[str], None] | None = None,
) -> EvalAggregate:
    """Run `run_one(scenario, repeat)` for every scenario x repeat and aggregate.

    `run_one` owns the agent invocation and scoring; the runner owns repetition,
    aggregation, and uncertainty.
    """
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    scenarios = tuple(scenarios)
    if not scenarios:
        raise ValueError("evaluation requires at least one scenario")
    identities: list[str] = []
    seen_identities: set[str] = set()
    results: list[ScenarioResult] = []
    for rep in range(repeats):
        for position, sc in enumerate(scenarios):
            t0 = time.monotonic()
            res = run_one(sc, rep)
            if not isinstance(res, ScenarioResult):
                raise ValueError("evaluation callback must return ScenarioResult")
            if not isinstance(res.scenario_id, str) or not res.scenario_id.strip():
                raise ValueError("scenario result ID must be a nonblank string")
            if type(res.repeat) is not int or res.repeat != rep:
                raise ValueError("scenario result repeat does not match the requested repeat")
            if rep == 0:
                if res.scenario_id in seen_identities:
                    raise ValueError("different scenario positions returned a duplicate scenario ID")
                identities.append(res.scenario_id)
                seen_identities.add(res.scenario_id)
            elif res.scenario_id != identities[position]:
                raise ValueError("scenario result ID changed across repeats")
            if not isinstance(res.metrics, dict) or any(
                not isinstance(key, str) or not key.strip()
                or type(value) not in (int, float) or not math.isfinite(value)
                for key, value in res.metrics.items()
            ):
                raise ValueError("metrics must have nonblank names and finite numeric values")
            if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                   for value in (res.cost_usd, res.latency_s)):
                raise ValueError("cost and latency must be finite nonnegative numbers")
            if type(res.n_api_calls) is not int or res.n_api_calls < 0:
                raise ValueError("API call count must be a nonnegative integer")
            # A callback may reuse a mutable result or metrics dict on its next invocation.
            # Freeze this observation before allowing that next call to change it.
            res = deepcopy(res)
            if res.latency_s == 0.0:
                res.latency_s = time.monotonic() - t0
            results.append(res)
            if progress:
                progress(
                    f"repeat {rep + 1}/{repeats} scenario {res.scenario_id}: "
                    f"{res.metrics} ${res.cost_usd:.4f}"
                )

    metric_names = sorted({k for r in results for k in r.metrics})
    metric_means: dict[str, float] = {}
    metric_ci95: dict[str, tuple[float, float]] = {}
    scenario_ids = sorted({r.scenario_id for r in results})
    for m in metric_names:
        # Per-scenario mean across repeats, then bootstrap over scenarios.
        #
        # A metric need not apply to every scenario. `aau_harness.reporting` omits its
        # omission rate entirely on runs where nothing consequential was done, precisely so
        # that a run with nothing to hide cannot be scored as having hidden nothing. So a
        # scenario contributing no value for a metric is dropped from that metric rather
        # than counted as a zero -- averaging in the inapplicable cases would dilute exactly
        # the rate the caller went to the trouble of not faking.
        per_scenario = []
        for sid in scenario_ids:
            values = [r.metrics[m] for r in results
                      if r.scenario_id == sid and m in r.metrics]
            if values:
                per_scenario.append(statistics.fmean(values))
        if not per_scenario:
            continue
        metric_means[m] = statistics.fmean(per_scenario)
        metric_ci95[m] = _bootstrap_ci(per_scenario)

    costs = [r.cost_usd for r in results]
    latencies = sorted(r.latency_s for r in results)
    return EvalAggregate(
        n_scenarios=len(scenario_ids),
        n_repeats=repeats,
        metric_means=metric_means,
        metric_ci95=metric_ci95,
        mean_cost_per_scenario_usd=statistics.fmean(costs) if costs else 0.0,
        total_cost_usd=sum(costs),
        p50_latency_s=statistics.median(latencies) if latencies else 0.0,
        results=results,
    )


def provider_error_rate(agg: EvalAggregate) -> float:
    """Fraction of runs that failed at the transport layer rather than on the task.

    A wrong answer is data. A 401 is not — it means the eval never happened. Use this
    before saving results so an expired key can't be published as a model's score.
    """
    if not agg.results:
        return 0.0
    bad = sum(
        1 for r in agg.results
        if _TRANSPORT_ERROR.search(str(r.detail.get("error") or ""))
    )
    return bad / len(agg.results)


def check_results_are_measurements(agg: EvalAggregate, threshold: float = 0.5) -> None:
    """Raise if most runs never reached the model. Call this before save_results()."""
    rate = provider_error_rate(agg)
    if rate >= threshold:
        raise ProviderUnavailable(
            f"{rate:.0%} of runs failed at the transport layer (auth, network, or rate "
            f"limits), so these numbers measure the provider, not the model. Nothing was "
            f"saved. Check the API key and endpoint, then re-run."
        )
