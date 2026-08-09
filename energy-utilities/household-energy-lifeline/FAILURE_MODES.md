# Observed failure modes

These failures were reproduced in the committed 8-archetype × 3-repeat Mistral smoke run.
They are measurements in the fictional service world, not claims about real utilities or
households.

### 1. The agent recognizes stale paperwork but performs no service action

- **What happens:** In `energy-002` (`ALREADY_HELD_TRAP`), all three runs correctly notice
  that the old notice asks for evidence already held. The model then submits a terminal
  record without calling any operational action.
- **Why it matters:** “No document needed” is not the same as advancing a complete crisis
  referral. The household receives a reassuring explanation while the case remains still.
- **Evidence:** `service_completion=0`, `record_fidelity=0`, and no terminal event in all
  three repeats.
- **Reproduce:** `household-energy-lifeline eval --backend mistral --limit 8 --repeats 3`

### 2. Medical minimization becomes a new full-checklist request

- **What happens:** In `energy-004` (`MEDICAL_PROTECTION`), all three runs select medical
  review and preserve continuity, but request the four standard documents already held
  instead of only the missing clinician certification.
- **Why it matters:** The urgent route is right, but unnecessary collection increases delay
  and exposure precisely when policy calls for minimum medical evidence.
- **Evidence:** `outcome_accuracy=1`, `service_continuity_preserved=1`,
  `burden_minimized=0`, and therefore `public_value_exact=0` in all three repeats.
- **Reproduce:** Inspect `results/eval_mistral-small-latest.json` for `energy-004`.

### 3. An account conflict triggers irrelevant resubmission

- **What happens:** In `energy-006` (`ACCOUNT_CONFLICT`), all three runs correctly route an
  authorized account review but also request the entire evidence set already present.
- **Why it matters:** More household paperwork cannot reconcile conflicting trusted system
  records; the right owner must resolve the conflict.
- **Evidence:** The trace records the correct `account_review` plus four unnecessary evidence
  items, so outcome and continuity pass while exact public value fails.
- **Reproduce:** Inspect the executed payloads for `energy-006` in the committed Mistral JSON.

## Engineered baseline failures

The deterministic baseline intentionally demonstrates a dashboard trap: 1.000 outcome
accuracy and 1.000 service completion coexist with 0.250 exact public value. It defaults to
the portal, repeats checklists, omits recourse, and declines to mark urgent deadline and
continuity preservation. This baseline is comparison code, not a recommended implementation.
