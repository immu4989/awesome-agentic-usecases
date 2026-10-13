from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_budget import review_budget
from aau_harness.eval_budget_diff import compare_budgets


def plan():
    return {"plan_version": "aau-operating-budget/1.0", "scenario_ids": ["routine", "specialist"],
            "minimum_repeats": 4, "cost_basis": "synthetic",
            "criteria": [{"metric": "completion", "direction": "higher", "limit": 1},
                         {"metric": "unauthorized", "direction": "lower", "limit": 0}],
            "limits": {"total_cost_usd": 100, "cost_per_passing_attempt_usd": .5, "p95_latency_s": 2,
                       "max_latency_s": 5, "total_api_calls": 100},
            "groups": [{"group_id": "all-cases", "scenario_ids": ["routine", "specialist"], "limits": {"p95_latency_s": 2}},
                       {"group_id": "specialist", "scenario_ids": ["specialist"], "limits": {"total_cost_usd": 1, "max_latency_s": 5}}]}


@pytest.mark.parametrize("field", ["total_cost_usd", "cost_per_passing_attempt_usd", "p95_latency_s", "max_latency_s", "total_api_calls"])
@pytest.mark.parametrize("direction", ["up", "down", "removed"])
def test_every_supported_upper_limit_change_remains_visible(field, direction):
    original, candidate = plan(), plan()
    if direction == "removed":
        del candidate["limits"][field]
    else:
        candidate["limits"][field] += 1 if direction == "up" else -.25
        if field == "total_api_calls" and direction == "down":
            candidate["limits"][field] = 99
    report = compare_budgets(original, candidate)
    kind = {"up": "limit_increased", "down": "limit_decreased", "removed": "limit_removed"}[direction]
    assert report["changes"] == [{"scope": {"kind": "overall"}, "field": field, "kind": kind,
                                  "baseline": original["limits"][field], "candidate": candidate["limits"].get(field)}]
    # Tightening a numerical ceiling still requests review; this is not an approval shortcut.
    assert report["status"] == "review_required"


@pytest.mark.parametrize("minimum,kind", [(1, "repeats_decreased"), (5, "repeats_increased")])
def test_repeat_requirement_changes_request_review(minimum, kind):
    candidate = plan()
    candidate["minimum_repeats"] = minimum
    report = compare_budgets(plan(), candidate)
    assert report["change_counts"][kind] == 1 and report["status"] == "review_required"


@pytest.mark.parametrize("change", ["raised-floor", "lowered-floor", "direction", "added", "removed"])
def test_any_criterion_change_is_a_denominator_change_not_a_strength_claim(change):
    candidate = plan()
    if change == "raised-floor":
        candidate["criteria"][0]["limit"] = 2
    elif change == "lowered-floor":
        candidate["criteria"][0]["limit"] = 0
    elif change == "direction":
        candidate["criteria"][0]["direction"] = "lower"
    elif change == "added":
        candidate["criteria"].append({"metric": "extra", "direction": "higher", "limit": 0})
    else:
        candidate["criteria"].pop()
    report = compare_budgets(plan(), candidate)
    assert report["change_counts"]["denominator_changed"] == 1
    assert report["changes"][0]["scope"]["kind"] == "joint_pass"
    assert report["status"] == "review_required"


def test_basis_changes_and_case_additions_are_not_inferred_as_stronger_or_weaker():
    candidate = plan()
    candidate["cost_basis"] = "charge"
    candidate["scenario_ids"].append("added")
    candidate["groups"][0]["scenario_ids"].append("added")
    report = compare_budgets(plan(), candidate)
    assert report["change_counts"]["basis_changed"] == 1
    assert report["change_counts"]["scope_changed"] == 2
    assert report["status"] == "review_required"


def test_case_removal_renamed_group_and_overlapping_coverage_do_not_erase_obligations():
    candidate = plan()
    candidate["groups"][1]["group_id"] = "renamed"
    candidate["scenario_ids"] = ["specialist"]
    candidate["groups"][0]["scenario_ids"] = ["specialist"]
    report = compare_budgets(plan(), candidate)
    assert report["change_counts"]["scope_changed"] == 2
    assert report["change_counts"]["group_removed"] == 1
    assert report["change_counts"]["group_added"] == 1
    removed = next(c for c in report["changes"] if c["kind"] == "group_removed")
    assert removed["baseline"]["scenario_ids"] == ["specialist"]
    assert removed["baseline"]["limits"] == plan()["groups"][1]["limits"]


def test_mixed_tightening_and_removal_cannot_cancel_in_report():
    candidate = plan()
    candidate["groups"].pop()
    candidate["groups"][0]["limits"]["total_api_calls"] = 1
    candidate["limits"]["max_latency_s"] = 1
    report = compare_budgets(plan(), candidate)
    assert report["change_counts"]["group_removed"] == 1
    assert report["change_counts"]["limit_added"] == 1
    assert report["change_counts"]["limit_decreased"] == 1
    assert report["status"] == "review_required"


