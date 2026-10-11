from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest
from aau_harness.catalog_cli import main
from aau_harness.eval_audit import audit_evaluation
from aau_harness.eval_import import import_observations
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
def test_import_rejects_invalid_or_incomplete_recordings(defect):
    source = recorded()
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
