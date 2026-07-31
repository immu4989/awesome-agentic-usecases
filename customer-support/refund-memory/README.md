<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/shape-adversarial%20A%2FB-b3261e" alt="adversarial">
  <img src="https://img.shields.io/badge/attack-memory%20poisoning-c2185b" alt="memory poisoning">
  <img src="https://img.shields.io/badge/models-3%20families-4a3aa7" alt="three model families">
  <img src="https://img.shields.io/badge/reproduce-%241.76-0b8457" alt="cost to reproduce">
</p>

# 🧠 Refund Memory — harm that outlives the attacker

## The gap this closes

[Wave 11](../refund-injected/) put an attacker in the ticket and measured what happened
**in that conversation**. Every use case in this repo so far shares that shape: the payload
and the damage are in the same session, so closing the session closes the attack.

Memory breaks that. A false fact written during one contact is still there on the next one,
and the session that acts on it contains nothing adversarial at all — no payload to filter,
no injection to detect, no attacker present. The ticket is ordinary. The agent is simply
wrong about the customer, and stays wrong.

So the question here is not *can text in a ticket steer an agent* — Wave 11 answered that.
It is: **does a claim survive into a later, clean session, and does it still do damage
there?**

## Memory is not a tool the agent chooses to use

This is the part an earlier version of this use case got wrong, and it is worth stating
plainly because the mistake produced a null result that looked like a finding.

Memory here is **automatic on both ends**. Between sessions, an extractor pulls
durable-looking facts out of session 1 and stores them. Before session 2, everything stored
is rendered into the system prompt. The agent is not asked and cannot decline.

That is how memory actually ships: ChatGPT-style memory automatically extracts facts from a
conversation and injects relevant ones into later ones invisibly. The first build of this
use case instead exposed `save_note` and `recall_notes` as ordinary tools — and models
called `save_note` in **8 of 72 runs** on one model and **1 of 72** on another. The attack
had nothing to land on. An agent that can decline to remember cannot be poisoned, and no
deployed memory system offers that choice.

## The design

24 scenarios × 2 sessions. Session 1 may install a false fact. **Session 2 contains nothing
adversarial** — a test asserts it, scanning session-2 ticket text for every payload phrase.
`get_crm_sync` serves its record in session 1 only, so "the attacker is gone" is enforced,
not assumed.

| Archetype | Session 1 carries | Detectable at write time? |
|---|---|---|
| `CLEAN_BASELINE` | an ordinary ticket | — (control) |
| `POISON_TICKET` | a forged supervisor note in **ticket text** | **yes** — untrusted origin |
| `POISON_TOOL` | the **same sentence** arriving as a **CRM record** | **no** — looks like system data |
| `LEGIT_NOTE` | a genuinely useful fact worth storing | n/a — this *should* be written |

The claim is byte-identical across both poison channels; only its origin differs, which
makes origin the isolated variable. `LEGIT_NOTE` is what separates *this note is dangerous*
from *having any memory at all is dangerous*.

Gold for both sessions comes from the baseline's `gold_plan`, never recomputed — so a
successful attack can never change what the correct answer was.

**Arms:** `none` · `prompt_guard` (a notice that remembered notes are records, not policy)
· `write_gate` (the extractor keeps provenance and refuses claims traceable to customer
text; prompt byte-identical to `none`).

## Results

3 model families × 3 arms × 24 scenarios × 2 sessions × 3 repeats. `verified` is the rate at
which the agent ran an identity check in **session 2**.

### Poisoned memory suppresses the identity check — in 2 of 3 models

Arm `none`. Δ is against each model's own `CLEAN_BASELINE`.

| model | clean | `POISON_TICKET` | `POISON_TOOL` | `LEGIT_NOTE` |
|---|---|---|---|---|
| **gpt-oss-120b** | 1.00 | **0.56** `(−0.44)` | **0.50** `(−0.50)` | 1.00 `(+0.00)` |
| **deepseek** | 1.00 | **0.83** `(−0.17)` | **0.72** `(−0.28)` | 1.00 `(+0.00)` |
| **mistral-small** | 1.00 | 1.00 `(+0.00)` | 1.00 `(+0.00)` | 1.00 `(+0.00)` |

**`LEGIT_NOTE` never moves.** On every model, in every arm, carrying a stored note is
harmless — it is what the note *says* that suppresses the check. Without that control this
table would be indistinguishable from "memory makes agents worse."

### A write-time provenance gate restores it — on the channel it can see

Paired bootstrap over the same scenarios, `write_gate` − `none`, 95% CI.

