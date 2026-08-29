"""Build public site data and reference receipts for the Collective Cyber Defense Lab."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
RECEIPTS = ROOT / "cyber-defense-evidence-mesh/examples/receipts"
MESH_CONTRACT = ROOT / "cyber-defense-evidence-mesh/examples/reference-mesh.json"
REPRODUCTION = ROOT / "independent-reproduction-exchange"
REPRODUCTION_DEMO = REPRODUCTION / "examples/revealed-protocol-demo"

for folder in (
    "verified-fix-commons", "agent-containment-drills", "essential-service-defender-box",
    "frontier-defense-benchmark", "cyber-defense-evidence-mesh", "public-defense-outcomes-observatory",
    "independent-reproduction-exchange",
):
    sys.path.insert(0, str(ROOT / folder))

from aau_containment import evaluate_drill  # noqa: E402
from aau_defense_benchmark import evaluate as evaluate_benchmark  # noqa: E402
from aau_defender_box import assess_campaign  # noqa: E402
from aau_evidence_mesh import build_index  # noqa: E402
from aau_fix import evaluate_contract  # noqa: E402
from aau_outcomes import evaluate as evaluate_outcomes  # noqa: E402
from aau_reproduction import build_submission, federate, issue_challenge, pack_payloads  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build_receipts() -> tuple[list[dict], dict, dict, dict]:
    declarations = []
    fixes = []
    for contract_path in sorted((ROOT / "verified-fix-commons/examples").glob("*.json")):
        contract = load(contract_path)
        receipt = evaluate_contract(contract)
        name = f"fix-{contract_path.stem}.json"
        write(RECEIPTS / name, receipt)
        declarations.append({
            "artifact_id": receipt["fix_id"], "kind": "verified_fix", "path": f"receipts/{name}",
            "evidence_level": receipt["evidence_level"], "producer": receipt["producer"],
            "reproduction_pack_path": None,
        })
        fixes.append({
            "fix_id": receipt["fix_id"], "title": contract["title"], "change_kind": contract["change"]["kind"],
            "case_count": receipt["summary"]["case_count"], "after_pass_rate": receipt["summary"]["after_pass_rate"],
            "evidence_level": receipt["evidence_level"],
            "path": f"https://github.com/immu4989/awesome-agentic-usecases/blob/main/verified-fix-commons/examples/{contract_path.name}",
        })

    drill = load(ROOT / "agent-containment-drills/examples/reference-containment-drill.json")
    containment = evaluate_drill(drill)
    write(RECEIPTS / "containment-reference.json", containment)
    declarations.append({
        "artifact_id": containment["drill_id"], "kind": "containment_drill", "path": "receipts/containment-reference.json",
        "evidence_level": "synthetic_reference", "producer": "AAU deterministic containment executor",
        "reproduction_pack_path": None,
    })

    campaign = load(ROOT / "essential-service-defender-box/examples/community-water-reference-campaign.json")
    defender = assess_campaign(campaign)
    write(RECEIPTS / "defender-reference.json", defender)
    declarations.append({
        "artifact_id": defender["campaign_id"], "kind": "defender_campaign", "path": "receipts/defender-reference.json",
        "evidence_level": "synthetic_reference", "producer": "AAU deterministic defender planner",
        "reproduction_pack_path": None,
    })

    suite = load(ROOT / "frontier-defense-benchmark/examples/collective-defense-suite.json")
    responses = load(ROOT / "frontier-defense-benchmark/examples/reference-protocol-responses.json")
    benchmark = evaluate_benchmark(suite, responses)
    write(RECEIPTS / "benchmark-reference.json", benchmark)
    declarations.append({
        "artifact_id": "reference-defense-protocol", "kind": "defense_benchmark", "path": "receipts/benchmark-reference.json",
        "evidence_level": "synthetic_reference", "producer": "AAU hand-authored protocol fixture",
        "reproduction_pack_path": None,
    })
    return declarations, {"fixes": fixes, "containment": containment}, {"campaign": campaign, "assessment": defender}, benchmark


def build_reproduction_demo(suite: dict, responses: dict) -> tuple[dict, dict]:
    challenge, oracle = issue_challenge(suite, "collective-defense-revealed-training-v1", "a" * 64)
    metadata = load(REPRODUCTION / "examples/reference-metadata.json")
    review = load(REPRODUCTION / "examples/reference-review.json")
    submission = build_submission(challenge, responses, metadata)
    payloads, adjudication = pack_payloads(challenge, oracle, submission, review)
    REPRODUCTION_DEMO.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        (REPRODUCTION_DEMO / name).write_bytes(payload)
    federation = federate([REPRODUCTION_DEMO])
    return {
        "status": adjudication["status"],
        "evidence_level": adjudication["evidence_level"],
        "challenge_id": challenge["challenge_id"],
        "task_count": len(challenge["tasks"]),
        "oracle_commitment_sha256": challenge["oracle_commitment_sha256"],
        "challenge_sha256": challenge["challenge_sha256"],
        "role_gate": adjudication["role_review"],
        "pipeline": [
            {"step": "Commit", "owner": "Issuer", "artifact": "Answer-free challenge + hidden oracle commitment"},
            {"step": "Run", "owner": "Reproducer", "artifact": "Offline response + environment + methodology declarations"},
            {"step": "Review", "owner": "Reviewer", "artifact": "Relationship evidence + transcript/blinding review"},
            {"step": "Reveal", "owner": "Verifier", "artifact": "Recomputed receipt + in-toto byte binding + manifest"},
        ],
        "unlock_requirements": [
            "A producer commitment distinct from the issuer",
            "A reviewer commitment distinct from both parties",
            "No affiliate, contractor, same-organization, or unknown relationship",
            "Human review of relationship evidence, blinding, affordances, and transcript",
            "A pack whose oracle, receipt, statement, adjudication, and byte manifest recompute",
        ],
    }, federation


def build() -> dict:
    declarations, control_data, defender_data, benchmark = build_receipts()
    mesh_contract = {
        "mesh_version": "aau-cyber-defense-evidence-mesh/0.2",
        "mesh_id": "aau-collective-cyber-defense-reference-v1",
        "title": "AAU Collective Cyber Defense public reference mesh",
        "producer": "AAU maintainer reference implementation",
        "artifacts": declarations,
        "boundaries": {
            "public_safe_artifacts_only": True, "raw_logs_excluded": True, "personal_data_excluded": True,
            "credentials_and_targets_excluded": True, "aggregate_outcomes_only": True,
            "not_a_threat_intelligence_feed": True, "not_a_certification": True,
        },
    }
    write(MESH_CONTRACT, mesh_contract)
    index = build_index(MESH_CONTRACT)
    outcomes = evaluate_outcomes(index)
    suite = load(ROOT / "frontier-defense-benchmark/examples/collective-defense-suite.json")
    responses = load(ROOT / "frontier-defense-benchmark/examples/reference-protocol-responses.json")
    reproduction, federation = build_reproduction_demo(suite, responses)
    families = []
    for family, summary in benchmark["families"].items():
        families.append({"family": family, **summary})
    return {
        "data_version": "aau-collective-cyber-defense-site/0.2",
        "generated_on": "2026-08-29",
        "sources": [
            {"label": "Collective cyberdefense", "publisher": "OpenAI", "url": "https://openai.com/collective-cyberdefense/"},
            {"label": "Known Exploited Vulnerabilities Catalog", "publisher": "CISA", "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"},
            {"label": "AI Agent Standards Initiative", "publisher": "NIST", "url": "https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative"},
            {"label": "Agent Identity and Authorization", "publisher": "NIST NCCoE", "url": "https://www.nccoe.nist.gov/projects/software-and-ai-agent-identity-and-authorization"},
            {"label": "GenAI semantic conventions", "publisher": "OpenTelemetry", "url": "https://github.com/open-telemetry/semantic-conventions-genai"},
            {"label": "Automated benchmark evaluation practices", "publisher": "NIST", "url": "https://www.nist.gov/news-events/news/2026/01/towards-best-practices-automated-benchmark-evaluations"},
            {"label": "Blind evaluation in AITE", "publisher": "NIST", "url": "https://www.nist.gov/news-events/news/2026/07/announcing-nists-artificial-intelligence-technology-evaluation-aite"},
            {"label": "Detecting and preventing evaluation cheating", "publisher": "NIST CAISI", "url": "https://www.nist.gov/caisi/cheating-ai-agent-evaluations/4-practices-detecting-and-preventing-evaluation-cheating"},
            {"label": "Statement v1", "publisher": "in-toto", "url": "https://in-toto.io/Statement/v1"},
            {"label": "Provenance 1.2", "publisher": "SLSA", "url": "https://slsa.dev/spec/v1.2/provenance"},
            {"label": "Artifact attestations", "publisher": "GitHub", "url": "https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations"},
        ],
        "fixes": control_data["fixes"],
        "containment": control_data["containment"]["summary"],
        "defender": defender_data["assessment"]["summary"],
        "defender_example": defender_data["campaign"],
        "benchmark": {"summary": benchmark["summary"], "families": families},
        "mesh": {"record_count": index["record_count"], "records": index["records"], "interchange": index["interchange"]},
        "outcomes": outcomes,
        "reproduction": reproduction,
        "federation": federation,
        "routes": [
            {"title": "Prove the fix", "description": "Close the vulnerability while retaining the legitimate twin, service continuity, and rollback.", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/verified-fix-commons"},
            {"title": "Prove the stop", "description": "Measure parent, child, and queued-work containment, then gate restart on human evidence.", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/agent-containment-drills"},
            {"title": "Plan locally", "description": "Turn authorized inventory evidence into a continuity-aware vulnerability route without an upload.", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/essential-service-defender-box"},
            {"title": "Benchmark safely", "description": "Test bounded defensive reasoning across five families without invoking a live target or tool.", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/frontier-defense-benchmark"},
            {"title": "Exchange evidence", "description": "Publish hashes, evidence levels, measurements, and control fingerprints—not sensitive raw logs.", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/cyber-defense-evidence-mesh"},
            {"title": "Measure honestly", "description": "Keep heterogeneous observations separate and show missing independent reproduction as a gap.", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/public-defense-outcomes-observatory"},
            {"title": "Reproduce blindly", "description": "Commit a hidden oracle, separate issuer/reproducer/reviewer roles, bind every byte, and suppress small public-result cells.", "href": "https://github.com/immu4989/awesome-agentic-usecases/tree/main/independent-reproduction-exchange"},
        ],
        "boundary": {
            "reference_results_only": True, "no_live_targets": True, "no_exploit_payloads": True,
            "zero_upload_workbench": True, "no_vendor_or_agency_ranking": True,
            "not_field_effectiveness_or_certification": True,
        },
    }


def main() -> None:
    output = DOCS / "collective-cyber-defense-data.json"
    write(output, build())
    print(f"wrote {output.relative_to(ROOT)} and reference mesh receipts")


if __name__ == "__main__":
    main()
