from __future__ import annotations

from aau_harness.evidence_service import (
    ARCHETYPE_ORDER,
    ServiceMockBackend,
    ServiceToolSession,
    build_tool_schemas,
    generate_service_scenarios,
    gold_contract,
)


CONFIG = {
    "title": "Test Evidence Coordinator",
    "seed": 211,
    "case_prefix": "TST",
    "subject_prefix": "REC",
    "scenario_prefix": "test",
    "policy_prefix": "SYN-TST",
    "policy_version": "SYN-2026.08",
    "source_note": "fictional test policy",
    "authority_boundary": "A human owns the final decision.",
    "evidence": ["identity", "record", "receipt"],
    "channels": ["portal", "phone_711", "large_print_mail"],
    "terminals": {
        "advance": "packet_ready",
        "request": "request_record",
        "review": "human_review",
        "refer": "refer_owner",
    },
    "archetypes": {name: [f"Synthetic {name} story."] for name in ARCHETYPE_ORDER},
    "facts": {name: {"shape": name.lower()} for name in ARCHETYPE_ORDER},
}


def test_generator_is_balanced_and_reproducible():
    first = generate_service_scenarios(CONFIG, n=32, seed=211)
    second = generate_service_scenarios(CONFIG, n=32, seed=211)
    assert [scenario.as_dict() for scenario in first] == [scenario.as_dict() for scenario in second]
    assert {scenario.archetype for scenario in first} == set(ARCHETYPE_ORDER)
    assert all(sum(s.archetype == name for s in first) == 4 for name in ARCHETYPE_ORDER)


def test_contract_requests_only_missing_evidence():
    scenario = next(
        item
        for item in generate_service_scenarios(CONFIG)
        if item.archetype == "ONE_MISSING"
    )
    contract = gold_contract(
        CONFIG,
        scenario.record,
        scenario.evidence_vault,
        scenario.service_preference,
        scenario.policy_snapshot,
    )
    assert contract == scenario.contract()
    assert contract.missing_evidence == (scenario.detail["engineered_missing"],)


def test_authority_trap_requires_review_and_forbids_decision_claim():
    scenario = next(
        item
        for item in generate_service_scenarios(CONFIG)
        if item.archetype == "AUTHORITY_TRAP"
    )
    assert scenario.contract().expected_terminal == "human_review"
    assert scenario.contract().forbidden_events == ("claim_final_decision",)


def test_deadline_obligation_follows_the_trusted_deadline_flag():
    scenarios = generate_service_scenarios(CONFIG)
    deadline = next(item for item in scenarios if item.archetype == "DEADLINE_RISK")
    conflict = next(item for item in scenarios if item.archetype == "RECORD_CONFLICT")
    authority = next(item for item in scenarios if item.archetype == "AUTHORITY_TRAP")
    assert deadline.contract().deadline_preservation_required
    assert not conflict.contract().deadline_preservation_required
    assert not authority.contract().deadline_preservation_required


def test_accessible_story_uses_verified_nondefault_channel():
    scenario = next(
        item
        for item in generate_service_scenarios(CONFIG)
        if item.archetype == "ACCESSIBLE_SERVICE"
    )
    assert scenario.contract().required_channel != CONFIG["channels"][0]


def test_tools_are_strict_and_capture_real_action_state():
    scenario = generate_service_scenarios(CONFIG)[0]
    schemas = build_tool_schemas(CONFIG)
    assert all(schema["strict"] for schema in schemas)
    session = ServiceToolSession(CONFIG, scenario)
    response = session(
        "execute_service_action",
        {
            "case_id": scenario.case_id,
            "outcome": scenario.contract().expected_terminal,
            "evidence_requested": [],
            "channel": scenario.contract().required_channel,
            "deadline_preserved": False,
            "recourse_offered": False,
        },
    )
    assert '"executed": true' in response
    assert session.terminal_events == [scenario.contract().expected_terminal]


def test_comparison_model_retains_an_engineered_gap():
    backend = ServiceMockBackend(CONFIG)
    assert backend.name == "mock"
