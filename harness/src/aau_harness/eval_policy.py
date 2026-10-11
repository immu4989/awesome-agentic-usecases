"""Review saved evaluations against explicit, non-compensating metric constraints."""

import argparse
from copy import deepcopy
import math
import statistics
import sys
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_compare import compare_evaluations
from .runner import _bootstrap_ci


def validate_policy(policy: dict) -> None:
    fields = {"policy_version", "scenario_ids", "minimum_repeats", "metrics"}
    version = policy.get("policy_version") if isinstance(policy, dict) else None
    if version == "aau-evaluation-review-policy/1.1":
        fields.add("cohorts")
    if not isinstance(policy, dict) or set(policy) != fields:
        raise AgentBomError("policy fields differ from the selected version's contract")
    if version not in ("aau-evaluation-review-policy/1.0", "aau-evaluation-review-policy/1.1"):
        raise AgentBomError("unsupported evaluation review policy version")
    ids = policy["scenario_ids"]
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 500
            or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in ids)
            or len(set(ids)) != len(ids)):
        raise AgentBomError("scenario_ids must contain 1 to 500 unique nonblank names")
    minimum = policy["minimum_repeats"]
    if type(minimum) is not int or minimum < 1 or minimum * len(ids) > 10000:
        raise AgentBomError("minimum_repeats must be positive and fit the observation limit")
    rules = policy["metrics"]
    if not isinstance(rules, list) or not 1 <= len(rules) <= 10:
        raise AgentBomError("policy requires 1 to 10 metric rules")
    names = set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {
            "metric", "direction", "candidate_observation_limit", "max_mean_regression", "max_regressed_scenarios"
        }:
            raise AgentBomError("metric rule fields differ from the policy contract")
        name = rule["metric"]
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in names:
            raise AgentBomError("metric names must be unique nonblank strings of at most 200 characters")
        names.add(name)
        if rule["direction"] not in ("higher", "lower"):
            raise AgentBomError("metric direction must be higher or lower")
        for field in ("candidate_observation_limit", "max_mean_regression"):
            value = rule[field]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise AgentBomError(f"{field} must be finite numeric data, not a boolean")
        if rule["max_mean_regression"] < 0:
            raise AgentBomError("max_mean_regression cannot be negative")
        count = rule["max_regressed_scenarios"]
        if type(count) is not int or not 0 <= count <= len(ids):
            raise AgentBomError("max_regressed_scenarios must fit the declared scenario count")
    if version == "aau-evaluation-review-policy/1.1":
        cohorts = policy["cohorts"]
        if not isinstance(cohorts, list) or not 1 <= len(cohorts) <= 20:
            raise AgentBomError("cohorts must contain 1 to 20 declared groups")
        seen, covered = set(), set()
        directions = {rule["metric"]: rule["direction"] for rule in rules}
        for cohort in cohorts:
            if not isinstance(cohort, dict) or set(cohort) != {"cohort_id", "scenario_ids", "metrics"}:
                raise AgentBomError("cohort fields must be cohort_id, scenario_ids, metrics")
            name = cohort["cohort_id"]
            if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in seen:
                raise AgentBomError("cohort IDs must be unique nonblank strings")
            seen.add(name)
            validate_policy({"policy_version": "aau-evaluation-review-policy/1.0", "minimum_repeats": 1,
                             "scenario_ids": cohort["scenario_ids"], "metrics": cohort["metrics"]})
            if not set(cohort["scenario_ids"]) <= set(ids):
                raise AgentBomError("cohort contains scenario IDs outside the declared evaluation")
            covered.update(cohort["scenario_ids"])
            if any(directions.get(rule["metric"]) != rule["direction"] for rule in cohort["metrics"]):
                raise AgentBomError("cohort metrics must use globally reviewed names and directions")
        if covered != set(ids):
            raise AgentBomError("declared cohorts must cover every scenario at least once")


def metric_checks(rule: dict, comparison: dict, candidate_rows: list[dict]) -> list[dict]:
    metric = rule["metric"]
    sign = 1 if rule["direction"] == "higher" else -1
    regression = max(0.0, -sign * comparison["mean_delta"])
    violated = [
        {"scenario_id": row["scenario_id"], "repeat": row["repeat"], "value": row["metrics"][metric]}
        for row in sorted(candidate_rows, key=lambda item: (item["scenario_id"], item["repeat"]))
        if sign * row["metrics"][metric] < sign * rule["candidate_observation_limit"]
    ]
    return [
        {"constraint": "candidate_observation_limit", "passed": not violated,
         "limit": rule["candidate_observation_limit"], "violations": violated},
        {"constraint": "max_mean_regression", "passed": regression <= rule["max_mean_regression"],
         "limit": rule["max_mean_regression"], "observed": regression},
        {"constraint": "max_regressed_scenarios",
         "passed": comparison["changes"]["regressed"] <= rule["max_regressed_scenarios"],
         "limit": rule["max_regressed_scenarios"], "observed": comparison["changes"]["regressed"]},
    ]


