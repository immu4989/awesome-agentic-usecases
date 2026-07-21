# 🎧 Customer Support & Success

Agentic use cases where the agent **does the work**, not just routes it. Support is
where most companies first give an agent write access — refunds, credits, replacements,
account changes — and it is where the interesting failures stop being misclassifications
and start being actions you cannot undo. Every use case is verified per
[VERIFICATION.md](../VERIFICATION.md).

| Use case | Capability | The question it answers | Status |
|---|---|---|---|
| [💸 refund-resolution-agent](refund-resolution-agent/) | `plan` `act` `human-in-loop` | Can an agent resolve a refund ticket end to end — verifying identity first, avoiding payouts it cannot claw back, and handing off when policy says it must? | ✅ Ready |

**Why this vertical scores differently.** Every other use case in this repo scores a
label. These score *behaviour*: whether prerequisites were respected, whether an
irreversible action was taken when policy forbade it, and only then whether the outcome
was right. An agent can pick the correct remedy and still fail, by paying out before it
verified who it was talking to.
