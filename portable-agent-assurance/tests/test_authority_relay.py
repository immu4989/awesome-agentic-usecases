from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("authority_relay", ROOT / "authority_relay.py")
assert SPEC and SPEC.loader
RELAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELAY)
PROFILE = ROOT / "examples/a2a-mcp-authority-relay-profile.json"
SUITE = ROOT / "examples/a2a-mcp-authority-relay-suite.json"
RECEIPT = ROOT / "examples/a2a-mcp-authority-relay-receipt.json"
ADAPTER = ROOT / "examples/authority_relay_reference_adapter.py"


def test_profile_compiles_to_clean_and_single_boundary_twins():
    profile = RELAY.load_json(PROFILE)
    suite = RELAY.generate_suite(profile)
    assert suite == json.loads(SUITE.read_text())
    assert len(suite["cases"]) == 25
    assert sum(row["clean_twin"] for row in suite["cases"]) == 2
    assert all(
        len(row["expected_reason_codes"]) == 1
        for row in suite["cases"]
        if not row["clean_twin"]
    )


def test_reference_and_answer_blind_command_receipts_are_exact():
    profile = RELAY.load_json(PROFILE)
    suite = RELAY.load_json(SUITE)
    reference = RELAY.run_suite(profile, suite, "reference", None, 2)
    command = RELAY.run_suite(profile, suite, "command", f"{sys.executable} {ADAPTER}", 2)
    assert command == json.loads(RECEIPT.read_text())
    assert reference["metrics"] == command["metrics"] == {
        "case_count": 25,
        "clean_twin_count": 2,
        "violation_count": 23,
        "exact_count": 25,
        "unsafe_allow_count": 0,
        "legitimate_block_count": 0,
    }
    RELAY.verify_receipt(command, profile, suite)


def test_allow_all_and_deny_all_fail_asymmetrically(tmp_path):
    profile = RELAY.load_json(PROFILE)
    suite = RELAY.load_json(SUITE)
    deny = tmp_path / "deny.py"
    deny.write_text(
        "import json,sys\njson.load(sys.stdin)\n"
        "json.dump({'decision':'block','reason_codes':['DENY_ALL']},sys.stdout)\n"
    )
    allow = tmp_path / "allow.py"
    allow.write_text(
        "import json,sys\njson.load(sys.stdin)\n"
        "json.dump({'decision':'allow','reason_codes':[]},sys.stdout)\n"
    )
    denied = RELAY.run_suite(profile, suite, "command", f"{sys.executable} {deny}", 2)
    allowed = RELAY.run_suite(profile, suite, "command", f"{sys.executable} {allow}", 2)
    assert denied["metrics"]["legitimate_block_count"] == 2
    assert allowed["metrics"]["unsafe_allow_count"] == 23


def test_profile_and_suite_drift_fail_closed():
    profile = RELAY.load_json(PROFILE)
    suite = RELAY.load_json(SUITE)
    widened = copy.deepcopy(profile)
    widened["routes"][0]["human_approval_required"] = False
    with pytest.raises(RELAY.RelayError, match="requires approval"):
        RELAY.validate_profile(widened)
    weakened = copy.deepcopy(profile)
    weakened["claim_boundaries"]["not_certification_deployment_authority_or_ato"] = False
    with pytest.raises(RELAY.RelayError, match="weakened"):
        RELAY.validate_profile(weakened)
    stale = copy.deepcopy(suite)
    stale["cases"][0]["expected_decision"] = "block"
    with pytest.raises(RELAY.RelayError, match="does not recompute"):
        RELAY.run_suite(profile, stale, "reference", None, 2)


def test_receipt_tampering_is_detected():
    profile = RELAY.load_json(PROFILE)
    suite = RELAY.load_json(SUITE)
    receipt = RELAY.load_json(RECEIPT)
    receipt["results"][0]["actual_decision"] = "block"
    with pytest.raises(RELAY.RelayError, match="exactness"):
        RELAY.verify_receipt(receipt, profile, suite)
