from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_pack import create_pack, verify_pack
from aau_harness.eval_policy import review_evaluations, validate_policy


def example():
    path = Path(__file__).resolve().parents[1] / "examples/evaluation-review/cohorts.py"
    spec = importlib.util.spec_from_file_location("cohort_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_positive_global_delta_cannot_hide_a_declared_channel_regression():
    policy, baseline, candidate, repaired = example().demo_inputs()
    legacy = {key: value for key, value in policy.items() if key != "cohorts"}
    legacy["policy_version"] = "aau-evaluation-review-policy/1.0"
    assert review_evaluations(legacy, baseline, candidate)["status"] == "constraints_met"
    report = review_evaluations(policy, baseline, candidate)
    assert report["comparisons"][0]["mean_delta"] == 0.5
    assert report["status"] == "constraints_not_met"
    assert all(failure["cohort_id"] == "assisted" for failure in report["failed_constraints"])
    routine, assisted = report["cohort_reviews"]
    assert routine["status"] == "constraints_met"
    delta = assisted["comparisons"][0]
    assert delta["mean_delta"] == -1
    assert delta["delta_ci95"] == [-1, -1]
    assert delta["scenario_count"] == 1
    assert delta["scope"]["full_evaluation_scenario_count"] == 4
    assert any("one scenario" in warning for warning in delta["warnings"])
    assert review_evaluations(policy, baseline, repaired)["status"] == "constraints_met"


def test_overlapping_cohorts_do_not_reweight_global_comparison():
    policy, baseline, candidate, _ = example().demo_inputs()
    policy["cohorts"].append({"cohort_id": "all", "scenario_ids": policy["scenario_ids"],
                              "metrics": deepcopy(policy["metrics"])})
    report = review_evaluations(policy, baseline, candidate)
    assert report["comparisons"][0]["mean_delta"] == 0.5
    assert report["cohort_reviews"][-1]["comparisons"][0]["mean_delta"] == 0.5
    assert len(report["failed_constraints"]) == 2


def test_lower_is_better_cohorts_detect_regression_despite_global_improvement():
    policy, original, changed, _ = example().demo_inputs()
    for rules in [policy["metrics"], *(group["metrics"] for group in policy["cohorts"])]:
        for rule in rules:
            rule.update(direction="lower", candidate_observation_limit=1)
    # Reverse the sources and preferred direction: global decrease, assisted increase.
    report = review_evaluations(policy, changed, original)
    assert report["comparisons"][0]["mean_delta"] == -0.5
    assert all(check["passed"] for check in report["metric_checks"][0]["checks"])
    assert report["cohort_reviews"][1]["comparisons"][0]["mean_delta"] == 1
    assert {failure["cohort_id"] for failure in report["failed_constraints"]} == {"assisted"}
    assert report["status"] == "constraints_not_met"


@pytest.mark.parametrize("defect", ["uncovered", "unknown-id", "duplicate-cohort", "duplicate-case", "empty",
                                     "unknown-metric", "reversed-direction", "unknown-field", "too-many-regressions"])
def test_cohort_policy_rejects_ambiguous_or_incomplete_scope(defect):
    policy, *_ = example().demo_inputs()
    group = policy["cohorts"][1]
    if defect == "uncovered":
        policy["cohorts"].pop()
    elif defect == "unknown-id":
        group["scenario_ids"] = ["unknown"]
    elif defect == "duplicate-cohort":
        group["cohort_id"] = "routine"
    elif defect == "duplicate-case":
        group["scenario_ids"] = ["assisted", "assisted"]
    elif defect == "empty":
        policy["cohorts"] = []
    elif defect == "unknown-metric":
        group["metrics"][0]["metric"] = "invented"
    elif defect == "reversed-direction":
        group["metrics"][0]["direction"] = "lower"
    elif defect == "unknown-field":
        group["ignored"] = True
    else:
        group["metrics"][0]["max_regressed_scenarios"] = 2
    with pytest.raises(AgentBomError):
        validate_policy(policy)


def test_cohort_observation_limits_use_only_member_observations():
    policy, baseline, candidate, _ = example().demo_inputs()
    policy["cohorts"][1]["metrics"][0]["candidate_observation_limit"] = 1
    report = review_evaluations(policy, baseline, candidate)
    violations = report["cohort_reviews"][1]["metric_checks"][0]["checks"][0]["violations"]
    assert [(row["scenario_id"], row["repeat"]) for row in violations] == [("assisted", 0), ("assisted", 1)]


def test_cohort_reports_recompute_and_html_preserves_scope_and_escapes_names(tmp_path):
    policy, baseline, candidate, _ = example().demo_inputs()
    policy["cohorts"][1]["cohort_id"] = '<script>alert("group")</script>'
    pack = tmp_path / "pack"
    report = create_pack(policy, baseline, candidate, pack)
    assert verify_pack(pack) == report
    page = (pack / "review.html").read_text()
    assert "<script" not in page
    assert "Cohort &lt;script&gt;" in page
    assert "not fairness certification" in page
    changed = json.loads((pack / "review.json").read_text())
    changed["cohort_reviews"] = []
    (pack / "review.json").write_text(json.dumps(changed))
    with pytest.raises(AgentBomError):
        verify_pack(pack)


def test_documented_cohort_twins_have_expected_cli_exit_codes(tmp_path):
    output = tmp_path / "cohorts"
    example().build_demo(output)
    for name, code in (("regressed", 1), ("repaired", 0)):
        assert main(["evaluation-pack", "verify", str(output / f"{name}-pack")]) == code
