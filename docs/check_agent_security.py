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
    if expected["data_version"] != "aau-agent-security-commons-data/0.5":
        raise SystemExit("Agent Security Commons data version drifted")
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
    crash = expected["side_effects"]["crash_lab"]
    if (
        crash["status"] != "evidence_passed"
        or crash["summary"]["case_count"] != 12
        or crash["summary"]["crash_point_count"] != 6
        or crash["summary"]["exact_count"] != 12
        or crash["summary"]["unsafe_resume_count"] != 0
        or crash["summary"]["duplicate_effect_breach_count"] != 0
        or crash["summary"]["unresolved_effect_count"] != 3
    ):
        raise SystemExit("side-effect crash-lab evidence drifted")
    race = expected["side_effects"]["race_lab"]
    if (
        race["status"] != "evidence_passed"
        or race["summary"]["case_count"] != 12
        or race["summary"]["attempt_count"] != 61
        or race["summary"]["exact_count"] != 12
        or race["summary"]["duplicate_effect_count"] != 0
        or race["summary"]["missing_effect_count"] != 0
        or race["summary"]["response_state_mismatch_count"] != 0
    ):
        raise SystemExit("side-effect race-lab evidence drifted")
    matrix = expected["side_effects"]["matrix"]
    if (
        matrix["matrix_version"] != "aau-agent-side-effect-safety-matrix/0.5"
        or matrix["status"] != "evidence_passed"
        or matrix["component_count"] != 3
        or matrix["aggregate"]["case_count"] != 36
        or matrix["aggregate"]["checked_outcome_count"] != 72
        or matrix["aggregate"]["exact_count"] != 72
        or matrix["aggregate"]["unsafe_count"] != 0
        or matrix["aggregate"]["availability_loss_count"] != 0
        or matrix["aggregate"]["unresolved_count"] != 3
        or matrix["coverage_binding"]["tool_id"] != "notification-service"
        or matrix["coverage_binding"]["operation"] != "send_synthetic_notice"
        or matrix["coverage_binding"]["semantic_tool_operation_count"] != 2
        or matrix["coverage_binding"]["fully_stressed_tool_operation_count"] != 1
        or [item["component_id"] for item in matrix["adapter_artifacts"]]
        != ["semantics", "crash_recovery", "concurrency"]
        or any(item["command_argv_index"] != 1 for item in matrix["adapter_artifacts"])
        or any(len(item["sha256"]) != 64 for item in matrix["adapter_artifacts"])
        or any(
            item["material_capture_mode"] != "static_local_python_imports"
            for item in matrix["adapter_artifacts"]
        )
        or matrix["material_count"] != 8
        or matrix["unresolved_import_count"] != 42
        or matrix["runtime_session_count"] != 109
        or matrix["runtime_material_count"] != 11
        or matrix["runtime_only_material_count"] != 3
        or matrix["unobserved_static_material_count"] != 0
        or matrix["runtime_capabilities"] != ["dynamic_code"]
        or any(
            len(item["material_set_sha256"]) != 64
            for item in matrix["adapter_artifacts"]
        )
        or len(matrix["adapter_artifacts"]) != 3
        or {item["component_id"] for item in matrix["adapter_artifacts"]}
        != {"semantics", "crash_recovery", "concurrency"}
    ):
        raise SystemExit("side-effect safety matrix evidence drifted")
    binding = expected["side_effects"]["release_binding"]
    if (
        binding["status"] != "evidence_bound"
        or binding["consequential_operation_count"] != 1
        or binding["fully_bound_consequential_operation_count"] != 1
        or binding["finding_count"] != 0
        or binding["material_set_count"] != 3
        or binding["material_set_match_count"] != 3
        or binding["runtime_snapshot_count"] != 3
        or binding["runtime_snapshot_match_count"] != 3
    ):
        raise SystemExit("side-effect release binding evidence drifted")
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
        ROOT / "agent-side-effect-ledger/crash-suite.schema.json",
        ROOT / "agent-side-effect-ledger/crash-receipt.schema.json",
        ROOT / "agent-side-effect-ledger/race-suite.schema.json",
        ROOT / "agent-side-effect-ledger/race-receipt.schema.json",
        ROOT / "agent-side-effect-ledger/side-effect-safety-matrix.schema.json",
        ROOT / "agent-side-effect-ledger/runtime-observation.schema.json",
        ROOT / "agent-side-effect-ledger/runtime-release-snapshot.schema.json",
        ROOT / "agent-side-effect-ledger/execution-materials.schema.json",
        ROOT / "agent-side-effect-ledger/release-binding-plan.schema.json",
        ROOT / "agent-side-effect-ledger/release-binding-receipt.schema.json",
        ROOT / "agent-side-effect-ledger/release-binding-manifest.schema.json",
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
        'id="asc-effect-crash-exact"',
        'id="asc-effect-crash-unknown"',
        'id="asc-effect-race-exact"',
        'id="asc-effect-race-duplicates"',
        'id="asc-effect-matrix-exact"',
        'id="asc-effect-matrix-artifacts"',
        'id="asc-effect-matrix-materials"',
        'id="asc-effect-matrix-unresolved"',
        'id="asc-effect-matrix-boundary"',
        'id="asc-effect-binding-count"',
        'id="asc-effect-binding-materials"',
        'id="asc-effect-binding-runtime"',
        'id="asc-effect-binding-release"',
        'id="asc-effect-binding-hash"',
        'id="asc-effect-matrix-hash"',
        'id="asc-effect-matrix-runtime-sessions"',
        'id="asc-effect-matrix-runtime-materials"',
        'id="asc-effect-matrix-runtime-only"',
        "Agent Security Commons",
        "Authorization is a live condition",
    ):
        if required not in html:
            raise SystemExit(f"site is missing Agent Security Commons marker: {required}")
    js = (DOCS / "agent-security.js").read_text()
    if "agent-security-data.json?v=11" not in js:
        raise SystemExit("Agent Security Commons browser data is not source-bound")
    if 'agent-security.css?v=7' not in html or 'agent-security.js?v=10' not in html:
        raise SystemExit("Agent Security Commons browser assets are not cache-busted")
    subprocess.run(["node", "--check", str(DOCS / "agent-security.js")], check=True)
    print("Agent Security Commons contracts, evidence, and browser surface are current")


if __name__ == "__main__":
    main()
