#!/usr/bin/env python3
"""Generate the three reference Impact Capsules and the public showcase."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.evidence_commons import (  # noqa: E402
    BOUNDARY,
    CAPSULE_VERSION,
    PRIVACY_CONTRACT,
    comparison,
    render_json,
    sha256_bytes,
    validate_capsule,
)


COMMON_SOURCES = [
    {
        "title": "OMB M-25-21 — Accelerating Federal Use of AI",
        "publisher": "Office of Management and Budget",
        "url": "https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf",
        "reviewed_at": "2026-08-27",
        "supports": "Expected-benefit evidence compared with existing agency processes, lifecycle reassessment, and independent review for high-impact AI.",
    },
    {
        "title": "Evidence-Based Policymaking: Practices to Help Manage and Assess Results",
        "publisher": "U.S. Government Accountability Office",
        "url": "https://www.gao.gov/products/gao-23-105460",
        "reviewed_at": "2026-08-27",
        "supports": "Plan for results, assess and build evidence, use evidence, and sustain learning and continuous improvement.",
    },
    {
        "title": "NIST AI 700-2 — ARIA Pilot Evaluation Report",
        "publisher": "National Institute of Standards and Technology",
        "url": "https://doi.org/10.6028/NIST.AI.700-2",
        "reviewed_at": "2026-08-27",
        "supports": "Separate model testing, red teaming, and field testing rather than treating one synthetic score as real-world impact evidence.",
    },
    {
        "title": "Quality Improvement Activities FAQs",
        "publisher": "HHS Office for Human Research Protections",
        "url": "https://www.hhs.gov/ohrp/regulations-and-policy/guidance/faq/quality-improvement-activities/index.html",
        "reviewed_at": "2026-08-27",
        "supports": "The purpose and design of an activity—not an evaluation label alone—determine whether human-subject protections may apply.",
    },
]


REFERENCE_DEFINITIONS = [
    {
        "capsule_id": "foia-routing-impact-pilot",
        "title": "FOIA Routing & Requester Burden Pilot",
        "mission": "Test whether an assistive routing agent can send public-records requests to the correct component, preserve tracking and appeal paths, and reduce avoidable clarification burden without deciding disclosure, exemptions, fees, or appeals.",
        "service_area": "Government transparency and public records",
        "beneficiaries": [
            "People seeking federal records",
            "Agency FOIA intake and requester-service teams",
            "Public-interest and accountability organizations",
        ],
        "suite_path": "government-transparency/foia-routing-appeal-navigator/evals/scenarios.jsonl",
        "suite_id": "foia-routing-appeal-synthetic-v1",
        "receipt_path": "government-transparency/foia-routing-appeal-navigator/results/eval_deepseek-v4-flash.json",
        "primary_metric": "service_exact",
        "partner_role": "An authorized agency FOIA program owner working with a human-factors or evaluation reviewer",
        "partner_contribution": "Review the synthetic task set, define the existing routing process, approve a privacy-safe comparator protocol, and publish only aggregate burden and routing measures.",
        "authority": {
            "accountable_role": "Authorized agency FOIA official",
            "protected_decisions": [
                "Whether records are responsive, exempt, segregable, or releasable",
                "Whether to grant expedited processing, a fee waiver, or an appeal",
            ],
            "agent_may": [
                "Suggest a component, proactive disclosure, clarification path, or staffed contact",
                "Prepare a traceable routing recommendation for human review",
            ],
            "agent_must_not": [
                "Issue an adverse determination or invent an exemption",
                "Submit, close, redirect, or adjudicate a request without authorized review",
            ],
        },
        "measures": [
            ("routing-exact", "Exact component or public-source routing", "proportion", "increase", "FOIA requesters", "Current staffed-routing audit", "Four representative weeks", "Blindly score reviewed synthetic and approved operational samples against the authorized route", "Component structures and regulations differ across agencies"),
            ("clarification-burden", "Avoidable requester clarification contacts", "contacts per request", "decrease", "FOIA requesters", "Current request-management records", "Four representative weeks", "Compare aggregate clarification contacts under unchanged intake definitions", "Contact count does not measure clarity, accessibility, or requester effort by itself"),
            ("protected-decision-attempts", "Autonomous protected-decision attempts", "count", "hold_zero", "FOIA requesters and accountable officials", "Zero permitted attempts", "Every pilot interaction", "Count attempted and executed disclosure, exemption, fee, expedition, and appeal decisions separately", "A zero count does not prove other routing or service behavior is correct"),
        ],
        "domain_source": {
            "title": "Guidance for Agency FOIA Regulations",
            "publisher": "U.S. Department of Justice, Office of Information Policy",
            "url": "https://www.justice.gov/oip/oip-guidance/guidance-agency-foia-regulations",
            "reviewed_at": "2026-08-27",
            "supports": "Public access, proactive disclosure, routing, response procedures, and agency-specific implementation boundaries.",
        },
        "limitations": [
            "The committed model result covers eight synthetic cases repeated three times, not production requests.",
            "A perfect synthetic routing score does not measure requester effort, accessibility, records-search quality, or lawful disclosure.",
            "Agency component structures and FOIA regulations vary and require local review.",
            "No observed human comparator, public-value observation, or independent reproduction is present.",
        ],
        "transfer": {
            "holds_when": ["The agency component map, public sources, deadlines, and protected authority match the reviewed task contract"],
            "fails_when": ["Another agency has different component jurisdiction, submission rules, appeal procedures, or source freshness"],
            "revalidate_on": ["Component reorganization, FOIA regulation change, portal change, source update, or workflow authority change"],
        },
    },
    {
        "capsule_id": "accessibility-remediation-impact-pilot",
        "title": "Accessible Digital Service Remediation Pilot",
        "mission": "Test whether an assistive agent can identify and route accessibility defects, propose a verifiable remediation plan, and reduce rework while keeping conformance, acceptance, and deployment decisions with authorized accessibility staff.",
        "service_area": "Accessible federal digital services",
        "beneficiaries": [
            "People with disabilities using public digital services",
            "Section 508 and accessibility testing teams",
            "Government content, design, engineering, and procurement teams",
        ],
        "suite_path": "accessibility-digital-services/accessibility-remediation-verifier/evals/scenarios.jsonl",
        "suite_id": "accessibility-remediation-synthetic-v1",
        "receipt_path": "accessibility-digital-services/accessibility-remediation-verifier/results/eval_deepseek-v4-flash.json",
        "primary_metric": "remediation_exact",
        "partner_role": "A Section 508 program manager or accessibility lead working with disabled users and independent testers",
        "partner_contribution": "Review the defect taxonomy and verification criteria, define the current remediation workflow, authorize an accessible evaluation protocol, and publish aggregate defect, rework, and burden measures.",
        "authority": {
            "accountable_role": "Authorized accessibility or Section 508 program official",
            "protected_decisions": [
                "Whether a service conforms with applicable accessibility requirements",
                "Whether remediation is accepted or a digital service is approved for release",
            ],
            "agent_may": [
                "Identify likely defect classes and propose testable remediation steps",
                "Route evidence to the responsible content, design, engineering, or procurement owner",
            ],
            "agent_must_not": [
                "Declare conformance from automated checks alone",
                "Approve a release, close a defect, or substitute for disabled-user and expert testing",
            ],
        },
        "measures": [
            ("verified-defect-coverage", "Verified defect coverage", "proportion", "increase", "Disabled users", "Current human accessibility audit", "One representative release cycle", "Score defects only after the approved manual and assistive-technology verification path", "Coverage depends on representative tasks, content, devices, and assistive technologies"),
            ("remediation-rework", "Remediation rework cycles", "cycles per verified defect", "decrease", "Accessibility, content, design, and engineering teams", "Current issue-tracker aggregate", "One representative release cycle", "Compare rework under a frozen definition of verified defect and accepted fix", "Lower rework can hide missed defects unless coverage remains visible"),
            ("false-conformance", "Unsupported conformance declarations", "count", "hold_zero", "Disabled users and accountable service owners", "Zero permitted declarations", "Every pilot artifact", "Count any conformance claim lacking the required authorized evidence and review", "Zero false declarations does not prove the service is accessible"),
        ],
        "domain_source": {
            "title": "Revised 508 Standards and 255 Guidelines",
            "publisher": "U.S. Access Board",
            "url": "https://www.access-board.gov/ict/",
            "reviewed_at": "2026-08-27",
            "supports": "Functional performance criteria and technical accessibility requirements for covered information and communication technology.",
        },
        "limitations": [
            "The committed model result covers eight synthetic defects repeated three times, not a production service.",
            "Automated or scenario-based success cannot establish accessibility conformance.",
            "Representative disabled-user and assistive-technology testing is not present.",
            "No observed human comparator, public-value observation, or independent reproduction is present.",
        ],
        "transfer": {
            "holds_when": ["The content type, user task, platform, assistive technologies, and verification protocol match the reviewed scope"],
            "fails_when": ["A different platform, component library, procurement scope, disability context, or testing method changes the evidence needed"],
            "revalidate_on": ["Major design-system, platform, content, accessibility-standard, assistive-technology, or release-process change"],
        },
    },
    {
        "capsule_id": "grant-obligation-impact-pilot",
        "title": "Small-Nonprofit Grant Obligation Evidence Pilot",
        "mission": "Test whether an assistive agent can turn a grant award into a complete, source-linked obligation checklist and reduce follow-up burden while leaving allowability, enforcement, payment, and funding decisions with authorized people.",
        "service_area": "Federal grants and nonprofit administration",
        "beneficiaries": [
            "Small nonprofits with limited grants-administration capacity",
            "Federal awarding-agency and pass-through monitoring teams",
            "Program, finance, and compliance staff responsible for grant evidence",
        ],
        "suite_path": "nonprofit-grant-management/grant-obligation-evidence-navigator/evals/scenarios.jsonl",
        "suite_id": "grant-obligation-evidence-synthetic-v1",
        "receipt_path": "nonprofit-grant-management/grant-obligation-evidence-navigator/results/eval_deepseek-v4-flash.json",
        "primary_metric": "decision_gate_exact",
        "partner_role": "A grants management specialist and small-nonprofit operations partner working with an evaluation reviewer",
        "partner_contribution": "Review the obligation and evidence taxonomy, define the existing checklist workflow, approve a minimum-data comparator protocol, and publish only aggregate completeness and burden measures.",
        "authority": {
            "accountable_role": "Authorized grants management or pass-through entity official",
            "protected_decisions": [
                "Whether a cost is allowable or an obligation is satisfied",
                "Whether to approve payment, impose a remedy, enforce, suspend, terminate, or award funding",
            ],
            "agent_may": [
                "Extract declared obligations and identify missing evidence for human review",
                "Prepare a source-linked checklist and deadline reminder",
            ],
            "agent_must_not": [
                "Decide allowability, compliance, payment, enforcement, or award status",
                "Invent award terms or request information beyond the reviewed minimum set",
            ],
        },
        "measures": [
            ("obligation-coverage", "Exact reviewed-obligation coverage", "proportion", "increase", "Small nonprofits and grants reviewers", "Current dual-reviewed checklist", "One representative reporting cycle", "Blindly compare source-linked obligation and missing-evidence sets under an unchanged award sample", "A checklist cannot determine whether evidence is authentic or a cost is allowable"),
            ("follow-up-burden", "Avoidable follow-up requests", "requests per award", "decrease", "Small nonprofit program and finance staff", "Current grants-management aggregate", "One representative reporting cycle", "Count repeated or out-of-scope evidence requests using a predeclared coding guide", "Lower request counts can conceal unresolved evidence gaps"),
            ("protected-grant-decisions", "Autonomous protected grant decisions", "count", "hold_zero", "Applicants, recipients, and accountable officials", "Zero permitted decisions", "Every pilot interaction", "Count attempted and executed allowability, payment, enforcement, and award decisions separately", "A zero count does not establish checklist correctness or grant compliance"),
        ],
        "domain_source": {
            "title": "2 CFR Part 200 — Uniform Administrative Requirements, Cost Principles, and Audit Requirements for Federal Awards",
            "publisher": "Electronic Code of Federal Regulations",
            "url": "https://www.ecfr.gov/current/title-2/subtitle-A/chapter-II/part-200",
            "reviewed_at": "2026-08-27",
            "supports": "Current federal award administration, internal control, financial management, records, monitoring, and remedy requirements.",
        },
        "limitations": [
            "The committed model result covers eight synthetic awards repeated three times, not live grant files.",
            "The primary decision-gate metric is 0.75, leaving a visible synthetic evidence gap.",
            "Award-specific terms, statutes, program rules, and pass-through requirements can change the obligation set.",
            "No observed human comparator, public-value observation, or independent reproduction is present.",
        ],
        "transfer": {
            "holds_when": ["The award terms, assistance listing, reporting period, pass-through role, and evidence definitions match the reviewed contract"],
            "fails_when": ["A different program, award instrument, special condition, statute, cost principle, or pass-through policy changes the obligation set"],
            "revalidate_on": ["Award amendment, reporting-period change, rule update, pass-through requirement change, or monitoring finding"],
        },
    },
]


def artifact_hash(relative: str) -> str:
    return sha256_bytes((ROOT / relative).read_bytes())


def snapshot_suite(definition: dict, receipt: dict) -> str:
    source = ROOT / definition["suite_path"]
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    receipt_ids = sorted({row["scenario_id"] for row in receipt["results"]})
    selected = [row for row in rows if row["scenario_id"] in receipt_ids]
    if len(selected) != receipt["n_scenarios"] or {
        row["scenario_id"] for row in selected
    } != set(receipt_ids):
        raise RuntimeError(f"cannot reconstruct scenario-id snapshot for {definition['capsule_id']}")
    relative = f"evidence-commons/reference-suites/{definition['capsule_id']}.jsonl"
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in selected))
    return relative


def build_capsule(definition: dict) -> dict:
    receipt_path = definition["receipt_path"]
    receipt = json.loads((ROOT / receipt_path).read_text())
    suite_path = snapshot_suite(definition, receipt)
    scenario_ids = sorted({row["scenario_id"] for row in receipt["results"]})
    metric_name = definition["primary_metric"]
    metric_value = receipt["metric_means"][metric_name]
    metric_interval = receipt["metric_ci95"][metric_name]
    measures = [
        {
            "metric_id": row[0],
            "name": row[1],
            "unit": row[2],
            "direction": row[3],
            "affected_group": row[4],
            "baseline_source": row[5],
            "measurement_window": row[6],
            "method": row[7],
            "limitation": row[8],
        }
        for row in definition["measures"]
    ]
    capsule = {
        "capsule_version": CAPSULE_VERSION,
        "capsule_id": definition["capsule_id"],
        "title": definition["title"],
        "mission": definition["mission"],
        "service_area": definition["service_area"],
        "status": "partner_sought",
        "origin": "maintainer_reference",
        "beneficiaries": definition["beneficiaries"],
        "artifacts": {
            "suite": {
                "artifact_id": "suite",
                "kind": "domain_scenario_set",
                "path": suite_path,
                "sha256": artifact_hash(suite_path),
                "classification": "synthetic",
                "suite_id": definition["suite_id"],
                "suite_kind": "domain_scenario_jsonl",
                "scenario_count": receipt["n_scenarios"],
                "provenance_note": "Eight current catalog scenarios selected by the historical receipt's scenario identifiers. The receipt did not record a suite hash, so identical evaluated bytes are not claimed.",
            },
            "agent_receipt": {
                "artifact_id": "agent-receipt",
                "kind": "domain_agent_evaluation",
                "path": receipt_path,
                "sha256": artifact_hash(receipt_path),
                "classification": "aggregate_public",
                "receipt_kind": "aau_domain_eval",
                "model": receipt["model"],
                "suite_binding": "scenario_ids_only",
                "scenario_ids_sha256": sha256_bytes(render_json(scenario_ids).encode()),
                "primary_metric": {
                    "name": metric_name,
                    "value": metric_value,
                    "interval_95": metric_interval,
                    "scenario_count": receipt["n_scenarios"],
                    "repeats": receipt["n_repeats"],
                    "observation_count": receipt["n_scenarios"] * receipt["n_repeats"],
                    "mean_cost_per_scenario_usd": receipt["mean_cost_per_scenario_usd"],
                    "p50_latency_s": receipt["p50_latency_s"],
                },
            },
            "human_study": None,
            "human_baseline": None,
            "public_value_observation": None,
            "reproduction": None,
        },
        "measurement_plan": measures,
        "partner_call": {
            "open": True,
            "role": definition["partner_role"],
            "contribution": definition["partner_contribution"],
            "contact_url": "https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=evidence-partner.yml",
            "prohibited_data": [
                "Names, email addresses, demographics, or participant-level responses",
                "Production case records, protected data, credentials, or controlled information",
                "Worker rankings, employment decisions, or unsupported certification claims",
            ],
        },
        "human_authority": definition["authority"],
        "evidence_quality": {
            "relevance_and_utility": "declared",
            "rigor": "synthetic_scenarios",
            "independence": "maintainer_reference",
            "transparency": "artifact_bound",
            "ethics": "institutional_determination_required_before_human_observation",
        },
        "privacy": dict(PRIVACY_CONTRACT),
        "transfer": definition["transfer"],
        "sources": [*COMMON_SOURCES, definition["domain_source"]],
        "limitations": [
            "The historical model receipt did not record a suite hash. Its eight scenario identifiers match this snapshot, but identical evaluated input bytes are not proven.",
            *definition["limitations"],
        ],
        "boundary": BOUNDARY,
    }
    return validate_capsule(capsule, ROOT)


def build_data(capsules: list[dict]) -> dict:
    rows = []
    for capsule in capsules:
        result = comparison(capsule)
        agent = capsule["artifacts"]["agent_receipt"]
        rows.append(
            {
                "id": capsule["capsule_id"],
                "title": capsule["title"],
                "mission": capsule["mission"],
                "service_area": capsule["service_area"],
                "status": result["derived_status"],
                "beneficiaries": capsule["beneficiaries"],
                "agent": {
                    "model": agent["model"],
                    **agent["primary_metric"],
                    "sha256": agent["sha256"],
                },
                "human_comparator": result["human_comparator"],
                "public_value_observed": result["public_value_observed"],
                "reproduction": result["reproduction"],
                "missing_evidence": result["missing_evidence"],
                "next_evidence": result["next_evidence"],
                "measurement_plan": capsule["measurement_plan"],
                "partner_call": capsule["partner_call"],
                "human_authority": capsule["human_authority"],
                "transfer": capsule["transfer"],
                "sources": capsule["sources"],
                "limitations": capsule["limitations"],
                "capsule_path": f"evidence-commons/capsules/{capsule['capsule_id']}.json",
            }
        )
    return {
        "schema_version": "aau-evidence-commons-browser/1.0",
        "generated_on": "2026-08-27",
        "stages": [
            {"id": "synthetic_reference", "label": "Synthetic reference", "meaning": "Reviewed public artifacts only"},
            {"id": "partner_sought", "label": "Partner sought", "meaning": "A bounded aggregate study gap is open"},
            {"id": "study_reviewed", "label": "Study reviewed", "meaning": "Suite-bound protocol only; institutional determination remains required"},
            {"id": "aggregate_published", "label": "Aggregate published", "meaning": "Observed aggregate only; no participant records"},
            {"id": "independently_reproduced", "label": "Reproduced", "meaning": "Independence is attested, not identity-verified"},
        ],
        "stats": {
            "capsules": len(rows),
            "open_partner_calls": sum(row["partner_call"]["open"] for row in rows),
            "observed_human_baselines": sum(row["human_comparator"] is not None for row in rows),
            "independent_reproductions": sum(row["reproduction"] is not None for row in rows),
            "visible_gaps": sum(len(row["missing_evidence"]) for row in rows),
        },
        "capsules": rows,
        "privacy": {"uploads": 0, "persistence": False, "participant_records": False},
        "boundary": BOUNDARY,
    }


def launch_svg(data: dict) -> str:
    stats = data["stats"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">AAU Evidence Commons</title>
  <desc id="desc">Three open partner calls connect synthetic agent evidence to human baselines, public value, and independent reproduction.</desc>
  <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#06121b"/><stop offset=".52" stop-color="#122f3b"/><stop offset="1" stop-color="#2b1835"/></linearGradient><linearGradient id="rail"><stop stop-color="#67e8c1"/><stop offset=".5" stop-color="#67a9ff"/><stop offset="1" stop-color="#dd91ff"/></linearGradient></defs>
  <rect width="1200" height="630" rx="42" fill="url(#bg)"/><path d="M0 500L1200 160M0 590L1200 250" stroke="#8bbbd0" opacity=".07" stroke-width="70"/>
  <g font-family="ui-monospace,SFMono-Regular,Menlo,monospace"><text x="68" y="65" fill="#67e8c1" font-size="17" letter-spacing="4">AAU / EVIDENCE COMMONS</text><text x="68" y="132" fill="#fff" font-size="40" font-weight="900">From a score to a public evidence chain.</text><text x="68" y="173" fill="#abc1d0" font-size="19">Artifact-bound · aggregate-only · every missing claim stays visible</text></g>
  <path d="M115 325H1085" stroke="#294657" stroke-width="14" stroke-linecap="round"/><path d="M115 325H360" stroke="url(#rail)" stroke-width="14" stroke-linecap="round"/>
  <g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" text-anchor="middle"><g fill="#06121b" font-size="14" font-weight="900"><circle cx="115" cy="325" r="44" fill="#67e8c1"/><text x="115" y="321">AGENT</text><text x="115" y="340">RECEIPT</text><circle cx="360" cy="325" r="44" fill="#78c9dc"/><text x="360" y="321">PARTNER</text><text x="360" y="340">SOUGHT</text><circle cx="600" cy="325" r="44" fill="#536f80"/><text x="600" y="321">HUMAN</text><text x="600" y="340">BASELINE</text><circle cx="842" cy="325" r="44" fill="#536f80"/><text x="842" y="321">PUBLIC</text><text x="842" y="340">VALUE</text><circle cx="1085" cy="325" r="44" fill="#536f80"/><text x="1085" y="321">REPRO-</text><text x="1085" y="340">DUCED</text></g></g>
  <g font-family="ui-monospace,SFMono-Regular,Menlo,monospace"><text x="68" y="485" fill="#91aaba" font-size="13">OPEN PILOT CAPSULES</text><text x="68" y="535" fill="#fff" font-size="38" font-weight="900">{stats['capsules']}</text><text x="315" y="485" fill="#91aaba" font-size="13">PARTNER CALLS</text><text x="315" y="535" fill="#67e8c1" font-size="38" font-weight="900">{stats['open_partner_calls']}</text><text x="555" y="485" fill="#91aaba" font-size="13">VISIBLE GAPS</text><text x="555" y="535" fill="#ffc96b" font-size="38" font-weight="900">{stats['visible_gaps']}</text><text x="795" y="485" fill="#91aaba" font-size="13">PARTICIPANT RECORDS</text><text x="795" y="535" fill="#fff" font-size="38" font-weight="900">0</text><text x="68" y="594" fill="#67e8c1" font-size="14">NO TRUST SCORE · NO WORKER RANKING · NO GOVERNMENT ENDORSEMENT</text></g>
</svg>'''


def main() -> None:
    capsule_root = ROOT / "evidence-commons" / "capsules"
    capsule_root.mkdir(parents=True, exist_ok=True)
    capsules = [build_capsule(item) for item in REFERENCE_DEFINITIONS]
    for capsule in capsules:
        (capsule_root / f"{capsule['capsule_id']}.json").write_text(render_json(capsule))
    data = build_data(capsules)
    (ROOT / "docs" / "evidence-commons-data.json").write_text(render_json(data))
    (ROOT / "docs" / "assets" / "evidence-commons.svg").write_text(launch_svg(data))
    print(
        f"wrote Evidence Commons — {data['stats']['capsules']} capsules, "
        f"{data['stats']['visible_gaps']} visible gaps"
    )


if __name__ == "__main__":
    main()
