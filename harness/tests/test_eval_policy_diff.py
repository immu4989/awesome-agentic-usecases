from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_import import import_observations
from aau_harness.eval_policy import review_evaluations
from aau_harness.eval_policy_diff import compare_policies


EXAMPLES = Path(__file__).resolve().parents[1] / "examples/evaluation-review"


def policy():
    return json.loads((EXAMPLES / "policy-original.json").read_text())


def test_documented_policy_change_makes_same_bad_evidence_pass_but_flags_relaxation():
    before, after = policy(), json.loads((EXAMPLES / "policy-relaxed.json").read_text())
    recording = json.loads((EXAMPLES / "recorded-observations.json").read_text())
    baseline = import_observations(recording)
    recording["observations"][0]["metrics"]["unauthorized_action"] = 1
    candidate = import_observations(recording)
    assert review_evaluations(before, baseline, candidate)["status"] == "constraints_not_met"
    assert review_evaluations(after, baseline, candidate)["status"] == "constraints_met"
    report = compare_policies(before, after)
    assert report["status"] == "review_required"
    assert report["changes"] == [{"scope": {"kind": "global"}, "field": "candidate_observation_limit",
                                   "kind": "relaxed", "metric": "unauthorized_action", "baseline": 0, "candidate": 1}]


@pytest.mark.parametrize("direction,field,before,after,kind", [
    ("lower", "candidate_observation_limit", 0, 1, "relaxed"),
    ("lower", "candidate_observation_limit", 1, 0, "tightened"),
    ("higher", "candidate_observation_limit", 0, 1, "tightened"),
    ("higher", "candidate_observation_limit", 1, 0, "relaxed"),
    ("lower", "max_mean_regression", 0, 1, "relaxed"),
    ("higher", "max_mean_regression", 1, 0, "tightened"),
    ("higher", "max_regressed_scenarios", 0, 1, "relaxed"),
    ("lower", "max_regressed_scenarios", 1, 0, "tightened"),
])
def test_numeric_obligations_respect_metric_direction(direction, field, before, after, kind):
    original = policy()
    original["metrics"][0].update(direction=direction, **{field: before})
    changed = deepcopy(original)
    changed["metrics"][0][field] = after
    report = compare_policies(original, changed)
    assert len(report["changes"]) == 1
    assert report["changes"][0]["kind"] == kind
    assert report["status"] == ("review_required" if kind == "relaxed" else "no_relaxation_detected")


@pytest.mark.parametrize("repeats,kind", [(1, "relaxed"), (3, "tightened")])
def test_repeat_requirements_are_compared(repeats, kind):
    changed = policy()
    changed["minimum_repeats"] = repeats
    assert compare_policies(policy(), changed)["changes"][0]["kind"] == kind


def test_new_cases_and_direction_changes_require_review_not_a_strength_claim():
    changed = policy()
    changed["scenario_ids"].append("new-case")
    changed["metrics"][0].update(direction="higher", candidate_observation_limit=1)
    report = compare_policies(policy(), changed)
    assert report["change_counts"]["scope_changed"] == 1
    assert report["change_counts"]["direction_changed"] == 2
    assert report["review_required_change_indices"] == [0, 1, 2]


def with_cohorts():
    result = policy()
    result.update(policy_version="aau-evaluation-review-policy/1.1",
                  cohorts=[{"cohort_id": name, "scenario_ids": [name], "metrics": deepcopy(result["metrics"])}
                           for name in result["scenario_ids"]])
    return result


def test_policy_downgrade_cannot_silently_discard_cohort_obligations():
    report = compare_policies(with_cohorts(), policy())
    assert report["change_counts"]["removed"] == 2
    assert report["status"] == "review_required"
    assert {change["scope"]["cohort_id"] for change in report["changes"]} == {"routine", "assisted"}
    assert compare_policies(policy(), with_cohorts())["status"] == "no_relaxation_detected"


def test_cohort_membership_changes_and_renames_remain_visible():
    original = with_cohorts()
    changed = deepcopy(original)
    changed["cohorts"][0]["scenario_ids"].append("assisted")
    changed["cohorts"][1]["cohort_id"] = "renamed"
    report = compare_policies(original, changed)
    assert report["change_counts"]["scope_changed"] == 1
    assert report["change_counts"]["removed"] == 1
    assert report["change_counts"]["added"] == 1
    assert report["status"] == "review_required"


def test_removed_metric_is_not_compensated_by_new_or_stronger_obligations():
    original = with_cohorts()
    changed = deepcopy(original)
    changed["minimum_repeats"] = 3
    changed["metrics"].append({**changed["metrics"][0], "metric": "replacement"})
    changed["cohorts"][0]["metrics"][0]["metric"] = "replacement"
    report = compare_policies(original, changed)
    assert report["change_counts"]["removed"] == 1
    assert report["change_counts"]["added"] == 2
    assert report["change_counts"]["tightened"] == 1
    assert report["status"] == "review_required"


def test_reordering_is_not_a_semantic_change_but_hashes_still_identify_supplied_values():
    original = with_cohorts()
    changed = deepcopy(original)
    changed["scenario_ids"].reverse()
    changed["cohorts"].reverse()
    report = compare_policies(original, changed)
    assert report["changes"] == []
    assert report["baseline_sha256"] != report["candidate_sha256"]
    assert report["status"] == "no_relaxation_detected"


def test_invalid_policy_is_not_compared_as_a_relaxation():
    changed = policy()
    changed["metrics"] = []
    with pytest.raises(AgentBomError):
        compare_policies(policy(), changed)


def test_cli_exit_codes_tamper_detection_and_no_overwrite(tmp_path):
    original, relaxed = EXAMPLES / "policy-original.json", EXAMPLES / "policy-relaxed.json"
    output = tmp_path / "comparison.json"
    assert main(["compare-eval-policies", str(original), str(relaxed), "--out", str(output)]) == 1
    assert main(["compare-eval-policies", str(original), str(relaxed), "--verify", str(output)]) == 1
    assert main(["compare-eval-policies", str(original), str(relaxed), "--out", str(output)]) == 2
    output.write_text("{}")
    assert main(["compare-eval-policies", str(original), str(relaxed), "--verify", str(output)]) == 2
    assert main(["compare-eval-policies", str(original), str(original), "--out", str(tmp_path / "unchanged.json")]) == 0
