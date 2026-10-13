import importlib.util
import itertools
import json
from copy import deepcopy
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.catalog_cli import main
from aau_harness.eval_repeatability import _curve, review_repeatability
from aau_harness.runner import ScenarioResult, run_eval


RULES = [{"metric": "completion", "direction": "higher", "limit": 1},
         {"metric": "unauthorized", "direction": "lower", "limit": 0}]


def evaluation(values):
    return run_eval(list(values), lambda scenario, repeat: ScenarioResult(
        scenario, repeat, dict(zip(("completion", "unauthorized"), values[scenario][repeat])),
        0, 0.1, 0), repeats=len(next(iter(values.values())))).as_dict()


def review(source, sizes=None, rules=None):
    return review_repeatability(source, criteria=RULES if rules is None else rules,
                                draw_sizes=[1, 2] if sizes is None else sizes)


def test_best_of_retries_conceals_joint_failure():
    report = review(evaluation({"service": [(1, 0), (1, 0), (1, 0), (1, 1)]}), [1, 2, 4])
    assert report["counts"] == {"all_recorded_pass": 0, "mixed": 1, "none_recorded_pass": 0}
    assert report["curve"][1] == {"draw_size": 2, "all_pass_fraction": .5, "any_pass_fraction": 1}
    assert report["curve"][2]["all_pass_fraction"] == 0
    row = report["scenarios"][0]
    assert row["passing_repeat_ids"] == [0, 1, 2]
    assert row["failures"] == [{"repeat": 3, "failed_criteria": [{"metric": "unauthorized", "value": 1}]}]
    assert row["curve"][1]["all_pass_subsets"] == 3
    assert row["curve"][1]["total_subsets"] == 6


def test_marginal_successes_must_not_be_combined_across_repeats():
    report = review(evaluation({"alternating": [(1, 1), (0, 0)]}))
    assert report["counts"]["none_recorded_pass"] == 1
    assert all(row["any_pass_fraction"] == 0 for row in report["curve"])


def test_equal_weight_scenarios_and_threshold_equality():
    source = evaluation({"good": [(1, 0)] * 2, "bad": [(0, 1)] * 2})
    report = review(source)
    assert report["curve"] == [{"draw_size": k, "all_pass_fraction": .5, "any_pass_fraction": .5} for k in (1, 2)]
    assert report["counts"] == {"all_recorded_pass": 1, "mixed": 0, "none_recorded_pass": 1}


def test_combinatorics_match_exhaustive_small_subset_enumeration():
    for n in range(1, 9):
        for passes in range(n + 1):
            values = [True] * passes + [False] * (n - passes)
            for row in _curve(passes, n, list(range(1, n + 1))):
                subsets = list(itertools.combinations(values, row["draw_size"]))
                assert row["total_subsets"] == len(subsets)
                assert row["all_pass_subsets"] == sum(all(item) for item in subsets)
                assert row["any_pass_subsets"] == sum(any(item) for item in subsets)


def test_large_subset_counts_do_not_require_enumerating_subsets():
    row = _curve(9999, 10000, [20])[0]
    assert row["all_pass_fraction"] == pytest.approx(.998)
    assert row["any_pass_fraction"] == 1
    assert row["total_subsets"] > 10**60


def test_observation_and_argument_order_do_not_change_derived_results():
    source = evaluation({"z": [(1, 0), (0, 0)], "a": [(1, 0)] * 2})
    report = review(source)
    source["results"].reverse()
    reordered = review(source, [2, 1], list(reversed(RULES)))
    assert report["scenarios"] == reordered["scenarios"]
    assert report["curve"] == reordered["curve"]
    assert report["criteria"] == reordered["criteria"]
    assert report["source_sha256"] != reordered["source_sha256"]


@pytest.mark.parametrize("sizes", [[], [0], [21], [True], [1, 1], [1.5], [3]])
def test_invalid_or_unavailable_subset_sizes_fail(sizes):
    with pytest.raises(AgentBomError):
        review(evaluation({"a": [(1, 0)] * 2}), sizes)


@pytest.mark.parametrize("rules", [[], RULES * 2, [{"metric": "", "direction": "higher", "limit": 1}],
                                    [{"metric": "completion", "direction": "guess", "limit": 1}],
                                    [{"metric": "completion", "direction": "higher", "limit": True}],
                                    [{"metric": "completion", "direction": "higher", "limit": float("nan")}],
                                    [{"metric": "completion", "direction": "higher", "limit": float("inf")}],
                                    [{**RULES[0], "ignored": 1}], [{"metric": "missing", "direction": "higher", "limit": 1}]])
def test_invalid_criteria_fail(rules):
    with pytest.raises(AgentBomError):
        review(evaluation({"a": [(1, 0)] * 2}), rules=rules)


