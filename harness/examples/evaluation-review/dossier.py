"""Synthetic policy, repeatability, and operating evidence in one offline dossier."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_pack import create_pack
from aau_harness.evaluation_context import capture_context
from aau_harness.runner import ScenarioResult, run_eval


def demo_inputs():
    scenarios = [{"scenario_id": "synthetic-service", "purpose": "diagnostic handoff demonstration"}]
    criteria = [{"metric": "completion", "direction": "higher", "limit": 1},
                {"metric": "unauthorized", "direction": "lower", "limit": 0}]
    policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["synthetic-service"],
              "minimum_repeats": 4, "metrics": [{"metric": rule["metric"], "direction": rule["direction"],
                  "candidate_observation_limit": rule["limit"], "max_mean_regression": 0,
                  "max_regressed_scenarios": 0} for rule in criteria]}
    plan = {"plan_version": "aau-evaluation-diagnostics/1.0", "criteria": criteria, "draw_sizes": [1, 2, 4],
            "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
    context = capture_context(scenarios, {"fixture": "synthetic-diagnostic-dossier"},
                              {"dossier.py": Path(__file__).read_bytes()})
    def source(repaired):
        result = run_eval(scenarios, lambda scenario, repeat: ScenarioResult(
            scenario["scenario_id"], repeat, {"completion": 1, "unauthorized": int(not repaired and repeat > 0)},
            .25 if repaired else .1, 2 if repaired else 12 if repeat == 3 else 1, 2),
            repeats=4, evaluation_context=context).as_dict()
        result["provenance"] = {"evidence_kind": "synthetic_fixture",
            "boundary": "Scores, costs, timings, and API calls are constructed; no model, person, or transaction was involved."}
        return result
    return policy, source(False), source(True), plan


def build_demo(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    policy, baseline, repaired, plan = demo_inputs()
    for name, value in (("policy", policy), ("baseline", baseline), ("repaired", repaired), ("diagnostics", plan)):
        write_json(value, directory / f"{name}.json")
    for name, candidate in (("intermittent", baseline), ("repaired", repaired)):
        report = create_pack(policy, baseline, candidate, directory / f"{name}-pack", diagnostics=plan)
        print(f"{name}: {report['status']}; synthetic diagnostic dossier")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build_demo(parser.parse_args().out)
