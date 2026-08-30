from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("aau_assurance", ROOT / "aau_assurance.py")
assert spec and spec.loader
assurance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assurance)


@pytest.fixture
def envelope() -> dict:
    return assurance.load_json(ROOT / "examples/synthetic-assurance-envelope.json")


@pytest.fixture
def suite() -> dict:
    return assurance.load_json(ROOT / "examples/mcp-a2a-conformance-suite.json")


def _resign(envelope: dict, token: str, **changed_claims) -> str:
    encoded_header, encoded_claims, _ = token.split(".")
    claims = json.loads(assurance._b64decode(encoded_claims))
    claims.update(changed_claims)
    encoded_claims = assurance._b64url(assurance.canonical_bytes(claims))
    signing_input = f"{encoded_header}.{encoded_claims}"
    secret = envelope["subject"]["identity_verifier"]["test_only_shared_secret"].encode()
    signature = assurance.hmac.new(secret, signing_input.encode(), assurance.hashlib.sha256).digest()
    return f"{signing_input}.{assurance._b64url(signature)}"


def test_reference_suite_is_exact_and_preserves_clean_twins(envelope, suite):
    receipt = assurance.evaluate_suite(envelope, suite)
    assert receipt["summary"] == {
        "case_count": 18,
        "exact_count": 18,
        "exact_rate": 1.0,
        "clean_twin_count": 2,
        "clean_twin_allow_count": 2,
        "identity_fixture_verified_count": 15,
        "production_identity_verified_count": 0,
    }


def test_synthetic_token_is_signature_and_claim_bound(envelope):
    token = assurance.mint_test_token(
        envelope,
        jti="test-token-001",
        issued_at="2026-08-30T12:05:00Z",
        expires_at="2026-08-30T12:50:00Z",
    )
    claims, reasons = assurance.verify_test_token(envelope, token, "2026-08-30T12:20:00Z")
    assert reasons == []
    assert claims["sub"] == envelope["subject"]["workload_identity"]["identifier"]
    assert claims["authority_ref"] == envelope["authority"]["lease_id"]


def test_token_signature_tamper_fails(envelope):
    token = assurance.mint_test_token(
        envelope,
        jti="test-token-002",
        issued_at="2026-08-30T12:05:00Z",
        expires_at="2026-08-30T12:50:00Z",
    )
    replacement = "A" if token[-1] != "A" else "B"
    _, reasons = assurance.verify_test_token(envelope, token[:-1] + replacement, "2026-08-30T12:20:00Z")
    assert "IDENTITY_SIGNATURE_INVALID" in reasons


def test_token_rejects_non_base64url_signature(envelope):
    token = assurance.mint_test_token(
        envelope,
        jti="test-token-003",
        issued_at="2026-08-30T12:05:00Z",
        expires_at="2026-08-30T12:50:00Z",
    )
    _, reasons = assurance.verify_test_token(envelope, token + "$", "2026-08-30T12:20:00Z")
    assert reasons == ["IDENTITY_TOKEN_MALFORMED"]


def test_token_rejects_even_signed_unexpected_claims(envelope):
    token = assurance.mint_test_token(
        envelope,
        jti="test-token-004",
        issued_at="2026-08-30T12:05:00Z",
        expires_at="2026-08-30T12:50:00Z",
    )
    changed = _resign(envelope, token, unbound_role="administrator")
    _, reasons = assurance.verify_test_token(envelope, changed, "2026-08-30T12:20:00Z")
    assert "IDENTITY_TOKEN_CLAIMS_INVALID" in reasons


def test_production_classification_is_rejected(envelope):
    changed = copy.deepcopy(envelope)
    changed["classification"]["live_system"] = True
    with pytest.raises(assurance.AssuranceError, match="synthetic"):
        assurance.validate_envelope(changed)


def test_boolean_policy_epoch_and_unhashable_peer_fail_cleanly(envelope):
    changed = copy.deepcopy(envelope)
    changed["authority"]["policy_epoch"] = True
    with pytest.raises(assurance.AssuranceError, match="positive integer"):
        assurance.validate_envelope(changed)
    changed = copy.deepcopy(envelope)
    changed["authority"]["allowed_peers"] = [{"agent": "confusable"}]
    with pytest.raises(assurance.AssuranceError, match="allowed peer"):
        assurance.validate_envelope(changed)


def test_suite_binding_fails_closed(envelope, suite):
    changed = copy.deepcopy(suite)
    changed["envelope_sha256"] = "a" * 64
    with pytest.raises(assurance.AssuranceError, match="not bound"):
        assurance.evaluate_suite(envelope, changed)


