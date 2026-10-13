"""Synthetic matching and changed test definitions with identical score headlines."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_context_diff import compare_evaluation_contexts
from aau_harness.evaluation_context import capture_context
from aau_harness.runner import ScenarioResult, run_eval


def demo_inputs():
    baseline_cases = [{"scenario_id": "routine", "authorization_required": False},
                      {"scenario_id": "assisted", "authorization_required": True}]
    changed_cases = [{"scenario_id": "routine", "authorization_required": True},
                     {"scenario_id": "replacement", "authorization_required": False}]

    def source(cases):
        context = capture_context(cases, {"synthetic_fixture": True}, {"context-drift.py": Path(__file__).read_bytes()})
        value = run_eval(cases, lambda case, repeat: ScenarioResult(case["scenario_id"], repeat,
            {"completion": 1}, 0, .1, 0), repeats=2, evaluation_context=context).as_dict()
        value["provenance"] = {"evidence_kind": "synthetic_fixture",
            "boundary": "Constructed scores and placeholder operational fields, not model runs or real service outcomes."}
        return value
    return source(baseline_cases), source(baseline_cases), source(changed_cases)


def build_demo(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    baseline, matched, changed = demo_inputs()
    for name, value in (("baseline", baseline), ("matched", matched), ("changed", changed)):
        write_json(value, directory / f"{name}.json")
    for name, value in (("matched", matched), ("changed", changed)):
        report = compare_evaluation_contexts(baseline, value)
        write_json(report, directory / f"{name}-context-review.json")
        print(f"{name}: {report['status']}; synthetic context inventory only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    build_demo(parser.parse_args().out)
