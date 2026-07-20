# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs, with a reproducing scenario id. Observations are
from the real-model runs in `results/`.

### 1. Trusting the alert framing over a benign explanation (the travel deception)

- **Reproduce:** the `TRAVEL_BENIGN` scenarios (`--backend fireworks`, gpt-oss-120b) —
  9 misses; the alert reads "foreign charge, new device, possible card fraud" and a
  matching travel notice is on file in the transaction record.
- **What happens:** gpt-oss files these as `card-fraud` instead of `false-positive`. It
  anchors on the alert's framing and the device/geo novelty, and doesn't credit the
  `travel_notice_matches` signal that policy FP-CARD-03 says to check first.
- **Why it matters:** every false positive here is a legitimate customer's card getting
  blocked on holiday. This is the direct financial-services analogue of the SOC
  scanner-deception in [alert-triage](../../security-operations/alert-triage-agent/) —
  does the agent believe the detection or verify it?

### 2. Clearing an authorized-but-fraudulent payment (the APP-scam deception)

- **Reproduce:** the `APP_SCAM` scenarios (`--backend mistral`) — the customer authorized
  the transfer from their own trusted device, and the beneficiary is a freshly added mule.
- **What happens:** Mistral treats the trusted device and customer authorization as
  exculpatory and mis-dispositions these toward release, ignoring FP-APP-05's explicit
  instruction that a trusted device does not clear a new-mule-beneficiary payment.
- **Why it matters:** APP scams are the fraud type where every classic signal is absent by
  construction, so a model that keys on device/velocity anomalies is blind to them.
  Notably this is the **opposite** deception from mode 1, and a **different model** falls
  for each — neither model is uniformly cautious or uniformly credulous.

### 3. Decisive-action avoidance: softening block into hold-for-review

- **Reproduce:** confirmed-fraud standard-customer scenarios (`--backend mistral`) —
  22 of its disposition misses.
- **What happens:** on confirmed card fraud or account takeover for a standard customer,
  policy FP-ESC-01 says `block_and_notify`. Mistral routes to the softer
  `hold_for_review` queue instead — correct queue, correct threat read, wrong action: it
  declines to take the decisive step.
- **Why it matters:** queue accuracy stays at 0.967 while disposition accuracy collapses
  to 0.500. The failure is entirely in *what the agent does about* the fraud, not whether
  it detected it — exactly the gap a disposition-level metric exists to expose, and a
  queue-only benchmark would score this agent as excellent.

### 4. Commit-stall on the hardest cases

- **Reproduce:** 8 of 90 gpt-oss-120b runs submitted no decision (`submitted` 0.911),
  concentrated on the deception scenarios.
- **What happens:** the model investigates, then ends the turn without calling
  `submit_triage` — the same commit-stall seen on
  [shift-coverage](../../retail-workforce/shift-coverage-triage-agent/). It stalls most on
  exactly the ambiguous cases a fraud desk most needs a decision on.
- **Why it matters:** an un-actioned fraud alert is a transaction sitting in limbo. The
  `submitted` metric prices it in as a full miss rather than silently dropping it.

### 5. One-directional bias: models over-call fraud on benign transactions — but it is beatable

- **Reproduce:** all `TRAVEL_BENIGN` and `ALLOWLIST_BENIGN` scenarios, on three of the
  four models tested. kimi-k2p6's queue misses are 5× travel-benign → card-fraud,
  2× allowlist-benign → app-scam, 1× allowlist-benign → account-takeover — *all eight are
  benign-called-fraud*. gpt-oss makes the same error 9 times.
- **What happens:** those models reliably detect real fraud and reliably over-detect it.
  Across their runs, none ever mistook an actual fraud case for benign at the queue level;
  the error is entirely one-directional.
- **The exception, and why it matters more than the rule:** `Qwen3.7-Plus` scores a
  perfect 1.000 queue accuracy with **zero** benign-called-fraud errors, defeating both
  deceptions. Its only misses are disposition-level escalate-vs-block confusion at the
  high-value boundary — a milder error class that never blocks a legitimate customer or
  releases a fraud.
- **Why it matters:** an accuracy number implies balanced errors; the confusion breakdown
  shows a systematic false-positive bias in most models, which in production means
  legitimate customers blocked rather than fraud missed. But because one model solves it
  outright, the bias is a **property of the model, not the task** — so it is fixable by
  model selection, and the only way to know which side your candidate errs on is to run
  this breakdown before you deploy.

> **Note on this entry.** An earlier version of this file claimed the fraud-direction bias
> held for *every* model tested. Adding `Qwen3.7-Plus` falsified that, and the claim was
> narrowed rather than quietly dropped. That is the intended failure mode of a findings
> document: new evidence rewrites it.

### 6. No best model — the ranking flips again

- **Cross-reference:** on this use case Mistral routes best (queue 0.967) while gpt-oss
  trails (0.789); on [SOC alert-triage](../../security-operations/alert-triage-agent/)
  gpt-oss leads. Across the repo, every model wins somewhere and loses somewhere.
- **Why it matters:** fraud triage stresses different capabilities than security or
  scheduling, and the leaderboard reshuffles. Pick the model per use case, verified —
  not per vendor benchmark.
