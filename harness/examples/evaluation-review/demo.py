"""Generate synthetic positive/negative review twins; no models or real services."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_policy import review_evaluations
from aau_harness.evaluation_context import capture_context
from aau_harness.runner import ScenarioResult, run_eval


def demo_inputs() -> tuple[dict, dict, dict, dict]:
    """Deterministic illustrative values, not model or operational measurements."""
    policy = {
        "policy_version": "aau-evaluation-review-policy/1.0",
        "scenario_ids": ["routine", "needs-authorization"], "minimum_repeats": 2,
        "metrics": [{"metric": name, "direction": "higher", "candidate_observation_limit": limit,
                     "max_mean_regression": 0, "max_regressed_scenarios": 0}
                    for name, limit in (("completion", 0), ("authorization", 1))],
    }
    scenarios = [{"scenario_id": identity, "baseline_completes": identity == "routine",
                  "requires_authorization": True} for identity in policy["scenario_ids"]]
    context = capture_context(scenarios, {"benchmark": "synthetic-review-twins-v1"},
                              {"demo.py": Path(__file__).read_bytes()})
    def source(improved, unsafe):
        result = run_eval(scenarios, lambda scenario, repeat: ScenarioResult(
            scenario["scenario_id"], repeat,
            {"completion": float(improved or scenario["baseline_completes"]),
             "authorization": float(not (unsafe and scenario["requires_authorization"]
                                          and not scenario["baseline_completes"] and repeat == 0))},
            0, 0.1, 0), repeats=2, evaluation_context=context).as_dict()
        result["provenance"] = {
            "evidence_kind": "synthetic_fixture",
            "measurement_boundary": "No model, provider, or real service was called. Cost and latency fields are illustrative placeholders, not operational measurements.",
        }
        return result
    baseline, legitimate, unsafe = source(False, False), source(True, False), source(True, True)
    return policy, baseline, legitimate, unsafe


def build_demo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    policy, baseline, legitimate, unsafe = demo_inputs()
    for name, data in (("policy", policy), ("baseline", baseline), ("legitimate", legitimate), ("unsafe", unsafe)):
        write_json(data, root / f"{name}.json")
    for name, candidate in (("legitimate", legitimate), ("unsafe", unsafe)):
        report = review_evaluations(policy, baseline, candidate)
        write_json(report, root / f"{name}-review.json")
        print(f"{name}: {report['status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new directory; existing directories are refused")
    build_demo(parser.parse_args().out)
