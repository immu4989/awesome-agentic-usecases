"""Synthetic cohort regression: aggregate improvement can conceal a channel regression."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_pack import create_pack
from aau_harness.evaluation_context import capture_context
from aau_harness.runner import ScenarioResult, run_eval


def demo_inputs():
    scenarios = [{"scenario_id": name, "channel": "assisted" if name == "assisted" else "routine"}
                 for name in ("routine-1", "routine-2", "routine-3", "assisted")]
    rule = {"metric": "completion", "direction": "higher", "candidate_observation_limit": 0,
            "max_mean_regression": 0, "max_regressed_scenarios": 0}
    policy = {"policy_version": "aau-evaluation-review-policy/1.1", "minimum_repeats": 2,
              "scenario_ids": [row["scenario_id"] for row in scenarios],
              "metrics": [{**rule, "max_regressed_scenarios": 1}],
              "cohorts": [{"cohort_id": channel, "scenario_ids": [row["scenario_id"] for row in scenarios if row["channel"] == channel],
                           "metrics": [deepcopy(rule)]} for channel in ("routine", "assisted")]}
    context = capture_context(scenarios, {"benchmark": "synthetic-channel-regression-v1"},
                              {"cohorts.py": Path(__file__).read_bytes()})
    def source(mode):
        result = run_eval(scenarios, lambda scenario, repeat: ScenarioResult(
            scenario["scenario_id"], repeat, {"completion": float(
                scenario["channel"] == "assisted" if mode == "baseline"
                else mode == "repaired" or scenario["channel"] == "routine")}, 0, 0.1, 0),
            repeats=2, evaluation_context=context).as_dict()
        result["provenance"] = {"evidence_kind": "synthetic_fixture",
                                "measurement_boundary": "Constructed scores, no model or person. Cost and latency are placeholders."}
        return result
    return policy, source("baseline"), source("regressed"), source("repaired")


def build_demo(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    policy, baseline, regressed, repaired = demo_inputs()
    for name, value in (("policy", policy), ("baseline", baseline), ("regressed", regressed), ("repaired", repaired)):
        write_json(value, directory / f"{name}.json")
    for name, candidate in (("regressed", regressed), ("repaired", repaired)):
        report = create_pack(policy, baseline, candidate, directory / f"{name}-pack")
        print(f"{name}: {report['status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build_demo(parser.parse_args().out)
