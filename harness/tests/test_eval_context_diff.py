from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest
from aau_harness.catalog_cli import main
from aau_harness.eval_compare import compare_evaluations
from aau_harness.eval_context_diff import compare_evaluation_contexts
from aau_harness.evaluation_context import capture_context
from aau_harness.runner import ScenarioResult, run_eval


def evidence(cases=None, *, config=None, scorers=None, repeats=2, score=1, context=True):
    if cases is None:
        cases = [{"scenario_id": "routine", "fact": 1}, {"scenario_id": "assisted", "fact": 2}]
    captured = capture_context(cases, config or {"setting": "v1"}, scorers or {"scorer.py": b"fixture v1"})
    return run_eval(cases, lambda case, repeat: ScenarioResult(case["scenario_id"], repeat,
        {"score": score}, 0, .1, 0), repeats=repeats, evaluation_context=captured if context else None).as_dict()


def test_matching_context_is_not_a_performance_approval():
    before, after = evidence(), evidence(score=0)
    original = deepcopy((before, after))
    report = compare_evaluation_contexts(before, after)
    assert (before, after) == original
    assert report == compare_evaluation_contexts(before, after)
    assert report["status"] == "declared_context_matched"
    assert not report["review_reasons"]
    assert report["sources"]["baseline"]["source_sha256"] == digest(before)
    assert report["sources"]["candidate"]["source_sha256"] == digest(after)
    assert "mean_delta" not in report
    assert report["scenario_fingerprints"]["counts"]["unchanged"] == 2
    assert "not a score comparison" in report["boundary"]


def test_scenario_drift_lists_added_removed_and_same_id_changed_cases():
    before = evidence()
    after = evidence([{"scenario_id": "routine", "fact": 999}, {"scenario_id": "replacement", "fact": 2}])
    report = compare_evaluation_contexts(before, after)
    assert report["status"] == "review_required"
    assert report["review_reasons"] == ["scenario_census_changed", "scenario_content_changed"]
    assert report["scenario_census"] == {"added": ["replacement"], "removed": ["assisted"], "shared": ["routine"]}
    assert {row["name"]: row["state"] for row in report["scenario_fingerprints"]["components"]} == {
        "assisted": "removed", "replacement": "added", "routine": "changed"}
    assert all(row["baseline_sha256"] or row["candidate_sha256"] for row in report["scenario_fingerprints"]["components"])
    with pytest.raises(AgentBomError):
        compare_evaluations(before, after, metric="score", direction="higher")


def test_scorer_and_config_drift_are_named_without_reading_source_code():
    before = evidence(scorers={"shared.py": b"old", "removed.py": b"removed"})
    after = evidence(scorers={"shared.py": b"new", "added.py": b"new"}, config={"setting": "v2"})
    report = compare_evaluation_contexts(before, after)
    assert report["review_reasons"] == ["scoring_sources_changed", "configuration_changed"]
    assert report["configuration"]["state"] == "changed"
    assert {row["name"]: row["state"] for row in report["scoring_fingerprints"]["components"]} == {
        "added.py": "added", "removed.py": "removed", "shared.py": "changed"}
    with pytest.raises(AgentBomError):
        compare_evaluations(before, after, metric="score", direction="higher")


@pytest.mark.parametrize("missing", ["baseline", "candidate", "both"])
def test_missing_context_is_unknown_not_fabricated_removal_or_match(missing):
    before = evidence(context=missing not in ("baseline", "both"))
    after = evidence(context=missing not in ("candidate", "both"))
    report = compare_evaluation_contexts(before, after)
    assert report["review_reasons"] == ["context_unavailable"]
    assert report["configuration"]["state"] == "unknown"
    assert not report["scoring_fingerprints"]["comparison_available"]
    assert report["scoring_fingerprints"]["counts"]["removed"] == 0
    assert report["scenario_fingerprints"]["counts"]["unknown"] == 2
    assert "contemporaneous" in report["next_steps"][0]


def test_observed_census_drift_is_reported_even_when_context_is_missing():
    report = compare_evaluation_contexts(evidence(context=False), evidence([{"scenario_id": "new"}], context=False))
    assert report["review_reasons"] == ["context_unavailable", "scenario_census_changed"]
    assert report["scenario_census"]["removed"] == ["assisted", "routine"]
    assert report["scenario_fingerprints"]["counts"]["unknown"] == 3


