# Failure modes

All real-model observations below come from the committed 28-scenario × 3-repeat Mistral
run. DeepSeek v4 Flash scored 1.000 on the same 84 runs, so none of these failures is a
property of the workflow itself. The deterministic mock failure remains a regression
control and is labelled separately.

### 1. Correct decision, wrong object: the action failed and the review still closed

- **Reproduce:** `eval_mistral-small-latest.json`; filter for `decision_accuracy = 1` and
  an empty `detail.predicted.actions` list.
- **Observed:** 36/84 submitted reviews had no executed AP action. In 33, the submitted
  decision was correct. In 35 of those 36, the model called the expected action tool, but
  supplied an invoice number that did not resolve to the internal `DOC-*` invoice object.
  The strict tool rejected it; the model submitted the review anyway.
- **Why it matters:** “hold” in a report does not stop a payment, and “schedule” does not
  pay a supplier. Entity identity is part of action correctness, not a formatting detail.
- **Metrics:** decision accuracy **0.810** versus action accuracy **0.417**.

### 2. Perfect payment safety hid an 87.5% clean-payment failure rate

- **Reproduce:** filter the Mistral result to gold decision `schedule`.
- **Observed:** `payment_safety` was **1.000**, but only **3 of 24** clean or independently
  verified payments executed with the authorized amount and trusted bank destination. The
  other 21 were overblocked or submitted without a successful payment action.
- **Why it matters:** a metric that only asks “did an unsafe payment execute?” rewards a
  system that cannot reliably pay legitimate suppliers. Pair restraint with clean-task
  completion and action execution.
- **Taxonomy:** [safety by inaction](../../FAILURE_TAXONOMY.md#safety-by-inaction).

### 3. Verified vendors were overblocked while every risky change was held

- **Reproduce:** compare `VERIFIED_BANK_CHANGE` with `UNVERIFIED_BANK_CHANGE` in the
  Mistral result.
- **Observed:** all 12 unverified changes received the correct `hold` decision, but 8/12
  verified changes were incorrectly held or rejected. Clean matches were also misclassified
  in 8/12 runs. The error direction is conservative, not random.
- **Why it matters:** blocking every unfamiliar remittance change can prevent fraud while
  damaging legitimate suppliers and creating a manual-review queue that teams cannot clear.
- **Taxonomy:** [directional bias](../../FAILURE_TAXONOMY.md#directional-bias).

## Regression control: trusted evidence retrieved, then ignored

- **Reproduce:** `vendor-payment-review-agent eval --backend mock`; inspect `sc-002`,
  `sc-009`, `sc-016`, and `sc-023`.
- **Observed in the mock only:** the mock reads the vendor master, receives an `unverified`
  state and a conflicting bank fingerprint, then schedules the payment anyway.
- **Purpose:** this is an engineered smoke-test failure. It proves the irreversible action,
  forbidden-action scorer, and scenario-level reporting are live; it is not model evidence.
