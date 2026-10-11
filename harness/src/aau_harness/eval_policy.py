"""Review saved evaluations against explicit, non-compensating metric constraints."""

import argparse
import math
import sys
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_compare import compare_evaluations


def validate_policy(policy: dict) -> None:
    fields = {"policy_version", "scenario_ids", "minimum_repeats", "metrics"}
    if not isinstance(policy, dict) or set(policy) != fields:
        raise AgentBomError("policy requires exactly policy_version, scenario_ids, minimum_repeats, metrics")
    if policy["policy_version"] != "aau-evaluation-review-policy/1.0":
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
        sign = 1 if rule["direction"] == "higher" else -1
        regression = max(0.0, -sign * comparison["mean_delta"])
        violated = [
            {"scenario_id": row["scenario_id"], "repeat": row["repeat"], "value": row["metrics"][metric]}
            for row in sorted(candidate["results"], key=lambda item: (item["scenario_id"], item["repeat"]))
            if sign * row["metrics"][metric] < sign * rule["candidate_observation_limit"]
        ]
        metric_checks = [
            {"constraint": "candidate_observation_limit", "passed": not violated,
             "limit": rule["candidate_observation_limit"], "violations": violated},
            {"constraint": "max_mean_regression", "passed": regression <= rule["max_mean_regression"],
             "limit": rule["max_mean_regression"], "observed": regression},
            {"constraint": "max_regressed_scenarios",
             "passed": comparison["changes"]["regressed"] <= rule["max_regressed_scenarios"],
             "limit": rule["max_regressed_scenarios"], "observed": comparison["changes"]["regressed"]},
        ]
        checks.append({"metric": metric, "checks": metric_checks})
        failures.extend({"metric": metric, "constraint": check["constraint"]}
                        for check in metric_checks if not check["passed"])
    # These apply to both sources and every metric, including summaries not selected
    # by the policy. Known historical discrepancies cannot silently satisfy a review.
    for label, source in (("baseline", baseline), ("candidate", candidate)):
        if source["n_repeats"] < policy["minimum_repeats"]:
            failures.append({"source": label, "constraint": "minimum_repeats"})
        if reports[0]["source_audits"][label]["status"] != "consistent":
            failures.append({"source": label, "constraint": "summary_consistency"})
    return {
        "report_version": "aau-evaluation-policy-review/1.0",
        "policy_sha256": digest(policy), "baseline_sha256": digest(baseline), "candidate_sha256": digest(candidate),
        "policy": policy, "status": "constraints_met" if not failures else "constraints_not_met",
        "failed_constraints": failures, "metric_checks": checks, "comparisons": reports,
        "unreviewed_metrics": sorted({name for source in (baseline, candidate)
                                       for row in source["results"] for name in row["metrics"]}
                                      - {rule["metric"] for rule in policy["metrics"]}),
        "boundary": "Mechanical review of supplied measurements against supplied constraints, not deployment approval, statistical noninferiority, NIST compliance, or proof of safety. Improvements cannot compensate for another failed constraint. Thresholds use unrounded point estimates and individual observed values, not confidence-interval significance. Policy timing, reviewer authority, matching scenario content, scoring validity, execution authenticity, and representativeness are not verified. Commit and independently review the policy before collecting candidate evidence; a hash alone does not prove preregistration. Unlisted metrics are not policy-reviewed.",
    }


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
