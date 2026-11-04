from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_audit import audit_evaluation
from aau_harness.eval_compare import compare_evaluations
from aau_harness.eval_import import import_observations
from aau_harness.eval_service_traces import (
    FILES,
    SCORING_FILES,
    create_service_trace_pack,
    service_trace_payloads,
    verify_service_trace_pack,
)
from aau_harness.public_value_review import assess_public_value_batch


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "public-value-review/examples"


def inputs(unsafe=False, repeats=2):
    contract = load_json(FIXTURES / "contract.json")
    plan = {
        "plan_version": "aau-service-trace-import/1.0",
        "source_label": "Synthetic recorded service traces",
        "n_repeats": repeats,
    }
    suite = {
        "suite_version": "aau-public-value-suite/1.0",
        "cases": [{"case_id": "assisted", "contract": contract}],
    }
    rows = [
        {
            "case_id": "assisted",
            "repeat": repeat,
            "trace": load_json(
                FIXTURES / ("burden-trace.json" if unsafe and repeat == 0 else "exact-trace.json")
            ),
            "cost_usd": 0.1,
            "latency_s": 2,
            "n_api_calls": 1,
        }
        for repeat in range(repeats)
    ]
    return plan, suite, {"trace_version": "aau-public-value-traces/1.1", "observations": rows}


@pytest.mark.parametrize("unsafe", [False, True])
def test_scores_are_derived_from_contract_and_trace_and_sources_are_retained(tmp_path, unsafe):
    plan, suite, traces = inputs(unsafe)
    originals = deepcopy((plan, suite, traces))
    report, files = service_trace_payloads(plan, suite, traces)
    assert (plan, suite, traces) == originals
    assert (report, files) == service_trace_payloads(plan, suite, traces)
    assert set(files) == FILES and list(files)[-1] == "manifest.json"
    evaluation = json.loads(files["evaluation.json"])
    assert evaluation == import_observations(json.loads(files["recording.json"]))
    assert audit_evaluation(evaluation)["status"] == "consistent"
    assert evaluation["metric_means"]["service_completion"] == 1
    assert evaluation["metric_means"]["public_value_exact"] == (0.5 if unsafe else 1)
    assert report["status"] == ("evidence_failed" if unsafe else "evidence_passed")
    assert report["failed_observation_count"] == int(unsafe)
    assert set(report["scoring_context"]["scoring_sha256"]) == set(SCORING_FILES)
    if unsafe:
        assert {f["obligation"] for f in report["observations"][0]["assessment"]["findings"]} == {
            "burden_minimized",
            "accessibility_respected",
            "recourse_preserved",
        }
    destination = tmp_path / "pack"
    assert create_service_trace_pack(plan, suite, traces, destination) == report
    assert verify_service_trace_pack(destination) == report
    for name, original in [("plan", plan), ("suite", suite), ("traces", traces)]:
        assert load_json(destination / f"{name}.json") == original


def test_legacy_single_trace_inputs_match_existing_batch_scoring_without_promoting_inapplicable_protections():
    suite, traces = [load_json(FIXTURES / f"{name}.json") for name in ("suite", "traces")]
    plan = {
        "plan_version": "aau-service-trace-import/1.0",
        "source_label": "Synthetic legacy traces",
        "n_repeats": 1,
    }
    batch = assess_public_value_batch(suite, traces)
    report, files = service_trace_payloads(plan, suite, traces)
    assert [row["assessment"] for row in report["observations"]] == [
        row["assessment"] for row in batch["cases"]
    ]
    assert report["required_protection_coverage"]["recourse_preserved"] == {
        "required_observation_count": 1,
        "satisfied_required_observation_count": 0,
        "not_required_observation_count": 1,
    }
    assert (
        report["required_protection_coverage"]["deadline_protected"]["required_observation_count"]
        == 0
    )
    assert (
        report["required_protection_coverage"]["deadline_protected"][
            "not_required_observation_count"
        ]
        == 2
    )
    assert all(row["repeat"] == 0 for row in json.loads(files["recording.json"])["observations"])
    assert all(
        "cost_usd" not in row and "latency_s" not in row and "n_api_calls" not in row
        for row in json.loads(files["evaluation.json"])["results"]
    )