@pytest.mark.parametrize("change", ["missing_metric", "missing_repeat", "duplicate", "nonfinite", "boolean"])
def test_coverage_and_invalid_scores_cannot_be_hidden(change):
    source = evaluation({"a": [(1, 0)] * 2})
    if change == "missing_metric":
        del source["results"][0]["metrics"]["completion"]
    elif change == "missing_repeat":
        source["results"].pop()
    elif change == "duplicate":
        source["results"][1] = deepcopy(source["results"][0])
    else:
        source["results"][0]["metrics"]["completion"] = float("inf") if change == "nonfinite" else True
    with pytest.raises(AgentBomError):
        review(source)


def test_summary_drift_is_exposed_without_repair_and_single_repeat_warns():
    source = evaluation({"a": [(1, 0)]})
    source["metric_means"]["completion"] = 0
    original = deepcopy(source)
    report = review(source, [1])
    assert report["source_audit"]["status"] == "inconsistent"
    assert source == original
    assert any("Only one repeat" in warning for warning in report["warnings"])
    assert any("No observed failures" in warning for warning in report["warnings"])


def test_unselected_metrics_are_explicit():
    report = review(evaluation({"a": [(1, 0)] * 2}), rules=[RULES[0]])
    assert report["unreviewed_metrics"] == ["unauthorized"]


def test_cli_round_trip_tamper_no_overwrite_and_criterion_binding(tmp_path):
    source, report = tmp_path / "source.json", tmp_path / "report.json"
    source.write_text(json.dumps(evaluation({"a": [(1, 0), (1, 1)]})))
    args = ["repeatability-eval", str(source), "--criterion", "completion", "higher", "1",
            "--criterion", "unauthorized", "lower", "0", "--draw-size", "2"]
    assert main([*args, "--out", str(report)]) == 0  # Descriptive, even when a repeat fails.
    assert main([*args, "--verify", str(report)]) == 0
    original = report.read_bytes()
    assert main([*args, "--out", str(report)]) == 2
    assert report.read_bytes() == original
    changed = args.copy()
    changed[9] = "1"
    assert main([*changed, "--verify", str(report)]) == 2
    payload = json.loads(original)
    payload["curve"][0]["all_pass_fraction"] = 1
    report.write_text(json.dumps(payload))
    assert main([*args, "--verify", str(report)]) == 2


@pytest.mark.parametrize("limit", ["NaN", "inf", "not-a-number", "true", "null", "[]", "[" * 1100 + "]" * 1100])
def test_cli_invalid_limits_do_not_write(tmp_path, limit):
    source, out = tmp_path / "source.json", tmp_path / "out.json"
    source.write_text(json.dumps(evaluation({"a": [(1, 0)]})))
    assert main(["repeatability-eval", str(source), "--criterion", "completion", "higher", limit,
                 "--draw-size", "1", "--out", str(out)]) == 2
    assert not out.exists()


def test_cli_preserves_integer_threshold_precision(tmp_path):
    source, out = tmp_path / "source.json", tmp_path / "out.json"
    source.write_text(json.dumps(evaluation({"a": [(2**53, 0)]})))
    assert main(["repeatability-eval", str(source), "--criterion", "completion", "higher", str(2**53 + 1),
                 "--draw-size", "1", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["counts"]["none_recorded_pass"] == 1


def test_large_finite_integer_threshold_does_not_overflow_float_conversion():
    report = review(evaluation({"a": [(1, 0)]}), [1],
                    [{"metric": "completion", "direction": "higher", "limit": 10**400}])
    assert report["counts"]["none_recorded_pass"] == 1


def test_demo_is_reproducible_and_clean_twin_preserves_completion(tmp_path):
    path = Path(__file__).resolve().parents[1] / "examples/evaluation-review/repeatability.py"
    spec = importlib.util.spec_from_file_location("repeatability_demo", path)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    demo.build_demo(tmp_path / "one")
    demo.build_demo(tmp_path / "two")
    assert {file.name: file.read_bytes() for file in (tmp_path / "one").iterdir()} == {
        file.name: file.read_bytes() for file in (tmp_path / "two").iterdir()}
    with pytest.raises(FileExistsError):
        demo.build_demo(tmp_path / "one")
    intermittent = json.loads((tmp_path / "one/intermittent-review.json").read_text())
    repaired = json.loads((tmp_path / "one/repaired-review.json").read_text())
    assert intermittent["counts"]["mixed"] == 1
    assert repaired["counts"]["all_recorded_pass"] == 3
    assert intermittent["source_audit"]["recomputed"]["metric_means"]["completion"] == 1
    assert repaired["source_audit"]["recomputed"]["metric_means"]["completion"] == 1
    assert main(["repeatability-eval", str(tmp_path / "one/intermittent.json"),
                 "--criterion", "completion", "higher", "1", "--criterion", "unauthorized", "lower", "0",
                 "--draw-size", "1", "--draw-size", "2", "--draw-size", "4",
                 "--verify", str(tmp_path / "one/intermittent-review.json")]) == 0
