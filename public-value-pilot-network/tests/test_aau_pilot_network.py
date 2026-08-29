import copy
import json
from pathlib import Path

import pytest

from aau_pilot_network import (
    PilotError,
    assess_pilot,
    build_pack,
    load_json,
    validate_pilot,
    verify_assessment,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
PILOT_PATH = ROOT / "pilots" / "foia-routing-partner-call.json"


@pytest.fixture
def pilot():
    return load_json(PILOT_PATH)


def test_partner_call_is_honestly_designed_with_visible_gaps(pilot):
    validate_pilot(pilot)
    assessment = assess_pilot(pilot)
    assert assessment["evidence_level"] == "designed"
    assert assessment["visible_gaps"] == [
        "human_baseline_missing",
        "institutional_determination_missing",
        "field_observation_missing",
        "independent_reproduction_missing",
    ]
    verify_assessment(assessment, pilot)


def test_assessment_is_deterministic(pilot):
    assert assess_pilot(pilot) == assess_pilot(copy.deepcopy(pilot))


def test_false_independence_and_causal_claim_fail_closed(pilot):
    pilot["reproduction"]["independent"] = True
    with pytest.raises(PilotError, match="must not imply independence"):
        validate_pilot(pilot)
    pilot = load_json(PILOT_PATH)
    pilot["field_observation"]["causal_claim"] = True
    with pytest.raises(PilotError, match="causal claim"):
        validate_pilot(pilot)


def test_verified_reproduction_requires_same_suite(pilot):
    pilot["reproduction"] = {
        "status": "verified",
        "independent": True,
        "organization": "Independent synthetic reviewer",
        "artifact_ref": "public/reproduction.json",
        "suite_sha256": "0" * 64,
        "reviewed_on": "2026-08-29",
    }
    with pytest.raises(PilotError, match="suite hash differs"):
        validate_pilot(pilot)


def test_pack_is_non_overwriting(tmp_path, pilot):
    assessment = assess_pilot(pilot)
    assessment_path = tmp_path / "assessment.json"
    write_json(assessment, assessment_path)
    with pytest.raises(PilotError, match="overwrite"):
        write_json(assessment, assessment_path)
    pack = tmp_path / "pack"
    build_pack(PILOT_PATH, assessment_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == {
        "README.md",
        "assessment.json",
        "pilot.json",
    }
