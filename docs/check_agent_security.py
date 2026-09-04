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
    side_effects = expected["side_effects"]["summary"]
    if (
        side_effects["case_count"] != 12
        or side_effects["event_count"] != 48
        or side_effects["duplicate_effects_prevented"] != 3
        or side_effects["reconciliation_count"] != 2
        or side_effects["at_most_one_breach_count"] != 0
        or side_effects["exact_outcome_rate"] != 1
        or side_effects["exact_reason_rate"] != 1
    ):
        raise SystemExit("side-effect ledger reference evidence drifted")
    conformance = expected["side_effects"]["conformance"]
    if (
        conformance["status"] != "evidence_passed"
        or conformance["summary"]["event_count"] != 48
        or conformance["summary"]["exact_outcome_count"] != 48
        or conformance["summary"]["exact_reason_count"] != 48
        or conformance["summary"]["unsafe_effect_outcome_count"] != 0
        or conformance["summary"]["unknown_retry_violation_count"] != 0
        or conformance["oracle_withheld"] is not True
    ):
        raise SystemExit("side-effect command conformance evidence drifted")
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
        ROOT / "agent-side-effect-ledger/side-effect-conformance-receipt.schema.json",
    ):
        schema = json.loads(schema_path.read_text())
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or not schema.get("$id"):
            raise SystemExit(f"invalid schema metadata: {schema_path.relative_to(ROOT)}")

    html = (DOCS / "index.html").read_text()
    for required in (
        'id="agent-security-commons"',
        'id="agent-side-effect-ledger"',
        'id="asc-effect-duplicate-count"',
        'id="asc-effect-receipt"',
        'id="asc-effect-conformance-exact"',
        'id="asc-effect-conformance-receipt"',
        "Agent Security Commons",
        "Authorization is a live condition",
    ):
        if required not in html:
            raise SystemExit(f"site is missing Agent Security Commons marker: {required}")
    js = (DOCS / "agent-security.js").read_text()
    if "agent-security-data.json?v=3" not in js:
        raise SystemExit("Agent Security Commons browser data is not source-bound")
    subprocess.run(["node", "--check", str(DOCS / "agent-security.js")], check=True)
    print("Agent Security Commons contracts, evidence, and browser surface are current")


if __name__ == "__main__":
    main()
