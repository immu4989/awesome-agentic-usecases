from __future__ import annotations

from aau_harness import AgentRun
from aau_harness.decision_gate import ARCHETYPE_ORDER

from ind_safety_reporting_coordinator.agent import MockBackend
from ind_safety_reporting_coordinator.evaluate import evaluate, score_run
from ind_safety_reporting_coordinator.tools import TOOL_SCHEMAS, ToolSession
from ind_safety_reporting_coordinator.world import generate_scenarios


def test_scenarios_are_balanced_and_reproducible():
    first = generate_scenarios(n=32, seed=457)
    second = generate_scenarios(n=32, seed=457)
    assert [scenario.as_dict() for scenario in first] == [scenario.as_dict() for scenario in second]
    assert {scenario.archetype for scenario in first} == set(ARCHETYPE_ORDER)
    assert all(sum(item.archetype == name for item in first) == 4 for name in ARCHETYPE_ORDER)


def test_transfer_trap_has_a_distinct_required_path():
    scenarios = generate_scenarios()
    ready = next(item for item in scenarios if item.archetype == "READY")
    transfer = next(item for item in scenarios if item.archetype == "TRANSFER_TRAP")
    assert transfer.contract().transfer_specificity_required
    assert (transfer.contract().expected_terminal, transfer.contract().expected_reason_code) != (ready.contract().expected_terminal, ready.contract().expected_reason_code)


def test_conjunctive_gate_contains_a_failed_condition():
    scenario = next(item for item in generate_scenarios() if item.archetype == "CONJUNCTIVE_GATE")
    assert "failed" in scenario.record["gate_states"].values()


def test_authority_trap_forbids_protected_decision():
    scenario = next(item for item in generate_scenarios() if item.archetype == "AUTHORITY_TRAP")
    assert scenario.contract().forbidden_events == ("claim_protected_decision",)
    assert scenario.contract().expected_terminal == 'sponsor_medical_safety_review'


def test_strict_tools_can_produce_an_exact_trace():
    assert all(schema["strict"] for schema in TOOL_SCHEMAS)
    scenario = generate_scenarios()[0]
    contract = scenario.contract()
    session = ToolSession(scenario)
    session("execute_gate_action", {"case_id": scenario.case_id, "outcome": contract.expected_terminal, "reason_code": contract.expected_reason_code, "evidence_relied_on": list(contract.held_evidence), "evidence_requested": list(set(contract.required_evidence) - set(contract.held_evidence)), "gates_confirmed": list(contract.satisfied_gates), "rights_notice_preserved": contract.rights_notice_required, "deadline_preserved": contract.deadline_preservation_required, "confidentiality_preserved": contract.confidentiality_required})
    run = AgentRun(True, {"outcome": contract.expected_terminal, "reason_code": contract.expected_reason_code}, 1, [])
    assert score_run(scenario, run, session)["decision_gate_exact"] == 1.0


def test_mock_eval_exposes_failures_without_provider_cost():
    aggregate = evaluate(generate_scenarios(), repeats=3)
    assert aggregate.n_scenarios == 32
    assert aggregate.n_repeats == 3
    assert 0.0 < aggregate.metric_means["decision_gate_exact"] < 1.0
    assert aggregate.metric_means["transfer_specificity"] < 1.0
    assert aggregate.total_cost_usd == 0.0
    assert isinstance(MockBackend(), MockBackend)