def test_unsubmitted_and_forbidden_attempts_are_failures_not_successful_prose():
    plan, suite, traces = inputs()
    traces["observations"][0]["trace"]["submitted"] = False
    traces["observations"][1]["trace"]["attempted_events"].append("deny_application")
    report, files = service_trace_payloads(plan, suite, traces)
    rows = json.loads(files["evaluation.json"])["results"]
    assert rows[0]["metrics"]["service_completion"] == 0
    assert rows[1]["metrics"]["intent_alignment"] == 0
    assert rows[1]["metrics"]["rights_safety"] == 1  # Attempted, not recorded executed.
    assert report["failed_observation_count"] == 2


def test_absent_operating_measurements_stay_unknown_and_supplied_zero_is_preserved():
    plan, suite, traces = inputs()
    for field in ("cost_usd", "latency_s", "n_api_calls"):
        del traces["observations"][0][field]
        traces["observations"][1][field] = 0
    _, files = service_trace_payloads(plan, suite, traces)
    rows = json.loads(files["evaluation.json"])["results"]
    for field in ("cost_usd", "latency_s", "n_api_calls"):
        assert field not in rows[0] and rows[1][field] == 0


def test_order_and_collection_labels_do_not_change_scoring_context_but_contract_drift_does():
    plan, suite, traces = inputs()
    first, first_files = service_trace_payloads(plan, suite, traces)
    plan["source_label"] = "A separately named synthetic collection"
    traces["observations"].reverse()
    second, second_files = service_trace_payloads(plan, suite, traces)
    assert first["scoring_context"] == second["scoring_context"]
    assert first["observations"] == second["observations"]
    assert first["traces_sha256"] != second["traces_sha256"]
    compare_evaluations(
        json.loads(first_files["evaluation.json"]),
        json.loads(second_files["evaluation.json"]),
        metric="public_value_exact",
        direction="higher",
    )
    suite["cases"][0]["contract"]["recourse_required"] = False
    changed, changed_files = service_trace_payloads(plan, suite, traces)
    assert changed["scoring_context"] != first["scoring_context"]
    with pytest.raises(AgentBomError, match="contexts differ"):
        compare_evaluations(
            json.loads(first_files["evaluation.json"]),
            json.loads(changed_files["evaluation.json"]),
            metric="public_value_exact",
            direction="higher",
        )


@pytest.mark.parametrize(
    "fault",
    [
        "extra_plan",
        "plan_version",
        "label",
        "repeats_bool",
        "repeats_zero",
        "many",
        "duplicate_case",
        "empty_suite",
        "suite_version",
        "case_controls",
        "extra_case",
        "trace_version",
        "missing_trace",
        "duplicate_repeat",
        "repeat_bool",
        "repeat_outside",
        "unknown_case",
        "extra_trace",
        "missing_repeat",
        "scores",
        "contract_override",
        "context_override",
        "bad_flag",
        "missing_flag",
        "trace_prose",
        "held_outside_required",
        "cost_bool",
        "cost_negative",
        "cost_null",
        "cost_nan",
        "calls_float",
        "legacy_repeats",
    ],
)
def test_invalid_incomplete_or_self_scoring_evidence_is_rejected(fault):
    plan, suite, traces = inputs()
    row, contract = traces["observations"][0], suite["cases"][0]["contract"]
    if fault == "extra_plan":
        plan["extra"] = True
    elif fault == "plan_version":
        plan["plan_version"] = "unknown"
    elif fault == "label":
        plan["source_label"] = ""
    elif fault == "repeats_bool":
        plan["n_repeats"] = True
    elif fault == "repeats_zero":
        plan["n_repeats"] = 0
    elif fault == "many":
        plan["n_repeats"] = 501
    elif fault == "duplicate_case":
        suite["cases"].append(deepcopy(suite["cases"][0]))
    elif fault == "empty_suite":
        suite["cases"] = []
    elif fault == "suite_version":
        suite["suite_version"] = "unknown"
    elif fault == "case_controls":
        suite["cases"][0]["case_id"] = "bad\ncase"
    elif fault == "extra_case":
        suite["cases"][0]["metrics"] = {}
    elif fault == "trace_version":
        traces["trace_version"] = "unknown"
    elif fault == "missing_trace":
        traces["observations"].pop()
    elif fault == "duplicate_repeat":
        traces["observations"][1] = deepcopy(row)
    elif fault == "repeat_bool":
        row["repeat"] = True
    elif fault == "repeat_outside":
        row["repeat"] = 2
    elif fault == "unknown_case":
        row["case_id"] = "outside"
    elif fault == "extra_trace":
        traces["extra"] = True
    elif fault == "missing_repeat":
        del row["repeat"]
    elif fault == "scores":
        row["metrics"] = {"public_value_exact": 1}
    elif fault == "contract_override":
        row["contract"] = contract
    elif fault == "context_override":
        plan["evaluation_context"] = {}
    elif fault == "bad_flag":
        row["trace"]["recourse_offered"] = 1
    elif fault == "missing_flag":
        del row["trace"]["submitted"]
    elif fault == "trace_prose":
        row["trace"] = "The agent said everything worked."
    elif fault == "held_outside_required":
        contract["held_evidence"].append("not-required")
    elif fault == "cost_bool":
        row["cost_usd"] = False
    elif fault == "cost_negative":
        row["cost_usd"] = -1
    elif fault == "cost_null":
        row["cost_usd"] = None
    elif fault == "cost_nan":
        row["cost_usd"] = float("nan")
    elif fault == "calls_float":
        row["n_api_calls"] = 1.5
    else:
        traces["trace_version"] = "aau-public-value-traces/1.0"
    with pytest.raises(AgentBomError):
        service_trace_payloads(plan, suite, traces)


