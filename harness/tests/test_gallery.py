import json
from pathlib import Path

import pytest

from aau_harness.gallery import (
    GALLERY_VERSION,
    GalleryError,
    build_gallery,
    evaluate_entry,
    validate_entry_shape,
)


ROOT = Path(__file__).resolve().parents[2]


def test_reference_gallery_has_contract_diversity_and_derived_levels():
    gallery = build_gallery(ROOT)
    assert gallery["version"] == GALLERY_VERSION
    assert len(gallery["entries"]) == 3
    assert {item["contract"]["name"] for item in gallery["entries"]} == {
        "Decision Gate",
        "Rights Continuity",
        "Critical Event Fan-Out",
    }
    assert all(item["trust"]["level"] in gallery["trust_model"]["levels"] for item in gallery["entries"])
    assert all(item["trust"]["score"]["total"] == 14 for item in gallery["entries"])


def test_entry_cannot_self_select_a_trust_badge():
    entry = json.loads((ROOT / "gallery" / "entries" / "batch-disposition-reference.json").read_text())
    entry["trust"] = {"level": "Verified"}
    with pytest.raises(GalleryError, match="unsupported fields"):
        validate_entry_shape(entry)


def test_contributor_cannot_claim_maintainer_reference_exception():
    entry = json.loads((ROOT / "gallery" / "gallery-entry.example.json").read_text())
    entry["origin"] = "maintainer-reference"
    with pytest.raises(GalleryError, match="forge-adaptation"):
        validate_entry_shape(entry)


def test_new_adaptation_must_commit_forge_provenance():
    entry = json.loads((ROOT / "gallery" / "gallery-entry.example.json").read_text())
    entry["lab_path"] = "pipeline-safety/incident-notification-coordinator"
    evaluated = evaluate_entry(ROOT, entry)
    provenance = next(check for check in evaluated["trust"]["checks"] if check["check"] == "Forge provenance")
    assert provenance["passed"] is False
    assert evaluated["trust"]["level"] == "Draft"


def test_bad_entry_shape_is_rejected():
    with pytest.raises(GalleryError, match="missing"):
        validate_entry_shape({"schema_version": "self-certified/9"})
