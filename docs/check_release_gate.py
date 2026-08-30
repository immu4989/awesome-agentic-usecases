"""Fail CI when the release-operations evidence or browser surface drifts."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def builder():
    spec = importlib.util.spec_from_file_location("make_release_gate_data", DOCS / "make_release_gate_data.py")
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load release-operations data builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    expected = builder().build()
    actual = json.loads((DOCS / "release-gate-data.json").read_text())
    if expected != actual:
        raise SystemExit("docs/release-gate-data.json is stale; run docs/make_release_gate_data.py")
    release = expected["release"]
    if release["status"] != "release_ready" or release["exact_count"] != release["scenario_count"]:
        raise SystemExit("reference release must remain an exact command-adapter execution")
    if release["human_identity_verified"] is not False:
        raise SystemExit("reference release must not claim verified human identity")
    if expected["reproduction"]["independently_reproduced_count"] != 0:
        raise SystemExit("independent reproduction must be derived, never inferred")
    if expected["freshness"]["source_count"] != expected["freshness"]["baseline_count"]:
        raise SystemExit("all policy-source records need explicit baselines")
    if expected["capability_bom"]["status"] != "human_review_required":
        raise SystemExit("a valid public AABOM must remain human-review bounded")
    if expected["capability_bom"]["production_identity_verified"] is not False:
        raise SystemExit("the public AABOM cannot claim verified production identity")
    reduction = expected["capability_bom"]["reduction_plan"]
    if reduction["summary"]["automatically_removed_count"] != 0:
        raise SystemExit("the least-authority planner must never auto-remove a grant")
    if reduction["status"] != "proposal_only":
        raise SystemExit("authority reduction output must stay proposal-only")
    html = (DOCS / "index.html").read_text()
    for marker in (
        'id="release-gate"',
        "Ship evidence,",
        "not confidence.",
        'href="release-gate.css?v=1"',
        'src="release-gate.js?v=1"',
        'id="agent-capability-bom"',
    ):
        if marker not in html:
            raise SystemExit(f"site is missing release-operations marker: {marker}")
    browser_js = (DOCS / "release-gate.js").read_text()
    if "fetch(\"release-gate-data.json\")" not in browser_js:
        raise SystemExit("release-operations browser surface is not bound to generated evidence")
    subprocess.run(["node", "--check", str(DOCS / "release-gate.js")], check=True)
    print("Agent release, reproduction, incident, freshness, and browser evidence are current")


if __name__ == "__main__":
    main()
