import copy
import json
from pathlib import Path

import pytest

from aau_defense_benchmark import BenchmarkError, build_pack, evaluate, load_json, validate_responses, validate_suite, verify_receipt, write_json


ROOT = Path(__file__).parents[1]
SUITE = ROOT / "examples" / "collective-defense-suite.json"
RESPONSES = ROOT / "examples" / "reference-protocol-responses.json"


def test_reference_protocol_covers_twenty_tasks_and_five_families():
    receipt = evaluate(load_json(SUITE), load_json(RESPONSES))
    assert receipt["summary"]["task_count"] == 20
    assert receipt["summary"]["exact_count"] == 20
    assert receipt["summary"]["unsafe_count"] == 0
    assert len(receipt["families"]) == 5


def test_evaluation_is_deterministic_and_verifiable():
    suite, responses = load_json(SUITE), load_json(RESPONSES)
    receipt = evaluate(suite, responses)
    assert receipt == evaluate(suite, responses)
    verify_receipt(receipt, suite, responses)


def test_missing_human_escalation_is_unsafe():
    suite, responses = load_json(SUITE), load_json(RESPONSES)
    responses["responses"][0]["human_escalation"] = False
    receipt = evaluate(suite, responses)
    assert receipt["summary"]["unsafe_count"] == 1
    assert receipt["summary"]["exact_count"] == 19


def test_wrong_action_is_measured_separately_from_safety():
    suite, responses = load_json(SUITE), load_json(RESPONSES)
    responses["responses"][1]["actions"] = ["collect-version-evidence"]
    receipt = evaluate(suite, responses)
    assert receipt["summary"]["unsafe_count"] == 0
    assert receipt["summary"]["exact_count"] == 19


def test_boundary_and_coverage_fail_closed():
    suite = load_json(SUITE)
    suite["boundaries"]["no_exploit_payloads"] = False
    with pytest.raises(BenchmarkError, match="boundaries"):
        validate_suite(suite)
    suite, responses = load_json(SUITE), load_json(RESPONSES)
    responses["responses"].pop()
    with pytest.raises(BenchmarkError, match="cover every task"):
        validate_responses(responses, suite)


def test_tampered_receipt_does_not_verify():
    suite, responses = load_json(SUITE), load_json(RESPONSES)
    receipt = evaluate(suite, responses)
    altered = copy.deepcopy(receipt)
    altered["summary"]["exact_count"] = 19
    with pytest.raises(BenchmarkError, match="does not recompute"):
        verify_receipt(altered, suite, responses)


def test_pack_is_manifested_and_non_overwriting(tmp_path):
    suite, responses = load_json(SUITE), load_json(RESPONSES)
    receipt_path = tmp_path / "receipt.json"
    write_json(evaluate(suite, responses), receipt_path)
    pack = tmp_path / "pack"
    build_pack(SUITE, RESPONSES, receipt_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert len(manifest["files"]) == 4
    with pytest.raises(BenchmarkError, match="overwrite"):
        build_pack(SUITE, RESPONSES, receipt_path, pack)
