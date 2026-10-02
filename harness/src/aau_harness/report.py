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
        "| Metric | Mean | 95% CI | Reporting scenarios | Reporting observations |",
        "|---|---|---|---|---|",
    ]
    coverage = agg.metric_coverage()
    for m, mean in agg.metric_means.items():
        lo, hi = agg.metric_ci95[m]
        support = coverage[m]
        lines.append(f"| {m} | {mean:.3f} | [{lo:.3f}, {hi:.3f}] | "
                     f"{support['reporting_scenarios']}/{support['declared_scenarios']} | "
                     f"{support['reporting_observations']}/{support['declared_observations']} |")
    lines += [
        f"| cost per scenario (USD) | {agg.mean_cost_per_scenario_usd:.4f} | — | — | — |",
        f"| p50 latency (s) | {agg.p50_latency_s:.2f} | — | — | — |",
        "",
        "Coverage counts observations that report each metric; missing metrics are not imputed as zero. "
        "They do not establish applicability or independent samples. Intervals resample reporting scenarios, "
        "using each scenario's mean over its available repeats.",
        "",
    ]
    partial = [name for name, counts in coverage.items()
               if counts["complete_repeat_scenarios"] < counts["reporting_scenarios"]]
    if partial:
        lines += ["Partial-repeat coverage: " + ", ".join(f"`{name}`" for name in partial) +
                  ". Investigate why these metrics were absent in some repeats before comparing scores.", ""]
    return "\n".join(lines)
