"""Repeated-run evaluation with paired bootstrap confidence intervals.

Agent runs are stochastic, so the runner treats "repeat the whole eval n times"
as the default shape, not an option. Metrics are aggregated per repeat and the
CI is bootstrapped over scenarios (paired: resampling scenario indices, keeping
each scenario's repeats together).
"""

from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, Sequence


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

    def as_dict(self) -> dict:
        return {
            "n_scenarios": self.n_scenarios,
            "n_repeats": self.n_repeats,
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
    results: list[ScenarioResult] = []
    for rep in range(repeats):
        for sc in scenarios:
            t0 = time.monotonic()
            res = run_one(sc, rep)
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
        # per-scenario mean across repeats, then bootstrap over scenarios
        per_scenario = [
            statistics.fmean(
                [r.metrics[m] for r in results if r.scenario_id == sid and m in r.metrics]
            )
            for sid in scenario_ids
        ]
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
        p50_latency_s=latencies[len(latencies) // 2] if latencies else 0.0,
        results=results,
    )
