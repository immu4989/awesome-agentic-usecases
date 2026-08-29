import copy

import pytest

from aau_outcomes import OutcomesError, evaluate, verify_report


def _index():
    records = []
    kinds = [
        ("verified_fix", "case_count", 4),
        ("containment_drill", "event_count", 21),
        ("defender_campaign", "decision_count", 3),
        ("defense_benchmark", "task_count", 20),
    ]
    for kind, key, count in kinds:
        records.append({
            "artifact_id": f"reference-{kind}", "kind": kind, "artifact_version": "0.1",
            "artifact_sha256": "a" * 64, "evidence_level": "synthetic_reference",
            "producer": "AAU reference", "independent_reproduction": False,
            "measurements": {key: count}, "control_fingerprints": [kind],
        })
    return {
        "index_version": "aau-cyber-defense-evidence-index/0.1", "mesh_id": "reference", "record_count": 4,
        "records": records,
        "claim_boundary": {"aggregate_public_evidence_only": True, "no_raw_logs_or_personal_data": True, "no_organizational_comparison": True, "not_threat_intelligence_or_certification": True},
    }


def test_report_keeps_heterogeneous_counts_separate():
    report = evaluate(_index())
    assert report["summary"]["artifact_count"] == 4
    assert report["summary"]["observation_counts_by_kind"] == {
        "containment_drill": 21, "defender_campaign": 3, "defense_benchmark": 20, "verified_fix": 4,
    }
    assert report["summary"]["independent_reproduction_count"] == 0
    assert report["visible_gaps"] == ["No independently reproduced artifact has been contributed yet."]


def test_report_is_deterministic_and_verifiable():
    index = _index()
    report = evaluate(index)
    assert report == evaluate(index)
    verify_report(report, index)


def test_false_independence_fails_closed():
    index = _index()
    index["records"][0]["evidence_level"] = "independently_reproduced"
    with pytest.raises(OutcomesError, match="lacks reproduction flag"):
        evaluate(index)


def test_tampered_report_does_not_verify():
    index = _index()
    report = evaluate(index)
    altered = copy.deepcopy(report)
    altered["summary"]["artifact_count"] = 5
    with pytest.raises(OutcomesError, match="does not recompute"):
        verify_report(altered, index)
