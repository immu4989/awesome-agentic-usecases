import json
from pathlib import Path

import pytest

from aau_harness.challenge import (
    CHALLENGE_VERSION,
    ChallengeError,
    _validate_receipt,
    build_challenge,
    load_challenges,
)


ROOT = Path(__file__).resolve().parents[2]


def test_challenge_board_is_honest_and_machine_derived():
    board = build_challenge(ROOT)
    assert board["version"] == CHALLENGE_VERSION
    assert board["stats"]["live_challenges"] == 5
    assert board["stats"]["community_finishes"] == 0
    assert board["stats"]["reference_finishes"] == 3
    assert all(item["type"] == "reference" for item in board["scoreboard"])
    assert all("receipt-ready" in item["achievements"] for item in board["scoreboard"])


def test_every_mission_starts_from_a_real_lab():
    data = load_challenges(ROOT)
    assert {item["track"] for item in data["challenges"]} == {"Reproduce", "Break", "Adapt"}
    assert all((ROOT / item["starter_lab"]).is_dir() for item in data["challenges"])
    assert all("--backend mock" in item["command"] or "aau start" in item["command"] for item in data["challenges"])


def test_unknown_challenge_metadata_is_rejected(monkeypatch):
    from aau_harness import challenge as module

    real_gallery = module.build_gallery(ROOT)
    altered = json.loads(json.dumps(real_gallery))
    altered["entries"][0]["challenge"] = {
        "id": "invented-mission",
        "track": "Break",
        "claim": "A claim with no catalog record.",
    }
    monkeypatch.setattr(module, "build_gallery", lambda _root: altered)
    with pytest.raises(ChallengeError, match="unknown challenge id"):
        module.build_challenge(ROOT)


def test_lightweight_receipt_validates_result_note_and_scenario(tmp_path):
    lab = tmp_path / "sample" / "lab"
    (lab / "results").mkdir(parents=True)
    (lab / "evals").mkdir()
    (tmp_path / "challenge" / "receipts").mkdir(parents=True)
    (lab / "evals" / "scenarios.jsonl").write_text('{"scenario_id":"case-017"}\n')
    (lab / "results" / "eval_reproduce_alice.json").write_text(json.dumps({
        "model": "mock", "backend": "mock", "n_scenarios": 1, "n_repeats": 3,
    }))
    (tmp_path / "challenge" / "receipts" / "alice-receipt.md").write_text(
        "# Receipt\n\nTraced the deciding mismatch to `case-017`.\n"
    )
    mission = {
        "id": "completion-gap", "track": "Reproduce", "title": "Completion gap",
        "starter_lab": "sample/lab",
    }
    receipt = {
        "schema_version": "aau-challenge-entry/1.0",
        "id": "alice-receipt",
        "challenge_id": "completion-gap",
        "track": "Reproduce",
        "contributor": {"name": "Alice", "github": "alice"},
        "lab_path": "sample/lab",
        "claim": "Reproduced the completion gap.",
        "evidence": {
            "result_path": "sample/lab/results/eval_reproduce_alice.json",
            "note_path": "challenge/receipts/alice-receipt.md",
            "scenario_ids": ["case-017"],
        },
    }
    evaluated = _validate_receipt(tmp_path, receipt, {mission["id"]: mission})
    assert evaluated["finish"] is True
    assert evaluated["achievements"] == ["receipt-ready"]


def test_lightweight_receipt_rejects_untraced_scenario(tmp_path):
    lab = tmp_path / "sample" / "lab"
    (lab / "results").mkdir(parents=True)
    (lab / "evals").mkdir()
    (tmp_path / "challenge" / "receipts").mkdir(parents=True)
    (lab / "evals" / "scenarios.jsonl").write_text('{"scenario_id":"case-001"}\n')
    (lab / "results" / "eval.json").write_text(json.dumps({"n_scenarios": 1, "n_repeats": 3}))
    (tmp_path / "challenge" / "receipts" / "bob.md").write_text("No linked id.\n")
    mission = {"id": "break-it", "track": "Break", "title": "Break it", "starter_lab": "sample/lab"}
    receipt = {
        "schema_version": "aau-challenge-entry/1.0", "id": "bob", "challenge_id": "break-it",
        "track": "Break", "contributor": {"name": "Bob", "github": "bob"},
        "lab_path": "sample/lab", "claim": "Found a failure.",
        "evidence": {"result_path": "sample/lab/results/eval.json", "note_path": "challenge/receipts/bob.md", "scenario_ids": ["case-999"]},
    }
    with pytest.raises(ChallengeError, match="scenario ids not found"):
        _validate_receipt(tmp_path, receipt, {mission["id"]: mission})
