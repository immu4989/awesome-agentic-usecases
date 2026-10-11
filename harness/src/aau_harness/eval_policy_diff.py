"""Explain changed evaluation obligations without treating policy edits as approval."""

import argparse
from copy import deepcopy
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_policy import validate_policy


REQUIRES_REVIEW = {"relaxed", "removed", "scope_changed", "direction_changed"}


def compare_policies(baseline: dict, candidate: dict) -> dict:
    for policy in (baseline, candidate):
        validate_policy(policy)
    changes = []

    def add(scope, field, kind, before, after, metric=None):
        changes.append({"scope": scope, "field": field, "kind": kind,
                        **({"metric": metric} if metric is not None else {}),
                        "baseline": deepcopy(before), "candidate": deepcopy(after)})

    def compare_scope(scope, before, after):
        before_ids, after_ids = sorted(before["scenario_ids"]), sorted(after["scenario_ids"])
        if before_ids != after_ids:
            # Even adding cases may dilute a mean or change the meaning of a count budget.
            add(scope, "scenario_ids", "scope_changed", before_ids, after_ids)
        old_rules = {rule["metric"]: rule for rule in before["metrics"]}
        new_rules = {rule["metric"]: rule for rule in after["metrics"]}
        for metric in sorted(set(old_rules) | set(new_rules)):
            old, new = old_rules.get(metric), new_rules.get(metric)
            if old is None or new is None:
                add(scope, "metric_rule", "added" if old is None else "removed", old, new, metric)
                continue
            changed_direction = old["direction"] != new["direction"]
            if changed_direction:
                add(scope, "direction", "direction_changed", old["direction"], new["direction"], metric)
            for field in ("candidate_observation_limit", "max_mean_regression", "max_regressed_scenarios"):
                if old[field] == new[field]:
                    continue
                if changed_direction:
                    kind = "direction_changed"
                else:
                    # Larger regression budgets relax; a higher floor tightens, a higher ceiling relaxes.
                    larger_relaxes = field != "candidate_observation_limit" or old["direction"] == "lower"
                    relaxed = (new[field] > old[field]) == larger_relaxes
                    kind = "relaxed" if relaxed else "tightened"
                add(scope, field, kind, old[field], new[field], metric)

    global_scope = {"kind": "global"}
    compare_scope(global_scope, baseline, candidate)
    if baseline["minimum_repeats"] != candidate["minimum_repeats"]:
        add(global_scope, "minimum_repeats",
            "relaxed" if candidate["minimum_repeats"] < baseline["minimum_repeats"] else "tightened",
            baseline["minimum_repeats"], candidate["minimum_repeats"])
    old_cohorts = {group["cohort_id"]: group for group in baseline.get("cohorts", [])}
    new_cohorts = {group["cohort_id"]: group for group in candidate.get("cohorts", [])}
    for name in sorted(set(old_cohorts) | set(new_cohorts)):
        scope = {"kind": "cohort", "cohort_id": name}
        old, new = old_cohorts.get(name), new_cohorts.get(name)
        if old is None or new is None:
            add(scope, "cohort", "added" if old is None else "removed", old, new)
        else:
            compare_scope(scope, old, new)
    required = [index for index, change in enumerate(changes) if change["kind"] in REQUIRES_REVIEW]
    return {
        "report_version": "aau-evaluation-policy-diff/1.0",
        "baseline_sha256": digest(baseline), "candidate_sha256": digest(candidate),
        "baseline_policy_version": baseline["policy_version"], "candidate_policy_version": candidate["policy_version"],
        "status": "review_required" if required else "no_relaxation_detected",
        "changes": changes, "review_required_change_indices": required,
        "change_counts": {kind: sum(change["kind"] == kind for change in changes)
                          for kind in ("added", "removed", "tightened", "relaxed", "scope_changed", "direction_changed")},
        "boundary": "Structural comparison of supplied policies, not approval, preregistration, a fairness assessment, or a proof of equivalent acceptance sets. Scenario membership changes and direction changes require review rather than being called stronger or weaker. A removed obligation is flagged even when another rule may cover it. No_relaxation_detected only means this comparison found no enumerated relaxation, removal, or incomparable scope/direction change; reviewers must still assess validity, representativeness, authority, and any new obligations. Hashes identify supplied JSON values, not policy approval or timing. No evaluation scores were examined and no approved pins were changed.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aau compare-eval-policies", description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_policies(load_json(args.baseline), load_json(args.candidate))
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise AgentBomError("policy comparison exceeds 2 MB")
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("policy comparison does not recompute")
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {len(report['changes'])} policy changes; not approval")
        return int(report["status"] == "review_required")
    except (AgentBomError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
