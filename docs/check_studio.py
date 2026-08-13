"""Fail CI when AAU Studio's interface, evidence index, or spec contract drifts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    catalog = json.loads((ROOT / "docs" / "use-cases.json").read_text())
    taxonomy = json.loads((ROOT / "docs" / "assets" / "taxonomy.json").read_text())
    studio = json.loads((ROOT / "docs" / "studio-data.json").read_text())
    schema = json.loads((ROOT / "docs" / "studio-spec.schema.json").read_text())
    example = json.loads((ROOT / "docs" / "studio-spec.example.json").read_text())
    html = (ROOT / "docs" / "index.html").read_text()
    script = (ROOT / "docs" / "explorer.js").read_text()

    assert studio["version"] == "aau-studio/1.0"
    assert schema["$id"].endswith("studio-spec.schema.json")
    assert example["contract_version"] == studio["version"]
    assert example["recommended_case"]["path"] in {
        item["path"] for item in studio["cases"]
    }
    assert (ROOT / "docs" / "assets" / "social-card-forge.png").is_file()
    assert (ROOT / "docs" / "assets" / "social-card-gallery.png").is_file()
    assert "social-card-challenge.png" in html, "current Challenge preview is not wired"
    assert len(studio["cases"]) == len(catalog)
    assert {item["path"] for item in studio["cases"]} == {item["path"] for item in catalog}
    assert studio["proof"]["failure_patterns"] == taxonomy["patterns"]
    assert studio["proof"]["failure_modes"] == taxonomy["failure_modes"]
    assert f"All {taxonomy['patterns']} failure patterns ↗" in html

    for item in studio["cases"]:
        evidence = item["evidence"]
        assert evidence["mock_available"], f"{item['path']} needs a zero-cost mock"
        assert evidence["reproducible_scenarios"], f"{item['path']} needs scenarios"
        assert evidence["real_result_artifacts"] >= 1, f"{item['path']} needs real evidence"
        assert evidence["observed_failure_modes"] >= 3, f"{item['path']} needs failures"
        assert item["contract"]["name"] and item["contract"]["path"]
        assert item["commands"]["evaluate"].endswith("--backend mock --repeats 3")

    required_ids = (
        "studio",
        "studio-form",
        "studio-workflow",
        "studio-industry",
        "studio-shape",
        "studio-results",
        "studio-kit",
        "compare-tray",
        "compare-dialog",
        "forge-command",
        "copy-forge-command",
    )
    for element_id in required_ids:
        assert f'id="{element_id}"' in html, f"Studio is missing #{element_id}"
    for behavior in (
        "rankStudioCases",
        "renderStudioResults",
        "downloadStudioSpec",
        "renderComparison",
        "buildIssueUrl",
        "slugifyStudio",
    ):
        assert behavior in script, f"Studio script is missing {behavior}"

    for discussion_form in ("show-and-tell.yml", "q-and-a.yml"):
        assert (ROOT / ".github" / "DISCUSSION_TEMPLATE" / discussion_form).is_file()
    assert (ROOT / "AAU_FORGE.md").is_file()
    assert 'aau-forge = "aau_harness.forge:main"' in (
        ROOT / "harness" / "pyproject.toml"
    ).read_text()
    forge_source = (
        ROOT / "harness" / "src" / "aau_harness" / "forge_contracts.py"
    ).read_text()
    for contract in ("Decision Gate", "Rights Continuity", "Critical Event Fan-Out"):
        assert contract in forge_source
    assert "aau forge doctor" in (ROOT / "AAU_FORGE.md").read_text()
    assert "contract-shaped runnable lab" in html

    print(f"AAU Studio integrity OK: {len(catalog)} indexed use cases")


if __name__ == "__main__":
    main()
