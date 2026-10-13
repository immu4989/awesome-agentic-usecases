import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_import import import_observations
from aau_harness.eval_operations import review_operations
from aau_harness.runner import ScenarioResult, run_eval


RULES = [{"metric": "completion", "direction": "higher", "limit": 1},
         {"metric": "unauthorized", "direction": "lower", "limit": 0}]


def evaluation(costs=(.1, .1, .1, .1), latencies=(1, 1, 1, 12), passed=(True, False, False, False)):
    return run_eval(["case"], lambda scenario, repeat: ScenarioResult(
        scenario, repeat, {"completion": 1, "unauthorized": int(not passed[repeat])},
        costs[repeat], latencies[repeat], 2), repeats=len(costs)).as_dict()


def review(source):
    return review_operations(source, criteria=RULES, cost_basis="synthetic")


def test_cost_per_pass_keeps_all_failures_and_tail_latency():
    report = review(evaluation())
    overall = report["overall"]
    assert overall["passing_attempt_count"] == 1
    assert overall["failing_attempt_count"] == 3
    assert overall["cost"]["total_usd"] == pytest.approx(.4)
    assert overall["cost"]["mean_per_attempt_usd"] == pytest.approx(.1)
    assert overall["cost"]["total_per_passing_attempt_usd"] == pytest.approx(.4)
    assert overall["cost"]["spent_on_failed_attempts_usd"] == pytest.approx(.3)
    assert overall["latency"]["p50_s"] == 1
    assert overall["latency"]["p95_s"] == 12
    assert overall["api_calls"]["total"] == 8
    assert len(report["scenarios"][0]["failures"]) == 3


def test_cheaper_attempt_can_cost_more_per_jointly_passing_attempt():
    cheap = review(evaluation())["overall"]
    repaired = review(evaluation(costs=(.25,) * 4, latencies=(2,) * 4, passed=(True,) * 4))["overall"]
    assert cheap["cost"]["mean_per_attempt_usd"] < repaired["cost"]["mean_per_attempt_usd"]
    assert cheap["cost"]["total_per_passing_attempt_usd"] > repaired["cost"]["total_per_passing_attempt_usd"]
    assert cheap["latency"]["p50_s"] < repaired["latency"]["p50_s"]
    assert cheap["latency"]["p95_s"] > repaired["latency"]["p95_s"]


def test_zero_passing_attempts_produce_unknown_unit_cost_not_zero_or_infinity():
    overall = review(evaluation(passed=(False,) * 4))["overall"]
    assert overall["cost"]["total_usd"] == .4
    assert overall["cost"]["total_per_passing_attempt_usd"] is None
    assert overall["cost"]["unit_cost_unavailable_reason"] == "no_passing_attempts"


@pytest.mark.parametrize("field,section", [("cost_usd", "cost"), ("latency_s", "latency"), ("n_api_calls", "api_calls")])
def test_partial_measurements_do_not_become_full_sample_statistics(field, section):
    source = evaluation()
    del source["results"][0][field]
    result = review(source)["overall"]
    assert result[section]["status"] == "partial"
    assert result[section]["reporting_observations"] == 3
    if section == "cost":
        assert result[section]["sum_reported_usd"] == pytest.approx(.3)
        for key in ("total_usd", "mean_per_attempt_usd", "total_per_passing_attempt_usd", "spent_on_failed_attempts_usd"):
            assert result[section][key] is None
    elif section == "latency":
        assert all(result[section][key] is None for key in ("p50_s", "p95_s", "max_s"))
    else:
        assert result[section]["sum_reported"] == 6
        assert result[section]["total"] is None
    assert result["attempt_count"] == 4
    assert result["passing_attempt_count"] == 1


def test_imported_scores_without_operational_data_are_unknown_not_free_or_instant():
    imported = import_observations({"format_version": "aau-recorded-observations/1.0", "source_label": "synthetic",
        "scenario_ids": ["case"], "n_repeats": 1,
        "observations": [{"scenario_id": "case", "repeat": 0, "metrics": {"completion": 1, "unauthorized": 0}}]})
    overall = review(imported)["overall"]
    for section in ("cost", "latency", "api_calls"):
        assert overall[section]["status"] == "unavailable"
        assert overall[section]["reporting_observations"] == 0
    assert overall["cost"]["sum_reported_usd"] is None
    assert overall["cost"]["total_per_passing_attempt_usd"] is None
    assert overall["latency"]["p50_s"] is None
    assert overall["api_calls"]["sum_reported"] is None


@pytest.mark.parametrize("field,value", [("cost_usd", -1), ("cost_usd", True), ("cost_usd", None),
    ("cost_usd", "0.1"), ("cost_usd", float("inf")), ("cost_usd", float("nan")),
    ("cost_usd", 10**400), ("latency_s", -1), ("latency_s", False), ("latency_s", None),
    ("latency_s", float("nan")), ("n_api_calls", -1), ("n_api_calls", 1.5),
    ("n_api_calls", True), ("n_api_calls", 10**12 + 1), ("n_api_calls", None)])
def test_invalid_operational_values_are_errors_not_missing(field, value):
    source = evaluation()
    source["results"][0][field] = value
    with pytest.raises(AgentBomError):
        review(source)


def test_zero_recorded_measurements_stay_zero_but_do_not_claim_free_service():
    source = evaluation()
    for row in source["results"]:
        row.update(cost_usd=0, latency_s=0, n_api_calls=0)
    report = review(source)
    assert report["overall"]["cost"]["total_usd"] == 0
    assert report["overall"]["latency"]["p95_s"] == 0
    assert report["overall"]["api_calls"]["total"] == 0
    assert any("does not establish a free service" in warning for warning in report["warnings"])


