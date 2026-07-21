"""Scoring for a watching agent.

Correctness alone does not describe a monitor. A pager that is right but fires twenty
minutes late is a different product from one that is right immediately, and a pager
that is right only because it never fires is worthless. So this use case scores:

- `severity_correct` — page / ticket / none matches gold.
- `no_false_page` — it did not page a window that warranted silence. This is the
  alert-fatigue metric, and it is scored on the archetypes designed to bait it.
- `caught_incident` — for windows that genuinely warranted a page, it paged.
- `patience_ok` — it did not commit before the evidence could support the call. An
  agent that pages on tick one of a transient gets this wrong even when a later
  incident makes the severity look right.
- `ticks_to_decide` — reported for context: how long the watch actually ran.
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

from .agent import SUBMIT_TOOL, SYSTEM_PROMPT, MockBackend
from .tools import TOOL_SCHEMAS, WatchSession
from .world import Scenario


def score_run(scenario: Scenario, run: AgentRun, session: WatchSession) -> dict[str, float]:
    submission = run.submission or {}
    said = submission.get("severity")
    gold = scenario.gold_severity

    severity_ok = float(run.submitted and said == gold)
    # Only meaningful on windows that should stay quiet; 1.0 elsewhere so the mean
    # reads as "share of runs that did not cry wolf".
    no_false_page = float(not (gold == "none" and said == "page"))
    caught = float(said == "page") if gold == "page" else 1.0
    # Committing before the evidence exists is luck, not judgement.
    patience_ok = float(
        scenario.detectable_tick is None
        or session.ticks_seen >= scenario.detectable_tick
        or said == gold == "none"
    )
    return {
        "severity_correct": severity_ok,
        "no_false_page": no_false_page,
        "caught_incident": caught,
        "patience_ok": patience_ok,
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
        session = WatchSession(scenario)
        t0 = time.monotonic()
        try:
            run = run_tool_agent(
                backend, SYSTEM_PROMPT, TOOL_SCHEMAS, scenario.alert_text,
                session, SUBMIT_TOOL, cost, max_turns=28,
            )
        except Exception as e:
            run = AgentRun(False, None, 0, [], error=f"{type(e).__name__}: {e}")
        latency = time.monotonic() - t0
        submission = run.submission or {}
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            repeat=repeat,
            metrics=score_run(scenario, run, session),
            cost_usd=cost.cost_usd,
            latency_s=latency,
            n_api_calls=cost.api_calls,
            detail={
                "archetype": scenario.archetype,
                "gold": {"severity": scenario.gold_severity},
                "predicted": {"severity": submission.get("severity")},
                "ticks_seen": session.ticks_seen,
                "detectable_tick": scenario.detectable_tick,
                "onset_tick": scenario.onset_tick,
                "saw_context": session.saw_context,
                "searched_runbook": session.searched_runbook,
                "n_turns": run.n_turns,
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
