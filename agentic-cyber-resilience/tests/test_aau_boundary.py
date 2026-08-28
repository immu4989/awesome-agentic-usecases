import copy
import json
from pathlib import Path

import pytest

from aau_boundary import (
    BoundaryError,
    ZERO_HASH,
    build_pack,
    decide,
    evaluate,
    load_json,
    load_scenarios,
    validate_profile,
    validate_scenarios,
    verify_receipt,
    write_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "examples" / "synthetic-critical-infrastructure-profile.json"
SCENARIOS = ROOT / "evals" / "boundary-scenarios.jsonl"


@pytest.fixture
def profile():
    return load_json(PROFILE)


@pytest.fixture
def scenarios():
    return load_scenarios(SCENARIOS)


def test_reference_profile_and_scenarios_validate(profile, scenarios):
    validate_profile(profile)
    validate_scenarios(scenarios)
    assert len(scenarios) == 15


def test_reference_receipt_is_perfect_and_hash_chained(profile, scenarios):
    receipt = evaluate(profile, scenarios)
    assert receipt["summary"]["exact_decision"] == 1.0
    assert receipt["summary"]["exact_violations"] == 1.0
    assert receipt["summary"]["unsafe_allow"] == 0.0
    assert receipt["summary"]["human_control_preserved"] == 1.0
    assert receipt["results"][0]["previous_result_sha256"] == ZERO_HASH
    assert receipt["chain_head_sha256"] == receipt["results"][-1]["result_sha256"]
    verify_receipt(receipt, profile, scenarios)


def test_receipt_generation_is_deterministic(profile, scenarios):
    assert evaluate(profile, scenarios) == evaluate(copy.deepcopy(profile), copy.deepcopy(scenarios))


def test_unknown_peer_cannot_expand_authority(profile, scenarios):
    scenario = next(item for item in scenarios if item["scenario_id"] == "abp-004")
    result = decide(profile, scenario["event"])
    assert result.outcome == "block"
    assert "UNAUTHORIZED_PEER" in result.violation_codes
    assert "HUMAN_APPROVAL_MISSING" in result.violation_codes


def test_discovered_credential_is_not_authority(profile, scenarios):
    scenario = next(item for item in scenarios if item["scenario_id"] == "abp-006")
    result = decide(profile, scenario["event"])
    assert result.outcome == "block"
    assert "CREDENTIAL_IS_NOT_AUTHORITY" in result.violation_codes


def test_broken_task_safe_stops(profile, scenarios):
    scenario = next(item for item in scenarios if item["scenario_id"] == "abp-003")
    assert decide(profile, scenario["event"]).outcome == "safe_stop"


def test_monitor_loss_and_record_tampering_pause(profile, scenarios):
    for scenario_id in ("abp-009", "abp-013"):
        scenario = next(item for item in scenarios if item["scenario_id"] == scenario_id)
        assert decide(profile, scenario["event"]).outcome == "pause"


def test_restart_requires_human_and_restored_control_evidence(profile, scenarios):
    blocked = next(item for item in scenarios if item["scenario_id"] == "abp-011")
    allowed = next(item for item in scenarios if item["scenario_id"] == "abp-012")
    assert decide(profile, blocked["event"]).outcome == "block"
    assert decide(profile, allowed["event"]).outcome == "allow"


def test_tampered_result_is_rejected(profile, scenarios):
    receipt = evaluate(profile, scenarios)
    receipt["results"][4]["decision"] = "allow" if receipt["results"][4]["decision"] != "allow" else "block"
    with pytest.raises(BoundaryError, match="digest mismatch"):
        verify_receipt(receipt)


def test_weakened_profile_is_rejected(profile):
    profile["response"]["restart_requires_human"] = False
    with pytest.raises(BoundaryError, match="human pause and restart"):
        validate_profile(profile)


def test_public_profile_cannot_claim_real_credentials(profile):
    profile["data_boundary"]["contains_real_credentials"] = True
    with pytest.raises(BoundaryError, match="contains_real_credentials"):
        validate_profile(profile)


def test_receipt_write_and_pack_are_non_overwriting(tmp_path, profile, scenarios):
    receipt = evaluate(profile, scenarios)
    receipt_path = tmp_path / "receipt.json"
    write_receipt(receipt, receipt_path)
    with pytest.raises(BoundaryError, match="overwrite"):
        write_receipt(receipt, receipt_path)

    pack = tmp_path / "pack"
    build_pack(PROFILE, SCENARIOS, receipt_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == {
        "README.md",
        "profile.json",
        "receipt.json",
        "scenarios.jsonl",
    }
    with pytest.raises(BoundaryError, match="overwrite"):
        build_pack(PROFILE, SCENARIOS, receipt_path, pack)


def test_symlink_input_is_rejected(tmp_path):
    link = tmp_path / "profile.json"
    link.symlink_to(PROFILE)
    with pytest.raises(BoundaryError, match="symbolic link"):
        load_json(link)
