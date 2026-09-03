"""Fail CI when Agent Security Commons contracts or browser evidence drift."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _load_builder():
    spec = importlib.util.spec_from_file_location("make_agent_security_data", DOCS / "make_agent_security_data.py")
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load agent security data builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    builder = _load_builder()
    expected = builder.build()
    actual = json.loads((DOCS / "agent-security-data.json").read_text())
    if actual != expected:
        raise SystemExit("docs/agent-security-data.json is stale; run docs/make_agent_security_data.py")
    if expected["runtime"]["event_count"] != 50 or expected["runtime"]["adapter_count"] != 6:
        raise SystemExit("ABP runtime reference coverage drifted")
    if len(expected["defender_kits"]) != 5 or len({item["sector"] for item in expected["defender_kits"]}) != 5:
        raise SystemExit("essential-service defender coverage drifted")
    if expected["controls"]["case_count"] != 12 or expected["controls"]["control_count"] != 8:
        raise SystemExit("matched control experiment coverage drifted")
    if expected["pilot"]["evidence_level"] != "designed" or len(expected["pilot"]["visible_gaps"]) != 4:
        raise SystemExit("reference pilot must remain honest about missing external evidence")

    for schema_path in (
        ROOT / "agentic-cyber-resilience/runtime-suite.schema.json",
        ROOT / "agentic-cyber-resilience/runtime-receipt.schema.json",
        ROOT / "agent-incident-regression-commons/incident.schema.json",
        ROOT / "essential-services-defender-kits/kit.schema.json",
        ROOT / "agent-control-observatory/experiment.schema.json",
        ROOT / "public-value-pilot-network/pilot.schema.json",
        ROOT / "agent-side-effect-ledger/side-effect-suite.schema.json",
        ROOT / "agent-side-effect-ledger/side-effect-receipt.schema.json",
    ):
        schema = json.loads(schema_path.read_text())
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or not schema.get("$id"):
            raise SystemExit(f"invalid schema metadata: {schema_path.relative_to(ROOT)}")

    html = (DOCS / "index.html").read_text()
    for required in (
        'id="agent-security-commons"',
        "Agent Security Commons",
        "Authorization is a live condition",
    ):
        if required not in html:
            raise SystemExit(f"site is missing Agent Security Commons marker: {required}")
    js = (DOCS / "agent-security.js").read_text()
    if "agent-security-data.json" not in js:
        raise SystemExit("Agent Security Commons browser data is not source-bound")
    subprocess.run(["node", "--check", str(DOCS / "agent-security.js")], check=True)
    print("Agent Security Commons contracts, evidence, and browser surface are current")


if __name__ == "__main__":
    main()
