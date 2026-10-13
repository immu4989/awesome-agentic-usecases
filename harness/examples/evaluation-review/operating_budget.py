"""Synthetic workload: a good aggregate conceals one slow, expensive service route."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_budget import review_budget
from aau_harness.eval_import import import_observations
from aau_harness.eval_matrix import create_matrix, verify_matrix
from aau_harness.evaluation_context import capture_context


def budget_inputs():
    ids = [f"routine-{i:02d}" for i in range(19)] + ["specialist-route"]
    criteria = [{"metric": "completion", "direction": "higher", "limit": 1}]
    limits = {"cost_per_passing_attempt_usd": .5, "p95_latency_s": 2}
    budget = {"plan_version": "aau-operating-budget/1.0", "scenario_ids": ids, "minimum_repeats": 4,
              "criteria": criteria, "cost_basis": "synthetic", "limits": limits,
              "groups": [{"group_id": "routine", "scenario_ids": ids[:-1], "limits": limits},
                         {"group_id": "specialist", "scenario_ids": ids[-1:], "limits": limits}]}
    context = capture_context([{"scenario_id": name} for name in ids], {"fixture": "operating-budget-demo"},
                              {"operating_budget.py": Path(__file__).read_bytes()})
    candidates = {}
    for name in ("aggregate-trap", "repaired"):
        candidates[name] = import_observations({"format_version": "aau-recorded-observations/1.1",
            "source_label": "Constructed synthetic costs and timings; no model or real users",
            "scenario_ids": ids, "n_repeats": 4, "evaluation_context": context,
            "observations": [{"scenario_id": identity, "repeat": repeat, "metrics": {"completion": 1},
                "cost_usd": 8 if name == "aggregate-trap" and identity == "specialist-route" else .1,
                "latency_s": 30 if name == "aggregate-trap" and identity == "specialist-route" else 1,
                "n_api_calls": 1} for identity in ids for repeat in range(4)]})
    policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ids, "minimum_repeats": 4,
              "metrics": [{"metric": "completion", "direction": "higher", "candidate_observation_limit": 1,
                           "max_mean_regression": 0, "max_regressed_scenarios": 0}]}
    matrix = {"plan_version": "aau-candidate-matrix/1.1", "candidate_ids": sorted(candidates),
              "criteria": criteria, "cost_basis": {name: "synthetic" for name in candidates}, "operating_budget": budget}
    return budget, matrix, policy, candidates


def build_demo(directory):
    budget, matrix, policy, candidates = budget_inputs()
    directory.mkdir(parents=True, exist_ok=False)
    write_json(budget, directory / "budget.json")
    for name, source in candidates.items():
        write_json(source, directory / f"{name}.json")
        report = review_budget(budget, source, cost_basis="synthetic")
        write_json(report, directory / f"{name}-budget.json")
        expected = "constraints_not_met" if name == "aggregate-trap" else "constraints_met"
        if report["status"] != expected or any(c["status"] != "met" for c in report["scopes"][0]["checks"]):
            raise ValueError("synthetic operating budget outcome differs from its contract")
    create_matrix(matrix, policy, candidates["repaired"], candidates, directory / "matrix")
    report = verify_matrix(directory / "matrix")
    if report["operating_groups"][0]["eligible_candidates"] != ["repaired"]:
        raise ValueError("synthetic matrix failed to retain the group-level exclusion")
    print("Synthetic example verified: aggregate limits pass; specialist group fails; repaired candidate meets all limits.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build_demo(parser.parse_args().out)
