"""Expose changed operating obligations and accounting assumptions before approving a budget."""

import argparse
from copy import deepcopy
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_budget import validate_budget


KINDS = ("scope_changed", "basis_changed", "denominator_changed", "group_added", "group_removed",
         "limit_added", "limit_removed", "limit_increased", "limit_decreased", "repeats_increased", "repeats_decreased")


def compare_budgets(baseline: dict, candidate: dict) -> dict:
    for plan in (baseline, candidate):
        validate_budget(plan)
    changes = []

    def add(scope, field, kind, before, after):
        changes.append({"scope": deepcopy(scope), "field": field, "kind": kind,
                        "baseline": deepcopy(before), "candidate": deepcopy(after)})

    def compare_scope(scope, before, after):
        old_ids, new_ids = sorted(before["scenario_ids"]), sorted(after["scenario_ids"])
        if old_ids != new_ids:
            add(scope, "scenario_ids", "scope_changed", old_ids, new_ids)
        old_limits, new_limits = before["limits"], after["limits"]
        for measure in sorted(set(old_limits) | set(new_limits)):
            old, new = old_limits.get(measure), new_limits.get(measure)
            if old == new:
                continue
            kind = ("limit_added" if old is None else "limit_removed" if new is None else
                    "limit_increased" if new > old else "limit_decreased")
            add(scope, measure, kind, old, new)

    overall = {"kind": "overall"}
    compare_scope(overall, baseline, candidate)
    if baseline["minimum_repeats"] != candidate["minimum_repeats"]:
        add(overall, "minimum_repeats", "repeats_increased" if candidate["minimum_repeats"] > baseline["minimum_repeats"] else
            "repeats_decreased", baseline["minimum_repeats"], candidate["minimum_repeats"])
    if baseline["cost_basis"] != candidate["cost_basis"]:
        add(overall, "cost_basis", "basis_changed", baseline["cost_basis"], candidate["cost_basis"])
    old_criteria = {rule["metric"]: rule for rule in baseline["criteria"]}
    new_criteria = {rule["metric"]: rule for rule in candidate["criteria"]}
    for metric in sorted(set(old_criteria) | set(new_criteria)):
        old, new = old_criteria.get(metric), new_criteria.get(metric)
        if old != new:
            # Every criterion change alters the defined unit, including apparently stricter ones.
            add({"kind": "joint_pass", "metric": metric}, "criterion", "denominator_changed", old, new)
    old_groups = {group["group_id"]: group for group in baseline["groups"]}
    new_groups = {group["group_id"]: group for group in candidate["groups"]}
    for name in sorted(set(old_groups) | set(new_groups)):
        old, new = old_groups.get(name), new_groups.get(name)
        scope = {"kind": "group", "group_id": name}
        if old is None or new is None:
            add(scope, "group", "group_added" if old is None else "group_removed", old, new)
        else:
            compare_scope(scope, old, new)
    report = {
        "report_version": "aau-operating-budget-diff/1.0", "baseline_sha256": digest(baseline),
        "candidate_sha256": digest(candidate), "status": "review_required" if changes else "no_obligation_change_detected",
        "changes": changes, "change_counts": {kind: sum(c["kind"] == kind for c in changes) for kind in KINDS},
        "boundary": "Structural comparison of two valid supplied operating budgets, not approval, policy timing, production suitability, or proof of equivalent acceptance sets. Every changed obligation or assumption requests review, including added groups and lower limits. Raised/lowered labels describe numeric thresholds only, not net policy strength when scope, cost basis, or success criteria also change. All joint-pass criterion changes are accounting-definition changes; scores are not examined and no savings or success improvements are inferred. Scope additions can dilute ratios or change percentiles. Group renames appear as removal plus addition, not inferred equivalence. Removed obligations remain visible even if another scope covers the same cases. Reordering lists/dictionaries and numerically equal limits are not enumerated as obligation changes; source-value hashes still identify the supplied inputs. A no-change result is not approval. No approved hashes, files, workflow settings, or source evaluations are modified. Names and plan details may be sensitive; inspect before sharing. Hashes are not signatures.",
    }
    if len(rendered(report)) > MAX_JSON_BYTES:
        raise AgentBomError("operating budget comparison exceeds 2 MB")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aau compare-operating-budgets", description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_budgets(load_json(args.baseline), load_json(args.candidate))
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("operating budget comparison does not recompute")
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {len(report['changes'])} operating budget changes; not approval")
        return int(bool(report["changes"]))
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
