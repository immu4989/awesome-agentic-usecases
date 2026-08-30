from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1]
REPO = MODULE.parent
spec = importlib.util.spec_from_file_location("aau_tevva", MODULE / "aau_tevva.py")
assert spec and spec.loader
tevva = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tevva)


@pytest.fixture
def profile() -> dict:
    return tevva.load_json(MODULE / "examples/agent-assurance-tevva.json")


def test_reference_profile_uses_exact_four_stages(profile):
    tevva.validate_profile(profile)
    assert all(stage in profile for stage in tevva.STAGES)
    assert len(profile["define_and_construct"]["blocks"]) == 6


def test_assessment_verifies_artifacts_and_keeps_gaps_visible(profile):
    assessment = tevva.assess(profile, REPO)
    assert assessment["status"] == "structurally_complete_with_visible_gaps"
    assert assessment["visible_gaps"] == [
        "planned_events_not_observed",
        "no_held_out_material",
        "no_observed_independent_reproduction",
    ]
    assert len(assessment["artifacts"]) == 7
    assert all(item["bytes_verified"] for item in assessment["artifacts"])


def test_unknown_block_reference_fails(profile):
    changed = copy.deepcopy(profile)
    changed["apply_and_measure"]["events"][0]["block_ids"].append("missing-block")
    with pytest.raises(tevva.TevvError, match="unknown Block"):
        tevva.validate_profile(changed)


def test_observed_event_requires_artifact(profile):
    changed = copy.deepcopy(profile)
    changed["apply_and_measure"]["events"][0]["evidence_artifact_ids"] = []
    with pytest.raises(tevva.TevvError, match="observed events"):
        tevva.validate_profile(changed)


def test_live_execution_tool_is_rejected(profile):
    changed = copy.deepcopy(profile)
    changed["apply_and_measure"]["toolbox"][0]["executes_live_system"] = True
    with pytest.raises(tevva.TevvError, match="live execution"):
        tevva.validate_profile(changed)


def test_artifact_hash_drift_fails(profile):
    changed = copy.deepcopy(profile)
    changed["evidence_artifacts"][0]["sha256"] = "a" * 64
    with pytest.raises(tevva.TevvError, match="digest differs"):
        tevva.assess(changed, REPO)


def test_artifact_digest_and_paths_are_unambiguous(profile):
    changed = copy.deepcopy(profile)
    changed["evidence_artifacts"][0]["sha256"] = "z" * 64
    with pytest.raises(tevva.TevvError, match="SHA-256"):
        tevva.validate_profile(changed)
    changed = copy.deepcopy(profile)
    changed["evidence_artifacts"][1]["path"] = changed["evidence_artifacts"][0]["path"]
    with pytest.raises(tevva.TevvError, match="paths must be unique"):
        tevva.validate_profile(changed)


def test_independent_reproduction_is_explicit_not_name_derived(profile):
    changed = copy.deepcopy(profile)
    event = changed["apply_and_measure"]["events"][2]
    event["id"] = "outside_adapter_run"
    event["status"] = "observed"
    event["evidence_artifact_ids"] = ["protocol_receipt"]
    assessment = tevva.assess(changed, REPO)
    assert "no_observed_independent_reproduction" not in assessment["visible_gaps"]
    assert "planned_events_not_observed" not in assessment["visible_gaps"]


def test_boolean_repeat_count_is_rejected(profile):
    changed = copy.deepcopy(profile)
    changed["apply_and_measure"]["protocol"]["repeats"] = True
    with pytest.raises(tevva.TevvError, match="repeats"):
        tevva.validate_profile(changed)


def test_pack_round_trip_and_non_overwrite(tmp_path, profile):
    pack = tmp_path / "tevva-pack"
    result = tevva.build_pack(MODULE / "examples/agent-assurance-tevva.json", REPO, pack)
    assert result["artifact_count"] == 7
    verified = tevva.verify_pack(pack)
    assert verified["status"] == "verified_experimental_profile"
    assert verified["not_nist_conformance"] is True
    with pytest.raises(tevva.TevvError, match="overwrite"):
        tevva.build_pack(MODULE / "examples/agent-assurance-tevva.json", REPO, pack)


def test_pack_rejects_artifact_tamper(tmp_path):
    pack = tmp_path / "tevva-pack"
    tevva.build_pack(MODULE / "examples/agent-assurance-tevva.json", REPO, pack)
    receipt = pack / "artifacts/portable-agent-assurance/examples/reference-pack/receipt.json"
    receipt.write_text(receipt.read_text() + "\n")
    with pytest.raises(tevva.TevvError, match="manifest binding"):
        tevva.verify_pack(pack)


def test_pack_rejects_unmanifested_file(tmp_path):
    pack = tmp_path / "tevva-pack"
    tevva.build_pack(MODULE / "examples/agent-assurance-tevva.json", REPO, pack)
    (pack / "unexpected.txt").write_text("unexpected")
    with pytest.raises(tevva.TevvError, match="file set"):
        tevva.verify_pack(pack)


def test_pack_recomputes_assessment_even_after_manifest_is_updated(tmp_path):
    pack = tmp_path / "tevva-pack"
    tevva.build_pack(MODULE / "examples/agent-assurance-tevva.json", REPO, pack)
    assessment_path = pack / "assessment.json"
    assessment = tevva.load_json(assessment_path)
    assessment["status"] = "structurally_complete"
    tevva._write_json(assessment_path, assessment)
    manifest_path = pack / "manifest.json"
    manifest = tevva.load_json(manifest_path)
    data = assessment_path.read_bytes()
    for row in manifest["files"]:
        if row["path"] == "assessment.json":
            row.update({"sha256": tevva.digest_bytes(data), "size": len(data)})
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with pytest.raises(tevva.TevvError, match="deterministic recomputation"):
        tevva.verify_pack(pack)


def test_pack_rejects_symlink(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    pack = tmp_path / "tevva-pack"
    tevva.build_pack(MODULE / "examples/agent-assurance-tevva.json", REPO, pack)
    target = pack / "README.md"
    target.unlink()
    os.symlink(pack / "profile.json", target)
    with pytest.raises(tevva.TevvError, match="file set|symlink"):
        tevva.verify_pack(pack)
