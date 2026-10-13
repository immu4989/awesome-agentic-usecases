from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest
from aau_harness.catalog_cli import main
from aau_harness.eval_audit import audit_evaluation
from aau_harness.eval_import import import_observations
from aau_harness.eval_operations import review_operations
from aau_harness.eval_pack import create_pack, verify_pack
from aau_harness.evaluation_context import capture_context


def recorded():
    return {"format_version": "aau-recorded-observations/1.0", "source_label": "synthetic external fixture",
            "scenario_ids": ["assisted", "routine"], "n_repeats": 2,
            "observations": [{"scenario_id": name, "repeat": repeat, "metrics": {"completion": 1.0}}
                             for name in ("assisted", "routine") for repeat in range(2)]}


def test_import_recomputes_summaries_without_fabricating_runtime_measurements():
    source = recorded()
    original = deepcopy(source)
    report = import_observations(source)
    assert source == original
    assert report == import_observations(source)
    assert audit_evaluation(report)["status"] == "consistent"
    assert report["metric_means"] == {"completion": 1.0}
    assert report["provenance"]["source_sha256"] == digest(source)
    assert report["provenance"]["evidence_kind"] == "imported_unverified_observations"
    assert set(report["results"][0]) == {"scenario_id", "repeat", "metrics"}
    assert not {"total_cost_usd", "p50_latency_s", "evaluation_context"} & set(report)
    source["observations"][0]["metrics"]["completion"] = 0
    assert report["results"][0]["metrics"]["completion"] == 1


def test_optional_metrics_remain_missing_instead_of_being_imputed():
    source = recorded()
    source["observations"][0]["metrics"]["optional"] = 0.6
    report = import_observations(source)
    assert report["metric_means"]["optional"] == 0.6
    assert report["metric_coverage"]["optional"]["reporting_observations"] == 1
    assert report["metric_coverage"]["optional"]["complete_repeat_scenarios"] == 0
    assert "optional" not in report["results"][1]["metrics"]


@pytest.mark.parametrize("defect", ["duplicate", "missing", "unknown", "duplicate-census", "unused-census",
                                     "extra-field", "unrecorded-detail", "bool-repeat", "bool-metric", "nan",
                                     "infinity", "no-metrics", "unsupported", "nonfinite-summary"])
@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_import_rejects_invalid_or_incomplete_recordings(defect, version):
    source = recorded()
    source["format_version"] = f"aau-recorded-observations/{version}"
    rows = source["observations"]
    if defect == "duplicate":
        rows[-1] = deepcopy(rows[0])
    elif defect == "missing":
        rows.pop()
    elif defect == "unknown":
        rows[0]["scenario_id"] = "undeclared"
    elif defect == "duplicate-census":
        source["scenario_ids"][1] = "assisted"
    elif defect == "unused-census":
        source["scenario_ids"].append("unmeasured")
    elif defect == "extra-field":
        source["model_was_executed"] = True
    elif defect == "unrecorded-detail":
        rows[0]["detail"] = {"private": "do not silently copy"}
    elif defect == "bool-repeat":
        source["n_repeats"] = True
    elif defect == "bool-metric":
        rows[0]["metrics"]["completion"] = True
    elif defect in ("nan", "infinity"):
        rows[0]["metrics"]["completion"] = float("nan" if defect == "nan" else "inf")
    elif defect == "no-metrics":
        for row in rows:
            row["metrics"] = {}
    elif defect == "unsupported":
        source["format_version"] = "unknown"
    else:
        for row in rows:
            row["metrics"]["completion"] = 1e308
    with pytest.raises(AgentBomError):
        import_observations(source)


def test_imported_evidence_supports_context_bound_cohort_review_and_pack(tmp_path):
    baseline = recorded()
    context = capture_context([{"scenario_id": name} for name in baseline["scenario_ids"]],
                              {"fixture": True}, {"scorer": b"synthetic supplied scorer v1"})
    baseline["evaluation_context"] = context
    candidate = deepcopy(baseline)
    for row in candidate["observations"]:
        if row["scenario_id"] == "assisted":
            row["metrics"]["completion"] = 0
    rule = {"metric": "completion", "direction": "higher", "candidate_observation_limit": 0,
            "max_mean_regression": 1, "max_regressed_scenarios": 1}
    policy = {"policy_version": "aau-evaluation-review-policy/1.1", "scenario_ids": baseline["scenario_ids"],
              "minimum_repeats": 2, "metrics": [rule],
              "cohorts": [{"cohort_id": name, "scenario_ids": [name],
                           "metrics": [{**rule, "max_mean_regression": 0}]} for name in baseline["scenario_ids"]]}
    pack = tmp_path / "pack"
    report = create_pack(policy, import_observations(baseline), import_observations(candidate), pack)
    assert verify_pack(pack) == report
    assert report["comparisons"][0]["context_match"]["status"] == "matched"
    assert report["failed_constraints"] == [{"cohort_id": "assisted", "metric": "completion",
                                               "constraint": "max_mean_regression"}]
    context["scenario_sha256"]["extra"] = "0" * 64
    with pytest.raises(AgentBomError):
        import_observations(baseline)


