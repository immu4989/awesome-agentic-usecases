import copy
import json
from pathlib import Path

import pytest

from aau_incident import (
    IncidentError,
    build_pack,
    evaluate_incident,
    load_json,
    scan_public_text,
    validate_incident,
    verify_receipt,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
INCIDENT_PATH = ROOT / "examples" / "public-agent-boundary-incident.json"


@pytest.fixture
def incident():
    return load_json(INCIDENT_PATH)


def test_reference_incident_is_safe_and_post_fix_exact(incident):
    validate_incident(incident)
    receipt = evaluate_incident(incident)
    assert receipt["summary"]["regression_count"] == 6
    assert receipt["summary"]["unsafe_allow_before_count"] == 5
    assert receipt["summary"]["post_fix_exact_rate"] == 1.0
    assert receipt["summary"]["legitimate_allow_preservation"] == 1.0
    verify_receipt(receipt, incident)


def test_evaluation_is_deterministic(incident):
    assert evaluate_incident(incident) == evaluate_incident(copy.deepcopy(incident))


def test_public_scan_returns_labels_not_values():
    findings = scan_public_text({"value": "Bearer abcdefghijklmnopqrstuvwxyz"})
    assert findings == ["bearer_token"]
    assert "abcdefghijklmnopqrstuvwxyz" not in repr(findings)


def test_sensitive_or_live_claims_fail_closed(incident):
    incident["classification"]["contains_real_credentials"] = True
    with pytest.raises(IncidentError, match="flags must be false"):
        validate_incident(incident)


def test_unknown_source_reference_is_rejected(incident):
    incident["timeline"][0]["source_refs"] = ["missing-source"]
    with pytest.raises(IncidentError, match="unknown source"):
        validate_incident(incident)


def test_receipt_and_pack_are_non_overwriting(tmp_path, incident):
    receipt = evaluate_incident(incident)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt, receipt_path)
    with pytest.raises(IncidentError, match="overwrite"):
        write_json(receipt, receipt_path)
    pack = tmp_path / "pack"
    build_pack(INCIDENT_PATH, receipt_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == {
        "README.md",
        "incident.json",
        "receipt.json",
    }


def test_tampering_is_detected(incident):
    receipt = evaluate_incident(incident)
    receipt["results"][0]["post_fix_outcome"] = "allow"
    with pytest.raises(IncidentError, match="digest mismatch"):
        verify_receipt(receipt)
