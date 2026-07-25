# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs. All arms use the same 30 scenarios and the same gold as
[exception-triage-agent](../exception-triage-agent/), so every number here is directly
comparable to that baseline. Accuracy is quoted **conditional on the agent submitting a
decision** unless stated otherwise — see failure 5 for why.

### 1. A solved task becomes an unsolved one, with no change to the task

- **Reproduce:** `--arm clean` then `--arm drift --backend fireworks --model
  accounts/fireworks/models/kimi-k2p6`. Clean **1.000** → drift **0.611**.
- **What happens:** kimi-k2p6 is the only model that ever scored a perfect 90/90 on this
  task. Serving it a cached record, a record that disagrees with the carrier feed, or a
  partial response costs it **39 points** — on the identical 30 tickets, with the identical
  gold, and the identical prompt.
- **Why it matters:** this is the eval-to-production gap made measurable. Nothing about the
  reasoning got harder; only the world got realistic. Any eval that hands the agent a
  truthful, complete, self-consistent world is reporting an upper bound, and this use case
  suggests the gap between that bound and production behaviour can be tens of points.

### 2. Robustness tracks a habit, not a capability

- **Reproduce:** compare `detail.refreshed` and the drift drop across the three models.
  kimi refreshes on 0.20 of runs and loses 39 points; Qwen 0.52 and loses 33; gpt-oss 1.00
  and loses 13.
- **What happens:** the ordering is monotonic across three vendors, and it reappears exactly
  where it should — accuracy on `STALE_SNAPSHOT` is kimi **0.22**, Qwen **0.33**, gpt-oss
  **0.89**.
- **Why it matters:** it is the **inverse** of clean-world skill. The strongest model on
  truthful data is the most fragile on realistic data. Selecting a model on eval accuracy
  therefore selects *against* production robustness unless the eval includes an unreliable
  world.

### 3. The winning behaviour is a reflex, and it looked like discernment

- **Reproduce:** `--arm clean --backend fireworks`. gpt-oss passes `refresh=true` on
  **90 of 90 clean runs**, where nothing is stale and there is nothing to refresh.
- **What happens:** gpt-oss never decides *when* to re-read. It always re-reads. The
  harness's `noticed` metric scored this 1.000 and initially read as the model detecting
  staleness and reacting to it; the clean arm proves it is an unconditional habit.
- **Why it matters:** two things. First, the cheap blunt policy ("always re-read before you
  act") beat the expensive one ("reason about whether this data is current") — the failure
  was never about reasoning, it was about what the agent assumed it could trust. Second, a
  metric that counts a *step* cannot distinguish a reaction from a reflex; only a control
  arm where the step is pointless can. Without the clean arm this would have been published
  as diligence.

### 4. Some bad data is unfixable at the agent layer

- **Reproduce:** `SILENT_WRONG` rows in any arm. kimi **0.00**, Qwen **0.00**, across every
  repeat.
- **What happens:** the record is wrong, carries no staleness marker, has no conflicting
  source, and a refresh returns the same wrong value. There is nothing to notice, so both
  precise models get every one of these wrong regardless of arm — including under the
  tool-layer `freshness_gate`, which repairs only what it can detect.
- **Why it matters:** this is the boundary on every guardrail in this repo. Environment
  design contains the failures it can see; a silently wrong upstream record is a data-quality
  problem and no amount of agent engineering touches it. Reporting a defence without this
  archetype would have made the gate look like a silver bullet.
- **Note:** gpt-oss scores 0.67 here, which is not robustness — it applies the value
  threshold less precisely, so corrupting the value less reliably flips its answer. Being
  imprecise is not the same as being resilient.

### 5. Two conclusions that were stall artifacts, not findings

- **Reproduce:** compare raw `action_accuracy` against accuracy among submitted runs for
  gpt-oss across arms.
- **What happened:** gpt-oss stalls, and stalls suppress accuracy without being wrong
  answers. Raw numbers therefore produced two false readings:
  - drift damage looked like −3 points (0.800 → 0.767); conditionally it is **−13**
    (0.960 → 0.831), because gpt-oss stalled *more* in the clean arm and suppressed the
    clean score;
  - the `prompt_guard` arm scored **0.856, above its own clean-world 0.800**, which would
    have contradicted this repo's standing "environment beats prompt" result. The guard had
    pushed `submitted` from 0.833 to 1.000. Conditionally it is 0.856 — still far below
    clean's 0.960. **It never beat the clean world.**
- **Why it matters:** the repo's own [failure taxonomy](../../FAILURE_TAXONOMY.md#commit-stall)
  states the rule that caught both: read `submitted` before any accuracy or safety metric.
  A stalling model makes every other number on the row mean something different.

### 6. A dead provider is indistinguishable from a model that failed everything

- **Reproduce:** run any arm with an invalid key. Before the fix, the CLI wrote a complete,
  well-formed results file with `0.000` on every metric.
- **What happened:** during this wave a Mistral key expired (401) and a Together balance ran
  out (402). Both produced full evals of zeros that would have been charted, committed, and
  published as model scores.
- **Why it matters:** in the saved JSON, "the provider was down" and "the model failed every
  scenario" look identical. The harness now separates them
  ([`provider_error_rate`](../../harness/src/aau_harness/runner.py)) and refuses to save a
  run that never reached the model. Building the detector from real outage strings
  immediately caught a bug in it: the native backend emits `HTTP 401`, but urllib — the path
  every OpenAI-compatible provider takes — emits `HTTP Error 402`, which the first version
  missed.

### 7. A salted hash nearly broke reproducibility, silently

- **Reproduce:** `pytest logistics-supply-chain/exception-triage-drift/tests -k stable_across_processes`.
- **What happened:** the first version of this use case chose the conflicting exception code
  with Python's built-in `hash()`, which is **salted per process**. The scenarios would have
  been different on every run, so nobody — including its author — could have reproduced a
  number from it. The same function could also pick a code routing to the *same* queue
  (`DAMAGED_IN_TRANSIT` and `LOST_IN_TRANSIT` are both carrier-claims), corrupting the
  record without moving the decision, so a share of `SOURCE_CONFLICT` scenarios were testing
  nothing at all.
- **Why it matters:** neither bug produced an error, an exception, or an implausible number.
  The first published figures looked entirely reasonable and were wrong. The tests that
  caught it assert the two properties the design depends on — the corruption must change the
  answer, and it must not depend on the interpreter's hash seed — and every affected arm was
  re-run afterwards. Verification claims are only worth what the tests behind them assert.
