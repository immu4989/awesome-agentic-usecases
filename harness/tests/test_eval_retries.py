from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_budget import review_budget
from aau_harness.eval_import import import_observations
from aau_harness.eval_operations import review_operations
from aau_harness.eval_pack import create_pack, verify_pack
from aau_harness.eval_retries import FILES, create_retry_pack, retry_payloads, verify_retry_pack
from aau_harness.evaluation_context import capture_context


def inputs():
    root = Path(__file__).resolve().parents[1] / "examples/evaluation-review"
    return tuple(
        json.loads((root / name).read_text()) for name in ("retry-plan.json", "retry-ledger.json")
    )


CRITERIA = [
    {"metric": "completion", "direction": "higher", "limit": 1},
    {"metric": "unauthorized", "direction": "lower", "limit": 0},
]


def test_retry_fixture_keeps_failed_costs_earlier_harm_and_whole_task_latency(tmp_path):
    plan, ledger = inputs()
    original = deepcopy((plan, ledger))
    report, files = retry_payloads(plan, ledger)
    assert report["task_count"] == 2 and report["attempt_count"] == 4 and report["retry_count"] == 2
    assert report["tasks_with_retries"] == 1 and report["last_only_metrics"] == ["completion"]
    rows = json.loads(files["evaluation.json"])["results"]
    assert rows[0]["metrics"] == {"completion": 1, "unauthorized": 1}
    assert rows[0]["cost_usd"] == pytest.approx(0.3) and rows[0]["n_api_calls"] == 3
    assert rows[0]["latency_s"] == 10  # Not final call (1) or sum of call durations (3).
    operations = review_operations(
        json.loads(files["evaluation.json"]), criteria=CRITERIA, cost_basis="synthetic"
    )
    assert operations["overall"]["cost"]["total_per_passing_attempt_usd"] == pytest.approx(0.4)
    assert operations["overall"]["latency"]["p95_s"] == 10
    assert json.loads(files["ledger.json"]) == ledger
    assert (plan, ledger) == original
    assert (report, files) == retry_payloads(plan, ledger)
    assert create_retry_pack(plan, ledger, tmp_path / "pack") == verify_retry_pack(
        tmp_path / "pack"
    )


@pytest.mark.parametrize("field", ["cost_usd", "n_api_calls"])
def test_one_unknown_attempt_prevents_complete_task_totals_and_budget_pass(field):
    plan, ledger = inputs()
    del ledger["tasks"][0]["attempts"][0][field]
    report, files = retry_payloads(plan, ledger)
    source = json.loads(files["evaluation.json"])
    assert field not in source["results"][0]
    coverage = report["tasks"][0]["operating"][field]
    assert coverage["reporting_attempts"] == 2 and coverage["complete_total"] is None
    assert coverage["observed_sum"] == pytest.approx(0.2 if field == "cost_usd" else 2)
    budget = {
        "plan_version": "aau-operating-budget/1.0",
        "scenario_ids": ["service"],
        "minimum_repeats": 2,
        "criteria": CRITERIA,
        "cost_basis": "synthetic",
        "groups": [],
        "limits": {"total_cost_usd" if field == "cost_usd" else "total_api_calls": 100},
    }
    assert (
        review_budget(budget, source, cost_basis="synthetic")["status"]
        == "constraints_not_verified"
    )


def test_missing_whole_task_latency_is_never_filled_from_attempt_latencies():
    plan, ledger = inputs()
    del ledger["tasks"][0]["elapsed_s"]
    report, files = retry_payloads(plan, ledger)
    assert report["tasks"][0]["whole_task_latency_s"] is None
    assert "latency_s" not in json.loads(files["evaluation.json"])["results"][0]


