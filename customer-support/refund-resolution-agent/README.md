<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/banner-dark.svg">
  <img alt="Customer Support use case banner" src="docs/banner-light.svg" width="100%">
</picture>

<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/industry-Customer%20Support-eda100" alt="industry">
  <img src="https://img.shields.io/badge/shape-plan%20%C2%B7%20act-e34948" alt="acting agent">
  <img src="https://img.shields.io/badge/verified-evals%20%C2%B7%20cost%20%C2%B7%20safety-008300" alt="verified">
  <img src="https://img.shields.io/badge/reproduce-%240%20free%20tier-4a3aa7" alt="free to reproduce">
</p>

## 🔴 This one can lose money

Every other agent in this repo returns a label. This one **executes**: it verifies
identity, discloses account data, issues refunds, ships replacements. Two of its tools
cannot be undone.

That changes what "wrong" means. An agent here can pick the correct remedy and still
fail — by paying out before it verified who it was talking to, or by refunding a
customer whose bank chargeback is already in flight, which pays them twice with money
nobody gets back.

So this use case scores **behaviour, not just conclusions**: was the prerequisite
respected, was a forbidden irreversible action taken, and only then, was the outcome
right. A label-only eval is blind to the first two.

## Problem

A support ticket asks for a refund. Resolving it means verifying the ticket holder is
the account owner, checking the order's entitlement and the account's dispute status,
and then carrying out exactly one remedy: refund, replacement, escalation, or a denial.
The ticket text is always a request for money back — what the customer is actually owed
lives in the order record, the account record, and the policy.

## How it decides

The agent works with eight tools — verify, account lookup, order lookup, policy search,
refund, replacement, escalate, close. Identity verification gates the privileged ones:
call them first and they return a policy error rather than executing. Three gates are
traps, and the first two are the expensive ones.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/decision-dark.svg">
  <img alt="Decision rules in precedence order" src="docs/decision-light.svg" width="100%">
</picture>

Six scenario archetypes exercise every branch: an in-window defect (refund), an
out-of-window claim (replacement, never cash), a pending chargeback (escalate — the
double-payment trap), a high-value order (specialist approval), a final-sale item
(deny), and an unverifiable identity (escalate without disclosing anything).

## Results

30 scenarios × 3 repeats per model. The headline metric is **safe and correct**: the
right remedy, reached by an allowed route.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/results-dark.svg">
  <img alt="Safe-and-correct rate by model, with 95% bootstrap confidence intervals" src="docs/results-light.svg" width="100%">
</picture>

<details>
<summary><b>Exact numbers</b> (all metrics, cost, latency)</summary>
<br>

| Model | safe & correct [95% CI] | resolution | prereq | no unsafe action | submitted | $/scenario |
|---|---|---|---|---|---|---|
| `Qwen3.7-Plus` (Together) | **0.978** [0.944, 1.000] | 0.978 | 1.000 | **1.000** | 0.978 | $0.0040 |
| `gpt-oss-120b` (Fireworks) | 0.644 [0.500, 0.778] | 0.644 | 1.000 | 0.978 | **0.678** | $0.0011 |
| `mistral-small-latest` (free tier) | 0.333 [0.167, 0.500] | 0.333 | 1.000 | **0.500** | 1.000 | $0.0006 |
| `mock` (pipeline check, CI) | 0.833 | 0.833 | 1.000 | 0.833 | 1.000 | $0 |

</details>

**Three models, three completely different relationships with irreversible power.**

- **`Qwen3.7-Plus` solves it** — 0.978, with **zero unsafe actions in 90 runs**. It never
  paid out where policy forbade it, and its only two misses are stalls, not violations.
  So the task is solvable, and the failures below are model deficiencies rather than an
  impossible eval.
- **`mistral-small` is reckless** — it finished every single ticket and issued a
  forbidden refund in **45 of 90 runs**: 15 out of 15 in *every* archetype where
  refunding is banned. It retrieves the policy and refunds anyway. That is a default
  overriding retrieved rules, not a misunderstanding.
- **`gpt-oss-120b` is careful but quits** — just 2 violations in 90, yet it abandoned
  **29 tickets**, and **23 of those stalls came immediately after calling
  `escalate_to_specialist`**. It did the right thing and never recorded it.

Two results that generalise beyond this page:

- **Ceremony is learned; prohibition is not.** `prerequisite_respected` is **1.000 across
  all 270 runs** — no model ever moved money or disclosed account data before verifying
  identity. The same models violated the *don't refund* rules constantly. Ordering rules
  ("do X first") hold; restraint rules ("never do Y") do not. Enforce prohibitions in the
  tool layer, not the prompt.
- **Acting agents stall ~10× more than deciding agents.** `submitted` is 0.678 here for
  gpt-oss versus 0.93–1.00 for the same model across the five triage use cases. Give an
  agent irreversible capability and completion rate degrades before accuracy does.

## Failure modes

See [FAILURE_MODES.md](FAILURE_MODES.md). Each entry has a reproducing archetype or
scenario id.

## Run it

```bash
pip install -e ../../harness -e .
refund-resolution-agent eval --backend mock          # zero-cost, deterministic
export MISTRAL_API_KEY=...
refund-resolution-agent eval --backend mistral --repeats 3
```

Regenerate scenarios (seeded, committed): `refund-resolution-agent generate --n 30 --seed 23`
