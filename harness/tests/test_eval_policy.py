import json
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_policy import review_evaluations, validate_policy
from aau_harness.runner import ScenarioResult, run_eval


def policy():
    return {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["a", "b"],
            "minimum_repeats": 2, "metrics": [
                {"metric": name, "direction": "higher", "candidate_observation_limit": limit,
                 "max_mean_regression": 0, "max_regressed_scenarios": 0}
                for name, limit in (("completion", 0), ("authorization", 1))]}


def evidence(candidate=False, unsafe=False, repeats=2):
    return run_eval(["a", "b"], lambda scenario, repeat: ScenarioResult(
        scenario, repeat, {"completion": float(candidate or scenario == "b"),
                           "authorization": float(not (unsafe and scenario == "a" and repeat == 0)),
                           "diagnostic": 0.0}, 0, 0.1, 0), repeats=repeats).as_dict()


def test_improved_completion_cannot_compensate_for_one_unauthorized_observation():
    report = review_evaluations(policy(), evidence(), evidence(True, True))
    assert report["status"] == "constraints_not_met"
    assert report["comparisons"][0]["mean_delta"] == 0.5
    assert report["metric_checks"][0]["checks"][0]["passed"]
    check = report["metric_checks"][1]["checks"][0]
    assert check["violations"] == [{"scenario_id": "a", "repeat": 0, "value": 0}]
    assert {item["constraint"] for item in report["failed_constraints"]} == {
        "candidate_observation_limit", "max_mean_regression", "max_regressed_scenarios"}
    assert report["unreviewed_metrics"] == ["diagnostic"]


def test_legitimate_improvement_passes_and_binds_every_input():
    before, after, rules = evidence(), evidence(True), policy()
    report = review_evaluations(rules, before, after)
    assert report["status"] == "constraints_met"
    assert report["failed_constraints"] == []
    assert report == review_evaluations(rules, before, after)
    changed = deepcopy(rules)
    changed["metrics"][0]["candidate_observation_limit"] = -1
    assert review_evaluations(changed, before, after)["policy_sha256"] != report["policy_sha256"]


def test_lower_direction_uses_ceiling_and_inclusive_limits():
    rules = policy()
    rules["metrics"] = [{"metric": "diagnostic", "direction": "lower",
                         "candidate_observation_limit": 0, "max_mean_regression": 0,
                         "max_regressed_scenarios": 0}]
    assert review_evaluations(rules, evidence(), evidence(True))["status"] == "constraints_met"
    after = evidence(True)
    after["results"][0]["metrics"]["diagnostic"] = 0.01
    report = review_evaluations(rules, evidence(), after)
    assert not report["metric_checks"][0]["checks"][0]["passed"]
    assert {"source": "candidate", "constraint": "summary_consistency"} in report["failed_constraints"]


def test_individual_limits_cannot_be_diluted_by_repeats_or_permissive_mean_budget():
    rules = policy()
    rules["metrics"][1].update(max_mean_regression=1, max_regressed_scenarios=2)
    report = review_evaluations(rules, evidence(), evidence(True, True))
    assert report["failed_constraints"] == [{"metric": "authorization", "constraint": "candidate_observation_limit"}]


def test_minimum_repeats_is_not_silently_waived():
    report = review_evaluations(policy(), evidence(repeats=1), evidence(True, repeats=1))
    assert report["failed_constraints"] == [
        {"source": "baseline", "constraint": "minimum_repeats"},
        {"source": "candidate", "constraint": "minimum_repeats"}]


def test_policy_requires_declared_cases_and_complete_required_metrics():
    rules = policy()
    rules["scenario_ids"] = ["a", "c"]
    with pytest.raises(AgentBomError, match="scenario IDs"):
        review_evaluations(rules, evidence(), evidence(True))
    after = evidence(True)
    del after["results"][0]["metrics"]["authorization"]
    with pytest.raises(AgentBomError, match="every observation"):
        review_evaluations(policy(), evidence(), after)


@pytest.mark.parametrize("defect", ["unknown", "empty", "duplicate", "bool-limit", "nan", "negative",
                                     "bool-repeats", "duplicate-id", "unknown-rule", "too-many-regressions"])
def test_strict_policy_contract(defect):
    rules = policy()
    if defect == "unknown":
        rules["allow_failures"] = True
    elif defect == "empty":
        rules["metrics"] = []
    elif defect == "duplicate":
        rules["metrics"].append(deepcopy(rules["metrics"][0]))
    elif defect == "bool-limit":
        rules["metrics"][0]["candidate_observation_limit"] = True
    elif defect == "nan":
        rules["metrics"][0]["max_mean_regression"] = float("nan")
    elif defect == "negative":
        rules["metrics"][0]["max_mean_regression"] = -1
    elif defect == "bool-repeats":
        rules["minimum_repeats"] = True
    elif defect == "duplicate-id":
        rules["scenario_ids"] = ["a", "a"]
    elif defect == "unknown-rule":
        rules["metrics"][0]["allow"] = True
    else:
        rules["metrics"][0]["max_regressed_scenarios"] = 3
    with pytest.raises(AgentBomError):
        validate_policy(rules)


@pytest.mark.parametrize("unsafe", [False, True])
def test_cli_exit_codes_exclusive_output_and_reverification(tmp_path, unsafe):
    paths = [tmp_path / name for name in ("policy.json", "before.json", "after.json", "review.json")]
    for path, value in zip(paths, (policy(), evidence(), evidence(True, unsafe))):
        path.write_text(json.dumps(value))
    args = ["review-evals", *map(str, paths[:3])]
    assert main([*args, "--out", str(paths[3])]) == int(unsafe)
    original = paths[3].read_bytes()
    assert main([*args, "--out", str(paths[3])]) == 2
    assert paths[3].read_bytes() == original
    assert main([*args, "--verify", str(paths[3])]) == int(unsafe)
    value = json.loads(original)
    value["status"] = "forged"
    paths[3].write_text(json.dumps(value))
    assert main([*args, "--verify", str(paths[3])]) == 2
    paths[3].write_bytes(original)
    changed = policy()
    changed["metrics"][0]["candidate_observation_limit"] = -1
    paths[0].write_text(json.dumps(changed))
    assert main([*args, "--verify", str(paths[3])]) == 2


def test_documented_synthetic_twins_reproduce_without_overwriting(tmp_path):
    script = Path(__file__).resolve().parents[1] / "examples/evaluation-review/demo.py"
    spec = importlib.util.spec_from_file_location("evaluation_review_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = tmp_path / "demo"
    module.build_demo(destination)
    for name in ("legitimate", "unsafe"):
        report = json.loads((destination / f"{name}-review.json").read_text())
        assert all(item["context_match"]["status"] == "matched" for item in report["comparisons"])
    for name, expected in (("legitimate", 0), ("unsafe", 1)):
        assert main(["review-evals", str(destination / "policy.json"), str(destination / "baseline.json"),
                     str(destination / f"{name}.json"), "--verify", str(destination / f"{name}-review.json")]) == expected
    with pytest.raises(FileExistsError):
        module.build_demo(destination)
