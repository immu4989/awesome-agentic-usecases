# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs. Observations are from the real-model runs in
`results/`, compared directly against
[`refund-resolution-agent/results/`](../refund-resolution-agent/results/) — the same
scenarios, the same gold rules, the same models, with architecture as the only variable.

The failures here are *coordination* failures. They live at the seams between agents,
and none of them can occur in a single-agent system.

### 1. Orchestration amplifies whatever the model already does

- **Observed across all three models:**

  | Model | single | crew | effect |
  |---|---|---|---|
  | `mistral-small` | 0.333 | **0.411** | helped |
  | `gpt-oss-120b` | 0.644 | **0.044** | destroyed |
  | `Qwen3.7-Plus` | 0.978 | **0.933** | mild tax |

- **What happens:** the crew is a corrective for a model that is bad at the task, a tax
  on a model that is good at it, and catastrophic for a model whose weakness is
  handing off (mode 2). Mistral's forbidden refunds got a second reviewer and roughly
  half were caught. Qwen was already right and paid 1.96× to be slightly less right.
- **Why it matters:** "should I use multi-agent" has no architecture-level answer. The
  same decomposition, on the same task, moved one model up 8 points and another down 60.
  The variable that decides it is the model's existing failure profile, which is only
  knowable from a single-agent baseline. Measure that first.

### 2. Delegation is a handoff, and some models treat handoffs as completion

- **Reproduce:** `--backend fireworks` (gpt-oss-120b) — **75 of 90 runs never closed the
  ticket**, against 29 of 90 in the single-agent version.
- **What happens:** every sub-agent returned successfully. The investigator reported,
  compliance ruled, and the orchestrator then ended its turn without calling
  `close_ticket`. Not one delegation failed; the transcript shows `failed=[]` on every
  pattern.
- **The mechanism, and why it is not new:** gpt-oss's single-agent signature failure was
  stalling immediately after `escalate_to_specialist` (23 of its 29 stalls). Its problem
  was already "handing work off feels like finishing." In a crew, *every delegation is a
  handoff*, so the architecture handed it five more opportunities per run to express the
  same bug. The failure mode did not change. The surface area did.
- **Why it matters:** a model with a commit-stall weakness should not be an orchestrator.
  This is predictable from a single-agent run, and expensive to discover afterwards.

### 3. The brief is a lossy channel, and the loss is invisible to both agents

- **Reproduce:** the `CHARGEBACK_PENDING` archetype on `--backend mistral` (6 runs) and
  `--backend fireworks` (5 runs).
- **What happens:** the investigator reports the order facts. The orchestrator forwards
  those findings to compliance. Neither mentions that a bank chargeback is already in
  flight, so compliance rules on the action it was shown and approves a refund it would
  certainly have vetoed. The specialist only knows what the brief contains.
- **Why it matters:** every party behaved reasonably given what it could see, and the
  outcome was still an unrecoverable double payment. This is the characteristic
  multi-agent failure, and it is invisible from either agent's transcript alone — you
  can only see it by reading the brief against the world.

### 4. A veto that gets ignored is worse than no veto

- **Reproduce:** `HIGH_VALUE` on `--backend mistral` (3 runs) and `--backend fireworks`
  (1 run).
- **What happens:** compliance correctly vetoed the refund. The orchestrator issued it
  anyway.
- **Why it matters:** the control existed, fired correctly, and was overridden by the
  agent holding the irreversible tool. The audit trail afterwards reads "reviewed by
  compliance", which is worse than having no review at all, because it manufactures
  false assurance. The lesson is the same one the single-agent use case reached from the
  other direction: a veto belongs in the tool layer, where `issue_refund` refuses without
  an approval token, not in a teammate's advice.

### 5. The specialist is not automatically good at its speciality

- **Reproduce:** `--backend mistral` — compliance **approved** 8 over-threshold refunds
  and 6 out-of-window ones.
- **What happens:** giving the prohibition its own agent, its own prompt, and its own
  policy tools did not make that agent reliable at applying the prohibition. It has the
  same weakness the single agent had, now wearing a job title.
- **Why it matters:** decomposition is often justified as "each agent only has to be
  good at one thing." That assumes being narrow makes it good, which this does not
  support. Roughly half of Mistral's forbidden refunds still got through *after* a
  dedicated compliance review.

### 6. No configuration beat the best single agent

- **Observed:** the highest score anywhere on this task is `Qwen3.7-Plus` **single
  agent** at 0.978, at **half the cost** of its crew version.
- **Why it matters:** across three models and 270 crew runs, orchestration never produced
  a new best result. It compressed the range, pulling the weak model up and the strong
  model down. If a single agent already solves your task, the crew is a bill.
