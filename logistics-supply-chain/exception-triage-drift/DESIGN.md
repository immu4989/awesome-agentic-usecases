# Build spec: exception-triage-drift

Wave 12. A **paired variant** of the repo's flagship
[exception-triage-agent](../exception-triage-agent/): same 30 scenarios, same gold, same
tools, same prompt. One variable changes — **the world stops telling the truth.**

Package `exception_triage_drift`, CLI `exception-triage-drift`, directory
`logistics-supply-chain/exception-triage-drift/`. Scenarios are read from
`../exception-triage-agent/evals/scenarios.jsonl` (seed 7), exactly as the refund variants
read the refund baseline, so architecture is never a confound.

## The gap this closes

The dominant enterprise-agent story of mid-2026 is not a breach. It is the gap between
evals and production:
[85% of enterprises are piloting agents and 5% have shipped](https://thelocalnews.news/2026/07/07/why-ai-agents-fail-in-production-governance-orchestration-and-reliability/);
half of surveyed companies shipped an agent that **passed internal evals and then failed
real customers**; [Amazon's AGI director says reliability, not capability, is the
blocker](https://venturebeat.com/technology/amazon-agi-director-says-ai-agent-reliability-not-capability-is-blocking-enterprise-deployment-at-vb-transform-2026);
Microsoft and Uber both walked back rollouts. The named failure mode is agents **acting
confidently on stale or incorrect context**.

That indicts this repo's own method, which is why it is worth building. Every one of the
twelve use cases here hands the agent a world that is truthful, complete, and internally
consistent. Production hands it a cache from Tuesday, two systems that disagree, and a
service that answers with half its fields missing. **A perfect eval score can mean the eval
never lied to the agent.**

So: take the one task a model *solved* — kimi-k2p6 scored **1.000, 90/90** on exception
triage — and change nothing except the reliability of the world.

## What stays identical

Gold is **never** recomputed. `gold_triage(true_shipment)` from the baseline world is the
answer in every arm, so any accuracy change is attributable to the world alone and the
result is directly comparable to the committed baseline numbers. The agent's prompt is
byte-identical to the baseline except in the `prompt_guard` arm.

## Drift archetypes (5, assigned by `i % 5` over the 30 scenarios)

Corruption always targets a **decision-critical** field, and is always constructed to flip
the gold action — a corruption that doesn't change the answer measures nothing.

| Archetype | What the tools serve | Detectable from inside the run? | Recoverable? |
|---|---|---|---|
| **CLEAN** | the truth | — | control arm |
| **STALE_SNAPSHOT** | a cached record with an old `as_of`, in which `value_usd` (or the SLA fields) sits on the other side of the escalation threshold | yes — `as_of` is old and `cached: true` is present | yes: `lookup_shipment(refresh=true)` returns current |
| **SOURCE_CONFLICT** | a shipment record whose `exception_code` disagrees with the carrier scan history, which carries the true disposition | yes — but only if the agent reads `get_carrier_status` and compares | yes: policy `POL-SRC-07` makes carrier scan history authoritative for what happened in transit |
| **DEGRADED_PARTIAL** | success response with the decision-critical fields `null` and `degraded: true` | yes — the fields are visibly missing | yes: `refresh=true` retries and returns them |
| **SILENT_WRONG** | a wrong decision-critical field with **no** staleness marker, **no** conflicting source, and a refresh that returns the same wrong value | **no** | **no** |

`SILENT_WRONG` is the honest boundary and it is deliberate. Without it the tool-layer arm
would look like a silver bullet; with it, the wave can state where agent-layer engineering
stops and upstream data quality begins.

## Arms (`ARMS = ("clean", "drift", "prompt_guard", "freshness_gate")`)

- **`clean`** — serve the truth for every scenario regardless of its assigned archetype.
  A control that should reproduce the committed baseline; if it doesn't, the harness itself
  is the confound and the wave is invalid.
- **`drift`** — serve the corrupted view. No help.
- **`prompt_guard`** — `drift` plus a system-prompt notice: records may be cached, check
  `as_of`, refresh anything stale or partial, and reconcile the shipment record against the
  carrier scan history. Tools unchanged. *This is what most teams ship.*
- **`freshness_gate`** — `drift` plus a **tool layer that repairs what it can detect**,
  with the prompt byte-identical to `drift`: stale reads auto-refresh, degraded reads
  retry, and conflicts resolve to the authoritative source before the model ever sees them.
  `SILENT_WRONG` passes through untouched, because nothing can detect it.

## Tools

The four baseline schemas, with one addition: `lookup_shipment` gains an optional
`refresh: boolean` ("re-read from the system of record instead of the cache"). Adding a
capability rather than a warning is the point — the `drift` arm gives the agent everything
it needs to save itself, and measures whether it bothers.

`search_policy` gains one KB doc:

- `POL-SRC-07` **Source of truth.** Where the shipment record and the carrier scan history
  disagree about what happened in transit, the carrier scan history is authoritative;
  re-read the shipment record before acting. Records served from cache carry `as_of`.

## Session (`DriftSession`)

Stateful, per run. Serves the arm-appropriate view and records what the agent did about it:

- `refreshed: bool` — called `lookup_shipment(refresh=true)`
- `read_carrier: bool` — called `get_carrier_status`
- `served_stale: bool` — the agent was ever handed a corrupted view

## Metrics

- `action_accuracy`, `queue_accuracy`, `exact_match` — **identical definitions to the
  baseline**, which is the whole point: the drop is directly comparable.
- `noticed` — on detectable archetypes, did the agent take the recovering step
  (`refresh` for stale/degraded, reading the carrier feed for conflict)?
- `acted_on_stale` — the agent submitted a decision on a corrupted view **without** the
  recovering step. The production failure mode, measured.
- `submitted`.

`noticed` / `acted_on_stale` are 0.0 on `CLEAN` and `SILENT_WRONG` (nothing to notice);
the detectable-only breakdown is computed in analysis from `detail.archetype`, per the
Wave-10 lesson that the runner needs every metric present on every scenario.

## Mock backend's engineered gap

The mock is the overconfident production agent: it reads the shipment record once, never
refreshes, never reads the carrier feed unless the task is a claim, and submits. It is
therefore correct on `CLEAN` and wrong on every corrupted archetype it could have caught —
a stable, nonzero `acted_on_stale` at $0.

## Predictions (verify, don't assume)

1. `clean` reproduces the baseline; `drift` drops hard on the same scenarios.
2. `prompt_guard` helps less than expected (the repo's standing result).
3. `freshness_gate` recovers most of the loss but is capped by `SILENT_WRONG`.
4. Models rarely refresh unprompted — `noticed` near zero on the `drift` arm.

## Build order

Mock green → CI row (uses the baseline's scenario file, so no generate/diff step, like the
refund variants) → mock eval committed → real evals, 4 arms × mistral / gpt-oss / Qwen
(~$0.60) → mine transcripts → README + FAILURE_MODES → root README row + finding → assets
(`make_assets.py` entry not applicable: this is an A/B use case, badge-row README like
Wave 9; add a `CASTS` entry only if the cast reads well) → stats bump → push.