@pytest.mark.parametrize("reducer,expected", [("min", 0), ("max", 1), ("last", 1)])
def test_explicit_metric_reducers_and_index_order_not_input_order(reducer, expected):
    plan, ledger = inputs()
    plan["metric_reducers"]["completion"] = reducer
    ledger["tasks"].reverse()
    ledger["tasks"][1]["attempts"].reverse()
    _, files = retry_payloads(plan, ledger)
    assert json.loads(files["evaluation.json"])["results"][0]["metrics"]["completion"] == expected
    assert json.loads(files["ledger.json"]) == ledger


@pytest.mark.parametrize("reducer", ["min", "max", "last"])
def test_missing_scores_do_not_become_success_and_last_is_explicit(reducer):
    plan, ledger = inputs()
    plan["metric_reducers"]["completion"] = reducer
    del ledger["tasks"][0]["attempts"][0]["metrics"]["completion"]
    report, files = retry_payloads(plan, ledger)
    metrics = json.loads(files["evaluation.json"])["results"][0]["metrics"]
    assert ("completion" in metrics) == (reducer == "last")
    assert report["tasks"][0]["metric_coverage"]["completion"]["reporting_attempts"] == 2
    del ledger["tasks"][0]["attempts"][-1]["metrics"]["completion"]
    _, files = retry_payloads(plan, ledger)
    assert "completion" not in json.loads(files["evaluation.json"])["results"][0]["metrics"]


def test_all_missing_costs_are_unknown_but_explicit_zero_is_retained():
    plan, ledger = inputs()
    for attempt in ledger["tasks"][0]["attempts"]:
        del attempt["cost_usd"]
        attempt["n_api_calls"] = 0
    report, files = retry_payloads(plan, ledger)
    assert report["tasks"][0]["operating"]["cost_usd"]["observed_sum"] is None
    assert json.loads(files["evaluation.json"])["results"][0]["n_api_calls"] == 0


