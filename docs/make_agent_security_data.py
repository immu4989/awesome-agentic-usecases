"""Build the browser-safe Agent Security Commons data from committed source artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

sys.path.insert(0, str(ROOT / "agentic-cyber-resilience"))
sys.path.insert(0, str(ROOT / "agent-incident-regression-commons"))
sys.path.insert(0, str(ROOT / "essential-services-defender-kits"))
sys.path.insert(0, str(ROOT / "agent-control-observatory"))
sys.path.insert(0, str(ROOT / "public-value-pilot-network"))
sys.path.insert(0, str(ROOT / "agent-side-effect-ledger"))

from aau_boundary import load_json as load_boundary_json  # noqa: E402
from aau_crash_lab import verify_receipt as verify_crash_receipt  # noqa: E402
from aau_incident import evaluate_incident, load_json as load_incident_json  # noqa: E402
from aau_observatory import evaluate_experiment, load_json as load_experiment_json  # noqa: E402
from aau_pilot_network import assess_pilot, load_json as load_pilot_json  # noqa: E402
from aau_race_lab import verify_receipt as verify_race_receipt  # noqa: E402
from aau_release_binding import verify_pack as verify_release_binding_pack  # noqa: E402
from aau_runtime import evaluate_suite as evaluate_runtime_suite  # noqa: E402
from aau_side_effect import (  # noqa: E402
    evaluate_suite as evaluate_side_effect_suite,
    verify_conformance_receipt as verify_side_effect_conformance,
)
from aau_side_effect_matrix import verify_pack as verify_side_effect_matrix_pack  # noqa: E402
from aau_defender import assess_kit, load_json as load_kit_json  # noqa: E402


def build() -> dict:
    profile = load_boundary_json(
        ROOT / "agentic-cyber-resilience/examples/synthetic-critical-infrastructure-profile.json"
    )
    suite = load_boundary_json(ROOT / "agentic-cyber-resilience/evals/runtime-conformance-suite.json")
    runtime = evaluate_runtime_suite(profile, suite)

    side_effect_suite = load_boundary_json(
        ROOT / "agent-side-effect-ledger/examples/reference-suite.json"
    )
    side_effects = evaluate_side_effect_suite(side_effect_suite)
    side_effect_conformance = load_boundary_json(
        ROOT / "agent-side-effect-ledger/examples/reference-conformance-receipt.json"
    )
    verify_side_effect_conformance(side_effect_conformance, side_effect_suite)
    crash_suite = load_boundary_json(ROOT / "agent-side-effect-ledger/examples/crash-suite.json")
    crash_receipt = load_boundary_json(
        ROOT / "agent-side-effect-ledger/examples/reference-crash-receipt.json"
    )
    verify_crash_receipt(crash_receipt, crash_suite)
    race_suite = load_boundary_json(ROOT / "agent-side-effect-ledger/examples/race-suite.json")
    race_receipt = load_boundary_json(
        ROOT / "agent-side-effect-ledger/examples/reference-race-receipt.json"
    )
    verify_race_receipt(race_receipt, race_suite)
    side_effect_matrix = verify_side_effect_matrix_pack(
        ROOT / "agent-side-effect-ledger/examples/reference-matrix-pack"
    )
    release_binding = verify_release_binding_pack(
        ROOT / "agent-side-effect-ledger/examples/reference-release-binding-pack"
    )

    incident_record = load_incident_json(
        ROOT / "agent-incident-regression-commons/examples/public-agent-boundary-incident.json"
    )
    incident = evaluate_incident(incident_record)

    kits = []
    for path in sorted((ROOT / "essential-services-defender-kits/kits").glob("*.json")):
        kit = load_kit_json(path)
        assessment = assess_kit(kit)
        kits.append(
            {
                "kit_id": kit["kit_id"],
                "title": kit["title"],
                "sector": kit["sector"],
                "beneficiary": kit["beneficiary"],
                "exercise_count": assessment["exercise_count"],
                "gap_count": len(assessment["control_states"]["gap"]),
                "planned_count": len(assessment["control_states"]["planned"]),
                "path": f"https://github.com/immu4989/awesome-agentic-usecases/blob/main/essential-services-defender-kits/kits/{path.name}",
            }
        )

    experiment = load_experiment_json(
        ROOT / "agent-control-observatory/experiments/authority-control-ladder.json"
    )
    control_report = evaluate_experiment(experiment)
    arms = []
    arm_titles = {item["arm_id"]: item["title"] for item in experiment["arms"]}
    for arm in control_report["arms"]:
        arms.append(
            {
                "arm_id": arm["arm_id"],
                "title": arm_titles[arm["arm_id"]],
                "active_control_count": len(arm["active_controls"]),
                "measurements": arm["measurements"],
                "unsafe_cases": [row["case_id"] for row in arm["cases"] if row["unsafe_allow"]],
            }
        )

    pilot_record = load_pilot_json(
        ROOT / "public-value-pilot-network/pilots/foia-routing-partner-call.json"
    )
    pilot = assess_pilot(pilot_record)

    return {
        "data_version": "aau-agent-security-commons-data/0.4",
        "generated_on": "2026-09-04",
        "runtime": {
            "event_count": runtime["event_count"],
            "run_count": runtime["run_count"],
            "adapter_count": 6,
            "adapters": ["Generic JSON", "MCP", "OpenAI Agents", "LangGraph", "CrewAI", "AutoGen"],
            "summary": runtime["summary"],
            "suite_sha256": runtime["suite_sha256"],
        },
        "side_effects": {
            "suite_id": side_effects["suite_id"],
            "receipt_sha256": side_effects["receipt_sha256"],
            "summary": side_effects["summary"],
            "conformance": {
                "status": side_effect_conformance["status"],
                "receipt_sha256": side_effect_conformance["receipt_sha256"],
                "summary": side_effect_conformance["summary"],
                "oracle_withheld": side_effect_conformance["claim_boundary"][
                    "oracle_withheld_from_adapter"
                ],
            },
            "crash_lab": {
                "status": crash_receipt["status"],
                "receipt_sha256": crash_receipt["receipt_sha256"],
                "summary": crash_receipt["summary"],
            },
            "race_lab": {
                "status": race_receipt["status"],
                "receipt_sha256": race_receipt["receipt_sha256"],
                "summary": race_receipt["summary"],
            },
            "matrix": {
                "matrix_version": side_effect_matrix["matrix_version"],
                "status": side_effect_matrix["status"],
                "matrix_sha256": side_effect_matrix["matrix_sha256"],
                "component_count": side_effect_matrix["component_count"],
                "aggregate": side_effect_matrix["aggregate"],
                "coverage_binding": side_effect_matrix["coverage_binding"],
                "adapter_artifacts": side_effect_matrix["adapter_artifacts"],
                "material_count": sum(
                    item["material_count"]
                    for item in side_effect_matrix["adapter_artifacts"]
                ),
                "unresolved_import_count": sum(
                    item["unresolved_import_count"]
                    for item in side_effect_matrix["adapter_artifacts"]
                ),
            },
            "release_binding": {
                "status": release_binding["status"],
                "release_id": release_binding["release_id"],
                "consequential_operation_count": release_binding[
                    "consequential_operation_count"
                ],
                "fully_bound_consequential_operation_count": release_binding[
                    "fully_bound_consequential_operation_count"
                ],
                "finding_count": len(release_binding["findings"]),
                "material_set_count": sum(
                    len(item["adapters"])
                    for item in release_binding["bindings"]
                ),
                "material_set_match_count": sum(
                    adapter["material_set_matches_matrix"]
                    for item in release_binding["bindings"]
                    for adapter in item["adapters"].values()
                ),
                "receipt_sha256": release_binding["receipt_sha256"],
            },
            "failure_shapes": [
                "unknown_outcome_requires_reconciliation",
                "changed_intent_key_conflict",
                "self_or_expired_approval",
                "compensation_is_a_second_effect",
            ],
        },
        "incident": {
            "incident_id": incident["incident_id"],
            "regression_count": incident["summary"]["regression_count"],
            "unsafe_allow_before_count": incident["summary"]["unsafe_allow_before_count"],
            "post_fix_exact_rate": incident["summary"]["post_fix_exact_rate"],
            "unresolved_question_count": incident["summary"]["unresolved_question_count"],
        },
        "defender_kits": kits,
        "controls": {
            "case_count": control_report["case_count"],
            "control_count": control_report["control_count"],
            "arms": arms,
        },
        "pilot": {
            "pilot_id": pilot["pilot_id"],
            "evidence_level": pilot["evidence_level"],
            "visible_gaps": pilot["visible_gaps"],
            "measure_count": len(pilot["measure_ids"]),
        },
        "routes": [
            {"label": "Run ABP 0.2", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/agentic-cyber-resilience"},
            {"label": "Guard side effects", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/agent-side-effect-ledger"},
            {"label": "Replay incident lessons", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/agent-incident-regression-commons"},
            {"label": "Choose a defender kit", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/essential-services-defender-kits"},
            {"label": "Compare controls", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/agent-control-observatory"},
            {"label": "Propose a public-value pilot", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/public-value-pilot-network"}
        ],
        "boundary": {
            "zero_upload": True,
            "no_live_targets": True,
            "no_tool_execution": True,
            "not_certification": True,
        },
    }


def main() -> None:
    output = DOCS / "agent-security-data.json"
    output.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