def test_cli_recomputes_import_and_refuses_overwrite_or_tampering(tmp_path):
    source, output = tmp_path / "recorded.json", tmp_path / "evaluation.json"
    source.write_text(json.dumps(recorded()))
    assert main(["import-eval", str(source), "--out", str(output)]) == 0
    assert main(["import-eval", str(source), "--verify", str(output)]) == 0
    assert main(["import-eval", str(source), "--out", str(output)]) == 2
    changed = json.loads(output.read_text())
    changed["provenance"]["evidence_kind"] = "executed"
    output.write_text(json.dumps(changed))
    assert main(["import-eval", str(source), "--verify", str(output)]) == 2
    source.write_text('{"format_version":"x","format_version":"y"}')
    assert main(["import-eval", str(source), "--out", str(tmp_path / "invalid.json")]) == 2
    assert not (tmp_path / "invalid.json").exists()


def test_documented_fixture_imports_and_audits_without_a_model(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/evaluation-review/recorded-observations.json"
    output, audit = tmp_path / "evaluation.json", tmp_path / "audit.json"
    assert main(["import-eval", str(source), "--out", str(output)]) == 0
    assert main(["import-eval", str(source), "--verify", str(output)]) == 0
    assert main(["audit-eval", str(output), "--out", str(audit)]) == 0
    assert json.loads(output.read_text())["metric_means"] == {"completion": 0.75, "unauthorized_action": 0.0}


def operating_recording():
    return json.loads((Path(__file__).resolve().parents[1]
                       / "examples/evaluation-review/recorded-operations.json").read_text())


CRITERIA = [{"metric": "completion", "direction": "higher", "limit": 1},
            {"metric": "unauthorized", "direction": "lower", "limit": 0}]


def test_import_preserves_supplied_operating_measurements_and_counts_failure_costs():
    source = operating_recording()
    original = deepcopy(source)
    result = import_observations(source)
    assert source == original
    assert result["results"] == source["observations"]
    assert result["provenance"]["import_format"].endswith("/1.1")
    assert result["provenance"]["source_sha256"] == digest(source)
    assert "not measured, rounded, unit-converted" in result["provenance"]["boundary"]
    assert audit_evaluation(result)["status"] == "consistent"
    report = review_operations(result, criteria=CRITERIA, cost_basis="synthetic")["overall"]
    assert report["passing_attempt_count"] == 1
    assert report["cost"]["total_usd"] == .4
    assert report["cost"]["total_per_passing_attempt_usd"] == .4
    assert report["cost"]["spent_on_failed_attempts_usd"] == pytest.approx(.3)
    assert report["latency"]["p95_s"] == 12
    assert report["api_calls"]["total"] == 8
    source["observations"][0]["cost_usd"] = 999
    assert result["results"][0]["cost_usd"] == .1


@pytest.mark.parametrize("field,section,summary", [("cost_usd", "cost", "total_usd"),
                                                  ("latency_s", "latency", "p95_s"),
                                                  ("n_api_calls", "api_calls", "total")])
@pytest.mark.parametrize("missing_count", [1, 4])
def test_missing_operating_values_remain_unknown_per_field(field, section, summary, missing_count):
    source = operating_recording()
    for row in source["observations"][:missing_count]:
        del row[field]
    result = import_observations(source)
    assert all(field not in row for row in result["results"][:missing_count])
    overall = review_operations(result, criteria=CRITERIA, cost_basis="unknown")["overall"]
    assert overall[section]["status"] == ("partial" if missing_count == 1 else "unavailable")
    assert overall[section]["reporting_observations"] == 4 - missing_count
    assert overall[section][summary] is None
    assert all(overall[key]["status"] == "complete" for key in ("cost", "latency", "api_calls") if key != section)


@pytest.mark.parametrize("field", ["cost_usd", "latency_s", "n_api_calls"])
@pytest.mark.parametrize("value", [None, True, "0.1", -1, float("nan"), float("inf"), {}, []])
def test_import_rejects_invalid_optional_operating_values(field, value):
    source = operating_recording()
    source["observations"][0][field] = value
    with pytest.raises(AgentBomError, match=field):
        import_observations(source)


@pytest.mark.parametrize("value", [1.0, .1, 10**12 + 1])
def test_import_call_counts_require_bounded_integers(value):
    source = operating_recording()
    source["observations"][0]["n_api_calls"] = value
    with pytest.raises(AgentBomError, match="n_api_calls"):
        import_observations(source)


def test_import_does_not_round_zero_or_precise_supplied_measurements():
    source = operating_recording()
    source["observations"][0].update(cost_usd=.000000123456, latency_s=0, n_api_calls=0)
    result = import_observations(source)
    assert result["results"][0] == source["observations"][0]
    assert "total_cost_usd" not in result
    assert "p50_latency_s" not in result


@pytest.mark.parametrize("field,value", [("latency_ms", 1000), ("currency", "EUR"),
                                        ("detail", {"private": "text"}), ("tokens", 100)])
def test_new_import_version_still_rejects_unknown_fields(field, value):
    source = operating_recording()
    source["observations"][0][field] = value
    with pytest.raises(AgentBomError):
        import_observations(source)


def test_old_import_version_does_not_silently_accept_operating_fields():
    source = operating_recording()
    source["format_version"] = "aau-recorded-observations/1.0"
    with pytest.raises(AgentBomError):
        import_observations(source)


@pytest.mark.parametrize("repaired", [False, True])
def test_operating_recordings_roundtrip_through_complete_dossier_and_cli(tmp_path, repaired):
    baseline = operating_recording()
    candidate = deepcopy(baseline)
    if repaired:
        for row in candidate["observations"]:
            row["metrics"]["unauthorized"] = 0
            row["cost_usd"] = .25
    policy = {"policy_version": "aau-evaluation-review-policy/1.0", "scenario_ids": ["service"],
              "minimum_repeats": 4, "metrics": [{"metric": rule["metric"], "direction": rule["direction"],
                  "candidate_observation_limit": rule["limit"], "max_mean_regression": 0,
                  "max_regressed_scenarios": 0} for rule in CRITERIA]}
    plan = {"plan_version": "aau-evaluation-diagnostics/1.0", "criteria": CRITERIA, "draw_sizes": [1, 4],
            "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
    for name, value in (("baseline", baseline), ("candidate", candidate), ("policy", policy), ("plan", plan)):
        (tmp_path / f"{name}.json").write_text(json.dumps(value))
    pack = tmp_path / "pack"
    code = 0 if repaired else 1
    assert main(["evaluation-pack", "from-recordings", str(tmp_path / "policy.json"),
                 str(tmp_path / "baseline.json"), str(tmp_path / "candidate.json"),
                 "--diagnostics", str(tmp_path / "plan.json"), "--out", str(pack)]) == code
    assert main(["evaluation-pack", "verify", str(pack), "--require-recordings", "--require-diagnostics"]) == code
    assert len(list(pack.iterdir())) == 13
    assert json.loads((pack / "candidate-recording.json").read_text()) == candidate
    operating = json.loads((pack / "candidate-operations.json").read_text())
    assert operating["overall"]["cost"]["total_per_passing_attempt_usd"] == (.25 if repaired else .4)
    changed = json.loads((pack / "candidate.json").read_text())
    changed["results"][0]["cost_usd"] = 0
    (pack / "candidate.json").write_text(json.dumps(changed))
    assert main(["evaluation-pack", "verify", str(pack), "--require-recordings", "--require-diagnostics"]) == 2


def test_operating_import_cli_detects_changed_measurements_and_avoids_partial_output(tmp_path):
    source, output = tmp_path / "recorded.json", tmp_path / "evaluation.json"
    data = operating_recording()
    source.write_text(json.dumps(data))
    assert main(["import-eval", str(source), "--out", str(output)]) == 0
    assert main(["import-eval", str(source), "--verify", str(output)]) == 0
    data["observations"][0]["cost_usd"] = 0
    source.write_text(json.dumps(data))
    assert main(["import-eval", str(source), "--verify", str(output)]) == 2
    data["observations"][0]["latency_s"] = "INVALID_PRIVATE_VALUE"
    source.write_text(json.dumps(data))
    assert main(["import-eval", str(source), "--out", str(tmp_path / "invalid.json")]) == 2
    assert not (tmp_path / "invalid.json").exists()
