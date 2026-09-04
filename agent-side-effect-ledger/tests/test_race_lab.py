import copy
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from aau_race_lab import (
    SideEffectError,
    attempt_request,
    run_suite,
    validate_suite,
    verify_receipt,
)
from aau_side_effect import load_json


ROOT = Path(__file__).parents[1]
SUITE_PATH = ROOT / "examples" / "race-suite.json"
RECEIPT_PATH = ROOT / "examples" / "reference-race-receipt.json"
ADAPTER_PATH = ROOT / "examples" / "reference_race_adapter.py"


def command(path: Path) -> str:
    return shlex.join([sys.executable, str(path)])


def test_reference_adapter_serializes_every_race_deterministically():
    suite = load_json(SUITE_PATH)
    first = run_suite(suite, command(ADAPTER_PATH))
    second = run_suite(suite, command(ADAPTER_PATH))
    assert first == second == load_json(RECEIPT_PATH)
    assert first["status"] == "evidence_passed"
    assert first["summary"] == {
        "case_count": 12,
        "attempt_count": 61,
        "exact_count": 12,
        "exact_rate": 1.0,
        "duplicate_effect_count": 0,
        "missing_effect_count": 0,
        "response_state_mismatch_count": 0,
    }
    verify_receipt(first, suite)


def test_attempt_request_withholds_the_oracle(tmp_path):
    suite = load_json(SUITE_PATH)
    case = suite["cases"][0]
    request = attempt_request(suite, case, case["attempts"][0], tmp_path)
    assert '"expected"' not in json.dumps(request)
    assert "worker_count" in request


def test_duplicate_attempt_identity_is_rejected():
    suite = load_json(SUITE_PATH)
    suite["cases"][1]["attempts"][0]["attempt_id"] = suite["cases"][0]["attempts"][0][
        "attempt_id"
    ]
    with pytest.raises(SideEffectError, match="duplicate race attempt_id"):
        validate_suite(suite)


def test_naive_check_then_act_adapter_exposes_duplicate_effects(tmp_path):
    adapter = tmp_path / "unsafe_adapter.py"
    adapter.write_text(
        "import json, pathlib, sys\n"
        "r=json.load(sys.stdin); d=pathlib.Path(r['state_dir'])\n"
        "if r['phase']=='attempt':\n"
        " p=d/(r['attempt']['attempt_id']+'.effect'); p.write_text('1')\n"
        " json.dump({'attempt_id':r['attempt']['attempt_id'],'outcome':'committed',"
        "'reason_codes':[]},sys.stdout)\n"
        "else:\n"
        " n=len(list(d.glob('*.effect')))\n"
        " json.dump({'case_id':r['case_id'],'effect_count':n,'key_count':n},sys.stdout)\n"
    )
    receipt = run_suite(load_json(SUITE_PATH), command(adapter))
    assert receipt["status"] == "evidence_failed"
    assert receipt["summary"]["duplicate_effect_count"] > 0


def test_deny_all_adapter_exposes_missing_legitimate_effects(tmp_path):
    adapter = tmp_path / "deny_adapter.py"
    adapter.write_text(
        "import json, sys\n"
        "r=json.load(sys.stdin)\n"
        "if r['phase']=='attempt':\n"
        " json.dump({'attempt_id':r['attempt']['attempt_id'],'outcome':'blocked',"
        "'reason_codes':['DENY_ALL']},sys.stdout)\n"
        "else:\n"
        " json.dump({'case_id':r['case_id'],'effect_count':0,'key_count':0},sys.stdout)\n"
    )
    receipt = run_suite(load_json(SUITE_PATH), command(adapter))
    assert receipt["status"] == "evidence_failed"
    assert receipt["summary"]["missing_effect_count"] > 0


def test_malformed_inspection_fails_closed(tmp_path):
    adapter = tmp_path / "malformed_adapter.py"
    adapter.write_text(
        "import json, sys\n"
        "r=json.load(sys.stdin)\n"
        "if r['phase']=='attempt':\n"
        " json.dump({'attempt_id':r['attempt']['attempt_id'],'outcome':'blocked',"
        "'reason_codes':[]},sys.stdout)\n"
        "else: json.dump({'case_id':r['case_id']},sys.stdout)\n"
    )
    with pytest.raises(SideEffectError, match="inspection fields"):
        run_suite(load_json(SUITE_PATH), command(adapter))


def test_race_suite_generator_is_reproducible(tmp_path):
    generated = tmp_path / "race-suite.json"
    generator = ROOT / "examples" / "make_race_suite.py"
    completed = subprocess.run(
        [sys.executable, str(generator), "--out", str(generated)],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert generated.read_bytes() == SUITE_PATH.read_bytes()


def test_tampered_race_receipt_fails_verification():
    suite = load_json(SUITE_PATH)
    receipt = copy.deepcopy(load_json(RECEIPT_PATH))
    receipt["summary"]["duplicate_effect_count"] = 1
    with pytest.raises(SideEffectError, match="digest mismatch"):
        verify_receipt(receipt, suite)
