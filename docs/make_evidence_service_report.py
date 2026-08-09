"""Generate the matched twelve-industry Evidence Service Contract report."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "use-cases.json"
OUTPUT = ROOT / "EVIDENCE_SERVICE_REPORT.md"
METRICS = (
    ("outcome_accuracy", "Outcome"),
    ("burden_minimized", "Minimum evidence"),
    ("accessibility_respected", "Access"),
    ("deadline_protected", "Deadline"),
    ("recourse_preserved", "Recourse"),
    ("rights_safety", "Rights"),
    ("service_exact", "Exact"),
)


def cases() -> list[dict]:
    catalog = json.loads(CATALOG.read_text())
    return [item for item in catalog if item["kind"] == "evidence-service benchmark"]


def result_files(item: dict) -> list[Path]:
    return sorted((ROOT / item["path"] / "results").glob("eval_*.json"))


def load_results(item: dict) -> list[dict]:
    output = []
    for path in result_files(item):
        data = json.loads(path.read_text())
        errors = [
            result.get("detail", {}).get("error")
            for result in data.get("results", [])
            if result.get("detail", {}).get("error")
        ]
        if errors:
            continue
        data["_path"] = path
        output.append(data)
    return output


def provider_label(result: dict) -> str:
    served = result.get("provenance", {}).get("served_model") or result["model"]
    return f"{result['backend']} / {served}"


def provider_order(all_results: dict[str, list[dict]]) -> list[str]:
    labels = {
        provider_label(result)
        for results in all_results.values()
        for result in results
        if result["backend"] != "mock"
    }
    return sorted(labels)


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def result_for(results: list[dict], label: str) -> dict | None:
    return next((result for result in results if provider_label(result) == label), None)


def matrix(items: list[dict], all_results: dict[str, list[dict]], providers: list[str]) -> str:
    header = "| Industry / lab | Deterministic baseline | " + " | ".join(providers) + " |"
    rule = "|---|---:|" + "---:|" * len(providers)
    rows = [header, rule]
    for item in items:
        results = all_results[item["path"]]
        mock = next(result for result in results if result["backend"] == "mock")
        values = []
        for provider in providers:
            result = result_for(results, provider)
            values.append(fmt(result["metric_means"]["service_exact"] if result else None))
        link = f"[{item['title']}]({item['path']}/)"
        rows.append(
            f"| **{item['industry']}**<br>{link} | "
            f"{mock['metric_means']['service_exact']:.3f} | "
            + " | ".join(values)
            + " |"
        )
    return "\n".join(rows)


def aggregate_table(
    items: list[dict], all_results: dict[str, list[dict]], providers: list[str]
) -> str:
    columns = ["Deterministic baseline", *providers]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        for result in all_results[item["path"]]:
            label = (
                "Deterministic baseline"
                if result["backend"] == "mock"
                else provider_label(result)
            )
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


def failure_sample(items: list[dict], all_results: dict[str, list[dict]]) -> str:
    names = {
        "service_completion": "terminal",
        "burden_minimized": "evidence",
        "accessibility_respected": "access",
        "deadline_protected": "deadline",
        "recourse_preserved": "recourse",
        "rights_safety": "rights",
        "intent_alignment": "authority intent",
        "record_fidelity": "record",
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
                if run["metrics"].get("service_exact") == 0:
                    failures = [
                        label for key, label in names.items() if run["metrics"].get(key) == 0
                    ]
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
    providers = provider_order(all_results)
    assert len(items) == 12, f"expected the matched 12-lab wave, found {len(items)}"
    assert len(providers) == 2, f"expected two clean real providers, found {providers}"
    for item in items:
        results = all_results[item["path"]]
        mock_results = [result for result in results if result["backend"] == "mock"]
        real_providers = {
            provider_label(result) for result in results if result["backend"] != "mock"
        }
        assert len(mock_results) == 1, (
            f"{item['path']} must contain exactly one clean deterministic baseline"
        )
        assert real_providers == set(providers), (
            f"{item['path']} has incomplete clean provider evidence: "
            f"expected {providers}, found {sorted(real_providers)}"
        )
    provider_summary = ", ".join(f"`{provider}`" for provider in providers) or "none"
    return f"""# Evidence Service Contract — matched industry report

**12 industries · 32 committed scenarios per lab · 8 balanced archetypes · 3 repeats
per benchmark arm.**

This is the cross-industry view of the [Evidence Service Contract](EVIDENCE_SERVICE_CONTRACT.md).
It asks whether an agent gets the terminal, exact missing evidence, access channel, deadline,
recourse, authority boundary, and executed record right **together**. Current committed
real providers: {provider_summary}.

These are synthetic smoke suites, not production rankings or claims about any agency,
company, program, model family, or real-world prevalence. The same scenario shapes make
transfer visible; domain owners still decide whether each fictional contract resembles the
service they operate.

## Exact service matrix

{matrix(items, all_results, providers)}

## What the aggregate hides

{aggregate_table(items, all_results, providers)}

Means are calculated across the 12 lab-level means so one industry cannot dominate the
suite. Confidence intervals remain in each lab's committed Markdown result. Cost uses
measured tokens and the repository's list-price table; provider free-tier billing may differ.
p50 includes provider and network conditions from the collection runs; do not read it as a
controlled or uncontended production-latency benchmark.

## One reproducible miss per industry

{failure_sample(items, all_results)}

Open the linked lab, then inspect its `results/*.json` row for the exact predicted record,
executed tool trace, metrics, model reasoning, usage, and provenance. A missing row above
means the provider result was not committed or contained a provider error; it is never
silently converted into a model score.

## How to use this report

1. **Pick the nearest evidence shape**, not merely the nearest industry name.
2. **Run the deterministic baseline** to verify generation, tools, trace, and scoring at $0.
3. **Replay the committed scenario IDs** on the candidate models and interventions.
4. **Inspect directional misses**—especially authority traps and deadlines—before averages.
5. **Replace fictional policy only with a domain owner**, preserving the exact contract.

<sub>Generated by `docs/make_evidence_service_report.py` from committed catalog and result
JSON. Edit the labs or their evidence; do not hand-edit this report.</sub>
"""


def main() -> None:
    OUTPUT.write_text(render())
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
