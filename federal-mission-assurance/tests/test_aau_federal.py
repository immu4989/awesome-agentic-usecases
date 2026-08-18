from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = ROOT / "federal-mission-assurance" / "aau_federal.py"
SPEC = importlib.util.spec_from_file_location("aau_federal", TOOL_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EXAMPLE = ROOT / "federal-mission-assurance" / "example-acquisition-profile.json"


def profile() -> dict:
    return json.loads(EXAMPLE.read_text())


def test_worked_profile_passes_semantic_validation():
    assert MODULE.validate_profile(profile()) == []


def test_missing_cease_use_trigger_is_visible():
    value = profile()
    value["monitoring"]["cease_use_trigger"] = ""
    assert "monitoring.cease_use_trigger is required" in MODULE.validate_profile(value)


def test_evidenced_control_needs_a_reference():
    value = profile()
    value["controls"][1]["evidence_refs"] = []
    errors = MODULE.validate_profile(value)
    assert any("is evidenced but declares no evidence_refs" in error for error in errors)


def test_control_evidence_must_be_declared_or_pack_generated():
    value = profile()
    value["controls"][1]["evidence_refs"] = ["untracked-claim.txt"]
    errors = MODULE.validate_profile(value)
    assert any("references undeclared evidence" in error for error in errors)


def test_malformed_section_is_reported_without_crashing():
    value = profile()
    value["data"] = "public"
    errors = MODULE.validate_profile(value)
    assert "data must be an object" in errors
    assert "data.classification has an invalid value" in errors


def test_pack_has_expected_files_and_verifiable_manifest(tmp_path):
    value = profile()
    files = MODULE.render_files(value)
    manifest = MODULE.build_manifest(value, files)
    assert set(files) == set(MODULE.PACK_NAMES) - {"manifest.json"}
    assert len(manifest["files"]) == 11
    assert manifest["claims"]["compliance_proved"] is False
    for name, contents in files.items():
        (tmp_path / name).write_text(contents)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    args = type("Args", (), {"directory": tmp_path})()
    assert MODULE.command_verify_pack(args) == 0


def test_manifest_detects_tampering(tmp_path):
    value = profile()
    files = MODULE.render_files(value)
    manifest = MODULE.build_manifest(value, files)
    for name, contents in files.items():
        (tmp_path / name).write_text(contents)
    (tmp_path / "README.md").write_text("changed")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    args = type("Args", (), {"directory": tmp_path})()
    assert MODULE.command_verify_pack(args) == 1


def test_manifest_cannot_read_outside_pack(tmp_path):
    value = profile()
    files = MODULE.render_files(value)
    manifest = MODULE.build_manifest(value, files)
    manifest["files"][0]["path"] = "../outside.txt"
    for name, contents in files.items():
        (tmp_path / name).write_text(contents)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    args = type("Args", (), {"directory": tmp_path})()
    assert MODULE.command_verify_pack(args) == 1
