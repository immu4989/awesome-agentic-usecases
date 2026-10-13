"""Check declared operating limits on complete recorded workloads and explicit groups."""

import argparse
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_operations import COST_BASES, _summary, review_operations
from .eval_repeatability import _criteria


LIMITS = {
    "total_cost_usd": ("cost", "total_usd"),
    "cost_per_passing_attempt_usd": ("cost", "total_per_passing_attempt_usd"),
    "p95_latency_s": ("latency", "p95_s"),
    "max_latency_s": ("latency", "max_s"),
    "total_api_calls": ("api_calls", "total"),
}
BOUNDARY = ("Checks inclusive upper limits on supplied recorded attempts, not production SLO compliance, "
            "future spending, verified invoices, deployment approval, fairness, or statistical assurance. "
            "Joint-pass criteria define an accounting denominator, not a quality gate. Use a separate policy review. "
            "Costs of failed attempts remain included; absent values are unknown. Cost basis and group membership "
            "are caller declarations. Groups may overlap; their totals must not be added. Thresholds and minimum "
            "repeats are supplied, not recommended or statistically justified. Small-sample p95 is often the maximum. "
            "No production traffic weights, missing costs, measurements, or runtime authenticity are inferred. "
            "Hashes bind supplied content but are not signatures. No execution, uploads, or approvals.")


def _ids(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= 500
            or any(not isinstance(name, str) or not name.strip() or len(name) > 200 for name in value)
            or len(set(value)) != len(value)):
        raise AgentBomError("scenario_ids requires 1 to 500 distinct nonblank names")
    return set(value)


def _limits(value):
    if not isinstance(value, dict) or not value or not set(value) <= set(LIMITS):
        raise AgentBomError("operating limits must select supported measures")
    for name, limit in value.items():
        if type(limit) not in (int, float) or not 0 <= limit <= sys.float_info.max:
            raise AgentBomError("operating limits must be finite nonnegative numbers, not booleans")
        if name == "total_api_calls" and type(limit) is not int:
            raise AgentBomError("total_api_calls limit must be an integer")


def validate_budget(plan: dict):
    fields = {"plan_version", "scenario_ids", "minimum_repeats", "criteria", "cost_basis", "limits", "groups"}
    if not isinstance(plan, dict) or set(plan) != fields or plan["plan_version"] != "aau-operating-budget/1.0":
        raise AgentBomError("operating budget fields differ from the 1.0 contract")
    ids = _ids(plan["scenario_ids"])
    n = plan["minimum_repeats"]
    if type(n) is not int or n < 1 or n * len(ids) > 10000:
        raise AgentBomError("minimum_repeats must be positive and fit the observation bound")
    _criteria(plan["criteria"])
    if not isinstance(plan["cost_basis"], str) or plan["cost_basis"] not in COST_BASES[:-1]:
        raise AgentBomError("budget cost basis must be estimate, charge, or synthetic")
    _limits(plan["limits"])
    groups = plan["groups"]
    if not isinstance(groups, list) or len(groups) > 20:
        raise AgentBomError("groups must contain at most 20 explicit groups")
    seen, covered = set(), set()
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"group_id", "scenario_ids", "limits"}:
            raise AgentBomError("each operating group requires group_id, scenario_ids, and limits")
        name = group["group_id"]
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in seen:
            raise AgentBomError("operating group IDs must be unique nonblank names")
        seen.add(name)
        selected = _ids(group["scenario_ids"])
        if not selected <= ids:
            raise AgentBomError("operating group contains undeclared scenarios")
        covered.update(selected)
        _limits(group["limits"])
    if groups and covered != ids:
        raise AgentBomError("declared operating groups must cover every scenario; overlap is allowed")


def review_budget(plan: dict, source: dict, *, cost_basis: str) -> dict:
    validate_budget(plan)
    operations = review_operations(source, criteria=plan["criteria"], cost_basis=cost_basis)
    if {row["scenario_id"] for row in operations["scenarios"]} != set(plan["scenario_ids"]):
        raise AgentBomError("operating budget requires the exact declared scenario census")
    prerequisites = [
        {"constraint": "minimum_repeats", "observed": source["n_repeats"], "limit": plan["minimum_repeats"],
         "status": "met" if source["n_repeats"] >= plan["minimum_repeats"] else "not_verified"},
        {"constraint": "metric_summary_consistency", "observed": operations["source_metric_audit"]["status"],
         "status": "met" if operations["source_metric_audit"]["status"] == "consistent" else "not_verified"},
    ]
    rules = _criteria(plan["criteria"])
    rows = sorted(source["results"], key=lambda r: (r["scenario_id"], r["repeat"]))
    passing = {(r["scenario_id"], r["repeat"]) for r in rows if all(
        r["metrics"][c["metric"]] >= c["limit"] if c["direction"] == "higher" else
        r["metrics"][c["metric"]] <= c["limit"] for c in rules)}

    def scope(ids, limits, kind, identity=None):
        summary = _summary([r for r in rows if r["scenario_id"] in ids], passing)
        checks = []
        for name, limit in sorted(limits.items()):
            section, field = LIMITS[name]
            observed = summary[section][field]
            reason = None
            if section == "cost" and cost_basis != plan["cost_basis"]:
                reason = "declared_cost_basis_mismatch"
            elif summary[section]["status"] != "complete":
                reason = "incomplete_measurement_coverage"
            elif observed is None:
                reason = "no_jointly_passing_attempts"
            checks.append({"constraint": name, "limit": limit, "observed": observed,
                           "status": "not_verified" if reason else "met" if observed <= limit else "exceeded",
                           "reason": reason})
        return {"scope": kind, "group_id": identity, "scenario_ids": sorted(ids), "summary": summary, "checks": checks}

    scopes = [scope(set(plan["scenario_ids"]), plan["limits"], "overall")]
    scopes.extend(scope(set(g["scenario_ids"]), g["limits"], "group", g["group_id"])
                  for g in sorted(plan["groups"], key=lambda g: g["group_id"]))
    checks = prerequisites + [c for s in scopes for c in s["checks"]]
    status = ("constraints_not_met" if any(c["status"] == "exceeded" for c in checks) else
              "constraints_not_verified" if any(c["status"] == "not_verified" for c in checks) else "constraints_met")
    report = {"report_version": "aau-operating-budget-review/1.0", "plan_sha256": digest(plan),
              "source_sha256": digest(source), "status": status, "declared_cost_basis": cost_basis,
              "required_cost_basis": plan["cost_basis"], "criteria": rules, "prerequisites": prerequisites,
              "scopes": scopes, "source_metric_audit": operations["source_metric_audit"],
              "warnings": operations["warnings"], "boundary": BOUNDARY}
    if len(rendered(report)) > MAX_JSON_BYTES:
        raise AgentBomError("operating budget report exceeds 2 MB")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aau operating-budget", description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("evaluation", type=Path)
    parser.add_argument("--cost-basis", choices=COST_BASES, required=True)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        report = review_budget(load_json(args.plan), load_json(args.evaluation), cost_basis=args.cost_basis)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("operating budget report does not recompute")
        else:
            write_json(report, args.out)
        print(f"Recorded operating budget: {report['status']}. Not production approval.")
        return 0 if report["status"] == "constraints_met" else 1
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
