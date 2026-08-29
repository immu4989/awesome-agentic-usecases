import json
from pathlib import Path

import pytest

from aau_defender import (
    DefenderError,
    assess_kit,
    build_pack,
    load_json,
    validate_kit,
    verify_assessment,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
KIT_PATHS = sorted((ROOT / "kits").glob("*.json"))


@pytest.mark.parametrize("path", KIT_PATHS, ids=lambda path: path.stem)
def test_all_five_kits_validate_and_expose_gaps_without_a_score(path):
    kit = load_json(path)
    validate_kit(kit)
    assessment = assess_kit(kit)
    assert assessment["exercise_count"] == 3
    assert assessment["control_states"]["gap"]
    assert assessment["control_states"]["planned"]
    assert "score" not in json.dumps(assessment).lower()
    verify_assessment(assessment, kit)


def test_reference_set_has_five_distinct_essential_service_profiles():
    assert len(KIT_PATHS) == 5
    kits = [load_json(path) for path in KIT_PATHS]
    assert len({kit["kit_id"] for kit in kits}) == 5
    assert len({kit["sector"] for kit in kits}) == 5


def test_human_authority_and_no_live_boundary_fail_closed():
    kit = load_json(KIT_PATHS[0])
    kit["agent_boundary"]["restart_authority"] = "agent:self"
    with pytest.raises(DefenderError, match="human role"):
        validate_kit(kit)
    kit = load_json(KIT_PATHS[0])
    kit["public_boundary"]["no_live_connections"] = False
    with pytest.raises(DefenderError, match="safety boundaries"):
        validate_kit(kit)


def test_assessment_and_pack_are_non_overwriting(tmp_path):
    kit_path = KIT_PATHS[0]
    assessment = assess_kit(load_json(kit_path))
    assessment_path = tmp_path / "assessment.json"
    write_json(assessment, assessment_path)
    with pytest.raises(DefenderError, match="overwrite"):
        write_json(assessment, assessment_path)
    pack = tmp_path / "pack"
    build_pack(kit_path, assessment_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == {
        "README.md",
        "assessment.json",
        "kit.json",
    }
