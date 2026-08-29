import copy
from pathlib import Path

import pytest

from aau_observatory import (
    ObservatoryError,
    evaluate_experiment,
    load_json,
    validate_experiment,
    verify_report,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_PATH = ROOT / "experiments" / "authority-control-ladder.json"


@pytest.fixture
def experiment():
    return load_json(EXPERIMENT_PATH)


def test_reference_control_ladder_is_matched_and_preserves_legitimate_actions(experiment):
    validate_experiment(experiment)
    report = evaluate_experiment(experiment)
    assert report["case_count"] == 12
    assert report["control_count"] == 8
    arms = {arm["arm_id"]: arm for arm in report["arms"]}
    assert arms["capability-only"]["measurements"]["unsafe_allow_rate"] == 1.0
    assert arms["identity-only"]["measurements"]["unsafe_allow_rate"] < 1.0
    assert arms["abp-runtime-reference"]["measurements"]["unsafe_allow_rate"] == 0.0
    assert arms["abp-runtime-reference"]["measurements"]["legitimate_allow_preservation"] == 1.0
    verify_report(report, experiment)


def test_report_is_deterministic(experiment):
    assert evaluate_experiment(experiment) == evaluate_experiment(copy.deepcopy(experiment))


def test_unknown_control_and_universal_score_claim_fail_closed(experiment):
    experiment["arms"][0]["active_controls"] = ["unknown"]
    with pytest.raises(ObservatoryError, match="active_controls"):
        validate_experiment(experiment)
    experiment = load_json(EXPERIMENT_PATH)
    experiment["boundary"]["no_universal_score"] = False
    with pytest.raises(ObservatoryError, match="boundaries"):
        validate_experiment(experiment)


def test_report_writer_does_not_overwrite(tmp_path, experiment):
    target = tmp_path / "report.json"
    write_json(evaluate_experiment(experiment), target)
    with pytest.raises(ObservatoryError, match="overwrite"):
        write_json(evaluate_experiment(experiment), target)
