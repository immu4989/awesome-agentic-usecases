"""Fail CI when the public Gallery, trust derivation, or contribution route drifts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.gallery import GALLERY_VERSION, LEVELS, build_gallery  # noqa: E402


def main() -> None:
    built = build_gallery(ROOT)
    published = json.loads((ROOT / "docs" / "gallery-data.json").read_text())
    assert built == published, "docs/gallery-data.json is stale; run docs/make_gallery_data.py"
    assert built["version"] == GALLERY_VERSION
    assert tuple(built["trust_model"]["levels"]) == LEVELS
    assert len(built["entries"]) >= 3, "Gallery needs three contract-diverse reference entries"
    assert len({entry["contract"]["name"] for entry in built["entries"]}) >= 3
    for entry in built["entries"]:
        score = entry["trust"]["score"]
        assert score["passed"] <= score["total"]
        assert entry["trust"]["level"] in LEVELS
        assert entry["contributor"]["profile_url"].startswith("https://github.com/")
        assert (ROOT / entry["lab_path"]).is_dir()
        if entry["origin"] == "forge-adaptation":
            lab = ROOT / entry["lab_path"]
            assert (lab / "aau-forge.json").is_file()
            assert (lab / "contract-blueprint.json").is_file()

    html = (ROOT / "docs" / "index.html").read_text()
    script = (ROOT / "docs" / "explorer.js").read_text()
    for element_id in ("gallery", "gallery-grid", "gallery-trust", "gallery-contract"):
        assert f'id="{element_id}"' in html, f"Gallery is missing #{element_id}"
    for label in (
        "Generated",
        "Domain reviewed",
        "Reproduced",
        "Verified",
        "Evidence level, not endorsement",
        "maintainer references",
    ):
        assert label in html or label in script, f"Gallery is missing trust copy: {label}"
    for behavior in ("loadGallery", "renderGallery", "galleryCard", "renderTrustLadder"):
        assert behavior in script, f"Gallery script is missing {behavior}"
    assert "gallery-data.json" in script
    assert (ROOT / ".devcontainer" / "devcontainer.json").is_file()
    assert (ROOT / "docs" / "assets" / "social-card-gallery.png").is_file()
    assert "social-card-reliability-2026.png" in html, "current research-release preview is not wired"
    assert (ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "gallery-adaptation.md").is_file()
    assert "aau-gallery = \"aau_harness.gallery:main\"" in (
        ROOT / "harness" / "pyproject.toml"
    ).read_text()
    print(
        f"AAU Gallery integrity OK: {built['stats']['adaptations']} adaptations, "
        f"{built['stats']['contributors']} contributors"
    )


if __name__ == "__main__":
    main()
