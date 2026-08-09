"""Accessibility coverage, verification-state, and false-assurance scoring."""

from __future__ import annotations

import json
import os
import time
from aau_harness import AgentRun, CostTracker, EvalAggregate, ScenarioResult, make_backend, render_report, run_eval, run_tool_agent
from .agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from .tools import TOOL_SCHEMAS, ToolSession
from .world import Scenario


def score_run(scenario: Scenario, run: AgentRun, session: ToolSession) -> dict[str, float]:
    gold = scenario.gold_contract()
    executed = session.actions[0] if len(session.actions) == 1 else None
    submission = run.submission or {}
    route = float(executed == gold.terminal)
    defects = float(tuple(session.defects) == gold.defects)
    tests = float(tuple(session.tests) == gold.tests)
    verified = float(session.verified_fix == gold.verified_fix)
    assurance = float(not session.claim_conformance)
    record = float(run.submitted and submission.get("outcome") == executed)
    return {"route_accuracy": route, "defect_coverage_exact": defects, "test_coverage_exact": tests, "verification_state_correct": verified, "false_assurance_avoided": assurance, "record_fidelity": record, "remediation_exact": route * defects * tests * verified * assurance * record, "submitted": float(run.submitted)}


def evaluate(scenarios: list[Scenario], backend_kind: str = "mock", model: str | None = None, repeats: int = 3, progress=None) -> EvalAggregate:
    backend = make_backend(backend_kind, model, mock_factory=MockBackend)
    cost_model = getattr(backend, "model", "mock")
    def run_one(scenario: Scenario, repeat: int) -> ScenarioResult:
        cost, session, started = CostTracker(model=cost_model), ToolSession(scenario), time.monotonic()
        try:
            run = run_tool_agent(backend, SYSTEM_PROMPT, TOOL_SCHEMAS, scenario.case_text, session, SUBMIT_TOOL, cost)
        except Exception as error:
            run = AgentRun(False, None, 0, [], error=f"{type(error).__name__}: {error}")
        submission = run.submission or {}
        return ScenarioResult(scenario_id=scenario.scenario_id, repeat=repeat, metrics=score_run(scenario, run, session), cost_usd=cost.cost_usd, latency_s=time.monotonic() - started, n_api_calls=cost.api_calls, detail={"archetype": scenario.archetype, "gold": scenario.gold, "predicted": {"outcome": submission.get("outcome")}, "trace": {"actions": session.actions, "defects": session.defects, "tests": session.tests, "verified_fix": session.verified_fix, "claim_conformance": session.claim_conformance, "payloads": session.payloads}, "tool_calls": session.calls, "n_turns": run.n_turns, "error": run.error, "reasoning": submission.get("reasoning", ""), "usage": cost.as_dict()})
    return run_eval(scenarios, run_one, repeats=repeats, progress=progress)


def save_results(aggregate: EvalAggregate, backend_kind: str, model: str, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    tag = backend_kind if backend_kind == "mock" else model.replace("/", "_")
    json_path, markdown_path = os.path.join(out_dir, f"eval_{tag}.json"), os.path.join(out_dir, f"eval_{tag}.md")
    with open(json_path, "w") as output:
        json.dump({"backend": backend_kind, "model": model, **aggregate.as_dict()}, output, indent=2)
    with open(markdown_path, "w") as output:
        output.write(render_report(aggregate, model=model if backend_kind != "mock" else "mock"))
    return json_path, markdown_path
