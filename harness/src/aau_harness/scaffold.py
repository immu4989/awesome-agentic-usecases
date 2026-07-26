"""Generate a new use case that already clears the verification bar.

The bar in VERIFICATION.md is deliberately high, and a high bar suppresses contribution:
writing a seeded world, a gold function the scorer shares, a deterministic mock, and the
tests that hold all three together is a day of work before anyone reaches the interesting
part. This generator does that day of work.

What it emits is not a stub. It is a complete, runnable use case whose mock eval is green,
whose tests pass, and whose scenario file is reproducible from a seed — so a contributor's
first command succeeds, and every subsequent edit is checked by tests that already encode
the bar. The domain is theirs to write; the rigor is already installed.

    aau-new-use-case --industry healthcare --name prior-auth-triage-agent --seed 41
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------------------
# Templates. Placeholders are __TOKENS__ rather than str.format fields, because the
# generated code is full of dict and f-string braces that would need doubling otherwise.
# ---------------------------------------------------------------------------------------

WORLD = '''"""Synthetic world for __TITLE__, and the generator whose rules are the eval's ground truth.

TODO(domain): replace the placeholder domain below with yours. The structure is what
matters and it is already correct:

  * the case text the agent sees **underdetermines** the answer — the deciding facts are
    reachable only through tools, so triage-by-text-alone fails;
  * at least one archetype is a **deception**: it reads as one thing and is another, which
    is what separates a measurement from a demo;
  * `gold_decision` is shared by the generator and the scorer, so scoring is exact rather
    than judged.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

QUEUES = ["queue-a", "queue-b", "queue-c", "no-action"]
ACTIONS = ["auto_resolve", "route_to_queue", "escalate_to_human"]

# TODO(domain): a threshold the case text never mentions, so it must be retrieved.
ESCALATION_THRESHOLD = 1000

KB = [
    {
        "id": "KB-ESC-01",
        "title": "Escalation criteria",
        "text": (
            "Escalate to a human when the recorded value exceeds "
            f"{ESCALATION_THRESHOLD}, or when the account is marked priority. Escalation "
            "overrides any automation eligibility."
        ),
    },
    {
        "id": "KB-AUTO-02",
        "title": "Automation eligibility",
        "text": (
            "Cases of type type-a with a validated candidate may be auto-resolved. "
            "Without a validated candidate, route to queue-a for manual research."
        ),
    },
    {
        "id": "KB-BENIGN-03",
        "title": "Known-benign sources",
        "text": (
            "Cases attributable to a known-benign source are not real exceptions and "
            "take no action. Verify the source before treating the pattern as genuine."
        ),
    },
]

# case type -> (gold queue, case-text templates the agent actually sees)
CASE_TYPES = {
    "TYPE_A": ("queue-a", [
        "Case {cid} has not progressed in days. The status page only says 'exception'.",
        "Something is wrong with {cid} — it was supposed to be handled automatically.",
    ]),
    "TYPE_B": ("queue-b", [
        "Case {cid} looks stuck. No updates for a week. What is going on?",
        "No movement on {cid}. Please look into this.",
    ]),
    # The deception: reads exactly like a genuine TYPE_B exception, but the context
    # reveals a known-benign source. An agent that trusts the text gets this wrong.
    "BENIGN_LOOKALIKE": ("no-action", [
        "Case {cid} is throwing repeated exceptions — hundreds of them overnight.",
        "Case {cid} keeps failing over and over. This looks serious.",
    ]),
}


@dataclass
class Scenario:
    scenario_id: str
    case_text: str
    case_id: str
    record: dict
    context: dict
    case_type: str
    gold_queue: str
    gold_action: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def gold_decision(case_type: str, record: dict, context: dict) -> tuple[str, str]:
    """Ground truth. The generator and the scorer share this function, which is what makes
    scoring exact — never re-derive the answer anywhere else."""
    if context["known_benign_source"]:
        return "no-action", "auto_resolve"
    queue = CASE_TYPES[case_type][0]
    if record["value"] > ESCALATION_THRESHOLD or record["priority"]:
        return queue, "escalate_to_human"
    if case_type == "TYPE_A" and record["has_validated_candidate"]:
        return queue, "auto_resolve"
    return queue, "route_to_queue"