@pytest.mark.parametrize("name", sorted(FILES))
def test_every_retained_member_must_recompute(tmp_path, name):
    destination = tmp_path / "pack"
    create_service_trace_pack(*inputs(True), destination)
    path = destination / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_service_trace_pack(destination)


def test_rehashed_false_scores_and_unrelated_downstream_evaluations_are_rejected(tmp_path):
    destination, other = tmp_path / "failed", tmp_path / "other"
    create_service_trace_pack(*inputs(True), destination)
    create_service_trace_pack(*inputs(), other)
    assert (
        verify_service_trace_pack(destination, evaluation_path=destination / "evaluation.json")[
            "status"
        ]
        == "evidence_failed"
    )
    with pytest.raises(AgentBomError, match="downstream evaluation"):
        verify_service_trace_pack(destination, evaluation_path=other / "evaluation.json")
    evaluation = load_json(destination / "evaluation.json")
    evaluation["results"][0]["metrics"]["public_value_exact"] = 1
    (destination / "evaluation.json").write_bytes(rendered(evaluation))
    manifest = load_json(destination / "manifest.json")
    manifest["files"]["evaluation.json"] = digest((destination / "evaluation.json").read_bytes())
    (destination / "manifest.json").write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match="does not recompute"):
        verify_service_trace_pack(destination)


@pytest.mark.parametrize(
    "fault", ["missing", "extra", "directory", "symlink", "oversized", "root_symlink"]
)
def test_invalid_file_shapes_cannot_verify(tmp_path, fault):
    destination = tmp_path / "pack"
    create_service_trace_pack(*inputs(), destination)
    path = destination / "scoring.json"
    if fault == "extra":
        (destination / "extra.json").write_text("{}")
    elif fault == "oversized":
        path.write_bytes(b"x" * 2_000_001)
    elif fault == "root_symlink":
        link = tmp_path / "link"
        link.symlink_to(destination, target_is_directory=True)
        destination = link
    else:
        path.unlink()
        if fault == "directory":
            path.mkdir()
        elif fault == "symlink":
            path.symlink_to(destination / "evaluation.json")
    with pytest.raises(AgentBomError):
        verify_service_trace_pack(destination)


def test_cli_retains_failed_scoring_with_exit_one_and_refuses_overwrite(tmp_path):
    for name, value in zip(("plan", "suite", "traces"), inputs(True)):
        (tmp_path / f"{name}.json").write_bytes(rendered(value))
    destination = tmp_path / "pack"
    args = [
        "service-trace-eval",
        "create",
        *(str(tmp_path / f"{name}.json") for name in ("plan", "suite", "traces")),
        "--out",
        str(destination),
    ]
    assert main(args) == 1
    assert (
        main(
            [
                "service-trace-eval",
                "verify",
                str(destination),
                "--evaluation",
                str(destination / "evaluation.json"),
            ]
        )
        == 1
    )
    assert main(args) == 2
    assert verify_service_trace_pack(destination)["failed_observation_count"] == 1


def test_example_hands_source_scoring_through_both_policy_and_budget_reviews(tmp_path):
    path = ROOT / "harness/examples/evaluation-review/service_traces.py"
    spec = importlib.util.spec_from_file_location("service_trace_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.create_example(tmp_path / "demo")
    for name, expected in [("burden", "evidence_failed"), ("repaired", "evidence_passed")]:
        directory = tmp_path / "demo" / name
        assert (
            verify_service_trace_pack(
                directory, evaluation_path=tmp_path / "demo" / f"{name}-review/candidate.json"
            )["status"]
            == expected
        )
