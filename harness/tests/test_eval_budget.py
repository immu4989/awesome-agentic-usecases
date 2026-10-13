from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_budget import review_budget, validate_budget
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_import import import_observations
from aau_harness.eval_matrix import create_matrix, verify_matrix


DEMO = Path(__file__).resolve().parents[1] / "examples/evaluation-review/operating_budget.py"
spec = importlib.util.spec_from_file_location("budget_example", DEMO)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def inputs():
    _, _, recording, diagnostics = demo_inputs()
    plan = {
        "plan_version": "aau-operating-budget/1.0",
        "scenario_ids": recording["scenario_ids"],
        "minimum_repeats": 4,
        "criteria": diagnostics["criteria"],
        "cost_basis": "synthetic",
        "limits": {
            "total_cost_usd": 1,
            "cost_per_passing_attempt_usd": 0.25,
            "p95_latency_s": 2,
            "max_latency_s": 2,
            "total_api_calls": 8,
        },
        "groups": [],
    }
    return plan, import_observations(recording)


def test_aggregate_pass_cannot_hide_group_failure_or_enter_matrix(tmp_path):
    budget, matrix, policy, candidates = demo.budget_inputs()
    original = deepcopy((budget, matrix, policy, candidates))
    report = review_budget(budget, candidates["aggregate-trap"], cost_basis="synthetic")
    assert report["status"] == "constraints_not_met"
    assert all(c["status"] == "met" for c in report["scopes"][0]["checks"])
    assert report["scopes"][0]["summary"]["latency"]["p95_s"] == 1
    specialist = report["scopes"][2]
    assert specialist["summary"]["latency"]["p95_s"] == 30
    assert specialist["summary"]["cost"]["total_per_passing_attempt_usd"] == 8
    assert all(c["status"] == "exceeded" for c in specialist["checks"])
    result = create_matrix(matrix, policy, candidates["repaired"], candidates, tmp_path / "matrix")
    assert result == verify_matrix(tmp_path / "matrix")
    assert result["candidates"][0]["policy_status"] == "constraints_met"
    assert result["candidates"][0]["exclusion_reasons"] == ["operating_budget_not_met_or_verified"]
    assert result["operating_groups"][0]["eligible_candidates"] == ["repaired"]
    assert len(list((tmp_path / "matrix").iterdir())) == 14
    assert (budget, matrix, policy, candidates) == original
    assert (
        b"specialist" not in (tmp_path / "matrix/matrix.html").read_bytes()
    )  # details live in linked reports
    assert b"all budget checks" in (tmp_path / "matrix/matrix.html").read_bytes()


def test_all_limits_are_inclusive_and_overlapping_groups_do_not_inflate_totals():
    plan, source = inputs()
    plan["groups"] = [
        {"group_id": name, "scenario_ids": plan["scenario_ids"], "limits": plan["limits"]}
        for name in ("first", "overlap")
    ]
    report = review_budget(plan, source, cost_basis="synthetic")
    assert report["status"] == "constraints_met"
    assert all(s["summary"]["cost"]["total_usd"] == 1 for s in report["scopes"])
    assert len(report["scopes"]) == 3


@pytest.mark.parametrize(
    "field,affected", [("cost_usd", "cost"), ("latency_s", "latency"), ("n_api_calls", "calls")]
)
def test_missing_measurements_never_pass_even_generous_limits(field, affected):
    plan, source = inputs()
    del source["results"][0][field]
    report = review_budget(plan, source, cost_basis="synthetic")
    assert report["status"] == "constraints_not_verified"
    unknown = [c for c in report["scopes"][0]["checks"] if c["status"] == "not_verified"]
    assert unknown and all(affected in c["constraint"] and c["observed"] is None for c in unknown)
    assert all(c["reason"] == "incomplete_measurement_coverage" for c in unknown)