@pytest.mark.parametrize("defect", ["null", "wrong-ids", "bad-hash", "unknown-field", "empty-scorers"])
def test_malformed_context_is_rejected_even_when_other_source_has_none(defect):
    candidate = evidence()
    context = candidate["evaluation_context"]
    if defect == "null":
        candidate["evaluation_context"] = None
    elif defect == "wrong-ids":
        context["scenario_sha256"]["not-observed"] = "0" * 64
    elif defect == "bad-hash":
        context["config_sha256"] = "bad"
    elif defect == "unknown-field":
        context["verified"] = True
    else:
        context["scoring_sha256"] = {}
    with pytest.raises(AgentBomError):
        compare_evaluation_contexts(evidence(context=False), candidate)


@pytest.mark.parametrize("defect", ["missing", "duplicate", "bool-repeat", "nonfinite", "unknown-metric-type"])
def test_invalid_observation_census_and_scores_remain_rejected(defect):
    candidate = evidence()
    if defect == "missing":
        candidate["results"].pop()
    elif defect == "duplicate":
        candidate["results"][-1] = deepcopy(candidate["results"][0])
    elif defect == "bool-repeat":
        candidate["results"][0]["repeat"] = True
    else:
        candidate["results"][0]["metrics"]["score"] = float("inf") if defect == "nonfinite" else "one"
    with pytest.raises(AgentBomError):
        compare_evaluation_contexts(evidence(), candidate)


def test_repeat_count_change_is_disclosed_but_not_treated_as_context_drift():
    report = compare_evaluation_contexts(evidence(), evidence(repeats=3))
    assert report["status"] == "declared_context_matched"
    assert report["repeat_counts_differ"]
    assert "Repeat counts differ" in report["warnings"][-1]


def test_stale_summaries_require_investigation_without_being_repaired():
    before = evidence()
    before["metric_means"]["score"] = 0
    report = compare_evaluation_contexts(before, evidence())
    assert report["review_reasons"] == ["baseline_metric_summaries_inconsistent"]
    assert report["configuration"]["state"] == "unchanged"
    assert report["source_metric_audits"]["baseline"] == {"status": "inconsistent", "mismatch_count": 1}
    assert before["metric_means"]["score"] == 0


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_recordings_are_supported_with_original_and_normalized_hashes(version):
    evaluation = evidence()
    keys = ("scenario_id", "repeat", "metrics") + (("cost_usd", "latency_s", "n_api_calls") if version == "1.1" else ())
    source = {"format_version": f"aau-recorded-observations/{version}", "source_label": "synthetic",
              "scenario_ids": ["routine", "assisted"], "n_repeats": 2,
              "evaluation_context": evaluation["evaluation_context"],
              "observations": [{key: row[key] for key in keys} for row in evaluation["results"]]}
    report = compare_evaluation_contexts(source, source, input_format="recordings")
    assert report["status"] == "declared_context_matched"
    assert report["sources"]["baseline"]["source_sha256"] == digest(source)
    assert report["sources"]["baseline"]["evaluation_sha256"] != digest(source)


@pytest.mark.parametrize("missing", [False, True])
def test_cli_roundtrip_exit_codes_no_overwrite_and_tamper_detection(tmp_path, missing):
    for name in ("baseline", "candidate"):
        (tmp_path / f"{name}.json").write_text(json.dumps(evidence(context=not missing)))
    args = ["compare-eval-contexts", str(tmp_path / "baseline.json"), str(tmp_path / "candidate.json")]
    output = tmp_path / "review.json"
    code = 1 if missing else 0
    assert main([*args, "--out", str(output)]) == code
    assert main([*args, "--verify", str(output)]) == code
    assert main([*args, "--out", str(output)]) == 2
    report = json.loads(output.read_text())
    report["boundary"] = "approved"
    output.write_text(json.dumps(report))
    assert main([*args, "--verify", str(output)]) == 2
    (tmp_path / "candidate.json").write_text('{"secret":"DO_NOT_PRINT", broken}')
    assert main([*args, "--out", str(tmp_path / "invalid.json")]) == 2
    assert not (tmp_path / "invalid.json").exists()


def test_synthetic_demo_has_same_scores_but_distinct_context_outcomes(tmp_path):
    path = Path(__file__).resolve().parents[1] / "examples/evaluation-review/context-drift.py"
    spec = importlib.util.spec_from_file_location("context_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "demo"
    module.build_demo(output)
    values = [json.loads((output / f"{name}.json").read_text()) for name in ("baseline", "matched", "changed")]
    assert all(value["metric_means"] == {"completion": 1} for value in values)
    assert json.loads((output / "matched-context-review.json").read_text())["status"] == "declared_context_matched"
    changed = json.loads((output / "changed-context-review.json").read_text())
    assert changed["scenario_census"]["removed"] == ["assisted"]
    assert changed["scenario_fingerprints"]["counts"]["changed"] == 1
