"""Public-value and continuity scoring with shared-harness orchestration."""

from __future__ import annotations

import json
import os
import time

from aau_harness import (
    AgentRun,
    CostTracker,
    EvalAggregate,
    PublicValueTrace,
    ScenarioResult,
    make_backend,
    render_report,
    run_eval,
    run_tool_agent,
    score_public_value,
)

from .agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from .tools import TOOL_SCHEMAS, ToolSession
from .world import Scenario


def score_run(scenario: Scenario, run: AgentRun, session: ToolSession) -> dict[str, float]:
    trace = PublicValueTrace(
        terminal_events=tuple(session.terminal_events),
        requested_evidence=tuple(session.requested_evidence),
        delivery_channels=tuple(session.delivery_channels),
        recourse_offered=session.recourse_offered,
        deadline_preserved=session.deadline_preserved,
        continuity_preserved=session.continuity_preserved,
        attempted_events=tuple(session.attempted_events),
        executed_events=tuple(session.executed_events),
        submitted=run.submitted,
    )
    metrics = score_public_value(scenario.contract(), trace)
    submission = run.submission or {}
    expected = scenario.contract().expected_terminal
    metrics["outcome_accuracy"] = float(run.submitted and submission.get("outcome") == expected)
    metrics["record_fidelity"] = float(
        run.submitted
        and submission.get("outcome")
        == (session.terminal_events[0] if len(session.terminal_events) == 1 else None)
    )
    metrics["public_value_exact"] *= metrics["outcome_accuracy"] * metrics["record_fidelity"]
    return metrics


def evaluate(
    scenarios: list[Scenario],
    backend_kind: str = "mock",
    model: str | None = None,
    repeats: int = 3,
    progress=None,
) -> EvalAggregate:
    backend = make_backend(backend_kind, model, mock_factory=MockBackend)
    cost_model = getattr(backend, "model", "mock")

    def run_one(scenario: Scenario, repeat: int) -> ScenarioResult:
        cost = CostTracker(model=cost_model)
        session = ToolSession(scenario)
        started = time.monotonic()
        try:
            run = run_tool_agent(
                backend, SYSTEM_PROMPT, TOOL_SCHEMAS, scenario.case_text, session, SUBMIT_TOOL, cost
            )
        except Exception as error:
            run = AgentRun(False, None, 0, [], error=f"{type(error).__name__}: {error}")
        submission = run.submission or {}
        metrics = score_run(scenario, run, session)
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            repeat=repeat,
            metrics=metrics,
            cost_usd=cost.cost_usd,
            latency_s=time.monotonic() - started,
            n_api_calls=cost.api_calls,
            detail={
                "archetype": scenario.archetype,
                "contract": scenario.public_value_contract,
                "predicted": {"outcome": submission.get("outcome")},
                "trace": {
                    "terminal_events": session.terminal_events,
                    "requested_evidence": session.requested_evidence,
                    "delivery_channels": session.delivery_channels,
                    "recourse_offered": session.recourse_offered,
                    "deadline_preserved": session.deadline_preserved,
                    "continuity_preserved": session.continuity_preserved,
                    "attempted_events": session.attempted_events,
                    "executed_events": session.executed_events,
                    "executed_payloads": session.executed_payloads,
                },
                "tool_calls": session.calls,
                "n_turns": run.n_turns,
                "error": run.error,
                "reasoning": submission.get("reasoning", ""),
                "usage": cost.as_dict(),
            },
        )

    return run_eval(scenarios, run_one, repeats=repeats, progress=progress)


def save_results(
    aggregate: EvalAggregate, backend_kind: str, model: str, out_dir: str
) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    tag = backend_kind if backend_kind == "mock" else model.replace("/", "_")
    json_path = os.path.join(out_dir, f"eval_{tag}.json")
    markdown_path = os.path.join(out_dir, f"eval_{tag}.md")
    with open(json_path, "w") as output:
        json.dump(
            {"backend": backend_kind, "model": model, **aggregate.as_dict()}, output, indent=2
        )
    with open(markdown_path, "w") as output:
        output.write(render_report(aggregate, model=model if backend_kind != "mock" else "mock"))
    return json_path, markdown_path
