"""Five synthetic candidates: cheap failure, trade-offs, domination, and unknown cost."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_import import import_observations
from aau_harness.eval_matrix import create_matrix, verify_matrix


def matrix_inputs():
    policy, baseline, repaired, diagnostics = demo_inputs()
    candidates = {}
    for name, cost, latency in (("cheap-unsafe", .01, .5), ("balanced", .25, 2),
                                ("fast", .5, 1), ("dominated", .75, 3), ("unknown-cost", .1, 1)):
        source = deepcopy(baseline if name == "cheap-unsafe" else repaired)
        for row in source["observations"]:
            row.update(cost_usd=cost, latency_s=latency)
        if name == "unknown-cost":
            del source["observations"][0]["cost_usd"]
        candidates[name] = import_observations(source)
    plan = {"plan_version": "aau-candidate-matrix/1.0", "candidate_ids": sorted(candidates),
            "criteria": diagnostics["criteria"], "cost_basis": {name: "synthetic" for name in candidates}}
    return plan, policy, import_observations(baseline), candidates


def build_demo(directory: Path):
    plan, policy, baseline, candidates = matrix_inputs()
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in (("plan", plan), ("policy", policy), ("baseline", baseline), *candidates.items()):
        write_json(value, directory / f"{name}.json")
    create_matrix(plan, policy, baseline, candidates, directory / "matrix")
    report = verify_matrix(directory / "matrix")
    if report["operating_groups"][0]["nondominated_recorded_candidates"] != ["balanced", "fast"]:
        raise ValueError("synthetic matrix outcomes differ from the example contract")
    print("Synthetic matrix verified: cheap failure excluded; balanced/fast trade off; missing cost stays unknown.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build_demo(parser.parse_args().out)