def test_failure_costs_are_included_and_zero_success_has_no_unit_cost():
    plan, source = inputs()
    plan["criteria"][0]["limit"] = 2
    report = review_budget(plan, source, cost_basis="synthetic")
    checks = {c["constraint"]: c for c in report["scopes"][0]["checks"]}
    assert checks["cost_per_passing_attempt_usd"]["reason"] == "no_jointly_passing_attempts"
    assert checks["total_cost_usd"]["observed"] == 1
    assert report["scopes"][0]["summary"]["cost"]["spent_on_failed_attempts_usd"] == 1
    assert report["status"] == "constraints_not_verified"


@pytest.mark.parametrize("basis", ["estimate", "charge", "unknown"])
def test_basis_mismatch_blocks_cost_but_not_measured_latency(basis):
    plan, source = inputs()
    report = review_budget(plan, source, cost_basis=basis)
    assert report["status"] == "constraints_not_verified"
    for check in report["scopes"][0]["checks"]:
        assert check["status"] == ("not_verified" if "cost" in check["constraint"] else "met")


def test_known_failure_remains_visible_alongside_unverified_and_insufficient_repeats():
    plan, source = inputs()
    plan["minimum_repeats"] = 5
    del source["results"][0]["cost_usd"]
    plan["limits"]["p95_latency_s"] = 1
    report = review_budget(plan, source, cost_basis="synthetic")
    assert report["status"] == "constraints_not_met"
    assert report["prerequisites"][0]["status"] == "not_verified"
    assert {c["status"] for c in report["scopes"][0]["checks"]} == {
        "met",
        "exceeded",
        "not_verified",
    }


@pytest.mark.parametrize(
    "defect",
    [
        "extra",
        "version",
        "bool-limit",
        "nan-limit",
        "infinite-limit",
        "negative-limit",
        "huge-limit",
        "unknown-limit",
        "fractional-calls",
        "empty-limits",
        "duplicate-ids",
        "empty-ids",
        "bool-repeats",
        "too-many-repeats",
        "unknown-basis",
        "empty-criteria",
        "unknown-group-id",
        "uncovered-group",
        "duplicate-group",
        "too-many-groups",
        "extra-group",
        "empty-group",
        "negative-group-limit",
    ],
)
def test_invalid_plans_fail_closed(defect):
    plan, _ = inputs()
    group = {
        "group_id": "all",
        "scenario_ids": plan["scenario_ids"],
        "limits": {"p95_latency_s": 2},
    }
    if defect == "extra":
        plan["weights"] = {}
    elif defect == "version":
        plan["plan_version"] = "future"
    elif defect in {"bool-limit", "nan-limit", "infinite-limit", "negative-limit", "huge-limit"}:
        plan["limits"]["p95_latency_s"] = {
            "bool-limit": True,
            "nan-limit": float("nan"),
            "infinite-limit": float("inf"),
            "negative-limit": -1,
            "huge-limit": 10**400,
        }[defect]
    elif defect == "unknown-limit":
        plan["limits"]["mean_cost"] = 1
    elif defect == "fractional-calls":
        plan["limits"]["total_api_calls"] = 1.5
    elif defect == "empty-limits":
        plan["limits"] = {}
    elif defect == "duplicate-ids":
        plan["scenario_ids"] *= 2
    elif defect == "empty-ids":
        plan["scenario_ids"] = []
    elif defect == "bool-repeats":
        plan["minimum_repeats"] = True
    elif defect == "too-many-repeats":
        plan["minimum_repeats"] = 10001
    elif defect == "unknown-basis":
        plan["cost_basis"] = "unknown"
    elif defect == "empty-criteria":
        plan["criteria"] = []
    else:
        plan["groups"] = [group]
        if defect == "unknown-group-id":
            group["scenario_ids"] = ["other"]
        elif defect == "uncovered-group":
            plan["scenario_ids"] = [*plan["scenario_ids"], "other"]
        elif defect == "duplicate-group":
            plan["groups"] *= 2
        elif defect == "too-many-groups":
            plan["groups"] *= 21
        elif defect == "extra-group":
            group["weight"] = 0
        elif defect == "empty-group":
            group["scenario_ids"] = []
        elif defect == "negative-group-limit":
            group["limits"]["p95_latency_s"] = -1
    with pytest.raises(AgentBomError):
        validate_budget(plan)


