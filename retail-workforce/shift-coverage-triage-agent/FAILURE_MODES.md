# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs, with a reproducing scenario id. Observations are
from the three real-model runs in `results/`.

### 1. Invented "overtime is expensive" heuristic overrides written policy

- **Reproduce:** `sc-000`, `sc-008`, `sc-022` (`--backend mistral`) — 3/3 repeats each;
  21 misses total across the run.
- **What happens:** policy POL-PREF-00 states the fill preference order explicitly —
  overtime first, then borrowing. Mistral repeatedly retrieves it, then picks
  `borrow_from_nearby` when a compliant overtime candidate exists at the home store,
  applying a real-world "overtime costs more" instinct that appears nowhere in the
  policy it just read.
- **Why it matters:** the model isn't failing to find the rule; it's overruling it with
  a prior. For a compliance-shaped task that's the dangerous direction — the agent looks
  reasonable and quietly violates the documented process.

### 2. Over-escalation: handing fillable shifts to the district manager

- **Reproduce:** `sc-002`, and 11 misses total (`--backend cerebras`/kimi-k2p6).
- **What happens:** the strongest model (0.822) makes almost all its errors by choosing
  `escalate_to_district` when a compliant overtime or borrow fill exists. It treats the
  weekly-hours arithmetic as a reason to punt rather than resolve.
- **Why it matters:** over-escalation is the quiet failure of a triage agent — every
  unnecessary escalation is a decision the system was supposed to make landing back on a
  human. Aggregate accuracy counts it the same as any other miss; the confusion
  breakdown is what reveals the agent is *cautious-wrong*, not *randomly wrong*.

### 3. Commit-stall: investigates, re-reads policy, never submits

- **Reproduce:** `sc-012`, `sc-014`, `sc-026` (`--backend fireworks`, gpt-oss-120b) —
  10 of 90 runs; `sc-014` searched the labor policy KB **five times in a row** before
  ending the turn with no decision.
- **What happens:** the model gathers the shift record and roster, then loops on
  policy search and exits without calling `submit_coverage_plan`. All the evidence, no
  decision.
- **Why it matters:** in production this is a shift that shows as "worked" but never gets
  covered. The `submitted` metric prices it in — gpt-oss submitted only 0.889 of the
  time here — and the loop-on-search signature is exactly what a per-model propensity
  check catches that a capability benchmark misses.

### 4. Same model, different domain, different competence

- **Cross-reference:** gpt-oss-120b scores 0.667 here but ~0.97 on the
  [security alert-triage](../../security-operations/alert-triage-agent/) use case; kimi
  leads here but is *beaten* by gpt-oss on alert-triage.
- **Why it matters:** there is no "best model" for agents — only a best model per task.
  Retail scheduling with compound labor-law arithmetic and SOC alert triage stress
  different capabilities, and the ranking flips between them. Verifying per use case,
  not per vendor benchmark, is the whole point.
