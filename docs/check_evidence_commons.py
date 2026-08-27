#!/usr/bin/env python3
"""Fail closed when the Evidence Commons drifts or overclaims."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.evidence_commons import comparison, validate_capsule  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    capsule_paths = sorted((ROOT / "evidence-commons" / "capsules").glob("*.json"))
    require(len(capsule_paths) == 3, "Evidence Commons must publish exactly three reference capsules")
    capsules = [validate_capsule(json.loads(path.read_text()), ROOT) for path in capsule_paths]
    comparisons = {item["capsule_id"]: comparison(item) for item in capsules}

    require(
        all(item["status"] == "partner_sought" for item in capsules),
        "reference capsule status must remain partner_sought until evidence is added",
    )
    require(
        all(item["artifacts"]["agent_receipt"]["suite_binding"] == "scenario_ids_only" for item in capsules),
        "historical receipts must not be relabeled hash_bound",
    )
    require(
        all(result["missing_evidence"][0] == "fresh hash-bound agent rerun on the reviewed suite" for result in comparisons.values()),
        "the suite-binding gap must remain first",
    )
    require(
        all(not result["claims"]["causal_impact_proved"] for result in comparisons.values()),
        "reference capsules must not claim causal impact",
    )

    browser = json.loads((ROOT / "docs" / "evidence-commons-data.json").read_text())
    require(browser["schema_version"] == "aau-evidence-commons-browser/1.0", "browser schema drifted")
    require(browser["stats"] == {
        "capsules": 3,
        "independent_reproductions": 0,
        "observed_human_baselines": 0,
        "open_partner_calls": 3,
        "visible_gaps": 15,
    }, "browser statistics must be artifact-derived and honest")
    require(browser["privacy"] == {"participant_records": False, "persistence": False, "uploads": 0}, "browser privacy boundary drifted")
    public = {item["id"]: item for item in browser["capsules"]}
    require(set(public) == set(comparisons), "browser capsules differ from validated capsules")
    for capsule_id, result in comparisons.items():
        item = public[capsule_id]
        require(item["status"] == result["derived_status"], f"{capsule_id}: browser status drifted")
        require(item["missing_evidence"] == result["missing_evidence"], f"{capsule_id}: browser gaps drifted")
        require(item["agent"]["value"] == result["agent_measurement"]["value"], f"{capsule_id}: browser metric drifted")

    schema_names = (
        "impact-capsule.schema.json",
        "public-value-observation.schema.json",
        "reproduction.schema.json",
    )
    for name in schema_names:
        schema = json.loads((ROOT / "evidence-commons" / name).read_text())
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{name}: unsupported schema draft")
        require(schema.get("additionalProperties") is False, f"{name}: top-level fields must be closed")

    html = (ROOT / "docs" / "index.html").read_text()
    css = (ROOT / "docs" / "evidence-commons.css").read_text()
    script = (ROOT / "docs" / "evidence-commons.js").read_text()
    required_ids = (
        "evidence-commons", "commons-console", "commons-card-list", "commons-detail-title",
        "commons-gaps-list", "commons-measure-grid", "commons-copy-cli", "commons-status-line",
    )
    for element_id in required_ids:
        require(f'id="{element_id}"' in html, f"live page is missing #{element_id}")
    require("evidence-commons.css?v=1" in html and "evidence-commons.js?v=1" in html, "live assets are not wired")
    require("@media (prefers-reduced-motion:reduce)" in css, "reduced-motion support is missing")
    for prohibited in ("localStorage", "sessionStorage", "sendBeacon", "XMLHttpRequest", "FormData("):
        require(prohibited not in script, f"browser desk must not use {prohibited}")
    require(not re.search(r"fetch\([^\)]*https?://", script), "browser desk must not transmit to remote endpoints")
    require((ROOT / "docs" / "assets" / "evidence-commons.svg").is_file(), "Evidence Commons visual is missing")
    print("Evidence Commons — 3 capsules, 15 honest gaps, zero raw records")


if __name__ == "__main__":
    main()