def test_wrong_census_and_malformed_observations_rejected():
    plan, source = inputs()
    plan["scenario_ids"] = ["other"]
    with pytest.raises(AgentBomError, match="census"):
        review_budget(plan, source, cost_basis="synthetic")
    plan, source = inputs()
    source["results"][0]["latency_s"] = True
    with pytest.raises(AgentBomError):
        review_budget(plan, source, cost_basis="synthetic")


@pytest.mark.parametrize("code", [0, 1])
def test_cli_verifies_both_outcomes_preserves_failure_and_refuses_overwrite(
    tmp_path, monkeypatch, code
):
    plan, source = inputs()
    if code:
        plan["limits"]["max_latency_s"] = 1
    for name, value in (("plan", plan), ("source", source)):
        (tmp_path / f"{name}.json").write_bytes(rendered(value))
    monkeypatch.chdir(tmp_path)
    args = ["operating-budget", "plan.json", "source.json", "--cost-basis", "synthetic"]
    assert main([*args, "--out", "report.json"]) == code
    assert main([*args, "--verify", "report.json"]) == code
    assert main([*args, "--out", "report.json"]) == 2
    report = json.loads((tmp_path / "report.json").read_text())
    report["scopes"][0]["summary"]["attempt_count"] = 999
    (tmp_path / "report.json").write_bytes(rendered(report))
    assert main([*args, "--verify", "report.json"]) == 2


def test_budget_reports_in_matrix_recomputed_even_if_rehashed(tmp_path):
    budget, matrix, policy, candidates = demo.budget_inputs()
    pack = tmp_path / "matrix"
    create_matrix(matrix, policy, candidates["repaired"], candidates, pack)
    name = "candidate-01-budget.json"
    report = json.loads((pack / name).read_text())
    report["status"] = "constraints_met"
    (pack / name).write_bytes(rendered(report))
    manifest = json.loads((pack / "manifest.json").read_text())
    manifest["files"][name] = digest((pack / name).read_bytes())
    (pack / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_matrix(pack)
    matrix["operating_budget"]["criteria"] = [
        {"metric": "completion", "direction": "higher", "limit": 0}
    ]
    with pytest.raises(AgentBomError, match="same joint-pass"):
        create_matrix(matrix, policy, candidates["repaired"], candidates, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_demo_contract(tmp_path):
    demo.build_demo(tmp_path / "demo")


def test_inconsistent_metric_headline_does_not_pass_budget():
    plan, source = inputs()
    source["metric_means"]["completion"] = 0
    report = review_budget(plan, source, cost_basis="synthetic")
    assert report["status"] == "constraints_not_verified"
    assert report["source_metric_audit"]["mismatches"]
    assert all(c["status"] == "met" for c in report["scopes"][0]["checks"])


def test_partial_success_includes_all_failed_attempt_costs():
    plan, _ = inputs()
    _, recording, _, _ = demo_inputs()
    report = review_budget(plan, import_observations(recording), cost_basis="synthetic")
    cost = report["scopes"][0]["summary"]["cost"]
    assert cost["total_per_passing_attempt_usd"] == .4
    assert cost["spent_on_failed_attempts_usd"] == pytest.approx(.3)
    assert report["status"] == "constraints_not_met"


def test_report_bound_enforced_before_write(tmp_path, monkeypatch):
    from aau_harness import eval_budget

    plan, source = inputs()
    for name, value in (("plan", plan), ("source", source)):
        (tmp_path / f"{name}.json").write_bytes(rendered(value))
    monkeypatch.setattr(eval_budget, "MAX_JSON_BYTES", 50)
    assert main(["operating-budget", str(tmp_path / "plan.json"), str(tmp_path / "source.json"),
                 "--cost-basis", "synthetic", "--out", str(tmp_path / "report.json")]) == 2
    assert not (tmp_path / "report.json").exists()