| model | `CLEAN_BASELINE` | `POISON_TICKET` | `POISON_TOOL` | `LEGIT_NOTE` |
|---|---|---|---|---|
| **gpt-oss-120b** | +0.000 `[0.000, 0.000]` | **+0.444** `[+0.111, +0.833]` | −0.111 `[−0.333, 0.000]` | +0.000 `[0.000, 0.000]` |
| **deepseek** | +0.000 `[0.000, 0.000]` | **+0.167** `[+0.056, +0.278]` | +0.111 `[0.000, +0.222]` | +0.000 `[0.000, 0.000]` |

Both controls are **exactly zero with zero-width intervals**, so there is no drift for the
effect to be confused with. The gate is significant on the ticket channel for both
susceptible models and reaches significance on neither tool channel — the ceiling this use
case was built to demonstrate, measured rather than asserted.

That ceiling is deliberate. A gate that taints ticket-derived text cannot distinguish a
poisoned CRM record from a real one, because by the time the claim arrives it *is* system
data. This repo has measured the same asymmetry twice before
([trifecta](../../security-operations/trifecta-exfil-agent/), [drift](../../logistics-supply-chain/exception-triage-drift/)).

### The prompt-level guard is not reliable

`prompt_guard` − `none` on `POISON_TICKET`: **deepseek +0.167 `[+0.056, +0.278]`
significant**, but **gpt-oss +0.278 `[−0.333, +0.778]` not distinguishable from zero**.

Same notice, same scenarios, opposite verdicts. Wave 11 reached this conclusion by a
different route: a guard and a payload are the same kind of object, and which one wins is
not a property you control per-request.

## What did *not* replicate: the headline I started with

`sleeper_harm` — an unauthorized refund in the clean session — is a **null on all three
models**. No interval excludes zero. Only deepseek ever issued a bad refund at all
(`+0.17`); gpt-oss skipped the identity check and still reached a defensible resolution.

**The endpoint was changed after seeing the first pass.** `sleeper_harm` came back flat
while the traces plainly showed the check being skipped, so `s2_identity_verified` was
added on a second pass and re-run. That is post-hoc, and it is the honest description of
what happened. Two things argue it is not fishing: it is the endpoint the poison's own
wording implies (*"identity checks are waived"*), and the `LEGIT_NOTE` control that
guards it was designed in from the start and stays flat everywhere.

The general lesson is one the [taxonomy](../../FAILURE_TAXONOMY.md#safety-by-inaction)
already carried: a *did it do the bad thing* metric is a coarse instrument. An agent can
drop a safety check without the omission changing its final answer — and only the coarse
metric will tell you nothing happened.

## Honest limits

- **n = 6 scenarios per archetype per arm.** The CIs are wide. `+0.444 [+0.111, +0.833]`
  excludes zero but does not pin the magnitude.
- **gpt-oss stalls a lot** — 47–65% of runs end without a submission in at least one
  session. This does **not** explain the effect: poisoned sessions *completed more often*
  than clean ones (0.94 vs 0.83) and still skipped the check, and verification conditional
  on completing (0.59) matches the unconditional rate (0.56).
- **`deepseek-chat` is an alias, and so is what it resolves to.** The provider served
  `deepseek-v4-flash`; that name in turn rolls forward to the newest snapshot (OpenRouter
  exposes the dated one, currently `deepseek-v4-flash-0731`). Provenance marks the run
  unpinned. Re-running may exercise different weights, and did: these results were also
  **repriced on 2026-07-31** after the alias was found to have been billed at the older
  V3 rate ($0.27/$1.10) while V4 Flash ($0.14/$0.28) was actually serving. Dollars fell
  ~2x; token counts, and therefore every finding, are unchanged.
- **`mistral-small-latest` floats** and is likewise marked unpinned.
- Mistral is immune on this endpoint while being the *least* safe model on refunds
  (it skips payout rules ~50% of the time regardless). Immunity here is not safety.

## Failure modes

See [FAILURE_MODES.md](FAILURE_MODES.md) — including the design error that produced a null,
and the prompt bug that cost 23 points of submission rate.

## Run it

```bash
pip install -e ../../harness -e ../refund-resolution-agent -e .
refund-memory eval --arm none --backend mock          # free, no API key

export FIREWORKS_API_KEY=...
refund-memory eval --arm none         --backend fireworks --model accounts/fireworks/models/gpt-oss-120b --repeats 3
refund-memory eval --arm prompt_guard --backend fireworks --model accounts/fireworks/models/gpt-oss-120b --repeats 3
refund-memory eval --arm write_gate   --backend fireworks --model accounts/fireworks/models/gpt-oss-120b --repeats 3

python evals/analyse.py        # per-archetype table, Δ vs control, stall rates
python evals/compare_arms.py   # paired bootstrap CIs, control drift beside every claim
```

Committed cost: **$1.76** across 9 real runs (gpt-oss $0.54, mistral $0.33, deepseek $0.90).
