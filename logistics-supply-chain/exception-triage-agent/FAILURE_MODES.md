# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs, with the scenario id that reproduces it. Modes 1–5
are from `results/eval_mistral-small-latest.json`; modes 6–7 are from
`results/eval_meta-llama_Llama-3.3-70B-Instruct-Turbo.json`. The two models fail in
disjoint ways: every failing Mistral run had called all four tools (judgment failures),
while Llama-3.3-70B's failures are structural (malformed submissions, skipped
investigation).

### 1. Reasoning–action contradiction

- **Reproduce:** `sc-028` (`--backend mistral`) — fails 3/3 repeats.
- **What happens:** the shipment's declared value is $2,294 — above the $2,000
  escalation threshold. The agent's submitted reasoning *states the breach and cites the
  policy*: "declared value $2294.12 (> $2000) … POL-ESC-01 requires escalati[on]" — and
  then submits `route_to_queue` anyway.
- **Why it matters:** the scariest agent failure shape. Auditing the reasoning text
  would pass this run; only checking the *action* against ground truth catches it.
  Rationale-level review is not a substitute for outcome-level evals.

### 2. Policy misreading → systematic under-automation

- **Reproduce:** `sc-011`, `sc-017`, `sc-029` (3/3 repeats each); also `sc-006`,
  `sc-023`, `sc-024` intermittently.
- **What happens:** policy POL-WX-05 says weather delays "may be auto-resolved via the
  customer-notification workflow," and POL-ADDR-02 allows auto-applying validated
  address candidates. The agent retrieves these policies, then asserts the opposite —
  "automation is not applicable for weather delays" (`sc-011`, verbatim) — and routes
  every automatable ticket to a human queue.
- **Why it matters:** zero auto-resolutions means the agent silently deletes the entire
  labor-savings case for deploying it. Aggregate accuracy (0.70) looks passable; the
  per-action breakdown shows automation eligibility is where it all concentrates.

### 3. Invented escalation rule (tier-driven over-escalation)

- **Reproduce:** `sc-020` (3/3), `sc-015` (2/3), `sc-009`, `sc-027` (1/3).
- **What happens:** lost or damaged shipments belonging to gold/platinum customers get
  `escalate_to_human` even though value and SLA are below every policy threshold. The
  agent applies an "important customer + emotive incident → escalate" heuristic that
  appears nowhere in the retrieved policy.
- **Why it matters:** over-escalation is the quiet failure that floods human queues and
  erodes trust in the triage system — invisible if you only measure "did it escalate
  when it should have."

### 4. Ignored compound policy clause

- **Reproduce:** `sc-016` (3/3 repeats).
- **What happens:** Platinum-tier customer with 20 SLA hours remaining — POL-ESC-01's
  second clause (platinum AND <24h) requires escalation. The agent cites POL-RET-06 for
  the queue, never applies the compound escalation clause, and routes.
- **Why it matters:** single-condition rules get applied; compound ones get dropped.
  This is the same failure the deterministic mock backend engineers on purpose
  (`agent.py`), so the reporting pipeline always exercises it.

### 5. Stochastic decision flips (why n≥3 is in the bar)

- **Reproduce:** `sc-009`, `sc-023`, `sc-024`, `sc-027` — each fails exactly 1 or 2 of
  3 repeats at temperature 0.
- **What happens:** identical scenario, identical prompt, different action across
  repeats.
- **Why it matters:** a single-run eval would have reported several of these scenarios
  as passes (or failures) purely by draw. This is the concrete case for requiring
  repeats + CIs in [VERIFICATION.md](../../VERIFICATION.md) — the 95% CI on action
  accuracy spans [0.53, 0.84].

### 6. Partial tool arguments (submitted, but malformed)

- **Reproduce:** `sc-000` (`--backend together`, `meta-llama/Llama-3.3-70B-Instruct-Turbo`)
  — 66 of 90 runs across the eval.
- **What happens:** the model calls `submit_triage` with the `queue` argument filled and
  the required `action` (and `reasoning`) arguments missing — and once passed a JSON
  Schema *fragment* as the value (`{'type': 'string', 'value': 'route_to_queue'}`).
  The submission "succeeds" mechanically; the decision is unusable.
- **Why it matters:** headline metrics can hide this completely — `submitted` reads
  0.967 while `action_accuracy` is 0.167. It's also a provider-surface issue: this
  eval's schemas declare every field `required`, but not every provider enforces
  required fields server-side the way Anthropic's strict tool use does. If your
  deployment target doesn't validate, your agent code must.

### 7. Skipped investigation

- **Reproduce:** `sc-004`, `sc-010`, `sc-022` (`--backend together`) — 17 of 90 runs
  submitted with **zero** investigation tool calls; 67 of 90 called only
  `lookup_shipment`, never the carrier feed or the policy KB.
- **What happens:** the model triages from the ticket text and priors alone, exactly
  what the system prompt forbids. Queue accuracy holds up passably (0.844 — the ticket
  text leaks some signal) which makes the shortcut look safe if you don't measure
  disposition accuracy.
- **Why it matters:** tool-use *capability* is not tool-use *propensity*. A model can
  pass every function-calling benchmark and still not bother calling the tools when it
  feels confident. Grounding requirements must be verified per model, not assumed.

### 8. Investigates fully, then stalls at the commit point

- **Reproduce:** `sc-018` (2/3 repeats), `sc-012`, `sc-013`, `sc-019`, `sc-026`
  (`--backend fireworks`, `gpt-oss-120b`) — 6 of 90 runs.
- **What happens:** the model calls the investigation tools correctly — sometimes
  searching policy twice — then ends its turn with explanatory text instead of calling
  `submit_triage`. All the evidence, no decision.
- **Why it matters:** the inverse of mode 7, and invisible to any eval that only checks
  tool-calling ability. In production this is a ticket that looks "worked" but never
  leaves the queue. The `submitted` metric exists exactly to price this in — scored as
  a full miss.

---

**The comparison across models is the point.** Three models, three disjoint dominant
failure shapes: Mistral-small investigates and misjudges (modes 1–5), Llama-3.3-70B
submits malformed or unearned decisions (6–7), gpt-oss-120b occasionally investigates
and never commits (8). A harness that measured only aggregate accuracy would rank them;
it wouldn't tell you *what breaks* — which is the difference between picking a model
and deploying one.

**And the ceiling is reachable:** `kimi-k2p6` scores 90/90 with zero failure modes —
its transcripts show it searching the policy KB twice per ticket (thresholds + the
exception-specific rule), the exact behavior whose absence produces modes 2 and 4. The
eval is solvable; the failures above are model deficiencies, not task impossibility.
