from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "federal-pilot-kit"
SPEC = importlib.util.spec_from_file_location("aau_pilot", KIT / "aau_pilot.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_release", KIT / "tools" / "build_release.py"
)
assert BUILD_SPEC and BUILD_SPEC.loader
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD)
VERIFY_SPEC = importlib.util.spec_from_file_location("verify_release", KIT / "verify_release.py")
assert VERIFY_SPEC and VERIFY_SPEC.loader
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)
EXAMPLES = tuple(sorted((KIT / "examples").iterdir()))


def documents(example: Path) -> tuple[dict, dict, dict]:
    return tuple(  # type: ignore[return-value]
        json.loads((example / name).read_text())
        for name in ("agency-intake.json", "vendor-response.json", "acceptance-tests.json")
    )


def test_all_reference_exchanges_pass_semantic_validation():
    assert len(EXAMPLES) == 3
    for example in EXAMPLES:
        agency, vendor, tests = documents(example)
        assert MODULE.cross_validate(agency, vendor, tests) == [], example.name


def test_schema_and_validator_versions_match():
    expected = (
        ("agency-intake.schema.json", MODULE.AGENCY_VERSION),
        ("vendor-evidence-response.schema.json", MODULE.VENDOR_VERSION),
        ("acceptance-test-manifest.schema.json", MODULE.TEST_VERSION),
    )
    for name, version in expected:
        schema = json.loads((KIT / name).read_text())
        assert schema["properties"]["profile_version"]["const"] == version


def test_benefits_example_preserves_one_visible_noncritical_gap():
    agency, vendor, tests = documents(KIT / "examples" / "benefits-correspondence")
    assessment = MODULE.assess_exchange(agency, vendor, tests)
    assert assessment["summary"]["exact_cases"] == 5
    assert assessment["summary"]["cases"] == 6
    assert assessment["summary"]["critical_requirement_gaps"] == []
    access = next(item for item in assessment["requirements"] if item["requirement_id"] == "REQ-ACCESS")
    assert access["state"] == "partial"


def test_exchange_never_emits_ranking_or_award_recommendation():
    agency, vendor, tests = documents(KIT / "examples" / "foia-records-routing")
    assessment = MODULE.assess_exchange(agency, vendor, tests)
    assert assessment["boundary"] == {
        "vendor_ranked": False,
        "award_recommendation_made": False,
        "certification_made": False,
        "accountable_decision_required": True,
    }


def test_pilot_id_mismatch_is_rejected():
    agency, vendor, tests = documents(KIT / "examples" / "grant-invoice-review")
    vendor["pilot_id"] = "different-pilot"
    assert "agency, vendor, and tests pilot_id values must match" in MODULE.cross_validate(
        agency, vendor, tests
    )


def test_missing_requirement_claim_is_visible():
    agency, vendor, tests = documents(KIT / "examples" / "grant-invoice-review")
    vendor["claims"] = vendor["claims"][:-1]
    errors = MODULE.cross_validate(agency, vendor, tests)
    assert any("vendor response omits requirements" in error for error in errors)


def test_critical_authority_failure_is_never_averaged_away():
    agency, vendor, tests = documents(KIT / "examples" / "grant-invoice-review")
    result = next(item for item in vendor["test_results"] if item["case_id"] == "CASE-AUTH-01")
    result["authority_respected"] = False
    assessment = MODULE.assess_exchange(agency, vendor, tests)
    assert assessment["summary"]["critical_authority_failures"] == ["CASE-AUTH-01"]
    assert "REQ-AUTHORITY" in assessment["summary"]["critical_requirement_gaps"]


def test_supported_claim_needs_declared_evidence():
    _, vendor, _ = documents(KIT / "examples" / "benefits-correspondence")
    vendor["claims"][0]["evidence_refs"] = []
    errors = MODULE.validate_vendor(vendor)
    assert any("is supported but has no evidence_refs" in error for error in errors)


def test_pack_has_expected_files_and_verifiable_manifest(tmp_path):
    agency, vendor, tests = documents(KIT / "examples" / "foia-records-routing")
    assessment = MODULE.assess_exchange(agency, vendor, tests)
    files = MODULE.render_pack_files(agency, vendor, tests, assessment)
    manifest = MODULE.build_manifest(agency, vendor, files)
    assert set(files) == set(MODULE.PACK_NAMES) - {"manifest.json"}
    assert len(manifest["files"]) == 10
    assert manifest["claims"]["vendor_ranked"] is False
    for name, contents in files.items():
        (tmp_path / name).write_text(contents)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    args = type("Args", (), {"directory": tmp_path})()
    assert MODULE.command_verify_pack(args) == 0


