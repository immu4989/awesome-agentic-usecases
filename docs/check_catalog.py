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

    catalog_paths = set(paths)
    assert catalog_paths == discover_packages(), "catalog and runnable package directories differ"
    assert catalog_paths == ci_directories(), "catalog and CI matrix directories differ"
    assert {f"{path}/" for path in paths} == readme_use_case_paths(), "catalog and README table differ"

    html = (ROOT / "docs" / "index.html").read_text()
    industries = {item["industry"] for item in cases}
    expected = [f"<b>{len(cases)}</b> use cases", f"<b>{len(industries)}</b> industries"]
    for text in expected:
        assert text in html, f"explorer proof point is stale: expected {text!r}"

    print(f"catalog integrity OK: {len(cases)} use cases, {len(industries)} industries")


if __name__ == "__main__":
    main()
