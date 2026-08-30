from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("a2a_1_delta", ROOT / "a2a_1_delta.py")
assert SPEC and SPEC.loader
DELTA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELTA)
PROFILE = ROOT / "examples/a2a-1-interface-authorization-profile.json"
SUITE = ROOT / "examples/a2a-1-interface-authorization-suite.json"
RECEIPT = ROOT / "examples/a2a-1-interface-authorization-receipt.json"
ADAPTER = ROOT / "examples/a2a_1_reference_adapter.py"


def test_profile_compiles_to_clean_and_single_delta_twins():
    profile = DELTA.load_json(PROFILE)
    suite = DELTA.generate_suite(profile)
    assert suite == json.loads(SUITE.read_text())
    assert len(suite["cases"]) == 17
    assert sum(row["clean_twin"] for row in suite["cases"]) == 2
    assert all(
        len(row["expected_reason_codes"]) == 1
        for row in suite["cases"]
        if not row["clean_twin"]
    )


def test_reference_and_answer_blind_command_receipts_are_exact():
    profile = DELTA.load_json(PROFILE)
    suite = DELTA.load_json(SUITE)
    reference = DELTA.run_suite(profile, suite, "reference", None, 2)
    command = DELTA.run_suite(profile, suite, "command", f"{sys.executable} {ADAPTER}", 2)
    assert command == json.loads(RECEIPT.read_text())
    assert reference["metrics"] == command["metrics"] == {
        "case_count": 17,
        "clean_twin_count": 2,
        "violation_count": 15,
        "exact_count": 17,
        "unsafe_allow_count": 0,
        "legitimate_block_count": 0,
    }
    DELTA.verify_receipt(command, profile, suite)


def test_deny_all_and_allow_all_fail_asymmetrically(tmp_path):
    profile = DELTA.load_json(PROFILE)
    suite = DELTA.load_json(SUITE)
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
    denied = DELTA.run_suite(profile, suite, "command", f"{sys.executable} {deny}", 2)
    allowed = DELTA.run_suite(profile, suite, "command", f"{sys.executable} {allow}", 2)
    assert denied["metrics"]["legitimate_block_count"] == 2
    assert allowed["metrics"]["unsafe_allow_count"] == 15


def test_profile_and_suite_drift_fail_closed():
    profile = DELTA.load_json(PROFILE)
    suite = DELTA.load_json(SUITE)
    legacy = copy.deepcopy(profile)
    legacy["protocol_revision"] = "0.3"
    with pytest.raises(DELTA.A2aDeltaError, match="protocol_revision"):
        DELTA.validate_profile(legacy)
    weakened = copy.deepcopy(profile)
    weakened["claim_boundaries"]["not_a2a_protocol_or_security_conformance"] = False
    with pytest.raises(DELTA.A2aDeltaError, match="weakened"):
        DELTA.validate_profile(weakened)
    stale = copy.deepcopy(suite)
    stale["cases"][0]["expected_decision"] = "block"
    with pytest.raises(DELTA.A2aDeltaError, match="does not recompute"):
        DELTA.run_suite(profile, stale, "reference", None, 2)


def test_receipt_tampering_is_detected():
    profile = DELTA.load_json(PROFILE)
    suite = DELTA.load_json(SUITE)
    receipt = DELTA.load_json(RECEIPT)
    receipt["results"][0]["exact"] = False
    with pytest.raises(DELTA.A2aDeltaError, match="exactness"):
        DELTA.verify_receipt(receipt, profile, suite)
