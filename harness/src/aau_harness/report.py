"""Render an EvalAggregate as the markdown results block use-case READMEs embed."""

from __future__ import annotations

from .runner import EvalAggregate


def render_report(agg: EvalAggregate, model: str, title: str = "Results") -> str:
    lines = [
        f"## {title}",
        "",
        f"Model: `{model}` · {agg.n_scenarios} scenarios × {agg.n_repeats} repeats "
        f"· total eval cost **${agg.total_cost_usd:.2f}**",
        "",
        "| Metric | Mean | 95% CI |",
        "|---|---|---|",
    ]
    for m, mean in agg.metric_means.items():
        lo, hi = agg.metric_ci95[m]
        lines.append(f"| {m} | {mean:.3f} | [{lo:.3f}, {hi:.3f}] |")
    lines += [
        f"| cost per scenario (USD) | {agg.mean_cost_per_scenario_usd:.4f} | — |",
        f"| p50 latency (s) | {agg.p50_latency_s:.2f} | — |",
        "",
    ]
    return "\n".join(lines)