def test_quantile_definition_and_small_sample_boundary():
    source = evaluation(costs=(1,) * 20, latencies=tuple(range(1, 21)), passed=(True,) * 20)
    report = review(source)
    assert report["overall"]["latency"]["p50_s"] == 10.5
    assert report["overall"]["latency"]["p95_s"] == 19
    assert report["overall"]["latency"]["max_s"] == 20
    assert not any("Fewer than 20" in warning for warning in report["warnings"])
    assert any("Fewer than 20" in warning for warning in review(evaluation())["warnings"])


def test_inconsistent_or_fabricated_stored_headlines_are_not_reused():
    source = evaluation()
    source.update(total_cost_usd=0, mean_cost_per_scenario_usd=0, p50_latency_s=0)
    source["metric_means"]["unauthorized"] = 0
    before = deepcopy(source)
    report = review(source)
    assert source == before
    assert report["overall"]["cost"]["total_usd"] == .4
    assert report["overall"]["latency"]["p50_s"] == 1
    assert report["source_metric_audit"]["status"] == "inconsistent"


def test_overflow_fails_instead_of_publishing_infinity():
    source = evaluation()
    for row in source["results"]:
        row["cost_usd"] = sys.float_info.max
    with pytest.raises(AgentBomError, match="finite numeric range"):
        review(source)


def test_scenario_breakdown_keeps_coverage_local_and_all_attempts_global():
    source = evaluation()
    source["n_scenarios"] = 2
    extra = deepcopy(source["results"])
    for row in extra:
        row["scenario_id"] = "second"
        del row["cost_usd"]
    source["results"].extend(extra)
    report = review(source)
    assert report["overall"]["attempt_count"] == 8
    assert report["overall"]["cost"]["total_usd"] is None
    assert report["scenarios"][0]["cost"]["total_usd"] == .4
    assert report["scenarios"][1]["cost"]["status"] == "unavailable"


def test_large_overall_sample_does_not_hide_small_scenario_tails():
    source = evaluation()
    original_rows = deepcopy(source["results"])
    source["n_scenarios"] = 6
    for index in range(1, 6):
        source["results"].extend({**row, "scenario_id": f"case-{index}"} for row in original_rows)
    report = review(source)
    assert report["overall"]["attempt_count"] == 24
    assert any("Each scenario has fewer than 20" in warning for warning in report["warnings"])


def test_cli_round_trip_and_changed_source_or_cost_basis_refused(tmp_path):
    source, out = tmp_path / "source.json", tmp_path / "report.json"
    value = evaluation()
    source.write_text(json.dumps(value))
    args = ["operating-eval", str(source), "--criterion", "completion", "higher", "1",
            "--criterion", "unauthorized", "lower", "0", "--cost-basis", "synthetic"]
    assert main([*args, "--out", str(out)]) == 0
    assert main([*args, "--verify", str(out)]) == 0
    original = out.read_bytes()
    assert main([*args, "--out", str(out)]) == 2
    assert out.read_bytes() == original
    assert main([*args[:-1], "unknown", "--verify", str(out)]) == 2
    value["results"][0]["cost_usd"] = 4
    source.write_text(json.dumps(value))
    assert main([*args, "--verify", str(out)]) == 2


def test_tampered_report_does_not_verify(tmp_path):
    source, out = tmp_path / "source.json", tmp_path / "report.json"
    source.write_text(json.dumps(evaluation()))
    args = ["operating-eval", str(source), "--criterion", "completion", "higher", "1", "--cost-basis", "synthetic"]
    assert main([*args, "--out", str(out)]) == 0
    payload = json.loads(out.read_text())
    payload["overall"]["cost"]["total_per_passing_attempt_usd"] = 0
    out.write_text(json.dumps(payload))
    assert main([*args, "--verify", str(out)]) == 2


def test_missing_success_metric_is_not_excluded_from_denominator():
    source = evaluation()
    del source["results"][0]["metrics"]["unauthorized"]
    with pytest.raises(AgentBomError, match="every criterion"):
        review(source)


@pytest.mark.parametrize("limit", ["NaN", "null", "true", "oops"])
def test_cli_invalid_criteria_do_not_publish(tmp_path, limit):
    source, out = tmp_path / "source.json", tmp_path / "report.json"
    source.write_text(json.dumps(evaluation()))
    assert main(["operating-eval", str(source), "--criterion", "completion", "higher", limit,
                 "--cost-basis", "synthetic", "--out", str(out)]) == 2
    assert not out.exists()


def test_invalid_declared_cost_basis_fails():
    with pytest.raises(AgentBomError, match="cost_basis"):
        review_operations(evaluation(), criteria=RULES, cost_basis="free")


def test_demo_is_deterministic_and_refuses_overwrite(tmp_path):
    path = Path(__file__).resolve().parents[1] / "examples/evaluation-review/operations.py"
    spec = importlib.util.spec_from_file_location("operations_demo", path)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    demo.build_demo(tmp_path / "one")
    demo.build_demo(tmp_path / "two")
    assert {file.name: file.read_bytes() for file in (tmp_path / "one").iterdir()} == {
        file.name: file.read_bytes() for file in (tmp_path / "two").iterdir()}
    with pytest.raises(FileExistsError):
        demo.build_demo(tmp_path / "one")
    for label in ("cheap-attempt", "repaired"):
        assert main(["operating-eval", str(tmp_path / f"one/{label}.json"),
                     "--criterion", "completion", "higher", "1", "--criterion", "unauthorized", "lower", "0",
                     "--cost-basis", "synthetic", "--verify", str(tmp_path / f"one/{label}-operations.json")]) == 0
