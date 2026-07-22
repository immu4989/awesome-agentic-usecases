# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs. Observations compare against
[`refund-resolution-agent/results/`](../refund-resolution-agent/results/) — the same
scenarios, the same gold rules, the same models, with a single intervention as the only
variable.

This use case exists to test the repo's own advice. What it found is that one of the two
standard remedies works almost for free, and the other one makes things substantially
worse.

### 1. The prompt nudge doubled the failure it was written to fix

- **Reproduce:** `--variant commit --backend fireworks` (gpt-oss-120b). Baseline stalls:
  **29 of 90**. With a terminal nudge appended to the system prompt: **59 of 90**.
- **What the intervention was:** one paragraph telling the model to call `close_ticket`
  before ending its turn, and that a ticket left open is a failure even when the
  investigation was correct. Nothing else changed.
- **What happened:** `submitted` fell from 0.678 to **0.344**, and `safe_and_correct`
  from 0.644 to **0.333**. The stall pattern also spread out: in the baseline, 24 of 29
  stalls came immediately after `escalate_to_specialist`; with the nudge, stalls appeared
  after `issue_refund` (15), `verify_identity` (9), and six other points.
- **Why it matters:** this is the intervention almost everyone reaches for first, and it
  is the one that cost 31 points. Adding an instruction about finishing did not make the
  model finish; it added another consideration to a model that was already failing to
  converge. Whatever the mechanism, the direction is unambiguous and it is the opposite
  of the intended one. Do not assume a prompt fix is free, or even neutral.

### 2. The disposition never changed, only the outcome

- **Reproduce:** `--variant enforced --backend mistral`. `blocked_attempt` is **0.489**:
  the model reached for a forbidden refund in **44 of 90 runs**, exactly as it did in the
  baseline.
- **What happens:** the tool layer refuses; the model's inclination is untouched. Nothing
  about the guardrail teaches it the policy, and it was never told the guard existed —
  the prompt is byte-identical to the baseline.
- **Why it matters:** it would be easy to read `no_unsafe_action` going 0.500 → 1.000 as
  "the agent learned the rule." It did not. Remove the guard and the 45 forbidden refunds
  come straight back. Any monitoring built on the agent's *behaviour* rather than the
  tool's *refusals* would show a clean record while the underlying disposition is
  unchanged. Instrument the block rate, not just the incident rate.

### 3. What the guard cost: essentially nothing, which is itself the finding

- **Observed:** `recovered_after_block` is **1.000**. In all 44 runs where the tool
  refused, the model went on to reach the **correct** resolution: 15 chargeback cases to
  `escalate`, 15 over-threshold to `escalate`, 14 out-of-window to `replacement`. Cost
  moved $0.0006 → $0.0007 per scenario and `submitted` moved 1.000 → 0.989.
- **Why it matters:** the honest worry about tool-layer enforcement is that a refused
  agent thrashes, stalls, or invents a different wrong answer, and that nobody publishes
  that number. Here the number is zero thrash. The model knew the right answer the whole
  time and simply preferred the shortcut. That reframes the advice: enforcement is not a
  workaround for a model that cannot follow policy, it is removing an easier option from
  a model that already knows better.

### 4. A small model with a guard beat a large model without one, and beat the crew

- **Observed:** enforced `mistral-small` scores **0.822**, against **0.644** for baseline
  `gpt-oss-120b` and **0.411** for the three-agent
  [crew](../refund-crew/) on the same task.
- **Why it matters:** the two expensive answers to "my agent does unsafe things" are a
  bigger model and more agents. On this task a free-tier model plus roughly thirty lines
  of tool-layer policy beat both, at a sixth of the crew's cost per scenario. Environment
  design outperformed both model scaling and architecture.
