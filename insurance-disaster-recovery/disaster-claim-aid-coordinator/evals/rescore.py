"""Recompute order-independent source coordination from committed action traces.

Use after changing a scoring definition that does not require another model call:

    PYTHONPATH=harness/src python evals/rescore.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from aau_harness import EvalAggregate, ScenarioResult, render_report
from aau_harness.runner import _bootstrap_ci

ROOT = Path(__file__).resolve().parents[1]
EXACT_COMPONENTS = (
    "service_completion",
    "burden_minimized",
    "accessibility_respected",
    "recourse_preserved",
    "deadline_protected",
    "service_continuity_preserved",
    "rights_safety",
    "intent_alignment",
    "source_coordination",
    "outcome_accuracy",
    "record_fidelity",
)


def rescore(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for result in data["results"]:
        expected = result["detail"]["expected_sources"]
        declared = result["detail"]["trace"]["declared_sources"]
        metrics = result["metrics"]
        metrics["source_coordination"] = float(
            set(declared) == set(expected) and len(declared) == len(set(declared))
        )
        metrics["public_value_exact"] = float(
            all(metrics[name] == 1.0 for name in EXACT_COMPONENTS)
        )

    names = sorted({name for result in data["results"] for name in result["metrics"]})
    scenario_ids = sorted({result["scenario_id"] for result in data["results"]})
    means = {}
    intervals = {}
    for name in names:
        values = []
        for scenario_id in scenario_ids:
            repeats = [
                result["metrics"][name]
                for result in data["results"]
                if result["scenario_id"] == scenario_id
            ]
            values.append(statistics.fmean(repeats))
        means[name] = round(statistics.fmean(values), 4)
        intervals[name] = [round(value, 4) for value in _bootstrap_ci(values)]
    data["metric_means"] = means
    data["metric_ci95"] = intervals
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    results = [
        ScenarioResult(
            scenario_id=item["scenario_id"],
            repeat=item["repeat"],
            metrics=item["metrics"],
            cost_usd=item["cost_usd"],
            latency_s=item["latency_s"],
            n_api_calls=item["n_api_calls"],
            detail=item["detail"],
        )
        for item in data["results"]
    ]
    aggregate = EvalAggregate(
        n_scenarios=data["n_scenarios"],
        n_repeats=data["n_repeats"],
        metric_means=means,
        metric_ci95={key: tuple(value) for key, value in intervals.items()},
        mean_cost_per_scenario_usd=data["mean_cost_per_scenario_usd"],
        total_cost_usd=data["total_cost_usd"],
        p50_latency_s=data["p50_latency_s"],
        results=results,
    )
    path.with_suffix(".md").write_text(
        render_report(aggregate, model=data["model"]), encoding="utf-8"
    )


if __name__ == "__main__":
    for result_path in sorted((ROOT / "results").glob("eval_*.json")):
        rescore(result_path)
        print(f"rescored {result_path.name}")
