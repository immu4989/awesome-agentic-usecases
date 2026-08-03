"""Recompute record-fidelity metrics from committed traces, without re-running inference.

Every metric here is a pure function of what the run already recorded: the submitted record
and the ordered list of tool calls, both stored verbatim in each result's `detail`. When the
scoring rule changes, the honest thing is to re-score the evidence — not to re-roll the
experiment. These are stochastic API calls at temperature, so a fresh run would produce
different traces and could never confirm or refute a *scoring* fix anyway.

What this does NOT cover: any change to the world, the tools, the prompt or the agent loop.
Those change what the agent sees, so they require a real re-run. This is only for scoring.

Run after editing `REPORT_SPEC`:

    python evals/rescore.py            # show the diff
    python evals/rescore.py --write    # apply it to results/*.json
"""

from __future__ import annotations

import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))

from aau_harness import EvalAggregate, render_report  # noqa: E402
from aau_harness.runner import _bootstrap_ci  # noqa: E402
from dpa_clause_review.evaluate import REPORT_SPEC  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, os.pardir, "results")
FIDELITY_KEYS = ("report_overclaims", "report_faithful", "report_omits")


def rescore_one(detail: dict, succeeded: bool) -> dict[str, float]:
    took = [a for a in detail.get("actions", []) if a in REPORT_SPEC.consequential]
    return REPORT_SPEC.check(detail.get("record") or {}, took,
                             succeeded=succeeded).as_metrics()


def main() -> int:
    write = "--write" in sys.argv
    changed_files = 0
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        with open(path) as f:
            doc = json.load(f)
        deltas = 0
        for r in doc["results"]:
            old = {k: v for k, v in r["metrics"].items() if k in FIDELITY_KEYS}
            new = rescore_one(r["detail"], succeeded=bool(r["metrics"].get("correct")))
            if old != new:
                deltas += 1
            for k in FIDELITY_KEYS:
                r["metrics"].pop(k, None)
            r["metrics"].update(new)
        # Re-aggregate exactly as `run_eval` does: per-scenario mean across repeats, then
        # bootstrap over scenarios, with scenarios that do not report a metric dropped from
        # it rather than counted as zero.
        sids = sorted({r["scenario_id"] for r in doc["results"]})
        for m in FIDELITY_KEYS:
            per_scenario = [
                statistics.fmean(vals) for sid in sids
                if (vals := [r["metrics"][m] for r in doc["results"]
                             if r["scenario_id"] == sid and m in r["metrics"]])
            ]
            doc["metric_means"].pop(m, None)
            doc["metric_ci95"].pop(m, None)
            if not per_scenario:
                continue
            doc["metric_means"][m] = round(statistics.fmean(per_scenario), 4)
            lo, hi = _bootstrap_ci(per_scenario)
            doc["metric_ci95"][m] = [round(lo, 4), round(hi, 4)]
        doc["metric_means"] = dict(sorted(doc["metric_means"].items()))
        doc["metric_ci95"] = dict(sorted(doc["metric_ci95"].items()))

        # The rendered report is derived from the aggregate, so rebuild it whenever the JSON
        # is written — through the harness's own renderer, not by patching the table by hand.
        # Done unconditionally so a `.md` can never drift from the `.json` beside it.
        md_path = path[: -len(".json")] + ".md"
        agg = EvalAggregate(
            n_scenarios=doc["n_scenarios"], n_repeats=doc["n_repeats"],
            metric_means=doc["metric_means"],
            metric_ci95={k: tuple(v) for k, v in doc["metric_ci95"].items()},
            mean_cost_per_scenario_usd=doc["mean_cost_per_scenario_usd"],
            total_cost_usd=doc["total_cost_usd"], p50_latency_s=doc["p50_latency_s"],
            results=[],
        )
        rendered = render_report(agg, model=doc["model"] if doc["backend"] != "mock" else "mock")
        stale_md = os.path.exists(md_path) and open(md_path).read() != rendered

        if not (deltas or stale_md):
            continue
        changed_files += 1
        print(f"  {os.path.basename(path):58} {deltas:3} of {len(doc['results'])} rescored"
              f"{'  (+report)' if stale_md else ''}")
        if not write:
            continue
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
        with open(md_path, "w") as f:
            f.write(rendered)
    if not changed_files:
        print("  nothing to rescore — committed metrics already match the current spec")
    elif not write:
        print("\n  dry run. re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
