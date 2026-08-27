#!/usr/bin/env python3
"""Fail CI when Human Baseline CLI, browser, or privacy boundaries drift."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.human_baseline import (  # noqa: E402
    validate_pack,
    validate_report,
    validate_session,
)


def main() -> None:
    pack = validate_pack(ROOT / "human-baseline-lab" / "reference-pack")
    study = pack["study"]
    sessions = []
    for path in sorted((ROOT / "human-baseline-lab" / "sessions").glob("*.json")):
        session = json.loads(path.read_text())
        validate_session(session, study)
        sessions.append(session)
    assert len(sessions) == 5
    assert all(session["session_kind"] == "synthetic_reference" for session in sessions)
    report = validate_report(
        json.loads((ROOT / "human-baseline-lab" / "reference-report.json").read_text())
    )
    assert report["source"]["session_count"] == len(sessions)
    assert report["source"]["session_kinds"] == {
        "human_observed": 0,
        "synthetic_reference": 5,
    }
    assert report["privacy"]["aggregate_only"] is True
    assert report["agent_comparison"]["adapter_kind"] != "mock"

    data = json.loads((ROOT / "docs" / "human-baseline-data.json").read_text())
    assert data["study"] == study
    assert data["reference"]["report_metrics"] == report["metrics"]
    assert data["privacy"] == {
        "uploads": 0,
        "persistence": False,
        "direct_identifiers": False,
        "practice_only": True,
    }

    html = (ROOT / "docs" / "index.html").read_text()
    script = (ROOT / "docs" / "human-baseline.js").read_text()
    css = (ROOT / "docs" / "human-baseline.css").read_text()
    for element_id in (
        "human-baseline-lab",
        "human-workbench",
        "human-outcomes",
        "human-result",
        "human-source-list",
    ):
        assert f'id="{element_id}"' in html, f"missing #{element_id}"
    for phrase in (
        "half the question",
        "HUMAN-PROTECTION CHECKPOINT",
        "not a human study",
        "BASELINE ≠ REPLACEMENT DECISION",
    ):
        assert phrase.lower() in html.lower()
    for behavior in (
        "renderCase",
        "recordAndContinue",
        "finishStudy",
        "practiceReceipt",
    ):
        assert behavior in script
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "sendBeacon",
        "XMLHttpRequest",
    ):
        assert forbidden not in script
    assert "human-baseline-data.json" in script
    assert "raw_responses_included: false" in script
    assert "human-result-grid" in css
    assert (ROOT / "docs" / "assets" / "human-baseline.svg").is_file()
    for schema in (
        "human-baseline-study.schema.json",
        "human-baseline-session.schema.json",
        "human-baseline-report.schema.json",
    ):
        value = json.loads((ROOT / "human-baseline-lab" / schema).read_text())
        assert value["$schema"].endswith("2020-12/schema")
        assert value["additionalProperties"] is False
    print(
        f"Human Baseline integrity OK: {len(study['cases'])} blinded cases, "
        f"{len(sessions)} synthetic protocol sessions"
    )


if __name__ == "__main__":
    main()
