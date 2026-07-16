"""Scoring and eval orchestration: wires the agent into the shared harness."""

from __future__ import annotations

import json
import os
import time

from aau_harness import CostTracker, EvalAggregate, ScenarioResult, render_report, run_eval

from .agent import AnthropicBackend, MockBackend, run_agent
from .world import Scenario


def make_backend(kind: str, model: str | None = None):
    if kind == "mock":
        return MockBackend()
    if kind == "anthropic":
        return AnthropicBackend(model=model or "claude-opus-4-8")
    from .openai_compat import PROVIDERS, OpenAICompatBackend

    if kind in PROVIDERS:
        return OpenAICompatBackend(kind, model=model)
    raise ValueError(f"unknown backend {kind!r}")


def score_run(scenario: Scenario, outcome) -> dict[str, float]:
    queue_ok = float(outcome.submitted and outcome.queue == scenario.gold_queue)
    action_ok = float(outcome.submitted and outcome.action == scenario.gold_action)
    return {
        "queue_accuracy": queue_ok,
        "action_accuracy": action_ok,
        "exact_match": queue_ok * action_ok,
        "submitted": float(outcome.submitted),
    }


def evaluate(
    scenarios: list[Scenario],
    backend_kind: str = "mock",
    model: str | None = None,
    repeats: int = 3,
    progress=None,
) -> EvalAggregate:
    backend = make_backend(backend_kind, model)
    cost_model = getattr(backend, "model", "mock")

    def run_one(scenario: Scenario, repeat: int) -> ScenarioResult:
        cost = CostTracker(model=cost_model)
        t0 = time.monotonic()
        try:
            outcome = run_agent(backend, scenario, cost)
        except Exception as e:  # provider outage / hard API error: score it, don't lose the eval
            return ScenarioResult(
                scenario_id=scenario.scenario_id,
                repeat=repeat,
                metrics={
                    "queue_accuracy": 0.0,
                    "action_accuracy": 0.0,
                    "exact_match": 0.0,
                    "submitted": 0.0,
                },
                cost_usd=cost.cost_usd,
                latency_s=time.monotonic() - t0,
                n_api_calls=cost.api_calls,
                detail={
                    "gold": {"queue": scenario.gold_queue, "action": scenario.gold_action},
                    "predicted": {"queue": None, "action": None},
                    "error": f"{type(e).__name__}: {e}",
                    "usage": cost.as_dict(),
                },
            )
        latency = time.monotonic() - t0
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            repeat=repeat,
            metrics=score_run(scenario, outcome),
            cost_usd=cost.cost_usd,
            latency_s=latency,
            n_api_calls=cost.api_calls,
            detail={
                "gold": {"queue": scenario.gold_queue, "action": scenario.gold_action},
                "predicted": {"queue": outcome.queue, "action": outcome.action},
                "n_turns": outcome.n_turns,
                "tool_calls": [c["name"] for c in outcome.tool_calls],
                "refused": outcome.refused,
                "error": outcome.error,
                "reasoning": outcome.reasoning,
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