def test_reordering_is_not_an_obligation_change_and_sources_are_not_modified():
    original, candidate = plan(), plan()
    candidate["scenario_ids"].reverse()
    candidate["criteria"].reverse()
    candidate["groups"].reverse()
    candidate["groups"][1]["scenario_ids"].reverse()
    before = deepcopy((original, candidate))
    report = compare_budgets(original, candidate)
    assert report["changes"] == [] and report["status"] == "no_obligation_change_detected"
    assert report["baseline_sha256"] != report["candidate_sha256"]
    assert (original, candidate) == before
    assert report == compare_budgets(original, candidate)


def test_equal_numeric_limit_representations_are_not_policy_changes():
    candidate = plan()
    candidate["limits"]["max_latency_s"] = 5.0
    report = compare_budgets(plan(), candidate)
    assert report["changes"] == []
    assert report["baseline_sha256"] != report["candidate_sha256"]


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("defect", ["unknown-version", "extra", "empty-criteria", "negative-limit", "bool-limit",
                                    "nan-limit", "duplicate-group", "uncovered-case"])
def test_both_input_plans_must_satisfy_the_exact_budget_contract(side, defect):
    inputs = {"baseline": plan(), "candidate": plan()}
    value = inputs[side]
    if defect == "unknown-version":
        value["plan_version"] = "future"
    elif defect == "extra":
        value["weights"] = {}
    elif defect == "empty-criteria":
        value["criteria"] = []
    elif defect == "negative-limit":
        value["limits"]["total_cost_usd"] = -1
    elif defect == "bool-limit":
        value["limits"]["total_cost_usd"] = True
    elif defect == "nan-limit":
        value["limits"]["total_cost_usd"] = float("nan")
    elif defect == "duplicate-group":
        value["groups"].append(deepcopy(value["groups"][0]))
    elif defect == "uncovered-case":
        value["scenario_ids"].append("uncovered")
    with pytest.raises(AgentBomError):
        compare_budgets(**inputs)


def example():
    path = Path(__file__).resolve().parents[1] / "examples/evaluation-review/budget_changes.py"
    spec = importlib.util.spec_from_file_location("budget_change_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_evidence_can_pass_only_because_the_plan_changed(tmp_path):
    module = example()
    source, pairs = module.change_inputs()
    for name, (before, after) in pairs.items():
        old_review = review_budget(before, source, cost_basis="synthetic")
        new_review = review_budget(after, source, cost_basis="synthetic")
        assert old_review["source_sha256"] == new_review["source_sha256"]
        assert old_review["status"] == "constraints_not_met" and new_review["status"] == "constraints_met"
        change = compare_budgets(before, after)
        assert change["status"] == "review_required"
        assert len(change["changes"]) == 1
        assert change["change_counts"]["denominator_changed" if name == "denominator" else "group_removed"] == 1
    before, after = pairs["denominator"]
    assert review_budget(before, source, cost_basis="synthetic")["scopes"][0]["summary"]["cost"]["total_per_passing_attempt_usd"] == .4
    assert review_budget(after, source, cost_basis="synthetic")["scopes"][0]["summary"]["cost"]["total_per_passing_attempt_usd"] == .1
    module.build_demo(tmp_path / "demo")


@pytest.mark.parametrize("changed", [False, True])
def test_cli_report_reverifies_outside_checkout_without_replacing_inputs(tmp_path, monkeypatch, changed):
    original, candidate = plan(), plan()
    if changed:
        candidate["limits"]["max_latency_s"] = 1
    for name, value in (("baseline", original), ("candidate", candidate)):
        (tmp_path / f"{name}.json").write_bytes(rendered(value))
    monkeypatch.chdir(tmp_path)
    args = ["compare-operating-budgets", "baseline.json", "candidate.json"]
    assert main([*args, "--out", "changes.json"]) == int(changed)
    assert main([*args, "--verify", "changes.json"]) == int(changed)
    assert main([*args, "--out", "changes.json"]) == 2
    report = json.loads((tmp_path / "changes.json").read_text())
    report["change_counts"]["basis_changed"] = 999
    (tmp_path / "changes.json").write_bytes(rendered(report))
    assert main([*args, "--verify", "changes.json"]) == 2
    assert (tmp_path / "baseline.json").read_bytes() == rendered(original)
    assert (tmp_path / "candidate.json").read_bytes() == rendered(candidate)


def test_report_size_guard_refuses_output(tmp_path, monkeypatch):
    from aau_harness import eval_budget_diff

    for name in ("baseline", "candidate"):
        (tmp_path / f"{name}.json").write_bytes(rendered(plan()))
    monkeypatch.setattr(eval_budget_diff, "MAX_JSON_BYTES", 100)
    assert main(["compare-operating-budgets", str(tmp_path / "baseline.json"), str(tmp_path / "candidate.json"),
                 "--out", str(tmp_path / "changes.json")]) == 2
    assert not (tmp_path / "changes.json").exists()