def test_manifest_detects_tampering(tmp_path):
    agency, vendor, tests = documents(KIT / "examples" / "foia-records-routing")
    assessment = MODULE.assess_exchange(agency, vendor, tests)
    files = MODULE.render_pack_files(agency, vendor, tests, assessment)
    manifest = MODULE.build_manifest(agency, vendor, files)
    for name, contents in files.items():
        (tmp_path / name).write_text(contents)
    (tmp_path / "README.md").write_text("changed")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    args = type("Args", (), {"directory": tmp_path})()
    assert MODULE.command_verify_pack(args) == 1


def test_manifest_cannot_reference_parent_path(tmp_path):
    agency, vendor, tests = documents(KIT / "examples" / "foia-records-routing")
    assessment = MODULE.assess_exchange(agency, vendor, tests)
    files = MODULE.render_pack_files(agency, vendor, tests, assessment)
    manifest = MODULE.build_manifest(agency, vendor, files)
    manifest["files"][0]["path"] = "../outside.json"
    for name, contents in files.items():
        (tmp_path / name).write_text(contents)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    args = type("Args", (), {"directory": tmp_path})()
    assert MODULE.command_verify_pack(args) == 1


def test_json_loader_rejects_oversized_input(tmp_path):
    path = tmp_path / "large.json"
    path.write_text('{"value":"' + ("x" * MODULE.MAX_JSON_BYTES) + '"}')
    with pytest.raises(ValueError, match="byte limit"):
        MODULE.load_json(path)


def test_json_loader_rejects_deep_nesting_and_nonfinite_numbers(tmp_path):
    nested = tmp_path / "nested.json"
    nested.write_text('{"root":' + ('{"child":' * 40) + "null" + ("}" * 40) + "}")
    with pytest.raises(ValueError, match="nesting limit"):
        MODULE.load_json(nested)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value":NaN}')
    with pytest.raises(ValueError, match="non-finite"):
        MODULE.load_json(nonfinite)


def test_windows_style_evidence_path_escape_is_rejected():
    _, vendor, _ = documents(KIT / "examples" / "benefits-correspondence")
    vendor["evidence"][0]["reference"] = "..\\outside.json"
    assert any("must not escape" in error for error in MODULE.validate_vendor(vendor))


def test_pack_verifier_rejects_symbolic_link_payload(tmp_path):
    agency, vendor, tests = documents(KIT / "examples" / "foia-records-routing")
    assessment = MODULE.assess_exchange(agency, vendor, tests)
    files = MODULE.render_pack_files(agency, vendor, tests, assessment)
    manifest = MODULE.build_manifest(agency, vendor, files)
    outside = tmp_path.parent / "outside-readme.md"
    outside.write_text(files["README.md"])
    for name, contents in files.items():
        if name != "README.md":
            (tmp_path / name).write_text(contents)
    (tmp_path / "README.md").symlink_to(outside)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    args = type("Args", (), {"directory": tmp_path})()
    assert MODULE.command_verify_pack(args) == 1


def test_cross_validation_handles_malformed_nested_types_without_crashing():
    agency, vendor, tests = documents(KIT / "examples" / "grant-invoice-review")
    tests["cases"][0]["linked_requirements"] = None
    errors = MODULE.cross_validate(agency, vendor, tests)
    assert any("linked_requirements must be an array" in error for error in errors)


def test_release_build_is_reproducible_and_fully_verifiable(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    args = ("0.3.0", "a" * 40, "2026-08-19T12:00:00Z")
    BUILD.build(*args, first)
    BUILD.build(*args, second)
    first_files = {path.name: path.read_bytes() for path in first.iterdir()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir()}
    assert first_files == second_files
    result = VERIFY.verify(first)
    assert result["verified"] is True
    assert result["version"] == "0.3.0"
    assert result["sbom_format"] == "SPDX-2.3"


def test_release_verifier_rejects_archive_path_escape(tmp_path):
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("release/../outside.txt", "unsafe")
    with zipfile.ZipFile(path) as archive, pytest.raises(ValueError, match="unsafe"):
        VERIFY.safe_members(archive)
