import copy
import json
from pathlib import Path

import pytest

from aau_fix import (
    FixError,
    build_openvex,
    build_pack,
    build_sarif,
    evaluate_contract,
    load_json,
    validate_contract,
    verify_receipt,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "examples").glob("*.json"))


@pytest.mark.parametrize("path", EXAMPLES)
def test_reference_fix_contracts_are_exact_and_safe(path):
    contract = load_json(path)
    validate_contract(contract)
    receipt = evaluate_contract(contract)
    assert receipt["evidence_level"] == "reference_exact"
    assert receipt["summary"]["exact_phase_rate"] == 1.0
    assert receipt["summary"]["after_pass_rate"] == 1.0
    assert receipt["summary"]["vulnerability_closed_rate"] == 1.0
    assert receipt["summary"]["legitimate_preservation_rate"] == 1.0
    assert receipt["summary"]["continuity_preservation_rate"] == 1.0
    assert receipt["summary"]["rollback_readiness_rate"] == 1.0
    assert receipt["summary"]["unsafe_after_count"] == 0
    verify_receipt(receipt, contract)


def test_compensating_control_requires_its_own_case():
    contract = load_json(ROOT / "examples/essential-service-compensating-control.json")
    contract["cases"] = [case for case in contract["cases"] if case["case_kind"] != "compensating_control"]
    with pytest.raises(FixError, match="requires a compensating_control case"):
        validate_contract(contract)


def test_public_safety_boundary_cannot_be_weakened():
    contract = load_json(ROOT / "examples/ai-generated-dependency-upgrade.json")
    contract["boundaries"]["no_live_target"] = False
    with pytest.raises(FixError, match="safety boundaries"):
        validate_contract(contract)


def test_failed_after_state_remains_visible():
    contract = load_json(ROOT / "examples/least-privilege-configuration.json")
    contract["cases"][0]["after"]["vulnerable"] = True
    receipt = evaluate_contract(contract)
    assert receipt["evidence_level"] == "designed"
    assert receipt["summary"]["unsafe_after_count"] == 1


def test_receipt_tampering_is_detected():
    contract = load_json(ROOT / "examples/ai-generated-dependency-upgrade.json")
    receipt = evaluate_contract(contract)
    receipt["cases"][0]["after"] = "fail"
    with pytest.raises(FixError, match="digest mismatch"):
        verify_receipt(receipt)


def test_outputs_and_packs_never_overwrite(tmp_path):
    path = ROOT / "examples/ai-generated-dependency-upgrade.json"
    contract = load_json(path)
    receipt = evaluate_contract(contract)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt, receipt_path)
    with pytest.raises(FixError, match="overwrite"):
        write_json(receipt, receipt_path)
    pack = tmp_path / "pack"
    build_pack(path, receipt_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == {
        "README.md",
        "fix-contract.json",
        "fix-receipt.json",
        "openvex.json",
        "results.sarif.json",
    }
    with pytest.raises(FixError, match="overwrite"):
        build_pack(path, receipt_path, pack)


def test_exports_are_machine_readable_and_non_certifying():
    contract = load_json(ROOT / "examples/least-privilege-configuration.json")
    receipt = evaluate_contract(copy.deepcopy(contract))
    vex = build_openvex(contract, receipt)
    sarif = build_sarif(contract, receipt)
    assert vex["@context"] == "https://openvex.dev/ns/v0.2.0"
    assert "not a production" in vex["statements"][0]["status_notes"]
    assert sarif["version"] == "2.1.0"
    assert all(result["properties"]["syntheticReference"] for result in sarif["runs"][0]["results"])
