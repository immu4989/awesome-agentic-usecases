#!/usr/bin/env python3
"""Fail when the public Boundary Lab drifts from its evidence or interaction contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "boundary-data.json"
MANIFEST_PATH = ROOT / "boundary-lab" / "pairs.json"
VALID_REVIEWS = {"trust", "verify", "block"}
FORBIDDEN = ("sk-live", "int-db-creds", "secret_value")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def require_text(path: Path, needles: tuple[str, ...]) -> None:
    text = path.read_text()
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")


def main() -> None:
    data = json.loads(DATA_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    if data["schema_version"] != "aau-boundary-lab/1.0":
        raise SystemExit("Boundary Lab public schema changed without a version update")
    pairs = data["pairs"]
    if len(pairs) != 8 or len(manifest["pairs"]) != 8:
        raise SystemExit("Boundary Lab v1 must expose exactly eight declared pairs")
    if [pair["order"] for pair in pairs] != list(range(1, 9)):
        raise SystemExit("Boundary Lab order must be contiguous from 1 through 8")
    if len({pair["id"] for pair in pairs}) != len(pairs):
        raise SystemExit("Boundary Lab pair IDs must be unique")
    if len({pair["industry"] for pair in pairs}) != 8:
        raise SystemExit("Boundary Lab v1 must retain eight distinct industries")
    if data["stats"] != {
        "pairs": 8,
        "industries": 8,
        "contracts": 5,
        "source_scenarios": 16,
    }:
        raise SystemExit(f"unexpected Boundary Lab stats: {data['stats']}")

    manifest_hash = digest(MANIFEST_PATH)
    source_scenarios: set[str] = set()
    for pair in pairs:
        reviews = pair["expected_reviews"]
        if set(reviews) != {"baseline", "changed"} or not set(reviews.values()) <= VALID_REVIEWS:
            raise SystemExit(f"{pair['id']}: invalid reviewer action")
        if reviews["baseline"] == reviews["changed"]:
            raise SystemExit(f"{pair['id']}: reviewer action does not move")
        if pair["baseline"]["oracle"]["terminal"] == pair["changed"]["oracle"]["terminal"]:
            raise SystemExit(f"{pair['id']}: source oracle does not move")
        if pair["presentation"] not in {"baseline-first", "changed-first"}:
            raise SystemExit(f"{pair['id']}: invalid presentation")
        if not pair["boundary"]["label"] or pair["boundary"]["before"] == pair["boundary"]["after"]:
            raise SystemExit(f"{pair['id']}: semantic boundary is not explicit")
        scenario_path = ROOT / pair["provenance"]["scenario_path"]
        if not scenario_path.is_file():
            raise SystemExit(f"{pair['id']}: missing source scenario file")
        if pair["provenance"]["scenario_sha256"] != digest(scenario_path):
            raise SystemExit(f"{pair['id']}: scenario source hash drifted")
        if pair["provenance"]["manifest_sha256"] != manifest_hash:
            raise SystemExit(f"{pair['id']}: manifest hash drifted")
        expected_share = (
            "https://immu4989.github.io/awesome-agentic-usecases/"
            f"?boundary={pair['id']}#boundary-lab"
        )
        if pair["links"]["share"] != expected_share:
            raise SystemExit(f"{pair['id']}: unstable share route")
        source_scenarios.update(
            {pair["baseline"]["scenario_id"], pair["changed"]["scenario_id"]}
        )
        if len(pair["sources"]) < 2 or not all(source["url"].startswith("https://") for source in pair["sources"]):
            raise SystemExit(f"{pair['id']}: each boundary needs two HTTPS evidence routes")

    if len(source_scenarios) != 16:
        raise SystemExit("Boundary Lab source scenarios must not be reused across pairs")
    serialized = DATA_PATH.read_text().lower()
    for token in FORBIDDEN:
        if token in serialized:
            raise SystemExit(f"Boundary Lab public data contains forbidden secret material: {token}")

    require_text(
        ROOT / "docs" / "index.html",
        (
            'id="boundary-lab"',
            'href="boundary-lab.css?v=1"',
            'src="boundary-lab.js?v=1"',
            'id="boundary-reveal-button"',
            'id="boundary-download-json"',
            'id="boundary-challenge-link"',
            'id="boundary-copy-status"',
            "Can You Trust This Agent? Change One Fact.",
            "One deciding fact",
        ),
    )
    require_text(
        ROOT / "docs" / "boundary-lab.js",
        (
            'fetch("boundary-data.json?v=1")',
            "localStorage",
            'params.set("boundary"',
            "new Blob",
            "toBlob",
            "x.com/intent/post",
            "/issues/new?title=",
            "aau-boundary-regression/1.0",
        ),
    )
    require_text(
        ROOT / "docs" / "boundary-lab.css",
        (
            ".boundary-split",
            "@media (max-width: 600px)",
            "@media (prefers-reduced-motion: reduce)",
            ".boundary-lab [hidden]",
        ),
    )
    require_text(
        ROOT / "docs" / "assets" / "boundary-lab.svg",
        ("AAU Boundary Lab", ">8<", ">16<", "Pharmaceutical Manufacturing", "Security Operations"),
    )
    require_text(
        ROOT / "boundary-lab" / "README.md",
        ("one semantic boundary", "python docs/make_boundary_lab_data.py", "Trust", "Verify", "Block"),
    )
    print("Boundary Lab integrity: 8 pairs, 16 source scenarios, hashes, privacy, and interactions verified")


if __name__ == "__main__":
    main()
