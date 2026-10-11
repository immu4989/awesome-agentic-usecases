import json
from copy import deepcopy

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_compare import compare_evaluations
from aau_harness.runner import ScenarioResult, run_eval


def evaluation(values, repeats=2):
    return run_eval(list(values), lambda scenario, repeat: ScenarioResult(
        scenario, repeat, {"score": values[scenario][repeat % len(values[scenario])]},
        0, 0.1, 0), repeats=repeats).as_dict()


def compare(before, after, direction="higher"):
    return compare_evaluations(before, after, metric="score", direction=direction)


def test_same_headline_average_can_hide_individual_regressions():
    before = evaluation({"a": [1], "b": [0]})
    after = evaluation({"a": [0], "b": [1]})
    report = compare(before, after)
    assert report["mean_delta"] == 0
    assert report["changes"] == {"improved": 1, "regressed": 1, "unchanged": 0}
    assert report["scenarios"][0]["change"] == "regressed"
    assert report["delta_ci95"] == [-1, 1]
    assert report == compare(before, after)


def test_pairs_by_id_and_keeps_repeats_in_scenario_clusters():
    before = evaluation({"a": [0, 2], "b": [10, 12]})
    after = evaluation({"a": [1, 3], "b": [11, 13]})
    after["results"].reverse()
    report = compare(before, after)
    assert report["mean_delta"] == 1
    assert report["delta_ci95"] == [1, 1]
    assert report["scenario_count"] == 2
    assert [row["delta"] for row in report["scenarios"]] == [1, 1]
    assert report["warnings"]
    assert compare(before, after, "lower")["changes"]["regressed"] == 2


def test_different_repeat_counts_are_explicit_and_scenarios_have_equal_weight():
    before = evaluation({"a": [0], "b": [0]}, repeats=1)
    after = evaluation({"a": [1, 2, 3], "b": [0]}, repeats=3)
    report = compare(before, after)
    assert report["mean_delta"] == 1
    assert report["baseline_repeat_count"] == 1
    assert report["candidate_repeat_count"] == 3
    assert any("Repeat counts differ" in warning for warning in report["warnings"])


@pytest.mark.parametrize("defect", ["missing-metric", "missing-row", "duplicate", "other-id", "bool", "nan"])
def test_refuses_selective_coverage_or_malformed_observations(defect):
    before = evaluation({"a": [0], "b": [1]})
    after = deepcopy(before)
    if defect == "missing-metric":
        del after["results"][0]["metrics"]["score"]
    elif defect == "missing-row":
        after["results"].pop()
    elif defect == "duplicate":
        after["results"][0] = deepcopy(after["results"][1])
    elif defect == "other-id":
        for row in after["results"]:
            if row["scenario_id"] == "b":
                row["scenario_id"] = "c"
    else:
        after["results"][0]["metrics"]["score"] = True if defect == "bool" else float("nan")
    with pytest.raises(AgentBomError):
        compare(before, after)


def test_summary_discrepancies_are_visible_not_used_as_measurements():
    before = evaluation({"a": [0], "b": [1]})
    after = deepcopy(before)
    after["metric_means"]["score"] = 999
    report = compare(before, after)
    assert report["mean_delta"] == 0
    assert report["source_audits"]["candidate"]["status"] == "inconsistent"
    assert report["source_audits"]["candidate"]["mismatches"]
    assert any("stored summaries" in warning for warning in report["warnings"])


def test_single_scenario_has_explicit_uncertainty_warning():
    source = evaluation({"a": [1]})
    assert any("One scenario" in warning for warning in compare(source, source)["warnings"])


def test_numeric_overflow_is_rejected_instead_of_exporting_infinity():
    before = evaluation({"a": [-1e300]}, repeats=1)
    after = evaluation({"a": [1e300]}, repeats=1)
    for source, value in ((before, -1e308), (after, 1e308)):
        source["results"][0]["metrics"]["score"] = value
    with pytest.raises(AgentBomError):
        compare(before, after)


def test_cli_offline_reverification_tamper_detection_and_exclusive_output(tmp_path):
    before = evaluation({"a": [1], "b": [0]})
    after = evaluation({"a": [0], "b": [1]})
    paths = [tmp_path / name for name in ("before.json", "after.json", "comparison.json")]
    for path, source in zip(paths, (before, after)):
        path.write_text(json.dumps(source))
    args = ["compare-evals", str(paths[0]), str(paths[1]), "--metric", "score", "--direction", "higher"]
    assert main([*args, "--out", str(paths[2])]) == 0
    original = paths[2].read_bytes()
    assert main([*args, "--out", str(paths[2])]) == 2
    assert paths[2].read_bytes() == original
    assert main([*args, "--verify", str(paths[2])]) == 0
    changed = json.loads(original)
    changed["mean_delta"] = 100
    paths[2].write_text(json.dumps(changed))
    assert main([*args, "--verify", str(paths[2])]) == 2
    paths[2].write_bytes(original)
    after["results"][0]["metrics"]["score"] = 0.5
    paths[1].write_text(json.dumps(after))
    assert main([*args, "--verify", str(paths[2])]) == 2


@pytest.mark.parametrize("metric,direction", [("", "higher"), ("score", "guess"), ("absent", "higher")])
def test_selection_must_be_explicit_and_valid(metric, direction):
    source = evaluation({"a": [1]})
    with pytest.raises(AgentBomError):
        compare_evaluations(source, source, metric=metric, direction=direction)
