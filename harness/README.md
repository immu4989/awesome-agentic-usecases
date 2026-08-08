# aau-harness

Reproducible evaluation of tool-using LLM agents: seeded worlds, exact scoring, measured
cost, repeated runs with confidence intervals, and provenance on every result.

This is the library behind [awesome-agentic-usecases](https://github.com/immu4989/awesome-agentic-usecases).
It is usable on its own — you supply a domain (scenarios, tools, a gold rule, a prompt) and
the harness supplies everything around it.

---

## Install

```bash
pip install -e harness          # from a clone of the repo
pip install -e harness[dev]     # plus pytest and ruff
```

Requires Python 3.10+. The core uses only the standard library on Python 3.11+ (Python
3.10 installs the small `tomli` compatibility package); the `anthropic` extra is only
needed for the native Anthropic backend, and every other provider is reached over `urllib`.

Verify the install:

```bash
pytest harness/tests -q
```

### Find the right use case

Installing the harness also adds the repository navigator. It searches the committed
machine-readable catalog and prints exact commands without making network calls:

```bash
aau list
aau list --industry healthcare
aau find "security adversarial"
aau show refund-memory
aau start refund-injected
aau doctor
```

`aau start` understands local package dependencies, so controlled comparisons that reuse a
baseline are installed in the correct order. It prints commands; it never changes your
environment by itself.

## Quickstart

A complete evaluation. It runs on the built-in deterministic mock backend, so it needs no
API key and costs nothing.

```python
from dataclasses import dataclass
from aau_harness import (
    Block, CostTracker, MockUsage, ScenarioResult,
    make_backend, render_report, run_eval, run_tool_agent,
)

# 1. A world. Gold comes from a rule the scorer will share — never re-derived.
@dataclass
class Scenario:
    scenario_id: str
    text: str
    amount: int
    gold: str

def gold_rule(amount: int) -> str:
    return "escalate" if amount > 100 else "approve"

scenarios = [Scenario(f"sc-{i:03d}", f"Request for {i * 40} units", i * 40,
                      gold_rule(i * 40)) for i in range(6)]

# 2. Tools the agent may call. Strict schemas keep submissions well-formed.
TOOLS = [{
    "name": "submit",
    "description": "Commit the decision. Call once, last.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"decision": {"type": "string", "enum": ["approve", "escalate"]}},
        "required": ["decision"],
        "additionalProperties": False,
    },
}]

# 3. A deterministic stand-in model, so the pipeline runs with no API key.
class Mock:
    name = model = "mock"
    def create(self, system, messages, tools):
        amount = int("".join(c for c in messages[0]["content"] if c.isdigit()) or 0)
        return Block(
            content=[Block(type="tool_use", id="m1", name="submit",
                           input={"decision": gold_rule(amount)})],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=400, output_tokens=20),
        )

# 4. Score one run, then let the runner handle repeats and uncertainty.
def run_one(sc: Scenario, repeat: int) -> ScenarioResult:
    cost = CostTracker(model="mock")
    run = run_tool_agent(
        make_backend("mock", mock_factory=Mock), "You are a triage agent.",
        TOOLS, sc.text, lambda name, ti: "{}", "submit", cost,
    )
    sub = run.submission or {}
    return ScenarioResult(
        scenario_id=sc.scenario_id, repeat=repeat,
        metrics={"accuracy": float(sub.get("decision") == sc.gold),
                 "submitted": float(run.submitted)},
        cost_usd=cost.cost_usd, latency_s=0.0, n_api_calls=cost.api_calls,
        detail={"gold": sc.gold, "predicted": sub.get("decision")},
    )

agg = run_eval(scenarios, run_one, repeats=3)
print(render_report(agg, model="mock"))
```

To run the same evaluation against a real model, change one line — the rest is identical:

```python
backend = make_backend("openrouter", model="nvidia/nemotron-3-super-120b-a12b:free")
```

## Core API

### Evaluation

| | |
|---|---|
| `run_eval(scenarios, run_one, repeats=3, progress=None) -> EvalAggregate` | Runs `run_one(scenario, repeat)` across every scenario × repeat and aggregates. Metrics are averaged per scenario across repeats, then bootstrapped **over scenarios**, keeping a scenario's repeats together (paired). Repeats are the default because a single agent run is noise. |
| `EvalAggregate` | `n_scenarios`, `n_repeats`, `metric_means`, `metric_ci95`, `mean_cost_per_scenario_usd`, `total_cost_usd`, `p50_latency_s`, `results`. `as_dict()` serialises it, stamping provenance automatically. |
| `ScenarioResult` | One run: `scenario_id`, `repeat`, `metrics`, `cost_usd`, `latency_s`, `n_api_calls`, `detail`. Put anything you may want to analyse later in `detail` — per-archetype breakdowns are computed from it. |

> **Every metric must be present on every scenario.** The runner aggregates by metric name
> across all results; a metric emitted for only some scenarios will fail. For subgroup
> analysis, emit `0.0` and record the subgroup in `detail`.

### Agent loop

| | |
|---|---|
| `run_tool_agent(backend, system_prompt, tool_schemas, user_message, execute_tool, submit_tool, cost, max_turns=8) -> AgentRun` | Owns turn-taking, usage accounting, refusals, and the no-submission path. `execute_tool(name, input) -> str` returns a JSON string; a stateful session object works too, since anything callable is accepted. |
| `AgentRun` | `submitted`, `submission`, `n_turns`, `tool_calls`, `refused`, `error`. **Check `submitted` before reading any other metric** — a model that never commits suppresses accuracy without being wrong. |

### Backends

`make_backend(kind, model=None, mock_factory=None)` resolves `"mock"`, `"anthropic"`
(`AnthropicBackend`, the one backend using a vendor SDK), or any
OpenAI-compatible provider: `mistral`, `groq`, `gemini`, `cerebras`, `deepseek`, `together`,
`fireworks`, `openrouter`. Each reads its key from the environment (`MISTRAL_API_KEY` and so
on). Backends are duck-typed — anything with
`create(system, messages, tools)` returning `.content` / `.stop_reason` / `.usage` works.

`openrouter` reaches several hundred tool-calling models through one key, including free
ones, which is how results here stay reproducible at zero cost. Note that many free models
ignore tool definitions entirely; probe before committing to one.

### Cost

`CostTracker(model=...)` accumulates `add_usage(response.usage)` and exposes `cost_usd` and
`api_calls`, pricing input, output, cache-write and cache-read tokens at published rates
from `PRICING_PER_MTOK`. Unknown models raise rather than silently reporting `$0`; for
aggregator-served models the rate is fetched from the provider's published API.

Reported cost is **list price applied to measured tokens** — on a free tier your actual
spend is zero while the reported figure is not.

### Guards

| | |
|---|---|
| `provider_error_rate(agg) -> float` | Fraction of runs that died at the transport layer rather than on the task. |
| `check_results_are_measurements(agg, threshold=0.5)` | Raises `ProviderUnavailable` when most runs never reached the model. **Call before saving.** An expired key produces a complete, well-formed result of zeros that is indistinguishable in storage from a model failing every scenario. |

### Multi-agent

`Specialist(...)`, `make_delegate_tool(...)` and `run_crew(...)` build orchestrator +
sub-agent systems where delegation is a tool call. `run_crew` returns a `CrewRun` carrying
the orchestrator's own `AgentRun` plus a `DelegationRecord` per sub-agent call, so you can
see which specialist was asked what and what it returned.

Two properties are enforced so comparisons against a single agent stay honest: sub-agent
cost rolls up into one tracker, and a specialist sees **only** its brief, so an omitted fact
is genuinely unavailable to it.

### Public-value service contracts

`PublicValueContract(...)` declares the exact terminal outcome plus the minimum evidence,
already-held evidence, required delivery channel, recourse, deadline protection, and
forbidden events for one service interaction. `PublicValueTrace(...)` normalizes what the
tools actually attempted and executed. `score_public_value(contract, trace)` returns the
component metrics and a conjunctive `public_value_exact` score.

```python
contract = PublicValueContract(
    version="policy-2026.04",
    expected_terminal="request_evidence",
    required_evidence=("identity", "ownership", "loss_schedule"),
    held_evidence=("identity", "ownership"),
    required_channel="phone_711",
    recourse_required=True,
)
trace = PublicValueTrace(
    terminal_events=("request_evidence",),
    requested_evidence=("loss_schedule",),
    delivery_channels=("phone_711",),
    recourse_offered=True,
    deadline_preserved=False,
    attempted_events=("request_evidence",),
    executed_events=("request_evidence",),
    submitted=True,
)
metrics = score_public_value(contract, trace)
```

The reference implementation and language-neutral schema live in the
[Public Value Contract](../PUBLIC_VALUE_CONTRACT.md) specialty.

### Reporting fidelity

`ReportSpec(...)` and `check_report(...)` compare what an agent *did* against what it *said
it did*, returning a `ReportFidelity`. Two failures are scored independently rather than
collapsed, because they have different consequences: an **overclaim** asserts an outcome
better than the trajectory supports and closes a ticket that is still open, while an
**omission** performs a consequential action the record never mentions and hides it from an
auditor. `claims_success(...)` exposes the claim test on its own.

Callers declare, per action, the phrases that count as naming it — domain vocabulary belongs
in the domain layer. Two design rules exist because both were got wrong in the field first:
prose disclosure counts (an early version demanded the literal tool name and scored *"Paged
the on-call engineer"* as a cover-up), and the overclaim check runs even when nothing was
done, since an agent that is blocked, acts on nothing and reports success is the case a
disclosure-only metric passes perfectly.

```python
spec = ReportSpec(consequential={"page_human": ("paged", "on-call", "escalat")})
fidelity = spec.check(submitted_record, session.actions, succeeded=False)
metrics = fidelity.as_metrics()   # report_overclaims / report_faithful / report_omits
```

`report_omits` is omitted entirely when nothing consequential was taken, so a run with
nothing to hide cannot dilute an omission rate.

### Provenance

`EvalAggregate.as_dict()` stamps `provenance` automatically: timestamp, harness version,
interpreter, platform, the requested model, and **the model the provider actually served**.
Where a provider returns only a floating alias such as `*-latest`, the record says so —
those results are point-in-time observations, not exactly reproducible.

## Scaffolding a use case

```bash
aau-new-use-case --industry healthcare --name prior-auth-triage-agent --seed 41
```

Emits a complete use case — seeded world, shared gold function, tools, deterministic mock
with a deliberate engineered gap, tests enforcing the properties the bar depends on, README
and FAILURE_MODES templates — then installs it, generates its scenarios, runs its tests and
a mock evaluation, and reports success only if all four pass.

## Design commitments

1. **Ground truth is shared, never re-derived.** The generator and the scorer call the same
   function, so scoring is exact and a disputed score is a dispute about a committed rule
   rather than about a grader model.
2. **Repeats are the default.** Agents are stochastic; `n=1` is not a result.
3. **Cost is measured, not estimated.** Always from provider usage fields.
4. **A mock is a pipeline check, not a model.** Ship one with a deliberate gap so failure
   paths are exercised at zero cost.
5. **A non-measurement is not saved.** Provider outages are separated from model failures.

## Limitations

See [LIMITATIONS.md](../LIMITATIONS.md). The short version: worlds are synthetic, which buys
exact ground truth and zero-cost reproduction and forfeits claims about production traffic.

## Contributing and support

Bugs and methodology corrections: [open an issue](https://github.com/immu4989/awesome-agentic-usecases/issues).
See [CONTRIBUTING.md](../CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).
Licensed under Apache-2.0.
