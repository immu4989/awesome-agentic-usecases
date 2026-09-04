import copy
import json
import shlex
import sys
from pathlib import Path

import pytest

from aau_crash_lab import (
    CRASH_POINTS,
    SideEffectError,
    adapter_request,
    run_suite,
    validate_suite,
    verify_receipt,
)
from aau_side_effect import load_json


ROOT = Path(__file__).parents[1]
SUITE_PATH = ROOT / "examples" / "crash-suite.json"
RECEIPT_PATH = ROOT / "examples" / "reference-crash-receipt.json"
ADAPTER_PATH = ROOT / "examples" / "reference_crash_adapter.py"


def reference_command() -> str:
    return shlex.join([sys.executable, str(ADAPTER_PATH)])


def test_reference_adapter_recovers_all_crash_points_exactly():
    suite = load_json(SUITE_PATH)
    receipt = run_suite(suite, reference_command())
    assert receipt == load_json(RECEIPT_PATH)
    assert receipt["status"] == "evidence_passed"
    assert receipt["summary"] == {
        "case_count": 12,
        "crash_point_count": 6,
        "exact_count": 12,
        "exact_rate": 1.0,
        "unsafe_resume_count": 0,
        "duplicate_effect_breach_count": 0,
        "unresolved_effect_count": 3,
    }
    verify_receipt(receipt, suite)


def test_suite_covers_every_declared_crash_point():
    suite = load_json(SUITE_PATH)
    assert {case["crash_after"] for case in suite["cases"]} == CRASH_POINTS
    validate_suite(suite)


def test_adapter_request_withholds_expected_answer(tmp_path):
    suite = load_json(SUITE_PATH)
    request = adapter_request(suite, suite["cases"][0], "inject", tmp_path)
    assert '"expected"' not in json.dumps(request)
    assert request["phase"] == "inject"


def test_target_cannot_resolve_before_dispatch():
    suite = load_json(SUITE_PATH)
    suite["cases"][0]["target_outcome"] = "committed"
    with pytest.raises(SideEffectError, match="before its crash point"):
        validate_suite(suite)


def test_missing_crash_exit_fails_closed(tmp_path):
    adapter = tmp_path / "does_not_crash.py"
    adapter.write_text("import sys\nsys.exit(0)\n")
    with pytest.raises(SideEffectError, match="expected 86"):
        run_suite(load_json(SUITE_PATH), shlex.join([sys.executable, str(adapter)]))


def test_incomplete_recovery_response_fails_closed(tmp_path):
    adapter = tmp_path / "incomplete.py"
    adapter.write_text(
        "import json, os, sys\n"
        "r=json.load(sys.stdin)\n"
        "os._exit(86) if r['phase']=='inject' else json.dump({}, sys.stdout)\n"
    )
    with pytest.raises(SideEffectError, match="response fields"):
        run_suite(load_json(SUITE_PATH), shlex.join([sys.executable, str(adapter)]))


def test_unsafe_resume_is_counted_separately(tmp_path):
    adapter = tmp_path / "unsafe.py"
    adapter.write_text(
        "import json, os, sys\n"
        "r=json.load(sys.stdin)\n"
        "if r['phase']=='inject': os._exit(86)\n"
        "json.dump({'case_id':r['case']['case_id'],"
        "'recovered_outcome':'recovery_ready','next_action':'dispatch_once',"
        "'known_effect_count':0,'reason_codes':[]},sys.stdout)\n"
    )
    receipt = run_suite(load_json(SUITE_PATH), shlex.join([sys.executable, str(adapter)]))
    assert receipt["status"] == "evidence_failed"
    assert receipt["summary"]["unsafe_resume_count"] > 0


def test_tampered_receipt_fails_verification():
    suite = load_json(SUITE_PATH)
    receipt = copy.deepcopy(load_json(RECEIPT_PATH))
    receipt["summary"]["unsafe_resume_count"] = 1
    with pytest.raises(SideEffectError, match="digest mismatch"):
        verify_receipt(receipt, suite)
