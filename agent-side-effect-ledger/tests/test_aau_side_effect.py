import copy
import json
from pathlib import Path

import pytest

from aau_side_effect import (
    SideEffectError,
    build_pack,
    evaluate_suite,
    load_json,
    validate_suite,
    verify_receipt,
    write_json,
)


ROOT = Path(__file__).parents[1]
SUITE = ROOT / "examples" / "reference-suite.json"


def test_reference_suite_is_exact_and_prevents_duplicate_effects():
    receipt = evaluate_suite(load_json(SUITE))
    summary = receipt["summary"]
    assert summary["case_count"] == 12
    assert summary["event_count"] == 48
    assert summary["exact_outcome_rate"] == 1
    assert summary["exact_reason_rate"] == 1
    assert summary["known_primary_effect_count"] == 7
    assert summary["compensation_effect_count"] == 1
    assert summary["duplicate_effects_prevented"] == 3
    assert summary["key_conflicts_blocked"] == 1
    assert summary["unknown_retries_blocked"] == 1
    assert summary["reconciliation_count"] == 2
    assert summary["unresolved_effect_count"] == 0
    assert summary["at_most_one_breach_count"] == 0


def test_receipt_is_deterministic_and_recomputable():
    suite = load_json(SUITE)
    first = evaluate_suite(suite)
    second = evaluate_suite(suite)
    assert first == second
    verify_receipt(first, suite)


def test_incorrect_oracle_is_measured_instead_of_hidden():
    suite = load_json(SUITE)
    suite["cases"][1]["events"][-1]["expected"]["outcome"] = "committed"
    receipt = evaluate_suite(suite)
    assert receipt["summary"]["exact_outcome_count"] == 47
    assert receipt["summary"]["exact_outcome_rate"] < 1


def test_claim_boundary_fails_closed():
    suite = load_json(SUITE)
    suite["boundaries"]["not_exactly_once_claim"] = False
    with pytest.raises(SideEffectError, match="boundaries"):
        validate_suite(suite)


def test_forward_reference_is_rejected():
    suite = load_json(SUITE)
    suite["cases"][0]["events"][1]["content"]["intent_ref"] = "future-event"
    with pytest.raises(SideEffectError, match="earlier event"):
        validate_suite(suite)


def test_all_zero_trace_parent_identifier_is_rejected():
    suite = load_json(SUITE)
    prepare = suite["cases"][-1]["events"][0]
    prepare["content"]["traceparent"] = (
        "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01"
    )
    receipt = evaluate_suite(suite)
    event = receipt["cases"][-1]["events"][0]
    assert event["outcome"] == "blocked"
    assert event["reason_codes"] == ["TRACE_CONTEXT_INVALID"]


def test_tampering_breaks_verification():
    receipt = evaluate_suite(load_json(SUITE))
    altered = copy.deepcopy(receipt)
    altered["summary"]["duplicate_effects_prevented"] = 4
    with pytest.raises(SideEffectError, match="digest mismatch"):
        verify_receipt(altered)


def test_write_and_pack_refuse_overwrite(tmp_path):
    suite = load_json(SUITE)
    receipt = evaluate_suite(suite)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt, receipt_path)
    with pytest.raises(SideEffectError, match="overwrite"):
        write_json(receipt, receipt_path)
    pack = tmp_path / "pack"
    build_pack(SUITE, receipt_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == {
        "README.md",
        "receipt.json",
        "suite.json",
    }
    with pytest.raises(SideEffectError, match="overwrite"):
        build_pack(SUITE, receipt_path, pack)