def cohort_comparison(comparison: dict, scenario_ids: list[str]) -> dict:
    """Subset already-validated pairs; do not rewrite or re-audit source summaries."""
    selected = set(scenario_ids)
    report = deepcopy(comparison)
    rows = [row for row in report["scenarios"] if row["scenario_id"] in selected]
    deltas = [row["delta"] for row in rows]
    try:
        mean, interval = statistics.fmean(deltas), list(_bootstrap_ci(deltas))
        if not all(math.isfinite(value) for value in [mean, *interval]):
            raise ValueError("nonfinite cohort statistics")
    except (ValueError, OverflowError) as exc:
        raise AgentBomError("cohort statistics exceed finite numeric range") from exc
    report.update(scenarios=rows, scenario_count=len(rows), mean_delta=mean, delta_ci95=interval,
                  changes={change: sum(row["change"] == change for row in rows)
                           for change in ("improved", "regressed", "unchanged")},
                  scope={"kind": "declared_cohort", "scenario_ids": sorted(selected),
                         "full_evaluation_scenario_count": comparison["scenario_count"]})
    if len(rows) == 1:
        report["warnings"].append("This cohort has one scenario; its interval cannot estimate between-scenario variation.")
    if len(set(deltas)) == 1:
        report["warnings"].append("Identical observed cohort deltas yield a degenerate interval, not certainty.")
    report["warnings"].append("Cohort membership is supplied, not independently verified. Intervals are descriptive and not adjusted for multiple comparisons.")
    return report


def review_evaluations(policy: dict, baseline: dict, candidate: dict) -> dict:
    validate_policy(policy)
    reports = []
    failures = []
    checks = []
    for rule in policy["metrics"]:
        metric = rule["metric"]
        comparison = compare_evaluations(baseline, candidate, metric=metric, direction=rule["direction"])
        if {row["scenario_id"] for row in comparison["scenarios"]} != set(policy["scenario_ids"]):
            raise AgentBomError("evaluation scenario IDs differ from the policy; no subset review is allowed")
        reports.append(comparison)
        evaluated = metric_checks(rule, comparison, candidate["results"])
        checks.append({"metric": metric, "checks": evaluated})
        failures.extend({"metric": metric, "constraint": check["constraint"]}
                        for check in evaluated if not check["passed"])
    # These apply to both sources and every metric, including summaries not selected
    # by the policy. Known historical discrepancies cannot silently satisfy a review.
    for label, source in (("baseline", baseline), ("candidate", candidate)):
        if source["n_repeats"] < policy["minimum_repeats"]:
            failures.append({"source": label, "constraint": "minimum_repeats"})
        if reports[0]["source_audits"][label]["status"] != "consistent":
            failures.append({"source": label, "constraint": "summary_consistency"})
    cohort_reviews = []
    for cohort in policy.get("cohorts", []):
        selected = set(cohort["scenario_ids"])
        candidate_rows = [row for row in candidate["results"] if row["scenario_id"] in selected]
        scoped_reports, scoped_checks, scoped_failures = [], [], []
        by_metric = {report["metric"]: report for report in reports}
        for rule in cohort["metrics"]:
            comparison = cohort_comparison(by_metric[rule["metric"]], cohort["scenario_ids"])
            evaluated = metric_checks(rule, comparison, candidate_rows)
            scoped_reports.append(comparison)
            scoped_checks.append({"metric": rule["metric"], "checks": evaluated})
            scoped_failures.extend({"cohort_id": cohort["cohort_id"], "metric": rule["metric"], "constraint": check["constraint"]}
                                   for check in evaluated if not check["passed"])
        failures.extend(scoped_failures)
        cohort_reviews.append({"cohort_id": cohort["cohort_id"], "scenario_ids": sorted(selected),
                               "status": "constraints_not_met" if scoped_failures else "constraints_met",
                               "metric_checks": scoped_checks, "comparisons": scoped_reports})
    result = {
        "report_version": "aau-evaluation-policy-review/1.0",
        "policy_sha256": digest(policy), "baseline_sha256": digest(baseline), "candidate_sha256": digest(candidate),
        "policy": policy, "status": "constraints_met" if not failures else "constraints_not_met",
        "failed_constraints": failures, "metric_checks": checks, "comparisons": reports,
        "unreviewed_metrics": sorted({name for source in (baseline, candidate)
                                       for row in source["results"] for name in row["metrics"]}
                                      - {rule["metric"] for rule in policy["metrics"]}),
        "boundary": "Mechanical review of supplied measurements against supplied constraints, not deployment approval, statistical noninferiority, NIST compliance, or proof of safety. Improvements cannot compensate for another failed constraint. Thresholds use unrounded point estimates and individual observed values, not confidence-interval significance. Policy timing, reviewer authority, matching scenario content, scoring validity, execution authenticity, and representativeness are not verified. Commit and independently review the policy before collecting candidate evidence; a hash alone does not prove preregistration. Unlisted metrics are not policy-reviewed.",
    }
    if cohort_reviews:
        result.update(report_version="aau-evaluation-policy-review/1.1", cohort_reviews=cohort_reviews,
                      cohort_boundary="Declared cohorts cover all scenarios and may overlap. Each cohort is checked separately without weighting the global mean again. Membership is supplied, not inferred or authenticated. Passing is not fairness certification or evidence about unmeasured populations; small cohorts and multiple unadjusted intervals require independent review.")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau review-evals", description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        report = review_evaluations(load_json(args.policy), load_json(args.baseline), load_json(args.candidate))
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("review report exceeds verification size limit")
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("review report does not recompute")
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {len(report['failed_constraints'])} failed constraints; not deployment approval")
        return int(report["status"] != "constraints_met")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
