#!/usr/bin/env python3
"""Fail CI when Community Evidence trust, privacy, or browser routes drift."""

from __future__ import annotations

import json

from make_community_evidence_data import ROOT, build_data


def main() -> None:
    built = build_data()
    published = json.loads((ROOT / "docs" / "community-evidence-data.json").read_text())
    assert built == published, "community-evidence-data.json is stale"
    assert built["stats"]["submissions"] >= 3
    assert built["stats"]["industries"] >= 3
    assert all(item["origin"] == "maintainer-reference" for item in built["entries"])
    assert all(item["evidence"]["level"] == "Generated" for item in built["entries"])
    assert (ROOT / "community-evidence" / "submission.schema.json").is_file()
    assert (ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "community-evidence.md").is_file()

    html_text = (ROOT / "docs" / "index.html").read_text()
    script = (ROOT / "docs" / "community-evidence.js").read_text()
    css = (ROOT / "docs" / "community-evidence.css").read_text()
    for element_id in (
        "community-evidence-loop",
        "evidence-desk",
        "evidence-validation-list",
        "evidence-showcase-grid",
    ):
        assert f'id="{element_id}"' in html_text, f"missing #{element_id}"
    for phrase in (
        "Your fork deserves",
        "Evidence level, not endorsement",
        "Nothing leaves this tab",
        "maintainer references",
    ):
        assert phrase in html_text or phrase in script
    for behavior in (
        "validateLocalFiles",
        "deriveEvidence",
        "buildContributionPack",
        "renderShowcase",
    ):
        assert behavior in script
    for forbidden in ("localStorage", "sessionStorage", "sendBeacon", "XMLHttpRequest"):
        assert forbidden not in script, f"browser desk must not use {forbidden}"
    assert "community-evidence-data.json" in script
    assert "AAUBoundaryZip.archive" in script
    assert "evidence-card" in css
    print(
        f"Community Evidence integrity OK: {built['stats']['submissions']} packs, "
        f"{built['stats']['receipts']} receipts"
    )


if __name__ == "__main__":
    main()
