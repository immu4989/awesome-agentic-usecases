from copy import deepcopy

import pytest

from aau_harness.agent_bom import AgentBomError
from aau_harness.eval_compare import compare_evaluations
from aau_harness.evaluation_context import capture_context, validate_context
from aau_harness.runner import ScenarioResult, run_eval


def context():
    return capture_context([{"scenario_id": "a", "case": {"record": 1}}, {"scenario_id": "b", "case": {"record": 2}}],
                           {"rule": "synthetic-v1"}, {"scorer.py": b"def score(): return 1\n"})


def evidence(fingerprint=None):
    return run_eval(["a", "b"], lambda scenario, repeat: ScenarioResult(
        scenario, repeat, {"score": 1.0}, 0, 0.1, 0), repeats=2, evaluation_context=fingerprint).as_dict()


def compare(before, after):
    return compare_evaluations(before, after, metric="score", direction="higher")


def test_context_matches_by_id_and_is_independent_of_mapping_order():
    first = context()
    reordered = capture_context([{"case": {"record": 2}, "scenario_id": "b"}, {"case": {"record": 1}, "scenario_id": "a"}],
                                {"rule": "synthetic-v1"}, {"scorer.py": b"def score(): return 1\n"})
    assert first == reordered
    assert compare(evidence(first), evidence(reordered))["context_match"]["status"] == "matched"


@pytest.mark.parametrize("field", ["scenario_sha256", "config_sha256", "scoring_sha256"])
def test_identical_ids_and_scores_do_not_hide_changed_benchmark_context(field):
    first = context()
    second = deepcopy(first)
    if field == "config_sha256":
        second[field] = "0" * 64
    else:
        second[field][next(iter(second[field]))] = "0" * 64
    with pytest.raises(AgentBomError, match=field):
        compare(evidence(first), evidence(second))


@pytest.mark.parametrize("missing", ["baseline", "candidate", "both"])
def test_legacy_results_remain_available_with_explicit_unknown_context(missing):
    before = evidence(None if missing in ("baseline", "both") else context())
    after = evidence(None if missing in ("candidate", "both") else context())
    report = compare(before, after)
    assert report["context_match"]["status"] == "unavailable"
    assert report["context_match"]["missing_sources"] == (["baseline", "candidate"] if missing == "both" else [missing])
    assert any("matching scenario IDs alone" in warning for warning in report["warnings"])


@pytest.mark.parametrize("defect", ["null", "bad-hash", "wrong-ids", "unknown-field", "empty-scorers"])
def test_malformed_present_context_is_not_treated_as_legacy_absence(defect):
    source = evidence(context())
    value = source["evaluation_context"]
    if defect == "null":
        source["evaluation_context"] = None
    elif defect == "bad-hash":
        value["config_sha256"] = "not a digest"
    elif defect == "wrong-ids":
        value["scenario_sha256"]["c"] = value["scenario_sha256"].pop("b")
    elif defect == "unknown-field":
        value["verified"] = True
    else:
        value["scoring_sha256"] = {}
    with pytest.raises(AgentBomError):
        compare(evidence(), source)


def test_runner_freezes_context_before_callbacks_and_on_export():
    original = context()
    mutable = deepcopy(original)
    def callback(scenario, repeat):
        mutable["config_sha256"] = "0" * 64
        return ScenarioResult(scenario, repeat, {"score": 1.0}, 0, 0.1, 0)
    aggregate = run_eval(["a", "b"], callback, repeats=1, evaluation_context=mutable)
    assert aggregate.evaluation_context == original
    exported = aggregate.as_dict()
    exported["evaluation_context"]["config_sha256"] = "1" * 64
    assert aggregate.evaluation_context == original


def test_invalid_context_fails_before_callback_and_wrong_result_identity_fails():
    called = []
    def callback(scenario, repeat):
        called.append(scenario)
        return ScenarioResult("unexpected", repeat, {"score": 1.0}, 0, 0.1, 0)
    with pytest.raises(AgentBomError):
        run_eval(["a", "b"], callback, evaluation_context={})
    assert called == []
    with pytest.raises(ValueError, match="scenario count"):
        run_eval(["a"], callback, evaluation_context=context())
    assert called == []
    with pytest.raises(ValueError, match="absent"):
        run_eval(["a", "b"], callback, evaluation_context=context())


def test_capture_rejects_duplicate_ids_nonfinite_values_and_nonbyte_sources():
    with pytest.raises(AgentBomError):
        capture_context([{"scenario_id": "a"}, {"scenario_id": "a"}], {}, {"score": b"x"})
    with pytest.raises(AgentBomError):
        capture_context([{"scenario_id": "a", "value": float("nan")}], {}, {"score": b"x"})
    with pytest.raises(AgentBomError):
        capture_context([{"scenario_id": "a"}], {}, {"score": "not bytes"})
    with pytest.raises(AgentBomError):
        capture_context([{"scenario_id": "a"}], {1: "ambiguous JSON key"}, {"score": b"x"})
    validate_context(context(), ["a", "b"])
