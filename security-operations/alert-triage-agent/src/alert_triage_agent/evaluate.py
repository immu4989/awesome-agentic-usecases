"""Scoring and eval orchestration: wires the SOC domain into the shared harness."""

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

from .agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from .tools import TOOL_SCHEMAS, execute_tool
from .world import Scenario


def score_run(scenario: Scenario, run: AgentRun) -> dict[str, float]:
    submission = run.submission or {}
    queue_ok = float(run.submitted and submission.get("queue") == scenario.gold_queue)
    disp_ok = float(
        run.submitted and submission.get("disposition") == scenario.gold_disposition
    )
    return {
        "queue_accuracy": queue_ok,
        "disposition_accuracy": disp_ok,
        "exact_match": queue_ok * disp_ok,
        "submitted": float(run.submitted),
    }


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
        t0 = time.monotonic()
        try:
            run = run_tool_agent(
                backend,
                SYSTEM_PROMPT,
                TOOL_SCHEMAS,
                scenario.alert_text,
                lambda name, tool_input: execute_tool(name, tool_input, scenario),
                SUBMIT_TOOL,
                cost,
            )
        except Exception as e:
            run = AgentRun(False, None, 0, [], error=f"{type(e).__name__}: {e}")
        latency = time.monotonic() - t0
        submission = run.submission or {}
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            repeat=repeat,
            metrics=score_run(scenario, run),
            cost_usd=cost.cost_usd,
            latency_s=latency,
            n_api_calls=cost.api_calls,
            detail={
                "gold": {"queue": scenario.gold_queue, "disposition": scenario.gold_disposition},
                "predicted": {"queue": submission.get("queue"),
                              "disposition": submission.get("disposition")},
                "n_turns": run.n_turns,
                "tool_calls": [c["name"] for c in run.tool_calls],
                "refused": run.refused,
                "error": run.error,
                "reasoning": submission.get("reasoning", ""),
                "usage": cost.as_dict(),
            },
        )

    return run_eval(scenarios, run_one, repeats=repeats, progress=progress)


def save_results(agg: EvalAggregate, backend_kind: str, model: str, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    tag = backend_kind if backend_kind == "mock" else model.replace("/", "_")
    json_path = os.path.join(out_dir, f"eval_{tag}.json")
    md_path = os.path.join(out_dir, f"eval_{tag}.md")
    with open(json_path, "w") as f:
        json.dump({"backend": backend_kind, "model": model, **agg.as_dict()}, f, indent=2)
    with open(md_path, "w") as f:
        f.write(render_report(agg, model=model if backend_kind != "mock" else "mock"))
    return json_path, md_path
