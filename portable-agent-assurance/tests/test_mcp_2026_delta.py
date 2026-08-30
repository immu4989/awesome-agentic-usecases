from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mcp_2026_delta", ROOT / "mcp_2026_delta.py")
assert spec and spec.loader
delta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delta)
PROFILE = ROOT / "examples/mcp-2026-authorization-profile.json"
SUITE = ROOT / "examples/mcp-2026-authorization-suite.json"
RECEIPT = ROOT / "examples/mcp-2026-authorization-receipt.json"
ADAPTER = ROOT / "examples/mcp_2026_reference_adapter.py"


def test_reference_profile_compiles_to_clean_and_single_delta_twins():
    profile = delta.load_json(PROFILE)
    suite = delta.generate_suite(profile)
    assert suite == json.loads(SUITE.read_text())
    assert len(suite["cases"]) == 16
    assert sum(row["clean_twin"] for row in suite["cases"]) == 2
    assert all(
        len(row["expected_reason_codes"]) == 1
        for row in suite["cases"]
        if not row["clean_twin"]
    )


def test_reference_and_command_receipts_are_exact():
    profile = delta.load_json(PROFILE)
    suite = delta.load_json(SUITE)
    reference = delta.run_suite(profile, suite, "reference", None, 2)
    command = delta.run_suite(
        profile, suite, "command", f"{sys.executable} {ADAPTER}", 2
    )
    assert command == json.loads(RECEIPT.read_text())
    assert reference["metrics"] == command["metrics"] == {
        "case_count": 16,
        "clean_twin_count": 2,
        "violation_count": 14,
        "exact_count": 16,
        "unsafe_allow_count": 0,
        "legitimate_block_count": 0,
    }
    delta.verify_receipt(command, profile, suite)


def test_deny_all_and_allow_all_fail_asymmetrically(tmp_path):
    profile = delta.load_json(PROFILE)
    suite = delta.load_json(SUITE)
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
    denied = delta.run_suite(profile, suite, "command", f"{sys.executable} {deny}", 2)
    allowed = delta.run_suite(profile, suite, "command", f"{sys.executable} {allow}", 2)
    assert denied["metrics"]["legitimate_block_count"] == 2
    assert allowed["metrics"]["unsafe_allow_count"] == 14


def test_profile_and_suite_drift_fail_closed():
    profile = delta.load_json(PROFILE)
    suite = delta.load_json(SUITE)
    old = copy.deepcopy(profile)
    old["protocol_revision"] = "2025-06-18"
    with pytest.raises(delta.McpDeltaError, match="protocol_revision"):
        delta.validate_profile(old)
    weakened = copy.deepcopy(profile)
    weakened["claim_boundaries"]["not_mcp_or_oauth_conformance"] = False
    with pytest.raises(delta.McpDeltaError, match="weakened"):
        delta.validate_profile(weakened)
    stale = copy.deepcopy(suite)
    stale["cases"][0]["expected_decision"] = "block"
    with pytest.raises(delta.McpDeltaError, match="does not recompute"):
        delta.run_suite(profile, stale, "reference", None, 2)


def test_receipt_tampering_is_detected():
    profile = delta.load_json(PROFILE)
    suite = delta.load_json(SUITE)
    receipt = delta.load_json(RECEIPT)
    receipt["results"][0]["exact"] = False
    with pytest.raises(delta.McpDeltaError, match="exactness"):
        delta.verify_receipt(receipt, profile, suite)
