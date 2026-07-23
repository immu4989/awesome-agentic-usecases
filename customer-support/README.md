<p align="center">
  <a href="../README.md">← all industries</a> ·
  <img src="https://img.shields.io/badge/industry-Customer%20Support-e34948" alt="Customer Support">
  <img src="https://img.shields.io/badge/use%20cases-4-e34948" alt="4 use cases">
  <img src="https://img.shields.io/badge/verified-evals%20%C2%B7%20cost%20%C2%B7%20failure%20modes-008300" alt="verified">
</p>

# 🎧 Customer Support & Success

Agentic use cases where the agent **does the work**, not just routes it. Support is where
most companies first give an agent write access — refunds, credits, replacements — and it
is where the interesting failures stop being misclassifications and start being actions you
cannot undo.

This vertical is built as one **controlled experiment in four parts**: a single refund task,
then three variations that each change exactly one thing, so every comparison is honest.

## The four parts

| Use case | Capability | The question | Headline finding |
|---|---|---|---|
| [💸 refund-resolution-agent](refund-resolution-agent/) | `plan` `act` `human-in-loop` | Can an agent resolve a refund end to end — verify identity first, avoid payouts it can't claw back, hand off when policy says so? | **Ceremony is learned, prohibition is not.** No model ever moved money before verifying identity (0 violations in 270 runs), yet mistral issued a forbidden refund in 15/15 runs of every banned archetype. |
| [👥 refund-crew](refund-crew/) | `multi-agent` | Does orchestration help? Three agents on the exact task one agent already solved, same scenarios. | **Orchestration amplifies whatever the model already does** — it moved one model +8 points and another −60, and never beat the best single agent. |
| [🔧 refund-guarded](refund-guarded/) | `intervention A/B` | Does *our own advice* work? We told people to put prohibitions in the tool layer — was that measured? | **Tool-layer enforcement gained +0.489 for free; a prompt paragraph telling the model to finish doubled the stalls it was written to fix.** |
| [🎯 refund-injected](refund-injected/) | `adversarial A/B` | Do the defences survive an attacker? Prompt injection through the customer's own ticket text. | **74% of attacks moved money past a prompt guard that named every attack shape; a tool-layer guard stopped 100%** — it doesn't make the agent resistant, it makes being fooled irrelevant. |

## Why this vertical scores differently

Every triage use case in the repo scores a *label*. These score *behaviour*: whether
prerequisites were respected, whether an irreversible action was taken when policy forbade
it, and only then whether the outcome was right. An agent can pick the correct remedy and
still fail — by paying out before it verified who it was talking to.

Because the crew, guarded, and injected variants all read the **same committed scenario
file** as the single-agent baseline, architecture, defence, and attack are each isolated as
the only variable. That is the controlled comparison almost nobody publishes.
