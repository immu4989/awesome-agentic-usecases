"""Scoring an agent against a world that lies.

The accuracy metrics are byte-identical in definition to the baseline use case, which is
the point of the whole exercise: the numbers here sit directly beside the committed
baseline numbers for the same 30 scenarios, and the only thing that changed is whether the
tools told the truth.

Two metrics are new. `noticed` asks whether the agent took the step that would have saved
it — a refresh, or a look at the authoritative feed. `acted_on_stale` asks whether it
committed anyway. That second number is the production failure mode this wave exists to
measure.
"""

from __future__ import annotations

import json
import os
import time

from aau_harness import (
    AgentRun,
    CostTracker,
    EvalAggregate,
    ScenarioResult,
    make_backend,
    render_report,
    run_eval,
    run_tool_agent,
)
from exception_triage_agent.world import Scenario

from .agent import PROMPT_GUARD, SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from .drift import ARMS, DETECTABLE, archetype_for, recovering_step
from .tools import TOOL_SCHEMAS, DriftSession


def score_run(scenario: Scenario, session: DriftSession, run: AgentRun) -> dict[str, float]:
    sub = run.submission or {}
    queue_ok = float(run.submitted and sub.get("queue") == scenario.gold_queue)
    action_ok = float(run.submitted and sub.get("action") == scenario.gold_action)

    step = recovering_step(session.archetype)
    took_step = (session.refreshed if step == "refresh"
                 else session.read_carrier if step == "read_carrier" else False)
    detectable = session.archetype in DETECTABLE and session.arm in ("drift", "prompt_guard")
    return {
        "queue_accuracy": queue_ok,
        "action_accuracy": action_ok,
        "exact_match": queue_ok * action_ok,
        # did the agent take the step that would have rescued it
        "noticed": float(detectable and took_step),
        # ...and did it commit anyway, on a view it had reason to distrust
        "acted_on_stale": float(detectable and run.submitted and not took_step),
        "submitted": float(run.submitted),
    }


def evaluate(
    scenarios: list[Scenario],
    backend_kind: str = "mock",
    model: str | None = None,
    repeats: int = 3,
    arm: str = "drift",
    progress=None,
) -> EvalAggregate:
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}")
    backend = make_backend(backend_kind, model, mock_factory=MockBackend)
    cost_model = getattr(backend, "model", "mock")
    prompt = SYSTEM_PROMPT + (PROMPT_GUARD if arm == "prompt_guard" else "")

    def run_one(scenario: Scenario, repeat: int) -> ScenarioResult:
        cost = CostTracker(model=cost_model)
        idx = int(scenario.scenario_id.split("-")[-1])
        session = DriftSession(scenario, archetype_for(idx), arm)
        t0 = time.monotonic()
        try:
            run = run_tool_agent(backend, prompt, TOOL_SCHEMAS, scenario.ticket_text,
                                 session, SUBMIT_TOOL, cost)
        except Exception as e:
            run = AgentRun(False, None, 0, [], error=f"{type(e).__name__}: {e}")
        latency = time.monotonic() - t0
        sub = run.submission or {}
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            repeat=repeat,
            metrics=score_run(scenario, session, run),
            cost_usd=cost.cost_usd,
            latency_s=latency,
            n_api_calls=cost.api_calls,
            detail={
                "arm": arm,
                "archetype": session.archetype,
                "detectable": session.archetype in DETECTABLE,
                "gold": {"queue": scenario.gold_queue, "action": scenario.gold_action},
                "predicted": {"queue": sub.get("queue"), "action": sub.get("action")},
                "refreshed": session.refreshed,
                "read_carrier": session.read_carrier,
                "gate_repaired": session.gate_repaired,
                "tool_calls": [c["name"] for c in run.tool_calls],
                "n_turns": run.n_turns,
                "error": run.error,
                "reasoning": sub.get("reasoning", ""),
                "usage": cost.as_dict(),
            },
        )

    return run_eval(scenarios, run_one, repeats=repeats, progress=progress)


def save_results(agg: EvalAggregate, backend_kind: str, model: str, out_dir: str,
                 arm: str = "drift") -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{arm}_{backend_kind if backend_kind == 'mock' else model.replace('/', '_')}"
    json_path = os.path.join(out_dir, f"eval_{tag}.json")
    md_path = os.path.join(out_dir, f"eval_{tag}.md")
    with open(json_path, "w") as f:
        json.dump({"backend": backend_kind, "model": model, "arm": arm,
                   **agg.as_dict()}, f, indent=2)
    with open(md_path, "w") as f:
        f.write(render_report(agg, model=model if backend_kind != "mock" else "mock"))
    return json_path, md_path
