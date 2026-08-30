# aau-harness

Reproducible evaluation of tool-using LLM agents: seeded worlds, exact scoring, measured
cost, repeated runs with confidence intervals, and provenance on every result.

This is the library behind [awesome-agentic-usecases](https://github.com/immu4989/awesome-agentic-usecases).
It is usable on its own — you supply a domain (scenarios, tools, a gold rule, a prompt) and
the harness supplies everything around it.

---

## Install

For evaluation in your own project:

```bash
python -m pip install aau-harness
```

For repository development:

```bash
python -m pip install -e harness
python -m pip install -e 'harness[dev]'  # plus pytest and ruff
```

Requires Python 3.10+. The core uses only the standard library on Python 3.11+ (Python
3.10 installs the small `tomli` compatibility package); the `anthropic` extra is only
needed for the native Anthropic backend, and every other provider is reached over `urllib`.

Verify the install:

```bash
aau --help
# From a repository clone:
pytest harness/tests -q
```

## Start an evidence project in five minutes

`aau init` generates a complete, non-overwriting evaluation project around an agent you already
have. It needs no AAU account, hosted dataset, model key, or upload.

```bash
aau init my-agent-eval
cd my-agent-eval
aau doctor .
aau evaluate suite.json --mock --out artifacts/protocol-receipt.json
aau evaluate suite.json --command "python adapter_command.py" --out artifacts/local-receipt.json
```

Every starter contains an explicitly synthetic three-case suite, command and local HTTP adapters,
exact outcome and forbidden-action checks, accountable human authority, a deterministic public
receipt, a standard-library test, immutable least-privilege CI, a receipt-sharing policy, an
evidence-flow visual, and a SHA-256 manifest. Generation is atomic and refuses to overwrite an
existing path.

Choose a transferable failure shape or an HTTP-first integration:

```bash
aau init service-eval --template public-service-routing
aau init support-eval --template customer-escalation
aau init incident-eval --template incident-triage --adapter http
```

`aau doctor` fails on unsafe sharing declarations, an invalid adapter contract, a drifted receipt,
unsafe manifest paths or symlinks, or weakened CI. It parses but does not execute project code by
default; use `aau doctor . --run-adapter` only for code you trust. Legitimate customization is
reported as a warning. Structural readiness remains an onboarding signal—not production
validation, certification, legal advice, or authority to deploy.
See the [complete examples](https://github.com/immu4989/awesome-agentic-usecases/tree/main/agent-evidence-starter/examples)
or use the [zero-upload browser wizard](https://immu4989.github.io/awesome-agentic-usecases/#agent-starter).

## Publish a privacy-bounded community evidence pack

After connecting a real command or endpoint adapter, `aau submit` turns the Starter and one or
more public aggregate receipts into a non-overwriting contribution directory:

```bash
aau submit ./my-agent-eval \
  --receipt ./artifacts/public-receipt.json \
  --id my-agent-evidence \
  --contributor-name "Your name" --github your-handle \
  --summary "What it helps with" --why-fork "What another team can adapt" \
  --beneficiaries "Who benefits" --industry "Your industry" \
  --failure-shape "The failure boundary" --tag routing --tag human-authority

aau submit --validate ./my-agent-evidence-aau-submission
```

The command rejects mock receipts, private or extra receipt fields, inconsistent aggregate
metrics, unsafe paths and symlinks, common sensitive-data patterns, stale checks, manifest drift,
and unsupported public files. It never executes the Starter adapter, uploads data, opens a pull
request, or overwrites an existing path.

Evidence levels are cumulative and artifact-derived: **Generated** requires a connected-agent
receipt and protected human authority; **Domain reviewed** adds an adapted 10-case suite, named
review scope, and sources; **Reproduced** adds three distinct run receipts; **Verified** adds a
named different reproducer linked to a receipt. These levels are not identity verification,
certification, endorsement, production validation, or authority to deploy. See the
[public contract and reference packs](https://github.com/immu4989/awesome-agentic-usecases/tree/main/community-evidence)
or use the [browser-local Contribution Desk](https://immu4989.github.io/awesome-agentic-usecases/#community-evidence-loop).

## Add the missing human comparator

`aau baseline` turns a reviewed public or synthetic suite into a blinded human-process study. It
keeps participant-visible tasks and the answer key separate, prohibits direct identifiers and free
text in session files, and starts with an explicit `not_determined` human-protection state.

```bash
aau baseline prepare suite.json \
  --id my-human-baseline \
  --title "My Human Baseline" \
  --purpose "Compare the reviewed task with the existing process" \
  --out human-baseline-pack

aau baseline summarize human-baseline-pack \
  --session private-sessions/session-01.json \
  --agent-receipt public-agent-receipt.json \
  --out public-human-baseline-report.json

aau baseline validate public-human-baseline-report.json
```

Aggregate reports include exactness with a Wilson interval, abstention, median and p90 task time,
confidence calibration, modal agreement, and Fleiss' kappa. Optional agent comparisons require the
same suite hash and scenario coverage and reject protocol mock receipts. Reports exclude participant
ids and raw outcome, confidence, and timing rows.

Before collecting real participant sessions, the responsible institution must record the relevant
human-subjects, quality-improvement, privacy, accessibility, labor, records, and consent or
withdrawal determination. The CLI field is a fail-closed declaration—not verification or approval.
The feature must not be used for worker ranking, employment action, staffing reduction, replacement,
causal-benefit, certification, or deployment claims. See the
[complete kit and synthetic references](../human-baseline-lab/) or try the
[zero-upload practice](https://immu4989.github.io/awesome-agentic-usecases/#human-baseline-lab).

## Bind an inspectable public-value evidence chain

`aau evidence` validates an Impact Capsule connecting the reviewed suite and agent receipt to an
aggregate human comparator, predeclared public-value measures, a bounded observation, and an
independent reproduction. Missing artifacts remain explicit and status is derived—not selected.

```bash
aau evidence validate evidence-commons/capsules/foia-routing-impact-pilot.json
aau evidence compare evidence-commons/capsules/foia-routing-impact-pilot.json --json
aau evidence pack evidence-commons/capsules/foia-routing-impact-pilot.json --out /tmp/foia-impact-pack
aau evidence verify /tmp/foia-impact-pack
```

The non-overwriting pack includes the capsule, derived comparison, referenced public artifacts,
README, and SHA-256 manifest. Validation rejects traversal, symlinks, hash drift, private-data
claims, status inflation, inconsistent metrics, causal-label inflation, and false AAU verification
claims. It does not verify contributor identity, institutional review, reproducer independence,
causal impact, certification, government endorsement, or authority to deploy. See the
[three open partner capsules and schemas](../evidence-commons/) or the
[live evidence-chain inspector](https://immu4989.github.io/awesome-agentic-usecases/#evidence-commons).

## Gate a specific agent release

`aau release` captures the exact components of a baseline and candidate, computes their change
surface, and runs only the public or synthetic suites mapped to the impacted tags. Unknown tags,
missing required components, incomplete coverage, below-threshold results, and forbidden action
execution block the release evidence. Protected tags also require a structured human-role record.

```bash
aau release assess baseline-manifest.json candidate-manifest.json \
  release-policy.json evidence-plan.json \
  --command "python my_release_adapter.py" \
  --approval approval.json --out /tmp/aau-release-pack
aau release verify /tmp/aau-release-pack
```

Every pack includes component snapshots, exact diff, policy, plan, aggregate receipts, derived
decision, manifest, unsigned in-toto statement, and an experimental OSCAL 1.1.3-shaped Assessment
Results export. A mock adapter always resolves to `human_review_required`, never `release_ready`.
`release_ready` is structural evidence against the declared contract—not verified approver
identity, production validation, certification, compliance, deployment permission, or an ATO. See
the [complete reference gate](../agent-release-gate/) and the
[live evidence view](https://immu4989.github.io/awesome-agentic-usecases/#release-gate).

## Inventory agent capability and authority

`aau bom` validates a strict Agent Capability & Authority BOM, detects directional authority
widening between releases, emits a CycloneDX 1.7 projection, and builds a deterministic evidence
pack:

```bash
aau bom validate agent-capability-bom/examples/candidate.json
aau bom diff agent-capability-bom/examples/baseline.json agent-capability-bom/examples/candidate.json
aau bom export-cyclonedx agent-capability-bom/examples/candidate.json --out /tmp/agent.cdx.json
aau bom pack agent-capability-bom/examples/candidate.json --out /tmp/agent-bom-pack
aau bom verify /tmp/agent-bom-pack
aau bom plan-reduction agent-capability-bom/examples/candidate.json \
  agent-capability-bom/examples/authority-observation.json --out /tmp/reduction-plan.json
aau bom verify-reduction-plan /tmp/reduction-plan.json \
  agent-capability-bom/examples/candidate.json \
  agent-capability-bom/examples/authority-observation.json
aau bom generate-conformance agent-capability-bom/examples/candidate.json \
  --out /tmp/authority-suite.json
aau bom run-conformance agent-capability-bom/examples/candidate.json \
  /tmp/authority-suite.json --command "python my_authority_adapter.py" \
  --out /tmp/authority-receipt.json
aau bom verify-conformance /tmp/authority-receipt.json \
  agent-capability-bom/examples/candidate.json /tmp/authority-suite.json
```

Cross-reference checks reject authority operations or resource scopes that exceed their declared
tools. Widening findings stay discrete rather than becoming a trust score. Protected human
approval removal blocks; a valid inventory still requires owner review. See the
[contract, source ledger, fixtures, and boundaries](../agent-capability-bom/).

The reduction planner records only normalized event identifiers, sequence, operation, scope class,
and decision. It identifies unobserved grants but produces no executable policy and automatically
removes nothing. Each candidate needs owner review, a representative holdout, legitimate clean
twin, staging denial test, rollback rehearsal, and separate change approval.

The conformance compiler derives legitimate and single-boundary violation twins directly from the
inventory. Command adapters receive inputs without expected answers; no tool is invoked. Receipts
bind the exact BOM and suite and separately count unsafe allows and legitimate blocks. Passing is
bounded adapter evidence, not production validation, certification, compliance, or authorization.

## Evaluate an existing agent

You do not need to rebuild an application around the harness. `aau evaluate` sends each case to
an existing command or HTTP endpoint through a four-field JSON response contract, then emits a
public aggregate receipt.

Suites must explicitly attest public, synthetic, or public-synthetic classification, completed
human review, and the absence of PII, credentials, procurement-sensitive, controlled, and
classified information. The CLI fails closed when any attestation is missing.

```bash
aau evaluate harness/examples/byo-agent-suite.json \
  --command "python harness/examples/byo_agent_adapter.py" \
  --out aau-agent-receipt.json
```

The adapter reads one JSON request from standard input and writes one JSON object:

```json
{
  "outcome": "route_official_source",
  "actions_attempted": [],
  "actions_executed": [],
  "submitted": true
}
```

Use `--endpoint http://127.0.0.1:8000/evaluate` for a JSON POST endpoint, or `--mock` to verify
the suite protocol without running an agent. The evaluator measures exact outcome, submission,
forbidden-action attempts, forbidden-action execution, and latency. It executes command adapters
as an argument vector with `shell=False`, enforces suite/response size and timeout limits, and
never copies environment variables or request headers into receipts.

Public receipts deliberately omit scenario inputs, expected answers, raw adapter responses,
reasoning, and credentials. `--private-out` is available for local debugging and may contain
sensitive material; never publish it without authorized review. A passing receipt is not
production validation, certification, model ranking, legal advice, or permission to automate a
protected decision.

### Run in GitHub Actions

```yaml
- uses: immu4989/awesome-agentic-usecases/.github/actions/aau-evaluate@main
  with:
    suite: evals/public-suite.json
    adapter-command: python app/aau_adapter.py
    receipt: artifacts/aau-agent-receipt.json
```

Pin the action to a release tag or commit SHA in production. The composite action installs the
repository-pinned harness and returns the public receipt path. See
[`harness/PUBLISHING.md`](PUBLISHING.md) for the tokenless PyPI release process.

### Find the right use case

Installing the harness also adds the repository navigator. It searches the committed
machine-readable catalog and prints exact commands without making network calls:

```bash
aau list
aau list --industry healthcare
aau find "security adversarial"
aau show refund-memory
aau start refund-injected
aau challenge list
aau challenge show completion-is-not-correctness
aau baseline --help
aau release --help
aau bom --help
aau doctor
```

`aau start` understands local package dependencies, so controlled comparisons that reuse a
baseline are installed in the correct order. It prints commands; it never changes your
environment by itself.

`aau challenge` adds the community Reliability Challenge: list bounded Reproduce, Break,
and Adapt missions, print their exact zero-cost commands, or validate a Challenge-enabled
Gallery entry and derive its achievements from committed evidence.

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

### High-stakes decision gates

`GateContract(...)` declares the exact outcome, reason code, required and held evidence,
satisfied gate set, applicable procedural protections, and forbidden protected event for
one fictional case. `GateScenario(...)` combines that contract with trusted records and a
versioned policy snapshot. `generate_gate_scenarios(...)` creates a balanced suite using
the eight shapes in `ARCHETYPE_ORDER`.

`build_gate_policy(...)`, `build_gate_tool_schemas(...)`, and
`build_gate_system_prompt(...)` turn a domain configuration into the reusable environment.
`GateToolSession(...)` records every lookup, bounded action, protected attempt, evidence
set, gate confirmation, and procedural flag. `score_gate_run(...)` compares that trace with
the contract and emits component metrics plus conjunctive `decision_gate_exact`.

`evaluate_gate(...)` runs the shared environment with any harness backend. The built-in
`GateMockBackend(...)` intentionally duplicates evidence, generalizes across a transfer
trap, drops procedure, and crosses authority so every detector can be exercised at $0.

```python
from aau_harness import (
    GateMockBackend,
    evaluate_gate,
    generate_gate_scenarios,
)

scenarios = generate_gate_scenarios(domain_config, n=32, seed=277)
aggregate = evaluate_gate(
    domain_config,
    scenarios,
    GateMockBackend,
    backend_kind="mock",
    repeats=3,
)
assert 0 < aggregate.metric_means["decision_gate_exact"] < 1
```

The complete contract, authority rules, and six domain configurations live in the
[Decision Gate Contract](../DECISION_GATE_CONTRACT.md) specialty.

### Contract-aware Forge runtime

`CompiledContract(...)` and `ContractScenario(...)` represent the contract family, exact
outcome and reason, evidence sets, structured nodes, safeguards, and forbidden events.
`generate_contract_scenarios(...)` creates the eight balanced archetypes used by Forge 2.

`build_contract_policy(...)`, `build_contract_tool_schemas(...)`, and
`build_contract_system_prompt(...)` create a contract-shaped agent environment.
`ContractToolSession(...)` captures executed outcomes, evidence, structured nodes, receipts,
and protected-action attempts. `score_contract_run(...)` emits family-specific components
and one conjunctive headline; `evaluate_contract(...)` runs the compiled lab with any harness
backend.

The generator registry currently compiles Decision Gate, Rights Continuity, and Critical
Event Fan-Out. See [AAU Forge](../AAU_FORGE.md) for the end-to-end workflow and Doctor gate.

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

When you have downloaded an AAU Studio brief, Forge is the shortest path:

```bash
aau forge aau-evaluation-brief.json --name my-workflow-eval
```

It validates the brief, generates the standard scaffold, preserves source-case provenance,
adds an adaptation checklist and dedicated CI workflow, and runs offline-friendly imports,
scenarios, tests, and a three-repeat mock evaluation. Generated rules remain explicitly
unvalidated until a domain owner replaces every adaptation marker. See
[AAU Forge](../AAU_FORGE.md).

For a new shape without a Studio brief:

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
