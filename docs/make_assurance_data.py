"""Build the browser-safe Portable Agent Assurance and TEVV-Athlon data."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build() -> dict:
    assurance = _module("aau_assurance", ROOT / "portable-agent-assurance/aau_assurance.py")
    mcp_delta = _module("mcp_2026_delta", ROOT / "portable-agent-assurance/mcp_2026_delta.py")
    tevva = _module("aau_tevva", ROOT / "tev-v-athlon-profile/aau_tevva.py")
    envelope = assurance.load_json(
        ROOT / "portable-agent-assurance/examples/synthetic-assurance-envelope.json"
    )
    suite = assurance.load_json(
        ROOT / "portable-agent-assurance/examples/mcp-a2a-conformance-suite.json"
    )
    receipt = assurance.evaluate_suite(envelope, suite)
    mcp_profile = mcp_delta.load_json(
        ROOT / "portable-agent-assurance/examples/mcp-2026-authorization-profile.json"
    )
    mcp_suite = mcp_delta.load_json(
        ROOT / "portable-agent-assurance/examples/mcp-2026-authorization-suite.json"
    )
    mcp_receipt = mcp_delta.load_json(
        ROOT / "portable-agent-assurance/examples/mcp-2026-authorization-receipt.json"
    )
    mcp_delta.verify_receipt(mcp_receipt, mcp_profile, mcp_suite)
    profile = tevva.load_json(ROOT / "tev-v-athlon-profile/examples/agent-assurance-tevva.json")
    assessment = tevva.assess(profile, ROOT)
    reason_counts: dict[str, int] = {}
    for row in receipt["results"]:
        for code in row["observed"]["reason_codes"]:
            reason_counts[code] = reason_counts.get(code, 0) + 1
    stages = []
    stage_titles = {
        "articulate_and_organize": "Articulate & Organize",
        "define_and_construct": "Define & Construct",
        "apply_and_measure": "Apply & Measure",
        "synthesize_and_interrogate": "Synthesize & Interrogate",
    }
    for number, stage in enumerate(tevva.STAGES, 1):
        coverage = assessment["stage_coverage"][stage]
        stages.append(
            {
                "number": f"0{number}",
                "id": stage,
                "title": stage_titles[stage],
                "detail": coverage,
            }
        )
    return {
        "data_version": "aau-assurance-live-data/0.1",
        "generated_on": "2026-08-30",
        "envelope": {
            "id": envelope["envelope_id"],
            "subject": envelope["subject"]["workload_identity"]["identifier"],
            "policy_epoch": envelope["authority"]["policy_epoch"],
            "action_count": len(envelope["authority"]["allowed_actions"]),
            "protocols": sorted(envelope["protocols"]),
            "production_identity_verified": False,
        },
        "suite": {
            **receipt["summary"],
            "suite_id": receipt["suite_id"],
            "result_chain_head_sha256": receipt["result_chain_head_sha256"],
            "reason_codes": [
                {"code": code, "count": count} for code, count in sorted(reason_counts.items())
            ],
        },
        "mcp_2026": {
            "protocol_revision": mcp_profile["protocol_revision"],
            "adapter_kind": mcp_receipt["adapter_kind"],
            "status": mcp_receipt["status"],
            **mcp_receipt["metrics"],
        },
        "tevva": {
            "profile_id": assessment["profile_id"],
            "status": assessment["status"],
            "block_count": assessment["stage_coverage"]["define_and_construct"]["block_count"],
            "event_count": len(assessment["events"]),
            "tool_count": assessment["stage_coverage"]["apply_and_measure"]["tool_count"],
            "artifact_count": len(assessment["artifacts"]),
            "stages": stages,
            "visible_gaps": assessment["visible_gaps"],
            "comment_deadline": profile["draft_basis"]["comment_deadline"],
        },
        "routes": [
            {"label": "Run the assurance envelope", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/portable-agent-assurance"},
            {"label": "Inspect the TEVV-Athlon profile", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/tev-v-athlon-profile"},
            {"label": "Review the NIST comment draft", "href": "https://github.com/immu4989/awesome-agentic-usecases/blob/main/tev-v-athlon-profile/NIST_AI_200_2_COMMENT_DRAFT.md"},
            {"label": "Use the GitHub Action", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/.github/actions/aau-assurance"},
        ],
        "boundaries": {
            "synthetic_only": True,
            "no_live_action": True,
            "not_nist_conformance": True,
            "not_certification": True,
            "not_government_endorsement": True,
        },
    }


def main() -> None:
    output = DOCS / "assurance-data.json"
    output.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
