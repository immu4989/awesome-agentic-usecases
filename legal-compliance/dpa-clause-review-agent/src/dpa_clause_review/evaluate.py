"""Scoring the review record against the review.

`missed_absence` is the metric the use case exists for: the agreement is reported clean
while a term GDPR Article 28(3) says it "shall stipulate" has no clause at all. That is the
Perini failure, and CLAUSE measured its static analogue at 9.3-31% F1.
"""

from __future__ import annotations

import json
import os
import time

from aau_harness import (
    AgentRun,
    CostTracker,
    EvalAggregate,
    ReportSpec,
    ScenarioResult,
    make_backend,
    render_report,
    run_eval,
    run_tool_agent,
)

from .agent import MockBackend
from .tools import SUBMIT_SCHEMA, SUBMIT_TOOL, ReviewSession, prompt_for, tool_schemas
from .world import ACCEPT, ARMS, ESCALATE, FLAG, DPA

MAX_TURNS = 16

REPORT_SPEC = ReportSpec(consequential={
    FLAG: ("flag", "defect", "missing", "absent", "inadequate", "non-compliant"),
    ESCALATE: ("escalat", "approv", "general counsel", "routed"),
    ACCEPT: ("accept", "acceptable", "no issues", "compliant"),
})


def _split(v) -> list[str]:
    return [p.strip() for p in str(v or "").replace(";", ",").split(",")
            if p.strip() and p.strip().lower() != "none"]


def evaluate(dpas: list[DPA], backend_kind: str = "mock", model: str | None = None,
             repeats: int = 3, arm: str = "none", progress=None) -> EvalAggregate:
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}")
    backend = make_backend(backend_kind, model,
                           mock_factory=lambda *_a, **_k: MockBackend(arm))
    cost_model = getattr(backend, "model", "mock")
    prompt = prompt_for(arm)
    schemas = tool_schemas() + [SUBMIT_SCHEMA]

    def run_one(dpa: DPA, repeat: int) -> ScenarioResult:
        cost = CostTracker(model=cost_model)
        sess = ReviewSession(dpa, arm)
        t0 = time.monotonic()
        try:
            run = run_tool_agent(backend, prompt, schemas, _brief(dpa), sess,
                                 SUBMIT_TOOL, cost, max_turns=MAX_TURNS)
        except Exception as e:
            run = AgentRun(False, None, 0, [], error=f"{type(e).__name__}: {e}")
        latency = time.monotonic() - t0

        rec = sess.record
        cited = _split(rec.get("clauses_reviewed"))
        defects = _split(rec.get("defects"))
        phantom = [c for c in cited if c not in sess.clauses_read]

        qid = str(rec.get("quoted_clause_id") or "").strip()
        quote = str(rec.get("quoted_text") or "").strip()
        src = next((c for c in dpa.clauses if c["clause_id"] == qid), None)
        phantom_quote = bool(quote) and (src is None
                                         or quote.lower() not in src["text"].lower())

        flagged = FLAG in sess.actions
        escalated = ESCALATE in sess.actions
        missed_absence = bool(dpa.missing_terms) and not flagged

        took = [a for a in sess.actions if a in REPORT_SPEC.consequential]
        fidelity = REPORT_SPEC.check(
            rec, took, succeeded=(flagged == dpa.gold_flags
                                  and escalated == dpa.gold_escalates))

        return ScenarioResult(
            scenario_id=dpa.scenario_id, repeat=repeat,
            metrics={
                "correct": float(flagged == dpa.gold_flags
                                 and escalated == dpa.gold_escalates),
                "flagged_correctly": float(flagged == dpa.gold_flags),
                "escalated_correctly": float(escalated == dpa.gold_escalates),
                "missed_absence": float(missed_absence),
                "phantom_clauses": float(bool(phantom)),
                "phantom_quote": float(phantom_quote),
                **fidelity.as_metrics(),
                "submitted": float(run.submitted),
                "record_filed": float(bool(rec)),
            },
            cost_usd=cost.cost_usd, latency_s=latency, n_api_calls=cost.api_calls,
            detail={"arm": arm, "dpa_id": dpa.dpa_id, "archetype": dpa.archetype,
                    "missing_terms": dpa.missing_terms,
                    "inadequate_terms": dpa.inadequate_terms,
                    "gold_flags": dpa.gold_flags, "gold_escalates": dpa.gold_escalates,
                    "actions": sess.actions, "clauses_read": sess.clauses_read,
                    "clauses_cited": cited, "phantom_clauses": phantom,
                    "defects_reported": defects,
                    "records_rejected": len(sess.rejected_records),
                    "record": rec, "error": run.error, "usage": cost.as_dict()},
        )

    return run_eval(dpas, run_one, repeats=repeats, progress=progress)


def _brief(dpa: DPA) -> str:
    return (f"Data processing agreement {dpa.dpa_id} from {dpa.counterparty}, contract "
            f"value ${dpa.contract_value_usd:,}. Counterparty paper. Review it.")


def save_results(agg: EvalAggregate, backend_kind: str, model: str, out_dir: str,
                 arm: str = "none") -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    tag = f"{arm}_{backend_kind if backend_kind == 'mock' else model.replace('/', '_')}"
    jp = os.path.join(out_dir, f"eval_{tag}.json")
    mp = os.path.join(out_dir, f"eval_{tag}.md")
    with open(jp, "w") as f:
        json.dump({"backend": backend_kind, "model": model, "arm": arm, **agg.as_dict()},
                  f, indent=2)
    with open(mp, "w") as f:
        f.write(render_report(agg, model=model if backend_kind != "mock" else "mock"))
    return jp, mp
