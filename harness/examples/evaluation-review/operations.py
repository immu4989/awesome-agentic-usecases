"""Synthetic operating-cost reversal: cheapest attempt is not cheapest passing attempt."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_operations import review_operations
from aau_harness.runner import ScenarioResult, run_eval


def build_demo(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    criteria = [{"metric": "completion", "direction": "higher", "limit": 1},
                {"metric": "unauthorized", "direction": "lower", "limit": 0}]
    for mode in ("cheap-attempt", "repaired"):
        repaired = mode == "repaired"
        source = run_eval(["synthetic-service"], lambda scenario, repeat: ScenarioResult(
            scenario, repeat, {"completion": 1, "unauthorized": int(not repaired and repeat > 0)},
            .25 if repaired else .1, 2 if repaired else 12 if repeat == 3 else 1, 2), repeats=4).as_dict()
        source["provenance"] = {"evidence_kind": "synthetic_fixture",
            "boundary": "All scores, costs, timings, and API-call counts are constructed placeholders. No model, person, payment, or service was involved."}
        report = review_operations(source, criteria=criteria, cost_basis="synthetic")
        write_json(source, directory / f"{mode}.json")
        write_json(report, directory / f"{mode}-operations.json")
        print(f"{mode}: {report['overall']['cost']['total_per_passing_attempt_usd']} synthetic USD per passing attempt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build_demo(parser.parse_args().out)
