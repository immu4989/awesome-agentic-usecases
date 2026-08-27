import json
from pathlib import Path

import pytest

from aau_harness.catalog_cli import main as aau_main
from aau_harness.evaluate import AdapterResult, evaluate_suite, load_suite
from aau_harness.human_baseline import (
    ABSTAIN,
    HumanBaselineError,
    SESSION_BOUNDARY,
    SESSION_VERSION,
    prepare_study,
    sha256_json,
    summarize_pack,
    validate_pack,
    validate_report,
    validate_session,
)


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "examples" / "byo-agent-suite.json"


def make_session(study, answer_key, session_id, *, errors=(), abstains=(), kind="synthetic_reference"):
    responses = []
    for index, case in enumerate(study["cases"]):
        scenario_id = case["scenario_id"]
        expected = answer_key["answers"][scenario_id]
        if scenario_id in abstains:
            outcome = ABSTAIN
        elif scenario_id in errors:
            outcome = next(value for value in study["outcomes"] if value != expected)
        else:
            outcome = expected
        responses.append(
            {
                "scenario_id": scenario_id,
                "outcome": outcome,
                "confidence": 55 + index * 10,
                "elapsed_ms": 1000 + index * 250,
            }
        )
    return {
        "session_version": SESSION_VERSION,
        "study_id": study["study_id"],
        "study_sha256": sha256_json(study),
        "anonymous_session_id": session_id,
        "session_kind": kind,
        "participant_role": study["participant_roles"][0],
        "protection_basis": (
            "synthetic_only"
            if kind == "synthetic_reference"
            else "institutional_determination_recorded"
        ),
        "responses": responses,
        "boundary": SESSION_BOUNDARY,
    }


def build_pack(tmp_path):
    pack = tmp_path / "baseline-pack"
    prepare_study(
        SUITE,
        pack,
        study_id="service-routing-baseline",
        title="Service Routing Human Baseline",
        purpose="Compare a reviewed synthetic routing task with the current human process.",
    )
    checked = validate_pack(pack)
    return pack, checked["study"], checked["answer_key"]


def test_prepare_is_blinded_hashed_non_overwriting_and_valid(tmp_path):
    pack, study, answer_key = build_pack(tmp_path)
    assert len(study["cases"]) == 3
    assert "expected" not in (pack / "study.json").read_text()
    assert answer_key["answers"]
    assert study["human_protections"]["review_status"] == "not_determined"
    assert set(path.name for path in pack.iterdir()) == {
        "README.md",
        "answer-key.json",
        "manifest.json",
        "session-template.json",
        "study.json",
    }
    with pytest.raises(HumanBaselineError, match="refusing to overwrite"):
        prepare_study(
            SUITE,
            pack,
            study_id="service-routing-baseline",
            title="Service Routing Human Baseline",
            purpose="A repeated attempt must not overwrite the study.",
        )


def test_summarize_is_aggregate_only_and_compares_a_real_adapter(tmp_path):
    pack, study, answer_key = build_pack(tmp_path)
    scenario_ids = [case["scenario_id"] for case in study["cases"]]
    sessions = [
        make_session(study, answer_key, "a" * 12),
        make_session(study, answer_key, "b" * 12, errors={scenario_ids[0]}),
        make_session(study, answer_key, "c" * 12, abstains={scenario_ids[1]}),
    ]
    session_paths = []
    for index, session in enumerate(sessions):
        path = tmp_path / f"session-{index}.json"
        path.write_text(json.dumps(session))
        session_paths.append(path)

    suite = load_suite(SUITE)
    answers = {case["scenario_id"]: case["expected"]["outcome"] for case in suite["cases"]}

    def adapter(payload):
        outcome = answers[payload["scenario_id"]]
        if payload["scenario_id"] == scenario_ids[0]:
            outcome = next(value for value in study["outcomes"] if value != outcome)
        return AdapterResult(
            {
                "outcome": outcome,
                "actions_attempted": [],
                "actions_executed": [],
                "submitted": True,
            },
            0.01,
        )

    receipt, _ = evaluate_suite(suite, adapter, "command")
    receipt_path = tmp_path / "agent-receipt.json"
    receipt_path.write_text(json.dumps(receipt))
    report_path = tmp_path / "public-report.json"
    report = summarize_pack(
        pack,
        session_paths,
        report_path,
        agent_receipt_path=receipt_path,
    )

    assert report["source"]["session_count"] == 3
    assert report["metrics"]["outcome_exact_rate"] == pytest.approx(7 / 9, abs=0.0001)
    assert report["metrics"]["abstain_rate"] == pytest.approx(1 / 9, abs=0.0001)
    assert report["agent_comparison"]["agent_exact_rate"] == pytest.approx(2 / 3, abs=0.0001)
    published = report_path.read_text()
    assert "anonymous_session_id" not in published
    assert '"outcome"' not in published
    assert '"confidence"' not in published
    assert '"elapsed_ms"' not in published
    assert "aaaaaaaaaaaa" not in published
    validate_report(json.loads(published))

    inconsistent_report = json.loads(published)
    inconsistent_report["source"]["session_kinds"]["human_observed"] = 1
    with pytest.raises(HumanBaselineError, match="session kinds"):
        validate_report(inconsistent_report)

    inconsistent_receipt = {**receipt, "scenario_count": 999}
    inconsistent_receipt_path = tmp_path / "inconsistent-agent-receipt.json"
    inconsistent_receipt_path.write_text(json.dumps(inconsistent_receipt))
    with pytest.raises(HumanBaselineError, match="scenario_count"):
        summarize_pack(
            pack,
            session_paths,
            tmp_path / "inconsistent-report.json",
            agent_receipt_path=inconsistent_receipt_path,
        )


def test_sessions_fail_closed_on_identity_review_and_coverage(tmp_path):
    _, study, answer_key = build_pack(tmp_path)
    session = make_session(study, answer_key, "d" * 12, kind="human_observed")
    session["protection_basis"] = "synthetic_only"
    with pytest.raises(HumanBaselineError, match="institutional determination"):
        validate_session(session, study)

    session = make_session(study, answer_key, "e" * 12)
    session["anonymous_session_id"] = "person@example.gov"
    with pytest.raises(HumanBaselineError, match="lowercase hex"):
        validate_session(session, study)

    session = make_session(study, answer_key, "f" * 12)
    session["responses"].pop()
    with pytest.raises(HumanBaselineError, match="every study case"):
        validate_session(session, study)


def test_pack_tamper_and_duplicate_sessions_are_rejected(tmp_path):
    pack, study, answer_key = build_pack(tmp_path)
    original = (pack / "study.json").read_text()
    (pack / "study.json").write_text(original + " ")
    with pytest.raises(HumanBaselineError, match="manifest mismatch"):
        validate_pack(pack)

    second_pack, study, answer_key = build_pack(tmp_path / "second")
    session = make_session(study, answer_key, "1" * 12)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(session))
    second.write_text(json.dumps(session))
    with pytest.raises(HumanBaselineError, match="must be unique"):
        summarize_pack(second_pack, [first, second], tmp_path / "report.json")


def test_catalog_cli_routes_baseline_outside_repository(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "cli-baseline"
    assert (
        aau_main(
            [
                "baseline",
                "prepare",
                str(SUITE),
                "--id",
                "cli-human-baseline",
                "--title",
                "CLI Human Baseline",
                "--purpose",
                "Exercise the public command outside a repository checkout.",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    assert "Human baseline ready" in capsys.readouterr().out
    assert validate_pack(output)["ready"] is True
