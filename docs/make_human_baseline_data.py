#!/usr/bin/env python3
"""Generate the Human Baseline Lab reference pack, report, site data, and visual."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness" / "src"))

from aau_harness.evaluate import AdapterResult, evaluate_suite, load_suite  # noqa: E402
from aau_harness.human_baseline import (  # noqa: E402
    ABSTAIN,
    SESSION_BOUNDARY,
    SESSION_VERSION,
    build_pack_files,
    build_study,
    render_json,
    sha256_json,
    summarize_sessions,
    validate_pack,
    validate_report,
    validate_session,
)


LAB = ROOT / "human-baseline-lab"
PACK = LAB / "reference-pack"
SESSIONS = LAB / "sessions"


def make_session(
    study: dict,
    answer_key: dict,
    index: int,
    *,
    errors: set[str] | None = None,
    abstains: set[str] | None = None,
) -> dict:
    errors = errors or set()
    abstains = abstains or set()
    responses = []
    for position, case in enumerate(study["cases"]):
        scenario_id = case["scenario_id"]
        expected = answer_key["answers"][scenario_id]
        if scenario_id in abstains:
            outcome = ABSTAIN
        elif scenario_id in errors:
            outcome = next(value for value in study["outcomes"] if value != expected)
        else:
            outcome = expected
        responses.append(
            {
                "scenario_id": scenario_id,
                "outcome": outcome,
                "confidence": min(95, 63 + position * 4 - len(errors) * 3),
                "elapsed_ms": 9200 + position * 1150 + index * 420,
            }
        )
    session = {
        "session_version": SESSION_VERSION,
        "study_id": study["study_id"],
        "study_sha256": sha256_json(study),
        "anonymous_session_id": f"{index:012x}",
        "session_kind": "synthetic_reference",
        "participant_role": study["participant_roles"][(index - 1) % 3],
        "protection_basis": "synthetic_only",
        "responses": responses,
        "boundary": SESSION_BOUNDARY,
    }
    validate_session(session, study)
    return session


def agent_receipt(suite: dict) -> dict:
    answers = {
        case["scenario_id"]: case["expected"]["outcome"] for case in suite["cases"]
    }
    outcomes = list(dict.fromkeys(answers.values()))
    engineered_errors = {"service-006", "service-007"}

    def adapter(payload: dict) -> AdapterResult:
        expected = answers[payload["scenario_id"]]
        outcome = (
            next(value for value in outcomes if value != expected)
            if payload["scenario_id"] in engineered_errors
            else expected
        )
        return AdapterResult(
            {
                "outcome": outcome,
                "actions_attempted": [],
                "actions_executed": [],
                "submitted": True,
            },
            0.041,
        )

    receipt, _ = evaluate_suite(suite, adapter, "command")
    return receipt


def launch_svg(report: dict) -> str:
    metrics = report["metrics"]
    agent = report["agent_comparison"]
    exact = round(metrics["outcome_exact_rate"] * 100)
    agent_exact = round(agent["agent_exact_rate"] * 100)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
  <title id="title">AAU Human Baseline Lab</title>
  <desc id="desc">A blinded local study compares aggregate human task evidence with an agent receipt while protecting participant and human authority boundaries.</desc>
  <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#07121b"/><stop offset=".55" stop-color="#12243a"/><stop offset="1" stop-color="#2a1735"/></linearGradient></defs>
  <rect width="1200" height="630" rx="38" fill="url(#bg)"/><path d="M70 205H1130M70 474H1130" stroke="#29445b" stroke-width="2"/>
  <g font-family="ui-monospace,SFMono-Regular,Menlo,monospace" fill="#edf7ff">
    <text x="70" y="68" fill="#58e1ba" font-size="17" letter-spacing="4">AAU / HUMAN BASELINE LAB</text>
    <text x="70" y="126" font-size="39" font-weight="800">An agent score answers half the question.</text>
    <text x="70" y="169" fill="#a4b9ca" font-size="19">Blind the task · measure the existing process · compare without ranking people</text>
    <g transform="translate(70 245)"><rect width="490" height="170" rx="22" fill="#102a31" stroke="#58e1ba" stroke-width="2"/><text x="28" y="38" fill="#58e1ba" font-size="14">SYNTHETIC PROTOCOL CHECK</text><text x="28" y="101" font-size="49" font-weight="800">{exact}%</text><text x="170" y="94" fill="#a4b9ca" font-size="16">aggregate exact</text><text x="28" y="138" fill="#a4b9ca" font-size="15">5 reference sessions · 40 task responses</text></g>
    <g transform="translate(640 245)"><rect width="490" height="170" rx="22" fill="#1a2742" stroke="#73a8ff" stroke-width="2"/><text x="28" y="38" fill="#73a8ff" font-size="14">ENGINEERED AGENT RECEIPT</text><text x="28" y="101" font-size="49" font-weight="800">{agent_exact}%</text><text x="170" y="94" fill="#a4b9ca" font-size="16">same-suite exact</text><text x="28" y="138" fill="#a4b9ca" font-size="15">descriptive only · no superiority claim</text></g>
    <text x="70" y="515" fill="#ffc96b" font-size="14">HUMAN-PROTECTION CHECKPOINT</text><text x="70" y="553" font-size="20" font-weight="700">Real participants require an institutional determination before collection.</text>
    <text x="70" y="599" fill="#58e1ba" font-size="14">ZERO UPLOADS · NO DIRECT IDENTIFIERS · AGGREGATE REPORT · SHA-256 SESSION BINDINGS</text>
  </g>
</svg>'''


def main() -> None:
    suite = load_suite(LAB / "reference-suite.json")
    study, answer_key = build_study(
        suite,
        study_id="public-service-routing-human-baseline",
        title="Public Service Routing Human Baseline",
        purpose=(
            "Demonstrate blinded same-suite measurement of routing accuracy, abstention, "
            "task time, confidence calibration, and agreement without production data."
        ),
    )
    PACK.mkdir(parents=True, exist_ok=True)
    for name, contents in build_pack_files(study, answer_key).items():
        (PACK / name).write_text(contents)
    checked = validate_pack(PACK)

    patterns = [
        ({}, {}),
        ({"service-006"}, {}),
        ({"service-007"}, {}),
        ({"service-002"}, {}),
        ({}, {"service-005"}),
    ]
    sessions = [
        make_session(study, answer_key, index, errors=set(errors), abstains=set(abstains))
        for index, (errors, abstains) in enumerate(patterns, start=1)
    ]
    SESSIONS.mkdir(parents=True, exist_ok=True)
    for index, session in enumerate(sessions, start=1):
        (SESSIONS / f"synthetic-{index:02d}.json").write_text(render_json(session))

    receipt = agent_receipt(suite)
    (LAB / "reference-agent-receipt.json").write_text(render_json(receipt))
    report = summarize_sessions(study, answer_key, sessions, agent_receipt=receipt)
    validate_report(report)
    (LAB / "reference-report.json").write_text(render_json(report))

    browser_data = {
        "schema_version": "aau-human-baseline-browser/1.0",
        "study": study,
        "practice_answer_key": answer_key["answers"],
        "reference": {
            "report_metrics": report["metrics"],
            "session_count": report["source"]["session_count"],
            "session_kind": "synthetic_reference",
            "agent_comparison": report["agent_comparison"],
        },
        "sources": [
            {
                "id": "nist-ai-700-2",
                "title": "NIST AI 700-2 — ARIA Pilot Evaluation Report",
                "url": "https://doi.org/10.6028/NIST.AI.700-2",
                "supports": "Separate model testing, red teaming, field testing, and questionnaire evidence.",
            },
            {
                "id": "omb-m-25-21",
                "title": "OMB M-25-21",
                "url": "https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf",
                "supports": "Expected benefit and impact measures compared with existing agency processes.",
            },
            {
                "id": "hhs-common-rule",
                "title": "HHS Common Rule",
                "url": "https://www.hhs.gov/ohrp/regulations-and-policy/regulations/common-rule/index.html",
                "supports": "Institutional responsibility for human-subjects determinations and protections.",
            },
        ],
        "privacy": {
            "uploads": 0,
            "persistence": False,
            "direct_identifiers": False,
            "practice_only": True,
        },
        "boundary": report["boundary"],
    }
    (ROOT / "docs" / "human-baseline-data.json").write_text(render_json(browser_data))
    (ROOT / "docs" / "assets" / "human-baseline.svg").write_text(launch_svg(report))
    print(
        "wrote Human Baseline Lab — "
        f"{checked['case_count']} cases, {len(sessions)} synthetic sessions, "
        f"agent exact {receipt['metrics']['exact_rate']:.3f}"
    )


if __name__ == "__main__":
    main()
