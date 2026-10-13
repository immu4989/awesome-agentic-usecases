"""An unchanged synthetic evaluation appears cheaper after a plan edit, not a repair."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_budget import review_budget
from aau_harness.eval_budget_diff import compare_budgets
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_import import import_observations


def change_inputs():
    _, recording, _, diagnostics = demo_inputs()
    evaluation = import_observations(recording)
    original = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": recording["scenario_ids"],
                "minimum_repeats": 4, "criteria": diagnostics["criteria"], "cost_basis": "synthetic",
                "limits": {"cost_per_passing_attempt_usd": .25, "p95_latency_s": 15}, "groups": []}
    denominator = deepcopy(original)
    denominator["criteria"][1]["limit"] = 1
    grouped = deepcopy(original)
    grouped["limits"]["cost_per_passing_attempt_usd"] = .5
    grouped["groups"] = [{"group_id": "protected-route", "scenario_ids": recording["scenario_ids"],
                           "limits": {"cost_per_passing_attempt_usd": .25}}]
    removed = deepcopy(grouped)
    removed["groups"] = []
    return evaluation, {"denominator": (original, denominator), "removed-group": (grouped, removed)}


def build_demo(directory):
    evaluation, pairs = change_inputs()
    directory.mkdir(parents=True, exist_ok=False)
    write_json(evaluation, directory / "evaluation.json")
    for name, (before, after) in pairs.items():
        for side, plan in (("before", before), ("after", after)):
            write_json(plan, directory / f"{name}-{side}.json")
            report = review_budget(plan, evaluation, cost_basis="synthetic")
            write_json(report, directory / f"{name}-{side}-review.json")
            expected = "constraints_not_met" if side == "before" else "constraints_met"
            if report["status"] != expected:
                raise ValueError("synthetic unchanged-evidence counterexample differs from its contract")
        difference = compare_budgets(before, after)
        if difference["status"] != "review_required":
            raise ValueError("changed budget must request review")
        write_json(difference, directory / f"{name}-changes.json")
    print("Synthetic examples verified: unchanged evaluation passes only after a denominator edit or group removal. Neither is an agent improvement.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build_demo(parser.parse_args().out)