def generate_scenarios(n: int = 30, seed: int = __SEED__) -> list[Scenario]:
    rng = random.Random(seed)
    types = list(CASE_TYPES)
    out: list[Scenario] = []
    for i in range(n):
        case_type = types[i % len(types)]          # balanced across types
        cid = f"CASE-{rng.randrange(10000, 99999)}"
        record = {
            "case_id": cid,
            "value": round(rng.lognormvariate(6.0, 1.0), 2),   # ~20% over the threshold
            "priority": rng.random() < 0.2,
            "has_validated_candidate": rng.random() < 0.5,
            "owner": rng.choice(["team-alpha", "team-beta", "team-gamma"]),
        }
        context = {
            "case_id": cid,
            "known_benign_source": case_type == "BENIGN_LOOKALIKE",
            "source_note": (
                "traffic matches the scheduled maintenance window (change CHG-4471)"
                if case_type == "BENIGN_LOOKALIKE" else "no allowlisted source match"
            ),
            "events_24h": rng.randrange(50, 900),
        }
        queue, action = gold_decision(case_type, record, context)
        out.append(Scenario(
            scenario_id=f"sc-{i:03d}",
            case_text=rng.choice(CASE_TYPES[case_type][1]).format(cid=cid),
            case_id=cid, record=record, context=context, case_type=case_type,
            gold_queue=queue, gold_action=action,
        ))
    return out


def save_scenarios(scenarios: list[Scenario], path: str) -> None:
    with open(path, "w") as f:
        for sc in scenarios:
            f.write(json.dumps(sc.as_dict()) + "\\n")


def load_scenarios(path: str) -> list[Scenario]:
    with open(path) as f:
        return [Scenario(**json.loads(line)) for line in f]


def search_kb(query: str, top_k: int = 2) -> list[dict]:
    terms = {w.strip(".,?!").lower() for w in query.split() if len(w) > 3}
    scored = []
    for doc in KB:
        text = (doc["title"] + " " + doc["text"]).lower()
        scored.append((sum(1 for t in terms if t in text), doc))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [d for s, d in scored[:top_k] if s > 0] or [scored[0][1]]
'''

TOOLS = '''"""Tool schemas the agent sees, and their execution against one scenario's world."""

from __future__ import annotations

import json

from .world import ACTIONS, QUEUES, Scenario, search_kb

