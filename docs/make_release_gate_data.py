"""Build the browser-safe release, reproduction, incident, and freshness view."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def build() -> dict:
    decision = load("agent-release-gate/examples/reference-pack/release-decision.json")
    release_diff = load("agent-release-gate/examples/reference-pack/release-diff.json")
    receipt = load("agent-release-gate/examples/reference-pack/receipts/aau-agent-release-conformance-v1.json")
    plan = load("agent-release-gate/examples/reference-pack/evidence-plan.json")
    oscal = load("agent-release-gate/examples/reference-pack/assessment-results.oscal.json")
    campaign = load("reproduction-challenges/campaign.json")
    accepted_reproductions = load("reproduction-challenges/accepted-reproductions.json")
    campaign_lock = load("reproduction-challenges/campaign-lock.json")
    exchange = load("agent-incident-exchange/examples/reference-exchange.json")
    sources = load("policy-freshness/sources.json")
    compatibility = load("policy-freshness/compatibility-report.json")
    mcp_delta = load("portable-agent-assurance/examples/mcp-2026-authorization-receipt.json")
    a2a_delta = load("portable-agent-assurance/examples/a2a-1-interface-authorization-receipt.json")
    capability_bom = load("agent-capability-bom/examples/candidate.json")
    capability_diff = load("agent-capability-bom/examples/reference-diff.json")
    capability_review = load("agent-capability-bom/examples/reference-pack/authority-review.json")
    cyclonedx = load("agent-capability-bom/examples/reference-pack/cyclonedx-1.7.json")
    reduction_plan = load("agent-capability-bom/examples/reference-reduction-plan.json")
    conformance_suite = load("agent-capability-bom/examples/reference-conformance-suite.json")
    conformance_receipt = load("agent-capability-bom/examples/reference-conformance-receipt.json")
    action_trust = load("workflow-dependency-trust/action-trust-lock.json")
    open_challenges = [row for row in campaign["challenges"] if row["status"] == "open"]
    oscal_result = oscal["assessment-results"]["results"][0]
    formats = sorted(
        path.name for path in (ROOT / "agent-incident-exchange/examples/reference-pack").glob("*.*json")
        if path.name != "manifest.json" and path.name != "exchange.json"
    )
    return {
        "data_version": "aau-release-operations-live-data/1.1",
        "generated_on": "2026-09-04",
        "release": {
            "release_id": decision["release_id"],
            "status": decision["status"],
            "adapter_kind": decision["adapter_kind"],
            "changed_components": len(release_diff["changes"]),
            "impacted_tags": release_diff["impacted_tags"],
            "changes": [
                {
                    "component_id": row["component_id"],
                    "kind": row["after_kind"],
                    "impact_tags": row["impact_tags"],
                }
                for row in release_diff["changes"]
            ],
            "scenario_count": receipt["scenario_count"],
            "exact_count": sum(row["exact"] for row in receipt["results"]),
            "clean_twin_count": sum(row["clean_twin_count"] for row in plan["suites"]),
            "oscal_observations": len(oscal_result["observations"]),
            "oscal_findings": len(oscal_result["findings"]),
            "human_identity_verified": False,
        },
        "reproduction": {
            "campaign_id": campaign["campaign_id"],
            "challenge_count": len(open_challenges),
            "task_count": sum(row["task_count"] for row in open_challenges),
            "independently_reproduced_count": len(accepted_reproductions["entries"]),
            "campaign_lock_sha256": campaign_lock["lock_sha256"],
            "challenges": campaign["challenges"],
        },
        "incidents": {
            "entry_count": len(exchange["entries"]),
            "critical_count": sum(row["severity"] == "critical" for row in exchange["entries"]),
            "clean_twin_count": sum(row["regression"]["clean_twin_present"] for row in exchange["entries"]),
            "export_count": len(formats),
            "exports": formats,
            "entries": [
                {
                    "incident_id": row["incident_id"],
                    "title": row["title"],
                    "severity": row["severity"],
                    "status": row["status"],
                    "failure_shape_count": len(row["failure_shapes"]),
                }
                for row in exchange["entries"]
            ],
        },
        "capability_bom": {
            "bom_id": capability_bom["bom_id"],
            "status": capability_review["status"],
            "owner_role": capability_bom["accountability"]["owner_role"],
            "model_count": len(capability_bom["models"]),
            "tool_count": len(capability_bom["tools"]),
            "authority_count": len(capability_bom["authorities"]),
            "route_count": len(capability_bom["data_routes"]),
            "evidence_count": len(capability_bom["evidence"]),
            "diff_status": capability_diff["status"],
            "finding_count": capability_diff["finding_count"],
            "blocking_count": capability_diff["blocking_count"],
            "findings": capability_diff["findings"],
            "cyclonedx_version": cyclonedx["specVersion"],
            "production_identity_verified": capability_bom["accountability"]["production_identity_verified"],
            "reduction_plan": {
                "status": reduction_plan["status"],
                "coverage": reduction_plan["coverage"],
                "summary": reduction_plan["summary"],
                "next_evidence_count": len(
                    next(
                        row for row in reduction_plan["authority_reviews"]
                        if row["candidate_reduction"]
                    )["required_next_evidence"]
                ),
            },
            "conformance": {
                "status": conformance_receipt["status"],
                "adapter_kind": conformance_receipt["adapter_kind"],
                "case_count": conformance_receipt["metrics"]["case_count"],
                "clean_twin_count": conformance_receipt["metrics"]["clean_twin_count"],
                "violation_twin_count": conformance_receipt["metrics"]["violation_twin_count"],
                "exact_count": conformance_receipt["metrics"]["exact_count"],
                "unsafe_allow_count": conformance_receipt["metrics"]["unsafe_allow_count"],
                "legitimate_block_count": conformance_receipt["metrics"]["legitimate_block_count"],
                "shape_count": len({row["shape"] for row in conformance_suite["cases"]}),
                "expected_answers_sent_to_adapter": False,
                "tools_executed": 0,
            },
        },
        "workflow_dependency_trust": {
            "lock_version": action_trust["lock_version"],
            "verified_at": action_trust["verified_at"],
            "lock_sha256": action_trust["lock_sha256"],
            "locator_mode": "workflow_path + job_id + external_use_ordinal + component",
            "line_numbers_are_identity": False,
            "yaml_aliases_rejected": action_trust["boundary"][
                "yaml_aliases_cannot_hide_action_uses"
            ],
            **action_trust["summary"],
        },
        "freshness": {
            "source_count": len(sources["sources"]),
            "baseline_count": sum(row["baseline"]["content_sha256"] is not None for row in sources["sources"]),
            "next_review_due": min(row["review_due"] for row in sources["sources"]),
            "next_review_days": (date.fromisoformat(min(row["review_due"] for row in sources["sources"])) - date(2026, 9, 3)).days,
            "compatibility": compatibility["summary"],
            "migration_gaps": [
                row for row in compatibility["bindings"]
                if row["status"] == "migration_required"
            ],
            "mcp_alignment": {
                **next(
                    row for row in compatibility["bindings"]
                    if row["source_id"] == "mcp-authorization"
                ),
                "case_count": mcp_delta["metrics"]["case_count"],
                "exact_count": mcp_delta["metrics"]["exact_count"],
                "unsafe_allow_count": mcp_delta["metrics"]["unsafe_allow_count"],
            },
            "a2a_alignment": {
                **next(
                    row for row in compatibility["bindings"]
                    if row["source_id"] == "a2a-specification"
                ),
                "case_count": a2a_delta["metrics"]["case_count"],
                "exact_count": a2a_delta["metrics"]["exact_count"],
                "unsafe_allow_count": a2a_delta["metrics"]["unsafe_allow_count"],
            },
            "sources": [
                {
                    "source_id": row["source_id"],
                    "title": row["title"],
                    "authority": row["authority"],
                    "source_revision": row["source_revision"],
                    "review_due": row["review_due"],
                    "fingerprint_mode": row["fingerprint_mode"],
                    "owner_count": len(row["owner_paths"]),
                }
                for row in sources["sources"]
            ],
        },
        "boundaries": {
            "synthetic_reference_not_deployment_authority": True,
            "outside_independence_human_reviewed": True,
            "incident_exchange_excludes_exploit_and_sensitive_data": True,
            "source_monitor_does_not_interpret_policy": True,
            "oscal_export_is_experimental_and_non_certifying": True,
            "capability_inventory_is_not_live_authorization": True,
            "authority_nonuse_never_auto_removes_permission": True,
            "authority_conformance_is_not_production_enforcement_evidence": True,
            "action_origin_verification_is_not_an_action_code_audit": True,
        },
    }


def main() -> None:
    output = DOCS / "release-gate-data.json"
    output.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
