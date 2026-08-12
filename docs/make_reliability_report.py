"""Build the repository-wide State of Agent Reliability evidence snapshot.

The report deliberately avoids a universal composite score. Each evaluation keeps the
metric selected by its own lab, while the public dashboard exposes the metric name,
confidence interval, result artifact, cost, latency, coverage, and provenance.

Outputs:
  - STATE_OF_AGENT_RELIABILITY_2026.md
  - docs/reliability-data.json
  - docs/reliability-data.csv

Run from any directory with:

    python docs/make_reliability_report.py
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPOSITORY_URL = "https://github.com/immu4989/awesome-agentic-usecases"
LIVE_URL = "https://immu4989.github.io/awesome-agentic-usecases/#reliability"

# These lists select a representative endpoint; they do not merge unlike metrics. The
# selected source metric remains visible in JSON, CSV, the dashboard, and every tooltip.
DIMENSIONS = {
    "exact": {
        "label": "Exact task success",
        "description": "The strictest available end-to-end or exact-match endpoint.",
        "metrics": [
            "decision_gate_exact",
            "public_value_exact",
            "service_exact",
            "exact_match",
            "safe_and_correct",
            "privacy_request_exact",
            "recovery_exact",
            "remediation_exact",
            "system_coverage_exact",
            "truthful_completion",
            "task_success",
            "session2_correct",
            "action_accuracy",
            "strategy_accuracy",
            "disposition_accuracy",
            "severity_correct",
            "resolution_correct",
            "outcome_accuracy",
            "correct",
            "queue_accuracy",
        ],
        "invert": [],
    },
    "completion": {
        "label": "Completion",
        "description": "Whether the agent reached the lab's terminal or submitted state.",
        "metrics": [
            "submitted",
            "record_filed",
            "action_completion",
            "service_completion",
            "truthful_completion",
            "disclosed",
            "notification_sent",
        ],
        "invert": [],
    },
    "safety": {
        "label": "Safety / boundary preservation",
        "description": "The strongest available non-harm or protected-boundary endpoint.",
        "metrics": [
            "no_unsafe_action",
            "safe_and_correct",
            "authority_respected",
            "rights_safety",
            "payment_safety",
            "prerequisite_respected",
            "confidentiality",
            "takeover_contained",
            "false_assurance_avoided",
            "exfiltration_success",
            "injection_success",
            "unauthorized_send",
            "unsafe_admit",
            "sleeper_harm",
            "violated",
            "false_success",
        ],
        "invert": [
            "exfiltration_success",
            "injection_success",
            "unauthorized_send",
            "unsafe_admit",
            "sleeper_harm",
            "violated",
            "false_success",
        ],
    },
}


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 6) if values else None


def display_model(model: str) -> str:
    return model.removeprefix("accounts/fireworks/models/").removeprefix("meta-llama/")


def markdown_anchor(heading: str) -> str:
    """Match the GitHub-flavored Markdown anchor for the taxonomy heading."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def select_dimension(result: dict[str, Any], dimension: str) -> dict[str, Any] | None:
    spec = DIMENSIONS[dimension]
    means = result["metric_means"]
    intervals = result["metric_ci95"]
    for metric in spec["metrics"]:
        if metric not in means:
            continue
        value = float(means[metric])
        interval = intervals.get(metric)
        inverted = metric in spec["invert"]
        if inverted:
            value = 1 - value
            if interval:
                interval = [1 - float(interval[1]), 1 - float(interval[0])]
        return {
            "metric": metric,
            "value": round(value, 6),
            "ci95": [round(float(bound), 6) for bound in interval] if interval else None,
            "inverted": inverted,
        }
    return None


def source_results() -> list[tuple[Path, dict[str, Any]]]:
    artifacts: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(ROOT.glob("*/*/results/eval_*.json")):
        result = json.loads(path.read_text())
        if result.get("backend") != "mock":
            artifacts.append((path, result))
    return artifacts


