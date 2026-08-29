import copy
import json
from pathlib import Path

import pytest

from aau_containment import ContainmentError, build_pack, evaluate_drill, load_json, validate_drill, verify_receipt, write_json


ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "reference-containment-drill.json"


def test_reference_drill_is_exact_and_bounded():
    receipt = evaluate_drill(load_json(EXAMPLE))
    summary = receipt["summary"]
    assert summary["event_count"] == 21
    assert summary["exact_outcome_rate"] == 1
    assert summary["exact_state_rate"] == 1
    assert summary["containment_breach_count"] == 0
    assert summary["post_control_block_count"] == 5
    assert summary["unauthorized_restart_block_count"] == 2
    assert summary["authorized_restart_count"] == 2
    assert summary["child_revocation_observed"] is True
    assert summary["queue_cancel_observed"] is True


def test_evaluation_is_deterministic_and_verifiable():
    drill = load_json(EXAMPLE)
    first = evaluate_drill(drill)
    second = evaluate_drill(drill)
    assert first == second
    verify_receipt(first, drill)


def test_safety_boundary_fails_closed():
    drill = load_json(EXAMPLE)
    drill["boundaries"]["no_live_target"] = False
    with pytest.raises(ContainmentError, match="boundaries"):
        validate_drill(drill)


def test_missing_control_shape_is_rejected():
    drill = load_json(EXAMPLE)
    for run in drill["runs"]:
        run["events"] = [event for event in run["events"] if event["kind"] != "evidence_mutation"]
    with pytest.raises(ContainmentError, match="missing required event kinds"):
        validate_drill(drill)


def test_an_incorrect_expectation_is_measured_not_hidden():
    drill = load_json(EXAMPLE)
    drill["runs"][0]["events"][3]["expected"]["outcome"] = "allow"
    receipt = evaluate_drill(drill)
    assert receipt["summary"]["exact_outcome_rate"] < 1


def test_tampering_breaks_verification():
    receipt = evaluate_drill(load_json(EXAMPLE))
    altered = copy.deepcopy(receipt)
    altered["summary"]["event_count"] = 22
    with pytest.raises(ContainmentError, match="digest mismatch"):
        verify_receipt(altered)


def test_write_and_pack_refuse_overwrite(tmp_path):
    drill = load_json(EXAMPLE)
    receipt = evaluate_drill(drill)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt, receipt_path)
    with pytest.raises(ContainmentError, match="overwrite"):
        write_json(receipt, receipt_path)
    pack = tmp_path / "pack"
    build_pack(EXAMPLE, receipt_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == {"README.md", "drill.json", "receipt.json"}
    with pytest.raises(ContainmentError, match="overwrite"):
        build_pack(EXAMPLE, receipt_path, pack)
