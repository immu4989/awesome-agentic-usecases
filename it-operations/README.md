# 🖥️ IT Ops & DevOps

Agentic use cases where the agent **watches** rather than answers. Monitoring is the
oldest automation problem in operations and still the least solved: the hard part was
never detecting a threshold breach, it was deciding which breaches deserve a human at
3am. Every use case is verified per [VERIFICATION.md](../VERIFICATION.md).

| Use case | Capability | The question it answers | Status |
|---|---|---|---|
| [📟 oncall-watch-agent](oncall-watch-agent/) | `watch` `decide` | Telemetry arrives a minute at a time. Is this window a page, a ticket, or nothing — and can the agent wait long enough to tell a real regression from a blip that heals itself? | ✅ Ready |

**Why this vertical scores differently.** Every other use case here hands the agent a
complete case file. This one advances a clock: the agent buys evidence one tick at a
time and cannot look ahead, so committing early means committing on less. That makes
*patience* a measurable property rather than a virtue, and it turns alert fatigue from
an anecdote into a number.
