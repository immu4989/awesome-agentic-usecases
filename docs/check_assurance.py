"""Fail CI when assurance, TEVV, or browser evidence drifts."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _load_builder():
    spec = importlib.util.spec_from_file_location("make_assurance_data", DOCS / "make_assurance_data.py")
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load assurance data builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    expected = _load_builder().build()
    actual = json.loads((DOCS / "assurance-data.json").read_text())
    if expected != actual:
        raise SystemExit("docs/assurance-data.json is stale; run docs/make_assurance_data.py")
    if expected["suite"]["case_count"] != 18 or expected["suite"]["exact_count"] != 18:
        raise SystemExit("assurance reference coverage drifted")
    if expected["suite"]["clean_twin_allow_count"] != 2:
        raise SystemExit("assurance reference must preserve both clean twins")
    delta = expected["mcp_2026"]
    if (
        delta["protocol_revision"] != "2026-07-28"
        or delta["adapter_kind"] != "command"
        or delta["status"] != "evidence_passed"
        or delta["case_count"] != 16
        or delta["exact_count"] != 16
        or delta["clean_twin_count"] != 2
        or delta["unsafe_allow_count"] != 0
        or delta["legitimate_block_count"] != 0
    ):
        raise SystemExit("MCP 2026 authorization delta evidence drifted")
    a2a = expected["a2a_1"]
    if (
        a2a["protocol_revision"] != "1.0"
        or a2a["specification_release"] != "v1.0.1"
        or a2a["adapter_kind"] != "command"
        or a2a["status"] != "evidence_passed"
        or a2a["case_count"] != 17
        or a2a["exact_count"] != 17
        or a2a["clean_twin_count"] != 2
        or a2a["unsafe_allow_count"] != 0
        or a2a["legitimate_block_count"] != 0
    ):
        raise SystemExit("A2A 1.0 interface and authorization delta evidence drifted")
    relay = expected["authority_relay"]
    if (
        relay["a2a_revision"] != "1.0"
        or relay["mcp_revision"] != "2026-07-28"
        or relay["route_count"] != 2
        or relay["adapter_kind"] != "command"
        or relay["status"] != "evidence_passed"
        or relay["case_count"] != 25
        or relay["exact_count"] != 25
        or relay["clean_twin_count"] != 2
        or relay["unsafe_allow_count"] != 0
        or relay["legitimate_block_count"] != 0
    ):
        raise SystemExit("cross-protocol authority relay evidence drifted")
    if expected["current_matrix"] != {
        "gate_count": 3,
        "case_count": 58,
        "exact_count": 58,
        "clean_twin_count": 6,
        "violation_count": 52,
        "unsafe_allow_count": 0,
        "legitimate_block_count": 0,
    }:
        raise SystemExit("current assurance matrix aggregate drifted")
    if expected["authority_trace"] != {
        "trace_count": 25,
        "span_count": 52,
        "allow_trace_count": 2,
        "block_trace_count": 23,
        "blocked_mcp_dispatch_count": 23,
        "raw_content_attribute_count": 0,
        "tracestate_field_count": 0,
        "baggage_field_count": 0,
    }:
        raise SystemExit("privacy-bounded authority trace evidence drifted")
    if expected["envelope"]["production_identity_verified"] is not False:
        raise SystemExit("synthetic reference must not claim production identity")
    if (
        len(expected["tevva"]["stages"]) != 4
        or expected["tevva"]["block_count"] != 6
        or expected["tevva"]["event_count"] != 3
        or expected["tevva"]["tool_count"] != 4
        or expected["tevva"]["artifact_count"] != 7
    ):
        raise SystemExit("TEVV-Athlon stage, Block, Event, Tool, or artifact coverage drifted")
    if expected["tevva"]["visible_gaps"] != [
        "planned_events_not_observed",
        "no_held_out_material",
        "no_observed_independent_reproduction",
    ]:
        raise SystemExit("TEVV-Athlon reference must keep external evidence gaps visible")
    for schema_path in (
        ROOT / "portable-agent-assurance/envelope.schema.json",
        ROOT / "portable-agent-assurance/suite.schema.json",
        ROOT / "portable-agent-assurance/receipt.schema.json",
        ROOT / "tev-v-athlon-profile/profile.schema.json",
    ):
        schema = json.loads(schema_path.read_text())
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or not schema.get("$id"):
            raise SystemExit(f"invalid schema metadata: {schema_path.relative_to(ROOT)}")
    html = (DOCS / "index.html").read_text()
    for marker in (
        'id="agent-assurance"',
        "Portable Agent Assurance",
        "Four stages. No magic score.",
        'id="paa-mcp-exact"',
        'id="mcp-2026-delta"',
        'id="a2a-1-delta"',
        'id="authority-relay-delta"',
        'id="paa-trace-spans"',
        'href="assurance.css?v=6"',
        'src="assurance.js?v=6"',
    ):
        if marker not in html:
            raise SystemExit(f"site is missing assurance marker: {marker}")
    browser_js = (DOCS / "assurance.js").read_text()
    if "http://" in browser_js or "https://" in browser_js:
        raise SystemExit("assurance browser code must not contact an external URL")
    for marker in ("file.text()", "1_000_000", "production identity not verified"):
        if marker not in browser_js:
            raise SystemExit(f"assurance browser boundary drifted: {marker}")
    action = (ROOT / ".github/actions/aau-assurance/action.yml").read_text()
    if "uses:" in action or "pip install" in action or "curl " in action:
        raise SystemExit("assurance composite action must remain dependency-free")
    if "GITHUB_ACTION_PATH/../../../portable-agent-assurance/aau_assurance.py" not in action:
        raise SystemExit("assurance action is not bound to the repository-pinned verifier")
    for marker in (
        "current_gates:",
        "assurance_matrix.py",
        'if: ${{ inputs.current_gates == \'true\' }}',
        "GITHUB_STEP_SUMMARY",
        "--mcp-adapter-command \"$AAU_MCP_ADAPTER\"",
        "--relay-adapter-command \"$AAU_RELAY_ADAPTER\"",
    ):
        if marker not in action:
            raise SystemExit(f"current assurance matrix action drifted: {marker}")
    subprocess.run(["node", "--check", str(DOCS / "assurance.js")], check=True)
    print("Portable Agent Assurance, TEVV profile, and browser surface are current")


if __name__ == "__main__":
    main()