def build_evaluations(cases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    evaluations = []
    for path, result in source_results():
        lab_path = str(path.parent.parent.relative_to(ROOT))
        case = cases[lab_path]
        provenance = result.get("provenance") or {}
        relative_result = str(path.relative_to(ROOT))
        dimensions = {
            name: select_dimension(result, name)
            for name in DIMENSIONS
        }
        evaluations.append(
            {
                "id": relative_result.replace("/", "--").removesuffix(".json"),
                "lab_path": lab_path,
                "title": case["title"],
                "icon": case["icon"],
                "industry": case["industry"],
                "kind": case["kind"],
                "contract": case["contract"]["name"],
                "model": result["model"],
                "model_display": display_model(result["model"]),
                "backend": result["backend"],
                "arm": result.get("arm") or result.get("variant") or "base",
                "n_scenarios": int(result["n_scenarios"]),
                "n_repeats": int(result["n_repeats"]),
                "scenario_trials": len(result["results"]),
                "mean_cost_usd": float(result["mean_cost_per_scenario_usd"]),
                "total_cost_usd": float(result["total_cost_usd"]),
                "p50_latency_s": float(result["p50_latency_s"]),
                "error_runs": sum(
                    bool((run.get("detail") or {}).get("error")) for run in result["results"]
                ),
                "dimensions": dimensions,
                "metric_means": result["metric_means"],
                "metric_ci95": result["metric_ci95"],
                "failure_patterns": case["failure_patterns"],
                "provenance": {
                    "stamped": bool(provenance),
                    "generated_at": provenance.get("generated_at"),
                    "requested_model": provenance.get("requested_model"),
                    "served_model": provenance.get("served_model"),
                    "served_differs": provenance.get("served_differs_from_requested", False),
                    "model_pinned": provenance.get("model_pinned"),
                },
                "result_path": relative_result,
                "result_url": f"{REPOSITORY_URL}/blob/main/{relative_result}",
                "lab_url": f"{REPOSITORY_URL}/tree/main/{lab_path}",
            }
        )
    return evaluations


def add_competitive_records(evaluations: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in evaluations:
        endpoint = item["dimensions"]["exact"]
        if endpoint:
            groups[(item["lab_path"], item["arm"], endpoint["metric"])].append(item)

    records: dict[str, dict[str, int]] = defaultdict(
        lambda: {"head_to_head_fields": 0, "wins": 0, "losses": 0}
    )
    for field in groups.values():
        if len(field) < 2:
            continue
        high = max(item["dimensions"]["exact"]["value"] for item in field)
        low = min(item["dimensions"]["exact"]["value"] for item in field)
        for item in field:
            record = records[item["model"]]
            record["head_to_head_fields"] += 1
            value = item["dimensions"]["exact"]["value"]
            if value == high:
                record["wins"] += 1
            if value == low:
                record["losses"] += 1
    return records


def build_model_summaries(
    evaluations: list[dict[str, Any]],
    records: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evaluations:
        by_model[item["model"]].append(item)

    summaries = []
    for model, items in by_model.items():
        dimension_values = {
            dimension: [
                item["dimensions"][dimension]["value"]
                for item in items
                if item["dimensions"][dimension]
            ]
            for dimension in DIMENSIONS
        }
        summaries.append(
            {
                "model": model,
                "display": display_model(model),
                "evaluations": len(items),
                "labs": len({item["lab_path"] for item in items}),
                "industries": len({item["industry"] for item in items}),
                "scenario_trials": sum(item["scenario_trials"] for item in items),
                "recorded_spend_usd": round(sum(item["total_cost_usd"] for item in items), 6),
                "median_exact": median(dimension_values["exact"]),
                "exact_coverage": len(dimension_values["exact"]),
                "median_completion": median(dimension_values["completion"]),
                "completion_coverage": len(dimension_values["completion"]),
                "median_safety": median(dimension_values["safety"]),
                "safety_coverage": len(dimension_values["safety"]),
                "median_cost_usd": median([item["mean_cost_usd"] for item in items]),
                "median_latency_s": median([item["p50_latency_s"] for item in items]),
                **records[model],
            }
        )
    return sorted(summaries, key=lambda item: (-item["evaluations"], item["display"]))


def build_stats(
    evaluations: list[dict[str, Any]],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    exact = [item for item in evaluations if item["dimensions"]["exact"]]
    paired = [item for item in exact if item["dimensions"]["completion"]]
    exact_ci_widths = [
        endpoint["ci95"][1] - endpoint["ci95"][0]
        for item in exact
        for endpoint in [item["dimensions"]["exact"]]
        if endpoint["ci95"]
    ]
    gaps = [
        item["dimensions"]["completion"]["value"]
        - item["dimensions"]["exact"]["value"]
        for item in paired
    ]
    high_completion_low_exact = sum(
        item["dimensions"]["completion"]["value"] >= 0.95
        and item["dimensions"]["exact"]["value"] < 0.70
        for item in paired
    )
    perfect_completion_below_half = sum(
        item["dimensions"]["completion"]["value"] == 1
        and item["dimensions"]["exact"]["value"] < 0.50
        for item in paired
    )
    return {
        "evaluations": len(evaluations),
        "labs": len({item["lab_path"] for item in evaluations}),
        "industries": len({item["industry"] for item in evaluations}),
        "models": len({item["model"] for item in evaluations}),
        "scenario_definitions": sum(item["n_scenarios"] for item in evaluations),
        "scenario_trials": sum(item["scenario_trials"] for item in evaluations),
        "recorded_spend_usd": round(sum(item["total_cost_usd"] for item in evaluations), 6),
        "median_cost_usd": median([item["mean_cost_usd"] for item in evaluations]),
        "median_latency_s": median([item["p50_latency_s"] for item in evaluations]),
        "failure_modes": taxonomy["failure_modes"],
        "failure_patterns": taxonomy["patterns"],
        "provenance_stamped": sum(item["provenance"]["stamped"] for item in evaluations),
        "model_pinned": sum(item["provenance"]["model_pinned"] is True for item in evaluations),
        "served_alias_mismatches": sum(
            item["provenance"]["served_differs"] for item in evaluations
        ),
        "exact_endpoint_coverage": len(exact),
        "paired_endpoint_coverage": len(paired),
        "mean_completion_exact_gap_points": round((mean(gaps) or 0) * 100, 1),
        "median_exact_ci_width_points": round((median(exact_ci_widths) or 0) * 100, 1),
        "high_completion_low_exact": high_completion_low_exact,
        "perfect_completion_below_half": perfect_completion_below_half,
    }


def build_failure_patterns(
    taxonomy: dict[str, Any],
    cases: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    patterns = []
    for item in taxonomy["index"]:
        patterns.append(
            {
                **item,
                "use_case_count": len(item["use_cases"]),
                "industries": sorted(
                    {cases[path]["industry"] for path in item["use_cases"] if path in cases}
                ),
                "contracts": sorted(
                    {cases[path]["contract"]["name"] for path in item["use_cases"] if path in cases}
                ),
                "url": (
                    f"{REPOSITORY_URL}/blob/main/FAILURE_TAXONOMY.md"
                    f"#{markdown_anchor(item['name'])}"
                ),
            }
        )
    return sorted(patterns, key=lambda item: (-item["use_case_count"], item["name"]))


def build_payload() -> dict[str, Any]:
    studio = json.loads((DOCS / "studio-data.json").read_text())
    cases = {case["path"]: case for case in studio["cases"]}
    taxonomy = json.loads((DOCS / "assets" / "taxonomy.json").read_text())
    evaluations = build_evaluations(cases)
    records = add_competitive_records(evaluations)
    stats = build_stats(evaluations, taxonomy)
    patterns = build_failure_patterns(taxonomy, cases)
    return {
        "version": "aau-reliability-report/1.0",
        "edition": "2026",
        "scope": "Committed non-mock eval_*.json artifacts in two-level use-case results folders.",
        "stats": stats,
        "dimensions": {
            name: {
                "label": spec["label"],
                "description": spec["description"],
                "selection_priority": spec["metrics"],
                "inverted_risk_metrics": spec["invert"],
            }
            for name, spec in DIMENSIONS.items()
        },
        "models": build_model_summaries(evaluations, records),
        "failure_patterns": patterns,
        "evaluations": evaluations,
        "methodology": {
            "universal_score": False,
            "comparison_unit": "same lab + same arm + same selected source metric",
            "confidence": "Committed 95% intervals are shown when the result artifact provides them.",
            "cost": "Provider-reported token cost committed by each evaluation artifact.",
            "limitations": [
                "Coverage is uneven across models and industries.",
                "Medians summarize unlike lab-specific endpoints and are descriptive, not rankings.",
                "Failure counts describe this repository's observed evidence, not population prevalence.",
                "Floating model aliases may serve different weights on a later rerun.",
                "Synthetic scenarios test contract behavior; they do not certify production safety.",
            ],
        },
    }


def write_csv(evaluations: list[dict[str, Any]]) -> None:
    fields = [
        "result_path",
        "lab_path",
        "title",
        "industry",
        "kind",
        "contract",
        "model",
        "backend",
        "arm",
        "n_scenarios",
        "n_repeats",
        "scenario_trials",
        "mean_cost_usd",
        "total_cost_usd",
        "p50_latency_s",
        "error_runs",
        "exact_metric",
        "exact_value",
        "exact_ci95_low",
        "exact_ci95_high",
        "completion_metric",
        "completion_value",
        "safety_metric",
        "safety_value",
        "provenance_stamped",
        "model_pinned",
        "served_alias_mismatch",
    ]
    with (DOCS / "reliability-data.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in evaluations:
            exact = item["dimensions"]["exact"] or {}
            completion = item["dimensions"]["completion"] or {}
            safety = item["dimensions"]["safety"] or {}
            interval = exact.get("ci95") or [None, None]
            writer.writerow(
                {
                    **{field: item[field] for field in fields[:16]},
                    "exact_metric": exact.get("metric"),
                    "exact_value": exact.get("value"),
                    "exact_ci95_low": interval[0],
                    "exact_ci95_high": interval[1],
                    "completion_metric": completion.get("metric"),
                    "completion_value": completion.get("value"),
                    "safety_metric": safety.get("metric"),
                    "safety_value": safety.get("value"),
                    "provenance_stamped": item["provenance"]["stamped"],
                    "model_pinned": item["provenance"]["model_pinned"],
                    "served_alias_mismatch": item["provenance"]["served_differs"],
                }
            )


def format_rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def report_markdown(payload: dict[str, Any]) -> str:
    stats = payload["stats"]
    model_rows = []
    for model in payload["models"]:
        model_rows.append(
            f"| {model['display']} | {model['evaluations']} | {model['labs']} | "
            f"{format_rate(model['median_exact'])} ({model['exact_coverage']}) | "
            f"{format_rate(model['median_completion'])} "
            f"({model['completion_coverage']}) | ${model['median_cost_usd']:.6f} | "
            f"{model['median_latency_s']:.2f}s | {model['wins']}/"
            f"{model['head_to_head_fields']} |"
        )
    top_patterns = payload["failure_patterns"][:5]
    pattern_rows = "\n".join(
        f"| [{item['name']}]({item['url']}) | {item['use_case_count']} | {item['one_liner']} |"
        for item in top_patterns
    )
    return f"""# State of Agent Reliability 2026

> An automatically generated evidence snapshot from this repository—not a market ranking,
> safety certification, or claim about all agent deployments. [Open the interactive report]({LIVE_URL}).

## The evidence surface

| Committed model evals | Scenario trials | Labs | Industries | Recorded spend | Observed failures |
|---:|---:|---:|---:|---:|---:|
| **{stats['evaluations']}** | **{stats['scenario_trials']:,}** | **{stats['labs']}** | **{stats['industries']}** | **${stats['recorded_spend_usd']:.2f}** | **{stats['failure_modes']}** |

The snapshot reads every committed, non-mock `eval_*.json` artifact in the 70 public labs.
It keeps each lab's metric name and 95% interval visible, and links every plotted value to
the exact source result. Download the same evidence as
[JSON](docs/reliability-data.json) or [CSV](docs/reliability-data.csv).

## Five findings worth acting on

1. **Completion is not correctness.** Across {stats['paired_endpoint_coverage']} artifacts
   with both endpoints, completion ran **{stats['mean_completion_exact_gap_points']:.1f}
   points above exact task success** on average. {stats['high_completion_low_exact']} artifacts
   completed at least 95% of runs while exact success remained below 70%.
2. **A perfect finish can still hide a failed task.**
   {stats['perfect_completion_below_half']} artifacts reached 100% completion with less than
   50% exact success. Status alone is not an outcome metric.
3. **Uncertainty is part of the result.** The median width of the committed 95% interval on
   the selected exact endpoint is **{stats['median_exact_ci_width_points']:.1f} points**.
   A three-decimal score without its interval overstates what these smoke runs know.
4. **Exceptions dominate the observed cross-industry failures.** “Similarity erases the
   exception” appears in **{top_patterns[0]['use_case_count']} labs**. A rule that works on a
   clean twin is not evidence that it transfers to the nearby exception.
5. **Reproducibility needs an identity check.** {stats['provenance_stamped']} of
   {stats['evaluations']} artifacts carry a provenance stamp; only {stats['model_pinned']}
   record a pinned model snapshot, and {stats['served_alias_mismatches']} record that the
   served model differed from the requested alias.

## Model coverage—not a universal leaderboard

The medians below describe the selected endpoint inside each model's *uneven* evaluation
portfolio. They are useful for coverage and hypothesis generation, not for declaring a winner.
A head-to-head field exists only where two or more models ran the same lab, arm, and source metric.

| Model | Evals | Labs | Median exact (n) | Median completion (n) | Median cost/scenario | Median p50 | Head-to-head wins/fields |
|---|---:|---:|---:|---:|---:|---:|---:|
{"\n".join(model_rows)}

## Most widespread observed failure patterns

| Pattern | Labs | What it catches |
|---|---:|---|
{pattern_rows}

## How to read and reproduce this report

- **Exact, completion, and safety are separate.** The generator chooses the strictest
  available source metric for each view and publishes that metric name. It never averages
  them into one “reliability score.”
- **Inverted risk metrics are explicit.** For safety views, a harmful event rate such as
  `exfiltration_success` is displayed as `1 − rate`; the source name and inversion remain in
  the data.
- **Cost and latency are observed, not normalized.** Provider pricing, cache behavior,
  regions, and floating aliases can change.
- **Failure incidence is repository incidence.** It does not estimate real-world prevalence.
- **Rebuild the complete release:** `python docs/make_reliability_report.py`.
- **Run a source lab at $0:** follow its `eval --backend mock --repeats 3` command.

The selection rules are code, not editorial judgment hidden in a chart. Inspect
[`docs/make_reliability_report.py`](docs/make_reliability_report.py), the
[verification standard](VERIFICATION.md), and the [failure taxonomy](FAILURE_TAXONOMY.md).
"""


def readme_snapshot(payload: dict[str, Any]) -> str:
    stats = payload["stats"]
    return f"""## New: State of Agent Reliability 2026

**[Open the interactive report]({LIVE_URL})** to inspect every committed real-model result
through the question that matters: exact task success, completion, safety boundaries, cost,
latency, or uncertainty. Every bar names its source metric, shows its 95% interval when
available, and opens the exact result artifact.

| Model evals | Scenario trials | Verified labs | Observed failures | Recorded spend |
|---:|---:|---:|---:|---:|
| **{stats['evaluations']}** | **{stats['scenario_trials']:,}** | **{stats['labs']}** | **{stats['failure_modes']}** | **${stats['recorded_spend_usd']:.2f}** |

The headline finding is difficult to hide in a benchmark table: across
{stats['paired_endpoint_coverage']} artifacts with both endpoints, **completion runs
{stats['mean_completion_exact_gap_points']:.1f} points above exact task success on average**.
{stats['high_completion_low_exact']} artifacts complete at least 95% of runs while exact
success remains below 70%; {stats['perfect_completion_below_half']} finish every run while
solving fewer than half exactly.

This is a research snapshot, not a manufactured universal leaderboard. Model coverage is
shown beside every median, unlike metrics stay separate, inverted safety rates remain
explicit, and failure incidence is clearly bounded to this repository. Read the
**[citable report](STATE_OF_AGENT_RELIABILITY_2026.md)**, download the generated
**[JSON](docs/reliability-data.json)** or **[CSV](docs/reliability-data.csv)**, and audit the
**[generator](docs/make_reliability_report.py)**. Any new committed result regenerates the
release, so its claims cannot silently drift from the evidence.
"""


def sync_readme(payload: dict[str, Any]) -> None:
    start = "<!-- RELIABILITY-SNAPSHOT:START -->"
    end = "<!-- RELIABILITY-SNAPSHOT:END -->"
    path = ROOT / "README.md"
    text = path.read_text()
    before, rest = text.split(start, 1)
    _old, after = rest.split(end, 1)
    path.write_text(f"{before}{start}\n\n{readme_snapshot(payload)}\n{end}{after}")


def main() -> None:
    payload = build_payload()
    (DOCS / "reliability-data.json").write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n"
    )
    write_csv(payload["evaluations"])
    (ROOT / "STATE_OF_AGENT_RELIABILITY_2026.md").write_text(report_markdown(payload))
    sync_readme(payload)
    stats = payload["stats"]
    print(
        "wrote State of Agent Reliability 2026 — "
        f"{stats['evaluations']} evaluations, {stats['scenario_trials']} trials, "
        f"{stats['failure_modes']} observed failures"
    )


if __name__ == "__main__":
    main()
