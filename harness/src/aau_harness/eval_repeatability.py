"""Inspect joint constraints across recorded repeats, without predicting future reliability."""

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_audit import audit_evaluation


def _criteria(criteria: list[dict]) -> list[dict]:
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 10:
        raise AgentBomError("require 1 to 10 observation criteria")
    names = set()
    for rule in criteria:
        if not isinstance(rule, dict) or set(rule) != {"metric", "direction", "limit"}:
            raise AgentBomError("each criterion requires exactly metric, direction, limit")
        name = rule["metric"]
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in names:
            raise AgentBomError("criterion metric names must be unique nonblank strings")
        names.add(name)
        if rule["direction"] not in ("higher", "lower"):
            raise AgentBomError("criterion direction must be higher or lower")
        limit = rule["limit"]
        if type(limit) not in (int, float) or (type(limit) is float and not math.isfinite(limit)):
            raise AgentBomError("criterion limit must be finite numeric data, not a boolean")
    return sorted((dict(rule) for rule in criteria), key=lambda rule: rule["metric"])


def _curve(passes: int, repeats: int, sizes: list[int]) -> list[dict]:
    result = []
    for size in sizes:
        total = math.comb(repeats, size)
        all_pass = math.comb(passes, size) if passes >= size else 0
        failures = repeats - passes
        any_pass = total - (math.comb(failures, size) if failures >= size else 0)
        result.append({"draw_size": size, "total_subsets": total,
                       "all_pass_subsets": all_pass, "any_pass_subsets": any_pass,
                       "all_pass_fraction": all_pass / total, "any_pass_fraction": any_pass / total})
    return result


def review_repeatability(source: dict, *, criteria: list[dict], draw_sizes: list[int]) -> dict:
    rules = _criteria(criteria)
    if (not isinstance(draw_sizes, list) or not 1 <= len(draw_sizes) <= 20
            or any(type(size) is not int or not 1 <= size <= 20 for size in draw_sizes)
            or len(set(draw_sizes)) != len(draw_sizes)):
        raise AgentBomError("draw_sizes must contain 1 to 20 unique integers between 1 and 20")
    sizes = sorted(draw_sizes)
    audit = audit_evaluation(source)
    repeats = source["n_repeats"]
    if max(sizes) > repeats:
        raise AgentBomError("draw size exceeds recorded repeats; no extrapolation or dropped sizes")
    grouped = {}
    for row in source["results"]:
        if any(rule["metric"] not in row["metrics"] for rule in rules):
            raise AgentBomError("every criterion must be measured in every repeat; no imputation or subset filtering")
        grouped.setdefault(row["scenario_id"], []).append(row)
    scenarios = []
    for scenario_id, observations in sorted(grouped.items()):
        passing, failures = [], []
        for row in sorted(observations, key=lambda item: item["repeat"]):
            failed = []
            for rule in rules:
                value = row["metrics"][rule["metric"]]
                passed = value >= rule["limit"] if rule["direction"] == "higher" else value <= rule["limit"]
                if not passed:
                    failed.append({"metric": rule["metric"], "value": value})
            if failed:
                failures.append({"repeat": row["repeat"], "failed_criteria": failed})
            else:
                passing.append(row["repeat"])
        count = len(passing)
        scenarios.append({"scenario_id": scenario_id, "passing_repeat_ids": passing,
                          "failures": failures, "passing_repeat_count": count,
                          "state": "all_recorded_pass" if count == repeats else
                                   "none_recorded_pass" if count == 0 else "mixed",
                          "curve": _curve(count, repeats, sizes)})
    warnings = []
    if repeats == 1:
        warnings.append("Only one repeat: within-scenario repeatability cannot be assessed.")
    if audit["status"] != "consistent":
        warnings.append("Stored summaries differ from recomputation; this report uses observations and does not repair the source.")
    warnings.append("Recorded repeat IDs do not prove independent executions. Copies, selection, shared state, or changed conditions can invalidate future-run interpretations.")
    if all(row["state"] == "all_recorded_pass" for row in scenarios):
        warnings.append("No observed failures is not proof of zero failure risk; finite recorded-subset fractions are not confidence bounds.")
    return {
        "report_version": "aau-recorded-repeatability/1.0", "source_sha256": digest(source),
        "criteria": rules, "draw_sizes": sizes,
        "scenario_count": len(scenarios), "repeat_count": repeats,
        "observation_count": len(source["results"]),
        "counts": {state: sum(row["state"] == state for row in scenarios)
                   for state in ("all_recorded_pass", "mixed", "none_recorded_pass")},
        "curve": [{"draw_size": size,
                   **{field: statistics.fmean(row["curve"][index][field] for row in scenarios)
                      for field in ("all_pass_fraction", "any_pass_fraction")}}
                  for index, size in enumerate(sizes)],
        "scenarios": scenarios, "source_audit": audit, "warnings": warnings,
        "unreviewed_metrics": sorted({name for row in source["results"] for name in row["metrics"]}
                                     - {rule["metric"] for rule in rules}),
        "method": {"unit": "scenario", "within_repeat": "all supplied criteria must pass together",
                   "sampling": "uniform subsets of k recorded repeats without replacement",
                   "all_pass_fraction": "C(passing_repeats, k) / C(recorded_repeats, k)",
                   "any_pass_fraction": "1 - C(failing_repeats, k) / C(recorded_repeats, k)",
                   "aggregation": "equal-weight mean across all declared scenarios",
                   "subset_counts": "exact integers; fractions are floating-point presentations"},
        "boundary": "Descriptive enumeration of supplied recorded outcomes, not a release gate, future-run probability, confidence interval, or evidence of production safety. All criteria are tested jointly on the same repeat; any-pass is a contrast, not permission to retry a consequential action. Threshold validity, preregistration, execution authenticity, independence, scoring correctness, and population representativeness are not verified. No repeats or scenarios are dropped. Repeat indices are not timestamps and this is not a consecutive-run analysis. Unlisted metrics are not reviewed. Source hashes bind supplied JSON values, not trusted provenance. Review scenario IDs, metric names, scores, and audit mismatches before sharing.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau repeatability-eval", description=__doc__)
    parser.add_argument("evaluation", type=Path)
    parser.add_argument("--criterion", nargs=3, action="append", required=True,
                        metavar=("METRIC", "DIRECTION", "LIMIT"), help="repeat for each joint observation constraint")
    parser.add_argument("--draw-size", type=int, action="append", required=True,
                        help="recorded subset size, 1 to 20; repeat for a curve")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        try:
            criteria = [{"metric": name, "direction": direction, "limit": json.loads(limit)}
                        for name, direction, limit in args.criterion]
        except (ValueError, RecursionError) as exc:
            raise AgentBomError("criterion limits must be numeric") from exc
        report = review_repeatability(load_json(args.evaluation), criteria=criteria, draw_sizes=args.draw_size)
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("repeatability report exceeds verification size limit")
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("repeatability report does not recompute")
        else:
            write_json(report, args.out)
        print(f"Recorded-repeat review: {report['counts']}. Descriptive only; not deployment approval.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
