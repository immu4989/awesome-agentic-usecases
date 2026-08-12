"""Fail CI when the public catalog, runnable packages, README, or CI drift apart."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "use-cases.json"


def load_catalog() -> list[dict]:
    data = json.loads(CATALOG.read_text())
    required = {"path", "title", "icon", "industry", "capabilities", "kind", "question", "cli"}
    assert data, "catalog must not be empty"
    for index, item in enumerate(data):
        missing = required - item.keys()
        assert not missing, f"catalog entry {index} is missing {sorted(missing)}"
        assert item["capabilities"], f"{item['path']} needs at least one capability"
    return data


def discover_packages() -> set[str]:
    return {
        str(path.parent.relative_to(ROOT))
        for path in ROOT.glob("*/*/pyproject.toml")
    }


def ci_directories() -> set[str]:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    return set(re.findall(r"^\s+- dir: ([^\s]+)$", workflow, re.MULTILINE))


def readme_use_case_paths() -> set[str]:
    readme = (ROOT / "README.md").read_text()
    start = readme.index("<!-- USE_CASES:START -->")
    end = readme.index("<!-- USE_CASES:END -->")
    block = readme[start:end]
    return set(re.findall(r"\]\(([^)]+/)/?\)", block))


def main() -> None:
    cases = load_catalog()
    paths = [item["path"] for item in cases]
    assert len(paths) == len(set(paths)), "catalog paths must be unique"
    clis = [item["cli"] for item in cases]
    assert len(clis) == len(set(clis)), "catalog CLI names must be unique"

    for item in cases:
        directory = ROOT / item["path"]
        assert directory.is_dir(), f"missing use-case directory: {item['path']}"
        for name in ("README.md", "FAILURE_MODES.md", "pyproject.toml", "tests"):
            assert (directory / name).exists(), f"{item['path']} is missing {name}"
        use_case_readme = (directory / "README.md").read_text()
        markers = {
            "<!-- README-EXPERIENCE:START -->": "README experience",
            "<!-- VISUAL-BRIEFING:START -->": "visual case file",
        }
        for marker, label in markers.items():
            assert use_case_readme.count(marker) == 1, f"{item['path']} is missing its {label}"
        for asset in (
            "experience.svg",
            "story-v2.svg",
            "scenario-map.svg",
            "benchmark.svg",
            "contrast.svg",
            "result-profile.svg",
            "failure-cards.svg",
        ):
            assert (directory / "docs" / asset).exists(), f"{item['path']} is missing docs/{asset}"
        story_svg = (directory / "docs" / "story-v2.svg").read_text()
        assert story_svg.count('<rect width="258" height="256"') == 4, (
            f"{item['path']} story must keep four fixed, readable act cards"
        )
        assert "animation:spotlight" not in story_svg and 'class="scene' not in story_svg, (
            f"{item['path']} story must never animate card opacity or position"
        )

    catalog_paths = set(paths)
    assert catalog_paths == discover_packages(), "catalog and runnable package directories differ"
    assert catalog_paths == ci_directories(), "catalog and CI matrix directories differ"
    assert {f"{path}/" for path in paths} == readme_use_case_paths(), "catalog and README table differ"

    html = (ROOT / "docs" / "index.html").read_text()
    readme = (ROOT / "README.md").read_text()
    industries = {item["industry"] for item in cases}
    taxonomy = json.loads((ROOT / "docs" / "assets" / "taxonomy.json").read_text())
    verified_model_evals = sum(
        json.loads(path.read_text()).get("backend") != "mock"
        for path in ROOT.glob("*/*/results/eval_*.json")
    )
    expected = [
        f"<b>{len(cases)}</b><small>use cases</small>",
        f"<b>{len(industries)}</b><small>industries</small>",
        f"<b>{verified_model_evals}</b><small>model evals</small>",
        f"<b>{taxonomy['failure_modes']}</b><small>observed failures</small>",
    ]
    for text in expected:
        assert text in html, f"explorer proof point is stale: expected {text!r}"

    explorer_copy = f"Search and filter all {len(cases)} verified use cases"
    assert readme.count(explorer_copy) == 1, (
        f"README explorer count is stale or duplicated: expected {explorer_copy!r} once"
    )

    proof_copy = (
        f"{len(industries)} industries shipping, {verified_model_evals} verified model-evals, "
        f"{taxonomy['failure_modes']} failure modes observed"
    )
    assert proof_copy in readme, f"README proof strip is stale: expected {proof_copy!r}"
    for mode in ("light", "dark"):
        stats = (ROOT / "docs" / "assets" / f"stats-{mode}.svg").read_text()
        assert proof_copy in stats, f"stats-{mode}.svg is stale: expected {proof_copy!r}"

    for asset in ("hero.svg", "hero-v4.webp"):
        assert (ROOT / "docs" / "assets" / asset).is_file(), f"missing visual asset: {asset}"
    hero = (ROOT / "docs" / "assets" / "hero.svg").read_text()
    hero_proof = (
        ("VERIFIED USE CASES", len(cases)),
        ("INDUSTRIES", len(industries)),
        ("MODEL EVALS", verified_model_evals),
        ("OBSERVED FAILURES", taxonomy["failure_modes"]),
    )
    for label, value in hero_proof:
        assert f'>{value}</text>' in hero and f'>{label}</text>' in hero, (
            f"landing-page hero is stale: expected {value} {label.lower()}"
        )

    schema = json.loads((ROOT / "docs" / "obligation-graph.schema.json").read_text())
    example = json.loads((ROOT / "docs" / "obligation-graph.example.json").read_text())
    assert schema["$id"].endswith("obligation-graph.schema.json")
    assert example["contract_version"] == "aau-obligation-graph/1.0"
    assert len(example["obligations"]) >= 2, "worked graph must prove one event can fan out"
    assert len({item["obligation_id"] for item in example["obligations"]}) == len(
        example["obligations"]
    ), "obligation ids must be unique"

    rights_schema = json.loads((ROOT / "docs" / "rights-continuity.schema.json").read_text())
    rights_example = json.loads((ROOT / "docs" / "rights-continuity.example.json").read_text())
    assert rights_schema["$id"].endswith("rights-continuity.schema.json")
    assert rights_example["contract_version"] == "aau-rights-continuity/1.0"
    assert {right["kind"] for right in rights_example["rights"]} == {"primary", "companion"}
    assert len({right["deadline"]["due_at"] for right in rights_example["rights"]}) > 1, (
        "worked rights graph must preserve independent clocks"
    )

    event_schema = json.loads((ROOT / "docs" / "critical-event-fanout.schema.json").read_text())
    event_example = json.loads((ROOT / "docs" / "critical-event-fanout.example.json").read_text())
    assert event_schema["$id"].endswith("critical-event-fanout.schema.json")
    assert event_example["contract_version"] == "aau-critical-event-fanout/1.0"
    assert len(event_example["branches"]) >= 3, "worked critical event must prove fan-out"
    assert len({branch["branch_id"] for branch in event_example["branches"]}) == len(
        event_example["branches"]
    ), "critical-event branch ids must be unique"

    taxonomy_heading = f"## {taxonomy['failure_modes']} failures, {taxonomy['patterns']} patterns"
    assert taxonomy_heading in readme, f"README taxonomy heading is stale: {taxonomy_heading!r}"
    assert f"Read all {taxonomy['patterns']} patterns" in readme, "README taxonomy link is stale"
    start_here = (ROOT / "START_HERE.md").read_text()
    taxonomy_copy = (
        f"groups {taxonomy['failure_modes']} observed failures into "
        f"{taxonomy['patterns']} recurring patterns"
    )
    assert taxonomy_copy in start_here, f"START_HERE taxonomy summary is stale: {taxonomy_copy!r}"

    for guide in ("START_HERE.md", "PLAYBOOKS.md", "BUILD_YOUR_OWN.md", "USE_CASE_RADAR.md"):
        assert (ROOT / guide).is_file(), f"missing user journey guide: {guide}"
        assert f'"{guide}"' in readme or f"({guide})" in readme, f"README does not link {guide}"

    print(f"catalog integrity OK: {len(cases)} use cases, {len(industries)} industries")


if __name__ == "__main__":
    main()