@pytest.mark.parametrize(
    "defect",
    [
        "plan-version",
        "plan-extra",
        "parallel",
        "bad-reducer",
        "empty-reducers",
        "ledger-version",
        "ledger-extra",
        "empty-tasks",
        "missing-task",
        "duplicate-task",
        "unknown-scenario",
        "bad-repeat",
        "zero-count",
        "bool-count",
        "over-count",
        "omitted-attempt",
        "duplicate-id",
        "cross-task-id",
        "duplicate-index",
        "bool-index",
        "index-gap",
        "extra-attempt",
        "extra-task",
        "bad-metric",
        "undeclared-metric",
        "bool-metric",
        "nan-cost",
        "negative-cost",
        "null-cost",
        "bool-cost",
        "fractional-calls",
        "overflow-calls",
        "overflow-cost",
        "too-short-elapsed",
        "null-elapsed",
        "metric-overflow",
        "bad-context",
    ],
)
def test_invalid_or_truncated_evidence_is_rejected_before_output(tmp_path, defect):
    plan, ledger = inputs()
    task = ledger["tasks"][0]
    attempt = task["attempts"][0]
    if defect == "plan-version":
        plan["plan_version"] = "future"
    elif defect == "plan-extra":
        plan["auto_retry"] = True
    elif defect == "parallel":
        plan["attempt_scope"] = "parallel"
    elif defect == "bad-reducer":
        plan["metric_reducers"]["completion"] = "average"
    elif defect == "empty-reducers":
        plan["metric_reducers"] = {}
    elif defect == "ledger-version":
        ledger["ledger_version"] = "future"
    elif defect == "ledger-extra":
        ledger["ignored"] = []
    elif defect == "empty-tasks":
        ledger["tasks"] = []
    elif defect == "missing-task":
        ledger["tasks"].pop()
    elif defect == "duplicate-task":
        ledger["tasks"][1]["repeat"] = 0
    elif defect == "unknown-scenario":
        task["scenario_id"] = "other"
    elif defect == "bad-repeat":
        task["repeat"] = True
    elif defect == "zero-count":
        task["attempt_count"] = 0
    elif defect == "bool-count":
        task["attempt_count"] = True
    elif defect == "over-count":
        task["attempt_count"] = 101
    elif defect == "omitted-attempt":
        task["attempts"].pop()
    elif defect == "duplicate-id":
        task["attempts"][1]["attempt_id"] = attempt["attempt_id"]
    elif defect == "cross-task-id":
        ledger["tasks"][1]["attempts"][0]["attempt_id"] = attempt["attempt_id"]
    elif defect == "duplicate-index":
        task["attempts"][1]["attempt_index"] = 0
    elif defect == "bool-index":
        attempt["attempt_index"] = False
    elif defect == "index-gap":
        attempt["attempt_index"] = 4
    elif defect == "extra-attempt":
        attempt["prompt"] = "not permitted"
    elif defect == "extra-task":
        task["cost_usd"] = 0.1
    elif defect == "bad-metric":
        attempt["metrics"]["completion"] = "1"
    elif defect == "undeclared-metric":
        attempt["metrics"]["hidden"] = 1
    elif defect == "bool-metric":
        attempt["metrics"]["completion"] = True
    elif defect == "nan-cost":
        attempt["cost_usd"] = float("nan")
    elif defect == "negative-cost":
        attempt["cost_usd"] = -1
    elif defect == "null-cost":
        attempt["cost_usd"] = None
    elif defect == "bool-cost":
        attempt["cost_usd"] = True
    elif defect == "fractional-calls":
        attempt["n_api_calls"] = 0.5
    elif defect == "overflow-calls":
        for a in task["attempts"]:
            a["n_api_calls"] = 10**12
    elif defect == "overflow-cost":
        for a in task["attempts"]:
            a["cost_usd"] = 1e308
    elif defect == "too-short-elapsed":
        task["elapsed_s"] = 1
    elif defect == "null-elapsed":
        task["elapsed_s"] = None
    elif defect == "metric-overflow":
        attempt["metrics"]["completion"] = 10**400
    elif defect == "bad-context":
        plan["evaluation_context"] = {}
    with pytest.raises(AgentBomError):
        create_retry_pack(plan, ledger, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("name", sorted(FILES))
def test_all_pack_members_are_recomputed_even_if_manifest_is_rehashed(tmp_path, name):
    plan, ledger = inputs()
    directory = tmp_path / "pack"
    create_retry_pack(plan, ledger, directory)
    path = directory / name
    value = json.loads(path.read_text())
    value["extra"] = "changed"
    path.write_bytes(rendered(value))
    if name != "manifest.json":
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["files"][name] = digest(path.read_bytes())
        (directory / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_retry_pack(directory)


def test_last_call_only_export_changes_cost_latency_and_harm_not_just_sample_count():
    plan, ledger = inputs()
    _, files = retry_payloads(plan, ledger)
    recording = json.loads(files["recording.json"])
    for row, task in zip(recording["observations"], ledger["tasks"]):
        last = task["attempts"][-1]
        row.update(
            {
                key: deepcopy(last[key])
                for key in ("metrics", "cost_usd", "latency_s", "n_api_calls")
            }
        )
    naive = review_operations(
        import_observations(recording), criteria=CRITERIA, cost_basis="synthetic"
    )["overall"]
    full = review_operations(
        json.loads(files["evaluation.json"]), criteria=CRITERIA, cost_basis="synthetic"
    )["overall"]
    assert naive["attempt_count"] == full["attempt_count"] == 2
    assert naive["passing_attempt_count"] == 2 and full["passing_attempt_count"] == 1
    assert naive["cost"]["total_per_passing_attempt_usd"] == 0.1
    assert full["cost"]["total_per_passing_attempt_usd"] == pytest.approx(0.4)
    assert naive["latency"]["p95_s"] == 1 and full["latency"]["p95_s"] == 10


def test_cli_outside_checkout_and_downstream_dossier_binding(tmp_path, monkeypatch):
    plan, ledger = inputs()
    for name, value in (("plan", plan), ("ledger", ledger)):
        (tmp_path / f"{name}.json").write_bytes(rendered(value))
    monkeypatch.chdir(tmp_path)
    assert main(["retry-eval", "create", "plan.json", "ledger.json", "--out", "pack"]) == 0
    assert main(["retry-eval", "create", "plan.json", "ledger.json", "--out", "pack"]) == 2
    source = json.loads(Path("pack/evaluation.json").read_text())
    policy = {
        "policy_version": "aau-evaluation-review-policy/1.0",
        "scenario_ids": ["service"],
        "minimum_repeats": 2,
        "metrics": [
            {
                "metric": "unauthorized",
                "direction": "lower",
                "candidate_observation_limit": 0,
                "max_mean_regression": 0,
                "max_regressed_scenarios": 0,
            }
        ],
    }
    create_pack(policy, source, source, Path("dossier"))
    assert verify_pack(Path("dossier"))["status"] == "constraints_not_met"
    args = ["retry-eval", "verify", "pack", "--evaluation", "dossier/candidate.json"]
    assert main(args) == 0
    source["results"][0]["cost_usd"] = 0.1
    Path("dossier/candidate.json").write_bytes(rendered(source))
    assert main(args) == 2
    assert json.loads(Path("plan.json").read_text()) == plan
    assert json.loads(Path("ledger.json").read_text()) == ledger


@pytest.mark.parametrize("defect", ["extra", "missing", "symlink", "oversized"])
def test_pack_file_boundary(tmp_path, defect):
    plan, ledger = inputs()
    directory = tmp_path / "pack"
    create_retry_pack(plan, ledger, directory)
    if defect == "extra":
        (directory / "extra").write_text("extra")
    elif defect == "missing":
        (directory / "accounting.json").unlink()
    elif defect == "symlink":
        (directory / "ledger.json").rename(tmp_path / "source.json")
        (directory / "ledger.json").symlink_to(tmp_path / "source.json")
    else:
        (directory / "ledger.json").write_bytes(b"x" * 2_000_001)
    with pytest.raises(AgentBomError):
        verify_retry_pack(directory)


def test_declared_context_survives_and_attempt_order_is_explicit():
    plan, ledger = inputs()
    plan["evaluation_context"] = capture_context(
        [{"scenario_id": "service"}],
        {"unit": "logical_task", "reducers": plan["metric_reducers"]},
        {"fixture": b"Synthetic full-trajectory scoring declaration, not actual execution"},
    )
    _, original = retry_payloads(plan, ledger)
    ledger["tasks"].reverse()
    for task in ledger["tasks"]:
        task["attempts"].reverse()
    _, reordered = retry_payloads(plan, ledger)
    assert original["recording.json"] == reordered["recording.json"]
    assert original["evaluation.json"] == reordered["evaluation.json"]
    assert json.loads(reordered["evaluation.json"])["evaluation_context"] == plan["evaluation_context"]
    assert original["ledger.json"] != reordered["ledger.json"]


def test_sequential_duration_roundoff_is_not_a_false_contract_failure():
    plan, ledger = inputs()
    task = ledger["tasks"][0]
    task["elapsed_s"] = .3
    for attempt in task["attempts"]:
        attempt["latency_s"] = .1
    retry_payloads(plan, ledger)
    task["elapsed_s"] = .29
    with pytest.raises(AgentBomError):
        retry_payloads(plan, ledger)


@pytest.mark.parametrize("bad", [None, [], "text", 1, True])
@pytest.mark.parametrize("side", ["plan", "ledger"])
def test_top_level_types_are_rejected(bad, side):
    plan, ledger = inputs()
    with pytest.raises(AgentBomError):
        retry_payloads(bad if side == "plan" else plan, bad if side == "ledger" else ledger)


def test_bounded_inputs_fail_before_output(tmp_path, monkeypatch):
    from aau_harness import eval_retries

    plan, ledger = inputs()
    monkeypatch.setattr(eval_retries, "MAX_JSON_BYTES", 100)
    with pytest.raises(AgentBomError):
        create_retry_pack(plan, ledger, tmp_path / "large")
    assert not (tmp_path / "large").exists()