TOOL_SCHEMAS = [
    {
        "name": "lookup_record",
        "description": (
            "Fetch the case record: recorded value, priority flag, and whether a validated "
            "candidate exists. Call this for every case — the decision rules depend on these "
            "fields, not on how urgent the case text sounds."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string", "description": "Case id, e.g. CASE-40182"}},
            "required": ["case_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "query_context",
        "description": (
            "Pull recent activity for a case, including whether the activity is attributable "
            "to a known-benign source. Case text frequently misreads benign activity as a "
            "real exception — verify here."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string", "description": "Case id"}},
            "required": ["case_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_kb",
        "description": (
            "Search the policy knowledge base. Escalation thresholds and automation "
            "eligibility live here, not in your instructions — check before deciding."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Keyword query"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_decision",
        "description": "Commit the decision for this case. Call exactly once. This ends the task.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": QUEUES, "description": "Target queue"},
                "action": {"type": "string", "enum": ACTIONS, "description": "What happens next"},
                "reasoning": {"type": "string", "description": "One paragraph citing the facts and KB clauses used"},
            },
            "required": ["queue", "action", "reasoning"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict, scenario: Scenario) -> str:
    if name == "lookup_record":
        if tool_input.get("case_id") != scenario.case_id:
            return json.dumps({"error": f"no record for {tool_input.get('case_id')!r}"})
        return json.dumps(scenario.record)
    if name == "query_context":
        if tool_input.get("case_id") != scenario.case_id:
            return json.dumps({"error": f"no context for {tool_input.get('case_id')!r}"})
        return json.dumps(scenario.context)
    if name == "search_kb":
        return json.dumps(search_kb(tool_input.get("query", "")))
    return json.dumps({"error": f"unknown tool {name!r}"})
'''

AGENT = '''"""Domain layer: the system prompt and a deterministic mock with an engineered gap."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import ESCALATION_THRESHOLD

SYSTEM_PROMPT = f"""\\
You are a __TITLE__ agent. You receive one case at a time and must assign it to the
correct queue with the correct action.

Rules of engagement:
- The case text is a first guess, not the truth. Activity from a known-benign source is
  not a real exception. Always verify against the record and the context before deciding.
- The escalation threshold ({ESCALATION_THRESHOLD}) and automation eligibility live in the
  knowledge base, not in these instructions. Search it before choosing an action.
- Investigate with the tools, then call submit_decision exactly once.

Queues: queue-a, queue-b, queue-c, no-action.
Actions: auto_resolve, route_to_queue, escalate_to_human.
"""

SUBMIT_TOOL = "submit_decision"


class MockBackend:
    """Deterministic scripted 'model': record -> context -> kb -> submit.

    Its rules mirror gold EXCEPT it ignores the known-benign source, so it treats the
    deception archetype as a genuine exception. That engineered gap gives CI a stable,
    nonzero error rate at $0 — a mock that scores perfectly would exercise none of the
    reporting or failure paths.

    TODO(domain): keep a gap when you rewrite this. It should be a *plausible* mistake.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n = sum(1 for m in messages if m["role"] == "assistant")
        cid = self._case_id(messages[0]["content"])
        if n == 0:
            b = Block(type="tool_use", id="m1", name="lookup_record", input={"case_id": cid})
        elif n == 1:
            b = Block(type="tool_use", id="m2", name="query_context", input={"case_id": cid})
        elif n == 2:
            b = Block(type="tool_use", id="m3", name="search_kb",
                      input={"query": "escalation threshold automation eligibility"})
        else:
            b = Block(type="tool_use", id="m4", name="submit_decision",
                      input=self._decide(messages))
        return Block(content=[b], stop_reason="tool_use",
                     usage=MockUsage(input_tokens=800 + 350 * n, output_tokens=80))

    @staticmethod
    def _case_id(text: str) -> str:
        for tok in text.replace(".", " ").replace(",", " ").split():
            t = tok.strip("'\\"?!")
            if t.startswith("CASE-"):
                return t
        return "UNKNOWN"

    @staticmethod
    def _world(messages: list) -> tuple[dict, dict]:
        record, context = {}, {}
        for m in messages:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for b in m["content"]:
                if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                    continue
                try:
                    d = json.loads(b["content"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(d, dict) and "has_validated_candidate" in d:
                    record = d
                elif isinstance(d, dict) and "known_benign_source" in d:
                    context = d
        return record, context

    def _decide(self, messages: list) -> dict:
        record, _context = self._world(messages)
        if not record:
            return {"queue": "queue-a", "action": "route_to_queue", "reasoning": "mock: no record"}
        # NOTE: the engineered gap — never consults context["known_benign_source"].
        if record.get("value", 0) > ESCALATION_THRESHOLD or record.get("priority"):
            action = "escalate_to_human"
        elif record.get("has_validated_candidate"):
            action = "auto_resolve"
        else:
            action = "route_to_queue"
        return {"queue": "queue-a", "action": action, "reasoning": "mock: rule-based"}
'''

EVALUATE = '''"""Scoring and eval orchestration: wires this domain into the shared harness."""

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
    sub = run.submission or {}
    queue_ok = float(run.submitted and sub.get("queue") == scenario.gold_queue)
    action_ok = float(run.submitted and sub.get("action") == scenario.gold_action)
    return {
        "queue_accuracy": queue_ok,
        "action_accuracy": action_ok,
        "exact_match": queue_ok * action_ok,
        # Always report this. A model that never commits is not a model that was careful,
        # and it silently suppresses every other metric on the row.
        "submitted": float(run.submitted),
    }


def evaluate(scenarios: list[Scenario], backend_kind: str = "mock", model: str | None = None,
             repeats: int = 3, progress=None) -> EvalAggregate:
    backend = make_backend(backend_kind, model, mock_factory=MockBackend)
    cost_model = getattr(backend, "model", "mock")

    def run_one(scenario: Scenario, repeat: int) -> ScenarioResult:
        cost = CostTracker(model=cost_model)
        t0 = time.monotonic()
        try:
            run = run_tool_agent(
                backend, SYSTEM_PROMPT, TOOL_SCHEMAS, scenario.case_text,
                lambda name, ti: execute_tool(name, ti, scenario), SUBMIT_TOOL, cost,
            )
        except Exception as e:
            run = AgentRun(False, None, 0, [], error=f"{type(e).__name__}: {e}")
        sub = run.submission or {}
        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            repeat=repeat,
            metrics=score_run(scenario, run),
            cost_usd=cost.cost_usd,
            latency_s=time.monotonic() - t0,
            n_api_calls=cost.api_calls,
            detail={
                "case_type": scenario.case_type,
                "gold": {"queue": scenario.gold_queue, "action": scenario.gold_action},
                "predicted": {"queue": sub.get("queue"), "action": sub.get("action")},
                "tool_calls": [c["name"] for c in run.tool_calls],
                "n_turns": run.n_turns,
                "error": run.error,
                "reasoning": sub.get("reasoning", ""),
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
'''

CLI = '''"""CLI: generate scenarios, run evals.

  __CLI__ generate --n 30 --seed __SEED__
  __CLI__ eval --backend mock
  __CLI__ eval --backend openrouter --repeats 3
"""

from __future__ import annotations

import argparse
import os
import sys

from aau_harness import ProviderUnavailable, check_results_are_measurements

from .evaluate import evaluate, save_results
from .world import generate_scenarios, load_scenarios, save_scenarios

PKG_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SCENARIOS = os.path.join(PKG_ROOT, "evals", "scenarios.jsonl")
DEFAULT_RESULTS = os.path.join(PKG_ROOT, "results")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="__CLI__")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate the scenario file (with ground truth)")
    g.add_argument("--n", type=int, default=30)
    g.add_argument("--seed", type=int, default=__SEED__)
    g.add_argument("--out", default=DEFAULT_SCENARIOS)

    e = sub.add_parser("eval", help="run the eval")
    e.add_argument("--backend", choices=["mock", "anthropic", "mistral", "groq", "gemini",
                                         "cerebras", "deepseek", "together", "fireworks",
                                         "openrouter"], default="mock")
    e.add_argument("--model", default=None)
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    e.add_argument("--limit", type=int, default=0)
    e.add_argument("--out", default=DEFAULT_RESULTS)

    args = p.parse_args(argv)

    if args.cmd == "generate":
        scenarios = generate_scenarios(n=args.n, seed=args.seed)
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        save_scenarios(scenarios, args.out)
        print(f"wrote {len(scenarios)} scenarios -> {args.out}")
        return 0

    scenarios = load_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]
    agg = evaluate(scenarios, backend_kind=args.backend, model=args.model,
                   repeats=args.repeats, progress=lambda m: print(f"  {m}"))
    resolved = args.model or args.backend
    if args.backend not in ("mock", "anthropic") and not args.model:
        from aau_harness.llm_providers import PROVIDERS
        resolved = PROVIDERS[args.backend].default_model
    try:
        check_results_are_measurements(agg)
    except ProviderUnavailable as exc:
        print(f"\\nREFUSING TO SAVE: {exc}", file=sys.stderr)
        return 2
    json_path, md_path = save_results(agg, args.backend, resolved, args.out)
    print()
    print(open(md_path).read())
    print(f"results -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

TESTS = '''"""Tests that hold the verification bar in place.

These are not decoration. Each one enforces a property the bar depends on, and they are
what let you edit the world confidently: if a change makes the eval meaningless, one of
these fails rather than the numbers quietly becoming wrong.
"""

import json

import pytest

from __PKG__.evaluate import evaluate
from __PKG__.tools import TOOL_SCHEMAS, execute_tool
from __PKG__.world import (
    ACTIONS,
    CASE_TYPES,
    QUEUES,
    generate_scenarios,
    gold_decision,
)

SCS = generate_scenarios(30, __SEED__)


def test_determinism():
    """Bar rule 2: the scenario file must be reproducible from its seed."""
    assert [s.as_dict() for s in generate_scenarios(30, __SEED__)] == [s.as_dict() for s in SCS]


def test_gold_is_shared_not_re_derived():
    """The scorer and the generator must agree by construction, not by coincidence."""
    for s in SCS:
        assert (s.gold_queue, s.gold_action) == gold_decision(s.case_type, s.record, s.context)


def test_coverage_at_scale():
    scs = generate_scenarios(120, __SEED__)
    assert {s.case_type for s in scs} == set(CASE_TYPES)
    assert {s.gold_queue for s in scs} <= set(QUEUES)
    assert {s.gold_action for s in scs} <= set(ACTIONS)


def test_the_deception_exists_and_is_deceptive():
    """A use case without a case that reads wrong is a demo, not a measurement."""
    lookalikes = [s for s in SCS if s.case_type == "BENIGN_LOOKALIKE"]
    assert lookalikes, "no deception archetype present"
    for s in lookalikes:
        assert s.context["known_benign_source"] is True     # the truth is in the tools
        assert s.gold_queue == "no-action"
        assert "benign" not in s.case_text.lower()          # ...and never in the text


def test_deciding_facts_are_not_in_the_case_text():
    """If the text gives the answer away, the agent never has to investigate."""
    for s in SCS:
        assert str(s.record["value"]) not in s.case_text


def test_submit_schema_is_strict():
    submit = next(t for t in TOOL_SCHEMAS if t["name"] == "submit_decision")
    assert submit["input_schema"]["additionalProperties"] is False
    assert submit["input_schema"]["properties"]["queue"]["enum"] == QUEUES


def test_tools_reject_an_unknown_id():
    out = json.loads(execute_tool("lookup_record", {"case_id": "CASE-00000"}, SCS[0]))
    assert "error" in out


def test_mock_eval_runs_and_reports_submitted():
    agg = evaluate(SCS, backend_kind="mock", repeats=3)
    assert agg.n_scenarios == 30
    assert agg.metric_means["submitted"] == 1.0
    assert "exact_match" in agg.metric_means


def test_mock_has_an_engineered_gap():
    """A mock that scores perfectly exercises none of the failure-reporting paths."""
    agg = evaluate(SCS, backend_kind="mock", repeats=1)
    assert 0.0 < agg.metric_means["exact_match"] < 1.0
    missed = [r for r in agg.results
              if r.detail["case_type"] == "BENIGN_LOOKALIKE" and r.metrics["queue_accuracy"] == 0.0]
    assert missed, "the mock should fall for the deception — that is its engineered gap"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

PYPROJECT = '''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "__SLUG__"
version = "0.1.0"
description = "TODO(domain): one sentence on the decision this agent makes and why it is hard."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
keywords = ["agents", "llm", "evaluation", "__INDUSTRY__"]
dependencies = ["aau-harness"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.4"]

[project.scripts]
__CLI__ = "__PKG__.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
'''

README = '''<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/industry-__INDUSTRY__-4a3aa7" alt="industry">
  <img src="https://img.shields.io/badge/reproduce-%240%20free%20tier-4a3aa7" alt="free to reproduce">
</p>

# __TITLE__

> **TODO(domain)** — this scaffold is runnable but generic. Replace the placeholder domain,
> then delete this block. Keep the section order; it is the repo's standard template.

## 🪤 The trap

TODO(domain): lead with the case that reads as one thing and is another. This is the most
important paragraph on the page — it is what makes the eval a measurement rather than a
demo. The scaffold ships one (`BENIGN_LOOKALIKE`): activity that looks like a real
exception until the context reveals a known-benign source.

## Problem

TODO(domain): what decision does this agent make, and what would a real team do with it?

## How it decides

The agent pulls the record and the context, searches the knowledge base, and commits a
queue and an action. The escalation threshold and automation rules live in the KB rather
than the prompt, so the agent has to retrieve them.

## Results

TODO: run real evals and paste the table. Minimum bar is n≥3 repeats with CIs and measured
cost. Report `submitted` alongside accuracy — a model that never commits will otherwise
look careful.

```bash
export OPENROUTER_API_KEY=...      # free tool-calling models available
__CLI__ eval --backend openrouter --repeats 3
```

## Failure modes

See [FAILURE_MODES.md](FAILURE_MODES.md) — at least 3, each one **observed** in a committed
run with a reproducing scenario id.

## Run it

```bash
pip install -e ../../harness -e .
__CLI__ generate --n 30 --seed __SEED__
__CLI__ eval --backend mock          # deterministic, no API key, $0
```
'''

FAILURE_MODES = '''# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in a committed eval run — never hypothesised. A use case whose evals never
fail has an eval set that is too easy, and that is a finding too.

> **TODO(domain)** — replace these with real observations once you have run real models,
> then delete this block. Keep the shape: what to run, what happened, why it matters.
> Check [FAILURE_TAXONOMY.md](../../FAILURE_TAXONOMY.md) first — most new failures turn out
> to be instances of a pattern already measured here, and saying which one is more useful
> than describing it fresh.

### 1. TODO: the deception failure

- **Reproduce:** `--backend <provider>`, scenario `sc-0XX`.
- **What happens:** the model trusts the case text over the context and treats benign
  activity as a real exception.
- **Why it matters:** TODO.

### 2. TODO: a policy the model retrieved and then ignored

- **Reproduce:** TODO.
- **What happens:** TODO.
- **Why it matters:** TODO.

### 3. TODO: commit-stall, if you see it

- **Reproduce:** check `submitted` in your results.
- **What happens:** the agent investigates correctly and never calls the submit tool.
- **Why it matters:** it is the most common failure in this repo — found in 8 of 13 use
  cases — and it is invisible to accuracy metrics, which simply omit the runs that never
  answered. See [the taxonomy](../../FAILURE_TAXONOMY.md#commit-stall).
'''


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")


def render(text: str, **tokens: str) -> str:
    for k, v in tokens.items():
        text = text.replace(f"__{k}__", v)
    return text


def build(industry: str, name: str, seed: int, root: str, title: str | None = None) -> str:
    slug = slugify(name)
    ind = slugify(industry)
    pkg = slug.replace("-", "_")
    cli = slug
    nice = title or slug.replace("-", " ").title()
    dest = os.path.join(root, ind, slug)
    if os.path.exists(dest):
        raise SystemExit(f"refusing to overwrite existing {dest}")

    tok = dict(PKG=pkg, CLI=cli, SLUG=slug, INDUSTRY=ind, TITLE=nice, SEED=str(seed))
    files = {
        "pyproject.toml": PYPROJECT,
        "README.md": README,
        "FAILURE_MODES.md": FAILURE_MODES,
        f"src/{pkg}/__init__.py": f'"""{nice}: TODO(domain) one-line summary."""\n',
        f"src/{pkg}/world.py": WORLD,
        f"src/{pkg}/tools.py": TOOLS,
        f"src/{pkg}/agent.py": AGENT,
        f"src/{pkg}/evaluate.py": EVALUATE,
        f"src/{pkg}/cli.py": CLI,
        f"tests/test_{pkg}.py": TESTS,
    }
    for rel, body in files.items():
        path = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(render(body, **tok))
    for d in ("evals", "results"):
        os.makedirs(os.path.join(dest, d), exist_ok=True)
        open(os.path.join(dest, d, ".gitkeep"), "w").close()
    return dest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="aau-new-use-case",
        description="Scaffold a use case that already clears the verification bar.")
    p.add_argument("--industry", required=True, help="e.g. healthcare, insurance, legal")
    p.add_argument("--name", required=True, help="e.g. prior-auth-triage-agent")
    p.add_argument("--seed", type=int, required=True, help="a seed no other use case uses")
    p.add_argument("--title", default=None, help="human title for the README")
    p.add_argument("--root", default=".", help="repo root (default: cwd)")
    p.add_argument("--no-verify", action="store_true",
                   help="skip the install + test + mock-eval check")
    a = p.parse_args(argv)

    dest = build(a.industry, a.name, a.seed, a.root, a.title)
    rel = os.path.relpath(dest, a.root)
    cli = slugify(a.name)
    print(f"created {rel}")

    if not a.no_verify:
        print("\nverifying the scaffold is green before you touch it...")
        steps = [
            ("install", [sys.executable, "-m", "pip", "install", "-q", "-e", dest]),
            ("generate", [cli, "generate", "--n", "30", "--seed", str(a.seed)]),
            ("tests", [sys.executable, "-m", "pytest", os.path.join(dest, "tests"), "-q"]),
            ("mock eval", [cli, "eval", "--backend", "mock", "--repeats", "3"]),
        ]
        for label, cmd in steps:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  {label}: FAILED\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
                return 1
            print(f"  {label}: ok")

    print(f"""
next:
  1. add the CI row to .github/workflows/ci.yml

          - dir: {rel}
            cli: {cli}
            seed: {a.seed}

  2. rewrite the domain in {rel}/src/{cli.replace('-', '_')}/world.py
     (search the tree for TODO(domain) — the tests will tell you if you break the bar)
  3. run real models, commit results/, then write FAILURE_MODES.md from what you saw
  4. regenerate the derived assets:
        python docs/make_assets.py && python docs/make_leaderboard.py
        python docs/make_terminal_demo.py && python docs/make_taxonomy.py
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
