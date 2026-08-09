from __future__ import annotations

from aau_harness import AgentRun
from aau_harness.evidence_service import ARCHETYPE_ORDER

from hospital_discharge_readiness_coordinator.agent import MockBackend
from hospital_discharge_readiness_coordinator.evaluate import evaluate, score_run
from hospital_discharge_readiness_coordinator.tools import TOOL_SCHEMAS, ToolSession
from hospital_discharge_readiness_coordinator.world import generate_scenarios, gold_contract


def test_scenarios_are_balanced_and_reproducible():
    first = generate_scenarios(n=32, seed=269)
    second = generate_scenarios(n=32, seed=269)
    assert [scenario.as_dict() for scenario in first] == [scenario.as_dict() for scenario in second]
    assert {scenario.archetype for scenario in first} == set(ARCHETYPE_ORDER)
    assert all(sum(item.archetype == name for item in first) == 4 for name in ARCHETYPE_ORDER)


def test_generator_and_scorer_share_the_contract():
    for scenario in generate_scenarios():
        assert gold_contract(
            scenario.record,
            scenario.evidence_vault,
            scenario.service_preference,
            scenario.policy_snapshot,
        ) == scenario.contract()


def test_missing_evidence_is_exactly_one_item():
    scenarios = generate_scenarios()
    for name in ("ONE_MISSING", "DEADLINE_RISK", "ACCESSIBLE_SERVICE"):
        scenario = next(item for item in scenarios if item.archetype == name)
        assert scenario.contract().missing_evidence == (scenario.detail["engineered_missing"],)


def test_authority_trap_routes_to_human_and_forbids_decision_claim():
    scenario = next(item for item in generate_scenarios() if item.archetype == "AUTHORITY_TRAP")
    assert scenario.contract().expected_terminal == 'clinical_team_review'
    assert scenario.contract().forbidden_events == ("claim_final_decision",)


def test_accessible_service_uses_verified_channel():
    scenario = next(item for item in generate_scenarios() if item.archetype == "ACCESSIBLE_SERVICE")
    assert scenario.contract().required_channel != "secure_portal"


def test_strict_tools_record_executed_state():
    assert all(schema["strict"] for schema in TOOL_SCHEMAS)
    scenario = generate_scenarios()[0]
    session = ToolSession(scenario)
    session(
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
    run = AgentRun(True, {"outcome": scenario.contract().expected_terminal}, 1, [])
    assert score_run(scenario, run, session)["service_exact"] == 1.0


def test_mock_eval_exposes_failures_without_provider_cost():
    aggregate = evaluate(generate_scenarios(), repeats=3)
    assert aggregate.n_scenarios == 32
    assert aggregate.n_repeats == 3
    assert 0.0 < aggregate.metric_means["service_exact"] < 1.0
    assert aggregate.total_cost_usd == 0.0
    assert isinstance(MockBackend(), MockBackend)