def test_clean_twin_cannot_precommit_a_block(suite):
    changed = copy.deepcopy(suite)
    changed["cases"][0]["expected"] = {
        "outcome": "block",
        "reason_codes": ["ACTION_OUTSIDE_AUTHORITY"],
    }
    with pytest.raises(assurance.AssuranceError, match="clean twins"):
        assurance.validate_suite(changed)


def test_revocation_blocks_even_a_clean_twin(envelope, suite):
    changed = copy.deepcopy(envelope)
    changed["authority"]["revocation_state"] = "revoked"
    changed_suite = copy.deepcopy(suite)
    changed_suite["envelope_sha256"] = assurance.digest(changed)
    result = assurance.evaluate_record(changed, changed_suite["cases"][0]["record"])
    assert result["outcome"] == "block"
    assert "AUTHORITY_REVOKED" in result["reason_codes"]


def test_monitor_loss_plus_operator_mismatch_blocks_instead_of_pausing(envelope, suite):
    record = copy.deepcopy(suite["cases"][0]["record"])
    record["context"]["monitoring_active"] = False
    record["context"]["token"] = _resign(
        envelope,
        record["context"]["token"],
        operator_ref="operator:unbound-fixture",
    )
    result = assurance.evaluate_record(envelope, record)
    assert result["outcome"] == "block"
    assert result["reason_codes"] == ["MONITORING_UNAVAILABLE", "OPERATOR_BINDING_MISMATCH"]


def test_record_rejects_ignored_top_level_fields(envelope, suite):
    record = copy.deepcopy(suite["cases"][0]["record"])
    record["unbound_authorization"] = "permit-all"
    with pytest.raises(assurance.AssuranceError, match="unexpected fields"):
        assurance.evaluate_record(envelope, record)


def test_receipt_tamper_is_rejected(envelope, suite):
    receipt = assurance.evaluate_suite(envelope, suite)
    changed = copy.deepcopy(receipt)
    changed["summary"]["exact_count"] -= 1
    with pytest.raises(assurance.AssuranceError, match="recomputation"):
        assurance.verify_receipt(changed, envelope, suite)


def test_otel_export_is_metadata_only(envelope, suite):
    receipt = assurance.evaluate_suite(envelope, suite)
    exported = assurance.export_otel(receipt)
    rendered = json.dumps(exported)
    assert exported["privacy"] == {
        "prompts_included": False,
        "credentials_included": False,
        "personal_data_included": False,
    }
    assert "eyJhbGci" not in rendered
    assert len(exported["events"]) == 18


def test_in_toto_statement_binds_exact_receipt(envelope, suite):
    receipt = assurance.evaluate_suite(envelope, suite)
    statement = assurance.in_toto_statement(receipt)
    assert statement["subject"][0]["digest"]["sha256"] == assurance.digest_bytes(
        assurance.canonical_bytes(receipt)
    )
    assert statement["predicate"]["signature_status"] == "unsigned_local_statement"


def test_pack_round_trip_and_non_overwrite(tmp_path, envelope, suite):
    envelope_path = ROOT / "examples/synthetic-assurance-envelope.json"
    suite_path = ROOT / "examples/mcp-a2a-conformance-suite.json"
    pack = tmp_path / "pack"
    assurance.build_pack(envelope_path, suite_path, pack)
    result = assurance.verify_pack(pack)
    assert result["status"] == "verified_synthetic_conformance"
    assert result["exact_count"] == 18
    with pytest.raises(assurance.AssuranceError, match="overwrite"):
        assurance.build_pack(envelope_path, suite_path, pack)


def test_pack_rejects_unmanifested_file(tmp_path):
    pack = tmp_path / "pack"
    assurance.build_pack(
        ROOT / "examples/synthetic-assurance-envelope.json",
        ROOT / "examples/mcp-a2a-conformance-suite.json",
        pack,
    )
    (pack / "extra.json").write_text("{}")
    with pytest.raises(assurance.AssuranceError, match="file set"):
        assurance.verify_pack(pack)


def test_pack_rejects_symlink(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    pack = tmp_path / "pack"
    assurance.build_pack(
        ROOT / "examples/synthetic-assurance-envelope.json",
        ROOT / "examples/mcp-a2a-conformance-suite.json",
        pack,
    )
    (pack / "README.md").unlink()
    os.symlink(pack / "suite.json", pack / "README.md")
    with pytest.raises(assurance.AssuranceError, match="regular file"):
        assurance.verify_pack(pack)
