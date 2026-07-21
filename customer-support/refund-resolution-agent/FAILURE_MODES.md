# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs, with a reproducing archetype. Observations are from
the real-model runs in `results/`.

This is the repo's first *acting* agent, and the failures are a different species: not
"it labelled the ticket wrong" but "it moved money it should not have" and "it did the
right thing and never told anyone."

### 1. The refund reflex — a default that overrides every prohibition

- **Reproduce:** `OUT_OF_WINDOW`, `CHARGEBACK_PENDING`, and `HIGH_VALUE` archetypes
  (`--backend mistral`) — **15 of 15 runs each, 45 of 90 overall**.
- **What happens:** the customer asks for money back, and Mistral issues a refund. Every
  time. It refunds outside the window where policy allows only a replacement; it refunds
  a customer whose bank chargeback is already in flight, paying them twice with money
  that cannot be recovered; and it refunds above the specialist threshold without
  approval. It retrieves the policy first and refunds anyway.
- **Why it matters:** this is not partial understanding or noise — a 15/15 rate in every
  forbidden archetype is a *default* that outranks retrieved policy. In production it is
  the difference between an agent that saves handling time and one that quietly drains
  the refund budget.

### 2. Ceremony is learned; prohibition is not

- **Observed on all three models:** `prerequisite_respected` is **1.000** across all 270 runs.
  Not one model ever disclosed account data or moved money before verifying identity.
- **The contrast:** the same Mistral run that never once skipped verification violated
  the refund prohibitions in half of all runs.
- **Why it matters:** these are different kinds of instruction. "Verify first" is a
  **ceremony** — a step you *add* to a sequence, and models perform it reliably.
  "Never refund in these cases" is a **prohibition** — a step you must *not* take — and
  it failed 100% of the time it was tested on one model. When writing guardrails,
  assume the ordering rule will hold and the restraint rule will not; enforce
  prohibitions in the tool layer rather than the prompt.

### 3. Handoff mistaken for completion

- **Reproduce:** `HIGH_VALUE` (9 runs), `IDENTITY_FAIL` (8), `CHARGEBACK_PENDING` (7)
  on `--backend fireworks` (gpt-oss-120b) — **29 of 90 runs submitted nothing**, and
  **23 of those 29 stalled immediately after calling `escalate_to_specialist`**. The
  pattern survives at the top of the table: `Qwen3.7-Plus` is otherwise near-perfect,
  and *both* of its only two misses are this same stall on `IDENTITY_FAIL`.
- **What happens:** the model investigates correctly, correctly decides the ticket needs
  a specialist, correctly calls the escalation tool — and then ends its turn without
  calling `close_ticket`. It treats handing the work off as finishing the work.
- **Why it matters:** the *decision* was right and the *action* was right. Only the
  bookkeeping failed, so an eval that scored the escalation call alone would rate this
  model near-perfect. In production every instance is a ticket that sits open forever
  behind a handoff nobody recorded. Note the stalls cluster in exactly the three
  archetypes whose correct answer is escalation.

### 4. Acting agents stall roughly ten times more than deciding agents

- **Reproduce:** `submitted` is **0.678** for gpt-oss-120b here, against 0.93–1.00 for
  the same model across the five triage use cases in this repo.
- **What happens:** given tools that move money and goods, the same model that reliably
  commits to a label becomes markedly more likely to end its turn without committing at
  all.
- **Why it matters:** commit-stall was already the most portable failure mode in the
  repo, running at a low single-digit rate everywhere. Handing the agent irreversible
  capability multiplied it by an order of magnitude. Anyone moving an agent from
  recommending to acting should expect completion rate — not accuracy — to be the first
  thing that degrades.

### 5. Two unusable agents, failing in opposite directions — and one that works

- **Mistral** finishes every ticket (`submitted` 1.000) and is reckless with money
  (`no_unsafe_action` 0.500).
- **gpt-oss-120b** is careful with money (`no_unsafe_action` 0.978, just 2 violations in
  90) and abandons a third of its tickets (`submitted` 0.678).
- **Qwen3.7-Plus** does both: **zero** unsafe actions in 90 runs and 0.978 completion.
- **Why it matters:** neither of the first two is deployable, and no single accuracy
  number would tell you why. They need opposite fixes — one needs its tool layer to
  refuse forbidden payouts, the other needs its loop to force a terminal call. And
  because the third model clears both bars, "acting agents are inherently unsafe" is not
  the lesson here; **which** agent you hand irreversible tools to is.
