"""Generate the matched Rights Continuity and Critical Event Fan-Out reports."""

from __future__ import annotations

import json
from pathlib import Path

from make_decision_gate_report import (
    aggregate_table,
    exact_matrix,
    load_results,
    miss_sample,
    provider_label,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "use-cases.json"


SUITES = (
    {
        "kind": "rights-continuity benchmark",
        "output": "RIGHTS_CONTINUITY_REPORT.md",
        "title": "Rights Continuity — matched service report",
        "contract": "RIGHTS_CONTINUITY_CONTRACT.md",
        "summary": (
            "A correct primary route is not exact when a companion protection expires, "
            "held evidence is requested again, recourse disappears, or a receipt is inflated."
        ),
        "traps": (
            "reliable agency data is ignored and a household receives duplicate burden",
            "urgent review inherits the routine sequence and loses its usable care window",
            "the 60-day cessation appeal overwrites the separate 15-day continuation election",
            "submitted or received is recorded as renewed, overturned, or benefits continuing",
        ),
    },
    {
        "kind": "critical-event benchmark",
        "output": "CRITICAL_EVENT_FANOUT_REPORT.md",
        "title": "Critical Event Fan-Out — matched system report",
        "contract": "CRITICAL_EVENT_FANOUT_CONTRACT.md",
        "summary": (
            "A successful response or initial notification is not exact when another actor, "
            "recipient, clock, update, follow-up, or executed receipt remains open."
        ),
        "traps": (
            "physical containment closes a still-reportable pipeline event",
            "business-associate and covered-entity recipient graphs are treated as identical",
            "a qualifying seven-day IND route inherits the familiar 15-day clock",
            "a draft, approved script, or initial report becomes accepted or finally closed",
        ),
    },
)


def cases(kind: str) -> list[dict]:
    catalog = json.loads(CATALOG.read_text())
    return [item for item in catalog if item["kind"] == kind]


def render(suite: dict) -> str:
    items = cases(suite["kind"])
    all_results = {item["path"]: load_results(item) for item in items}
    provider_sets = [
        {
            provider_label(result)
            for result in all_results[item["path"]]
            if result["backend"] != "mock"
        }
        for item in items
    ]
    providers = sorted(set.intersection(*provider_sets))
    assert len(items) == 3, f"expected three matched labs, found {len(items)}"
    assert providers, "expected at least one complete clean real-provider arm"
    for item in items:
        results = all_results[item["path"]]
        mocks = [result for result in results if result["backend"] == "mock"]
        reals = {provider_label(result) for result in results if result["backend"] != "mock"}
        assert len(mocks) == 1, f"{item['path']} must contain one deterministic baseline"
        assert set(providers).issubset(reals), (
            f"{item['path']} has incomplete matched-provider evidence: expected {providers}, "
            f"found {sorted(reals)}"
        )
    matched_results = {
        item["path"]: [
            result
            for result in all_results[item["path"]]
            if result["backend"] == "mock" or provider_label(result) in providers
        ]
        for item in items
    }
    provider = "`, `".join(providers)
    traps = "\n".join(f"- {trap};" for trap in suite["traps"][:-1])
    traps += f"\n- {suite['traps'][-1]}."
    return f"""# {suite['title']}

**3 industries · 96 committed scenarios · 8 balanced archetypes per lab · 3 repeats
per benchmark arm.**

This is the matched view of the [{suite['title'].split(' —')[0]} Contract]({suite['contract']}).
{suite['summary']} Current committed real-provider arm: `{provider}`.

These are synthetic smoke suites, not production rankings, legal conclusions, or live-case
instructions. The deterministic arm runs all 32 scenarios per lab; the real-provider arm
repeats the first eight seeded scenarios to expose every archetype at bounded cost.

## Exact decision matrix

{exact_matrix(items, matched_results, providers)}

## What the exact score contains

{aggregate_table(items, matched_results, providers)}

Means are calculated across three lab-level means so one industry cannot dominate the
suite. Confidence intervals, tool traces, usage, latency, cost, requested and served model,
and exact gold records remain in each linked lab's committed result files.

## One reproducible miss per industry

{miss_sample(items, matched_results)}

## Transfer anatomy held constant

{traps}

Provider errors are never converted into scores. The matched report includes only arms
completed cleanly across all three labs. Additional clean lab-level results remain visible
in their individual case files; missing, stalled, or errored arms are not a performance
conclusion.

## Use the suite

1. Pick the nearest failure shape rather than relying on the industry label.
2. Run the deterministic baseline to verify generation, tools, trace, and scoring at $0.
3. Replay a failed scenario ID after each rule, prompt, model, or tool-layer change.
4. Inspect deadline, evidence, authority, and receipt misses before the aggregate score.
5. Replace fictional policy only with a domain owner and a dated source snapshot.

<sub>Generated by `docs/make_next_impact_reports.py` from committed catalog and result JSON.
Edit labs or evidence; do not hand-edit this report.</sub>
"""


def main() -> None:
    for suite in SUITES:
        output = ROOT / suite["output"]
        output.write_text(render(suite))
        print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
