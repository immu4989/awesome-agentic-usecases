import copy
import json
from pathlib import Path

import pytest

from aau_defender_box import DefenderBoxError, assess_campaign, build_pack, load_json, validate_campaign, verify_assessment, write_json


ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "community-water-reference-campaign.json"


def test_reference_campaign_routes_all_decisions():
    result = assess_campaign(load_json(EXAMPLE))
    assert result["summary"] == {
        "asset_count": 3,
        "vulnerability_count": 2,
        "decision_count": 3,
        "known_exploited_decision_count": 2,
        "gate_pass_count": 3,
        "gate_fail_count": 0,
        "all_decisions_ready": True,
    }
    assert {row["recommended_route"] for row in result["decisions"]} == {"patch", "compensating_control", "investigate"}


def test_assessment_is_deterministic_and_verifiable():
    campaign = load_json(EXAMPLE)
    result = assess_campaign(campaign)
    assert result == assess_campaign(campaign)
    verify_assessment(result, campaign)


def test_wrong_route_is_visible_as_a_failed_gate():
    campaign = load_json(EXAMPLE)
    campaign["decisions"][0]["route"] = "compensating_control"
    result = assess_campaign(campaign)
    assert result["summary"]["gate_fail_count"] == 1


def test_missing_human_approval_fails_the_gate():
    campaign = load_json(EXAMPLE)
    campaign["decisions"][0]["human_approved"] = False
    assert assess_campaign(campaign)["summary"]["gate_fail_count"] == 1


def test_broken_continuity_fails_the_gate():
    campaign = load_json(EXAMPLE)
    campaign["continuity_tests"][0]["service_available"] = False
    assert assess_campaign(campaign)["summary"]["gate_fail_count"] == 1


def test_boundary_and_complete_coverage_fail_closed():
    campaign = load_json(EXAMPLE)
    campaign["boundaries"]["no_live_scanning"] = False
    with pytest.raises(DefenderBoxError, match="boundaries"):
        validate_campaign(campaign)
    campaign = load_json(EXAMPLE)
    campaign["decisions"].pop()
    with pytest.raises(DefenderBoxError, match="cover every affected asset"):
        validate_campaign(campaign)


def test_pack_is_verifiable_and_non_overwriting(tmp_path):
    campaign = load_json(EXAMPLE)
    result = assess_campaign(campaign)
    result_path = tmp_path / "assessment.json"
    write_json(result, result_path)
    pack = tmp_path / "pack"
    build_pack(EXAMPLE, result_path, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    assert len(manifest["files"]) == 3
    with pytest.raises(DefenderBoxError, match="overwrite"):
        build_pack(EXAMPLE, result_path, pack)


def test_tampered_assessment_does_not_verify():
    campaign = load_json(EXAMPLE)
    result = assess_campaign(campaign)
    altered = copy.deepcopy(result)
    altered["summary"]["gate_pass_count"] = 2
    with pytest.raises(DefenderBoxError, match="does not recompute"):
        verify_assessment(altered, campaign)
