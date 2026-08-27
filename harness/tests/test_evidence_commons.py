import json
from pathlib import Path

import pytest

from aau_harness.catalog_cli import main as aau_main
from aau_harness.evidence_commons import (
    OBSERVATION_BOUNDARY,
    PRIVACY_CONTRACT,
    REPRODUCTION_BOUNDARY,
    EvidenceCommonsError,
    build_pack,
    comparison,
    validate_capsule,
    validate_public_value_record,
    validate_reproduction_record,
    verify_pack,
)


ROOT = Path(__file__).resolve().parents[2]
CAPSULE_ROOT = ROOT / "evidence-commons" / "capsules"


def load_capsule(name="foia-routing-impact-pilot"):
    path = CAPSULE_ROOT / f"{name}.json"
    return path, json.loads(path.read_text())


def test_reference_capsules_are_artifact_bound_and_keep_gaps_visible():
    paths = sorted(CAPSULE_ROOT.glob("*.json"))
    assert len(paths) == 3
    for path in paths:
        capsule = validate_capsule(json.loads(path.read_text()), ROOT)
        result = comparison(capsule)
        assert result["derived_status"] == "partner_sought"
        assert result["agent_measurement"]["observation_count"] == 24
        assert result["human_comparator"] is None
        assert result["public_value_observed"] is False
        assert result["reproduction"] is None
        assert result["missing_evidence"][0] == (
            "fresh hash-bound agent rerun on the reviewed suite"
        )
        assert result["claims"] == {
            "causal_impact_proved": False,
            "institutional_review_verified_by_aau": False,
            "identity_verified_by_aau": False,
            "certification_proved": False,
            "government_endorsement_proved": False,
            "deployment_authorized": False,
        }


def test_pack_is_portable_deterministic_non_overwriting_and_tamper_evident(tmp_path):
    capsule_path, capsule = load_capsule()
    output = tmp_path / "impact-pack"
    built = build_pack(capsule_path, ROOT, output)
    checked = verify_pack(output)
    assert built["capsule_id"] == capsule["capsule_id"]
    assert checked["ready"] is True
    assert (output / "comparison.json").is_file()
    assert len(list((output / "artifacts").iterdir())) == 2
    with pytest.raises(EvidenceCommonsError, match="refusing to overwrite"):
        build_pack(capsule_path, ROOT, output)

    artifact = next((output / "artifacts").iterdir())
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(EvidenceCommonsError, match="manifest mismatch"):
        verify_pack(output)


def test_status_inflation_path_traversal_and_private_claims_fail_closed():
    _, capsule = load_capsule()
    capsule["status"] = "aggregate_published"
    with pytest.raises(EvidenceCommonsError, match="inflated or stale"):
        validate_capsule(capsule, ROOT, verify_artifacts=False)

    _, capsule = load_capsule()
    capsule["artifacts"]["suite"]["path"] = "../private.json"
    with pytest.raises(EvidenceCommonsError, match="traverse parents"):
        validate_capsule(capsule, ROOT, verify_artifacts=False)

    _, capsule = load_capsule()
    capsule["privacy"]["participant_level_data_included"] = True
    with pytest.raises(EvidenceCommonsError, match="aggregate-only"):
        validate_capsule(capsule, ROOT, verify_artifacts=False)

    _, capsule = load_capsule()
    capsule["artifacts"]["reproduction"] = {
        "artifact_id": "premature-reproduction",
        "kind": "aau_independent_reproduction",
        "path": "evidence-commons/premature-reproduction.json",
        "sha256": "a" * 64,
        "classification": "aggregate_public",
        "organization_id": "example-independent-lab",
        "outcome": "reproduced",
        "independence_attested": True,
        "independence_verified_by_aau": False,
    }
    with pytest.raises(EvidenceCommonsError, match="complete preceding evidence chain"):
        validate_capsule(capsule, ROOT, verify_artifacts=False)


def test_cli_works_outside_repository(tmp_path, monkeypatch, capsys):
    capsule_path, _ = load_capsule("grant-obligation-impact-pilot")
    monkeypatch.chdir(tmp_path)
    assert (
        aau_main(
            [
                "evidence",
                "compare",
                str(capsule_path),
                "--root",
                str(ROOT),
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["capsule_id"] == "grant-obligation-impact-pilot"
    assert result["agent_measurement"]["value"] == 0.75
    assert result["next_evidence"] == "fresh hash-bound agent rerun on the reviewed suite"


def test_public_value_record_rejects_causal_label_inflation():
    record = {
        "observation_version": "aau-public-value-observation/1.0",
        "observation_id": "foia-observation-01",
        "capsule_id": "foia-routing-impact-pilot",
        "method": "descriptive_before_after",
        "metric_results": [
            {
                "metric_id": "clarification-burden",
                "baseline_value": 1.4,
                "observed_value": 1.1,
                "unit": "contacts per request",
                "direction": "decrease",
                "window": "Four representative weeks",
                "affected_group": "FOIA requesters",
                "uncertainty": "Descriptive aggregate only",
                "limitation": "No concurrent control group",
            }
        ],
        "causal_claim": False,
        "decision": {
            "accountable_role": "Authorized agency FOIA official",
            "outcome": "not_decided",
            "conditions": ["Complete independent review"],
        },
        "privacy": PRIVACY_CONTRACT,
        "limitations": ["The observation is descriptive and cannot establish causality."],
        "boundary": OBSERVATION_BOUNDARY,
    }
    assert validate_public_value_record(record)["causal_claim"] is False
    record["causal_claim"] = True
    with pytest.raises(EvidenceCommonsError, match="causal claim is inconsistent"):
        validate_public_value_record(record)


def test_reproduction_record_checks_tolerance_and_attested_independence():
    record = {
        "reproduction_version": "aau-impact-reproduction/1.0",
        "reproduction_id": "foia-reproduction-01",
        "source_capsule_id": "foia-routing-impact-pilot",
        "source_capsule_version": "aau-impact-capsule/1.0",
        "source_artifacts": [{"artifact_id": "foia-suite", "sha256": "a" * 64}],
        "organization_id": "example-independent-lab",
        "independence_attested": True,
        "scope": "Rerun the public synthetic suite without modifying expected outcomes.",
        "environment": "Python 3.12 on a clean Linux runner.",
        "outcome": "reproduced",
        "metric_checks": [
            {
                "name": "service_exact",
                "source_value": 1.0,
                "reproduced_value": 0.99,
                "tolerance": 0.02,
                "within_tolerance": True,
            }
        ],
        "divergences": [],
        "limitations": ["Identity and independence are attested, not verified by AAU."],
        "privacy": PRIVACY_CONTRACT,
        "boundary": REPRODUCTION_BOUNDARY,
    }
    assert validate_reproduction_record(record)["outcome"] == "reproduced"
    record["metric_checks"][0]["within_tolerance"] = False
    with pytest.raises(EvidenceCommonsError, match="tolerance result is inconsistent"):
        validate_reproduction_record(record)
