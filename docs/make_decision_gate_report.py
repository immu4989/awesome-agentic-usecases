"""Generate the matched six-industry Decision Gate Contract report."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "use-cases.json"
OUTPUT = ROOT / "DECISION_GATE_REPORT.md"
METRICS = (
    ("outcome_accuracy", "Outcome"),
    ("reason_fidelity", "Rule-specific reason"),
    ("evidence_fidelity", "Evidence"),
    ("gate_fidelity", "Gates"),
    ("transfer_specificity", "Transfer specificity"),
    ("authority_respected", "Authority"),
    ("record_fidelity", "Record truth"),
    ("decision_gate_exact", "Exact"),
)


def cases() -> list[dict]:
    catalog = json.loads(CATALOG.read_text())
    return [item for item in catalog if item["kind"] == "decision-gate benchmark"]


def load_results(item: dict) -> list[dict]:
    output = []
    for path in sorted((ROOT / item["path"] / "results").glob("eval_*.json")):
        data = json.loads(path.read_text())
        errors = [
            run.get("detail", {}).get("error")
            for run in data.get("results", [])
            if run.get("detail", {}).get("error")
        ]
        if errors:
            continue
        data["_path"] = path
        output.append(data)
    return output


def provider_label(result: dict) -> str:
    served = result.get("provenance", {}).get("served_model") or result["model"]
    return f"{result['backend']} / {served}"


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def result_for(results: list[dict], label: str) -> dict | None:
    return next((result for result in results if provider_label(result) == label), None)


def exact_matrix(items: list[dict], all_results: dict, providers: list[str]) -> str:
    rows = [
        "| Industry / lab | Deterministic baseline | " + " | ".join(providers) + " |",
        "|---|---:|" + "---:|" * len(providers),
    ]
    for item in items:
        results = all_results[item["path"]]
        mock = next(result for result in results if result["backend"] == "mock")
        values = []
        for provider in providers:
            result = result_for(results, provider)
            values.append(fmt(result["metric_means"]["decision_gate_exact"] if result else None))
        rows.append(
            f"| **{item['industry']}**<br>[{item['title']}]({item['path']}/) | "
            f"{mock['metric_means']['decision_gate_exact']:.3f} | "
            + " | ".join(values)
            + " |"
        )
    return "\n".join(rows)


def aggregate_table(items: list[dict], all_results: dict, providers: list[str]) -> str:
    columns = ["Deterministic baseline", *providers]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        for result in all_results[item["path"]]:
            label = "Deterministic baseline" if result["backend"] == "mock" else provider_label(result)
            grouped[label].append(result)
    rows = [
        "| Suite mean | " + " | ".join(columns) + " |",
        "|---|" + "---:|" * len(columns),
    ]
    for key, label in METRICS:
        cells = [
            fmt(statistics.fmean(result["metric_means"][key] for result in grouped[column]))
            if grouped[column]
            else "—"
            for column in columns
        ]
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    rows.append(
        "| Median p50 latency | "
        + " | ".join(
            "0.00s"
            if column == "Deterministic baseline"
            else f"{statistics.median(result['p50_latency_s'] for result in grouped[column]):.2f}s"
            for column in columns
        )
        + " |"
    )
    rows.append(
        "| Total measured cost | "
        + " | ".join(
            f"${sum(result['total_cost_usd'] for result in grouped[column]):.4f}"
            for column in columns
        )
        + " |"
    )
    return "\n".join(rows)


def miss_sample(items: list[dict], all_results: dict) -> str:
    names = {
        "outcome_accuracy": "terminal",
        "reason_fidelity": "reason",
        "evidence_fidelity": "evidence",
        "gate_fidelity": "gate",
        "rights_notice": "rights",
        "deadline_protected": "deadline",
        "confidentiality": "confidentiality",
        "authority_respected": "authority",
        "record_fidelity": "record",
        "transfer_specificity": "transfer",
    }
    rows = [
        "| Industry | Provider | Scenario | Failed exact obligations |",
        "|---|---|---|---|",
    ]
    for item in items:
        candidates = []
        for result in all_results[item["path"]]:
            if result["backend"] == "mock":
                continue
            for run in result["results"]:
                if run["metrics"].get("decision_gate_exact") == 0:
                    failures = [label for key, label in names.items() if run["metrics"].get(key) == 0]
                    candidates.append((provider_label(result), run["scenario_id"], failures))
        if not candidates:
            rows.append(f"| {item['industry']} | all measured providers | — | no miss in smoke suite |")
            continue
        provider, scenario_id, failures = candidates[0]
        rows.append(
            f"| {item['industry']} | {provider} | `{scenario_id}` | {', '.join(failures)} |"
        )
    return "\n".join(rows)


def render() -> str:
    items = cases()
    all_results = {item["path"]: load_results(item) for item in items}
    providers = sorted(
        {
            provider_label(result)
            for results in all_results.values()
            for result in results
            if result["backend"] != "mock"
        }
    )
    assert len(items) == 6, f"expected the matched 6-lab wave, found {len(items)}"
    assert len(providers) == 2, f"expected two clean real providers, found {providers}"
    for item in items:
        results = all_results[item["path"]]
        mocks = [result for result in results if result["backend"] == "mock"]
        reals = {provider_label(result) for result in results if result["backend"] != "mock"}
        assert len(mocks) == 1, f"{item['path']} must contain one deterministic baseline"
        assert reals == set(providers), (
            f"{item['path']} has incomplete clean provider evidence: "
            f"expected {providers}, found {sorted(reals)}"
        )
    provider_summary = ", ".join(f"`{provider}`" for provider in providers)
    return f"""# Decision Gate Contract — matched industry report

**6 industries · 32 committed scenarios per lab · 8 balanced archetypes · 3 repeats
per benchmark arm.**

This is the cross-industry view of the [Decision Gate Contract](DECISION_GATE_CONTRACT.md).
It asks whether outcome, exact reason, available evidence, satisfied gates, applicable
procedure, protected authority, and executed record are correct **together**. Current
committed real providers: {provider_summary}.

These are synthetic smoke suites, not production rankings, legal conclusions, or claims
about real-world prevalence. The first eight seeded scenarios are repeated to expose every
archetype with bounded cost; the full 32-scenario worlds are committed for reproduction and
extension.

## Exact decision matrix

{exact_matrix(items, all_results, providers)}

## What the exact score contains

{aggregate_table(items, all_results, providers)}

Means are calculated across six lab-level means so no industry dominates the suite.
Confidence intervals remain in each lab's committed result Markdown. Provider p50 includes
collection-time network conditions and should not be read as a controlled production latency
comparison.

## One reproducible miss per industry

{miss_sample(items, all_results)}

Open a linked lab and inspect its `results/*.json` row for the exact gold contract, predicted
record, executed tool trace, token usage, and provider provenance. A provider error is never
converted into a score: errored files are excluded and make this generator fail the suite's
completeness assertion.

## How to use the suite

1. Pick the nearest **gate and transfer shape**, not just the nearest industry.
2. Run the deterministic baseline to prove generation, tools, trace, and scoring at $0.
3. Replay a failed scenario ID across models, prompts, and tool-layer interventions.
4. Inspect evidence, authority, and record misses before reading the aggregate.
5. Replace the fictional policy only with a domain owner and a dated source snapshot.

<sub>Generated by `docs/make_decision_gate_report.py` from committed catalog and result
JSON. Edit the labs or their evidence; do not hand-edit this report.</sub>
"""


def main() -> None:
    OUTPUT.write_text(render())
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
