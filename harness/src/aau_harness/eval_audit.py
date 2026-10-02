"""Offline internal-consistency audit of evaluation metric summaries."""

import argparse
import math
import sys
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .runner import ScenarioResult, run_eval


def _rounded_summary(value):
    if type(value) in (int, float) and math.isfinite(value):
        return float(round(value, 4))
    if isinstance(value, list):
        return [_rounded_summary(item) for item in value]
    return value


def audit_evaluation(source: dict) -> dict:
    if not isinstance(source, dict):
        raise AgentBomError("evaluation must be an object")
    count, repeats, rows = source.get("n_scenarios"), source.get("n_repeats"), source.get("results")
    if (type(count) is not int or type(repeats) is not int or count < 1 or repeats < 1
            or count * repeats > 10000 or count > 500):
        raise AgentBomError("audit requires 1 to 500 scenarios and at most 10000 observations")
    if not isinstance(rows, list) or len(rows) != count * repeats:
        raise AgentBomError("evaluation does not cover its declared observation count")
    indexed = {}
    metric_names = set()
    for row in rows:
        if not isinstance(row, dict):
            raise AgentBomError("invalid evaluation observation")
        scenario, repeat = row.get("scenario_id"), row.get("repeat")
        if (not isinstance(scenario, str) or not scenario.strip() or len(scenario) > 200
                or type(repeat) is not int or not 0 <= repeat < repeats):
            raise AgentBomError("invalid scenario ID or repeat index")
        key = scenario, repeat
        if key in indexed:
            raise AgentBomError("duplicate scenario-repeat observation")
        metrics = row.get("metrics")
        if not isinstance(metrics, dict) or any(not isinstance(name, str) or len(name) > 200 for name in metrics):
            raise AgentBomError("invalid metric names")
        metric_names.update(metrics)
        if len(metric_names) > 100:
            raise AgentBomError("audit supports at most 100 metric names")
        indexed[key] = metrics
    scenarios = sorted({key[0] for key in indexed})
    if len(scenarios) != count:
        raise AgentBomError("scenario count does not match declaration")
    # Reuse the runner's metric validation and bootstrap implementation, but never invoke
    # a model. Placeholder operational fields are not audited or included in the report.
    def replay(scenario, repeat):
        return ScenarioResult(scenario, repeat, indexed[scenario, repeat], 0, 0.1, 0)
    try:
        aggregate = run_eval(scenarios, replay, repeats=repeats)
    except (ValueError, OverflowError) as exc:
        raise AgentBomError(f"invalid metric observation: {exc}") from exc
    expected = {
        "metric_means": {key: round(value, 4) for key, value in aggregate.metric_means.items()},
        "metric_ci95": {key: [round(lo, 4), round(hi, 4)] for key, (lo, hi) in aggregate.metric_ci95.items()},
    }
    for key in expected:
        if not isinstance(source.get(key), dict):
            raise AgentBomError(f"evaluation lacks {key}")
    mismatches = []
    for field, values in expected.items():
        supplied = source[field]
        for metric in sorted(set(values) | set(supplied)):
            actual, wanted = supplied.get(metric), values.get(metric)
            # JSON comparison distinguishes booleans from numeric scores.
            if (metric not in supplied or metric not in values
                    or rendered(_rounded_summary(actual)) != rendered(_rounded_summary(wanted))):
                mismatches.append({"field": field, "metric": metric,
                                   "recorded": actual, "recomputed": wanted})
    coverage = aggregate.metric_coverage()
    if "metric_coverage" in source and rendered(source["metric_coverage"]) != rendered(coverage):
        mismatches.append({"field": "metric_coverage", "recorded": source["metric_coverage"],
                           "recomputed": coverage})
    return {
        "report_version": "aau-evaluation-metric-audit/1.0", "source_sha256": digest(source),
        "scenario_count": count, "repeat_count": repeats, "observation_count": len(rows),
        "recomputed": expected, "metric_coverage": coverage,
        "coverage_was_recorded": "metric_coverage" in source,
        "mismatches": mismatches, "status": "consistent" if not mismatches else "inconsistent",
        "boundary": "Internal consistency of supplied per-observation metric values and the current harness's rounded scenario-bootstrap summaries only. Consistency does not mean good scores. Does not verify scoring ground truth, executed scenarios, source authenticity, provider availability, costs, latency, provenance, independence, or population representativeness. Missing optional metrics remain excluded, not imputed.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau audit-eval", description=__doc__)
    parser.add_argument("results", type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path, help="recompute and compare an existing audit report")
    args = parser.parse_args(argv)
    try:
        report = audit_evaluation(load_json(args.results))
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("audit report exceeds verification size limit")
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("evaluation audit report does not recompute")
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {len(report['mismatches'])} metric summary mismatches")
        return int(report["status"] != "consistent")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
