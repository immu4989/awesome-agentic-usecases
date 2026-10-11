"""Paired scenario-level comparison of saved evaluations, without model calls."""

import argparse
import math
import statistics
import sys
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_audit import audit_evaluation
from .evaluation_context import compare_contexts
from .runner import _bootstrap_ci


def compare_evaluations(baseline: dict, candidate: dict, *, metric: str, direction: str) -> dict:
    if not isinstance(metric, str) or not metric.strip() or len(metric) > 200:
        raise AgentBomError("metric must be a nonblank name of at most 200 characters")
    if direction not in ("higher", "lower"):
        raise AgentBomError("direction must be higher or lower")
    audits = [audit_evaluation(source) for source in (baseline, candidate)]
    context_match = compare_contexts(baseline, candidate)
    groups = []
    for source in (baseline, candidate):
        grouped = {}
        for row in source["results"]:
            if metric not in row["metrics"]:
                raise AgentBomError("selected metric must be present in every observation on both sides; no imputation or intersection filtering")
            grouped.setdefault(row["scenario_id"], []).append((row["repeat"], row["metrics"][metric]))
        groups.append(grouped)
    if set(groups[0]) != set(groups[1]):
        raise AgentBomError("baseline and candidate must contain exactly the same scenario IDs")
    # Match scenarios, not row positions or repeat indices. Repeats are averaged
    # within each side before resampling scenario deltas as complete clusters.
    rows = []
    sign = 1 if direction == "higher" else -1
    try:
        for scenario in sorted(groups[0]):
            before, after = [statistics.fmean(value for _, value in sorted(group[scenario])) for group in groups]
            delta = after - before
            if not all(math.isfinite(value) for value in (before, after, delta)):
                raise ValueError("non-finite comparison")
            benefit = sign * delta
            rows.append({"scenario_id": scenario, "baseline_mean": before,
                         "candidate_mean": after, "delta": delta,
                         "change": "improved" if benefit > 0 else "regressed" if benefit < 0 else "unchanged"})
        deltas = [row["delta"] for row in rows]
        mean = statistics.fmean(deltas)
        interval = list(_bootstrap_ci(deltas))
        if not all(math.isfinite(value) for value in [mean, *interval]):
            raise ValueError("non-finite bootstrap summary")
    except (ValueError, OverflowError) as exc:
        raise AgentBomError("comparison arithmetic exceeds finite numeric range") from exc
    warnings = []
    if context_match["status"] == "unavailable":
        warnings.append("Evaluation context unavailable for " + ", ".join(context_match["missing_sources"])
                        + "; matching scenario IDs alone do not establish comparable cases or scoring.")
    if len(rows) < 2:
        warnings.append("One scenario cannot estimate between-scenario variation; its interval is degenerate.")
    if len(set(deltas)) == 1:
        warnings.append("All observed scenario deltas are identical; a zero-width interval does not prove certainty.")
    if baseline["n_repeats"] != candidate["n_repeats"]:
        warnings.append("Repeat counts differ; within-scenario uncertainty may differ between sides.")
    for label, audit in zip(("baseline", "candidate"), audits):
        if audit["status"] != "consistent":
            warnings.append(f"{label} stored summaries differ from current recomputation; comparison uses observations, not those summaries.")
    return {
        "report_version": "aau-paired-evaluation-comparison/1.0",
        "context_match": context_match,
        "baseline_sha256": digest(baseline), "candidate_sha256": digest(candidate),
        "metric": metric, "preferred_direction": direction,
        "scenario_count": len(rows),
        "baseline_repeat_count": baseline["n_repeats"], "candidate_repeat_count": candidate["n_repeats"],
        "mean_delta": mean, "delta_ci95": interval,
        "changes": {change: sum(row["change"] == change for row in rows)
                    for change in ("improved", "regressed", "unchanged")},
        "scenarios": rows, "warnings": warnings,
        "source_audits": {label: {"status": audit["status"], "mismatches": audit["mismatches"]}
                          for label, audit in zip(("baseline", "candidate"), audits)},
        "method": {"unit": "scenario", "delta": "candidate minus baseline",
                   "within_scenario": "mean of all repeats on each side",
                   "interval": "percentile bootstrap of paired scenario deltas",
                   "resamples": 2000, "seed": 0, "confidence_level": 0.95},
        "boundary": "Descriptive comparison of supplied observations, not a release gate or proof of improvement. Matching scenario IDs do not establish identical scenario content, scoring rules, execution conditions, or authentic runs; verify those separately. Repeats are not independent scenarios. The interval resamples observed scenarios only, does not model within-scenario run uncertainty, and assumes exchangeable scenario units. Synthetic scenarios do not establish population representativeness. No multiple-comparison correction, practical-effect threshold, cost audit, or production safety claim is provided.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau compare-evals", description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--direction", required=True, choices=("higher", "lower"))
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_evaluations(load_json(args.baseline), load_json(args.candidate),
                                    metric=args.metric, direction=args.direction)
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("comparison report exceeds verification size limit")
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("comparison report does not recompute")
        else:
            write_json(report, args.out)
        print(f"Compared {report['scenario_count']} scenarios: {report['changes']}. Descriptive only; not a release decision.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
