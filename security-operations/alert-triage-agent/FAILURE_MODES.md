# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs, with a reproducing scenario id. Observations are
from the three real-model runs in `results/`.

### 1. The scanner deception — trusting the alert text over the telemetry

- **Reproduce:** `sc-029` (`--backend mistral` AND `--backend fireworks`/gpt-oss) —
  fails 3/3 repeats on **both** models.
- **What happens:** the alert is 2,100 failed logins against a host — it reads as
  brute force, and the `query_events` telemetry explicitly notes the source is the
  authorized Nessus scanner pool (change CHG-88213). Runbook RB-FP-02 says that's a
  false positive. Both models file it as `credential-abuse` anyway, anchored on the
  alert's framing instead of the evidence that contradicts it.
- **Why it matters:** this is the single most important behavior to measure in SOC
  automation — does the agent believe the detection or verify it? Two different models
  fail it identically and deterministically, which means it's a property of the task's
  deception, not a model quirk. A benchmark of "can it call tools" would never surface it.

### 2. Ignored compound clause — under-escalating active threats on high-value targets

- **Reproduce:** `sc-022`, `sc-024`, `sc-027` (`--backend mistral`) — 3/3 repeats each;
  all 14 disposition misses in the run share this shape.
- **What happens:** RB-ESC-01 requires escalation to incident response when an active
  threat touches a crown-jewel asset or an admin identity. Mistral routes these to the
  ordinary analyst queue — it retrieves the asset record showing `privilege: admin`,
  retrieves the runbook, and still applies only the base rule.
- **Why it matters:** single-condition rules get applied; the compound
  (threat AND high-value) condition gets dropped. Queue accuracy stays high (0.967)
  while disposition accuracy falls to 0.833 — the exact failure aggregate accuracy hides.

### 3. Over-escalation — the opposite error, on a different model

- **Reproduce:** `sc-008`, `sc-021` (`--backend fireworks`, kimi-k2p6).
- **What happens:** kimi escalates standard-asset, standard-privilege active threats to
  incident response when the runbook says route to an analyst. Where Mistral
  under-escalates, kimi over-escalates.
- **Why it matters:** the two failure directions have opposite operational costs
  (missed incidents vs. alert-fatigued responders), and they belong to different models.
  You cannot pick a disposition threshold without knowing which way your specific model
  leans — which is only visible from a per-model run.

### 4. Same model, different domain, different competence

- **Cross-reference:** gpt-oss-120b is the accuracy leader here (0.967) yet scores only
  0.667 on the [retail shift-coverage](../../retail-workforce/shift-coverage-triage-agent/)
  use case; kimi leads shift-coverage but is beaten by gpt-oss on this one.
- **Why it matters:** there is no "best agent model," only a best model per task. The
  ranking flips between SOC triage and retail scheduling because they stress different
  capabilities. Verify per use case, not per vendor leaderboard.
