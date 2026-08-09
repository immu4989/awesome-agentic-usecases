# Observed failure modes

These failures were reproduced in the committed Mistral smoke suite. They describe the
fictional benchmark, not real insurer or government performance.

### 1. A referral is recorded as money already received

- **What happens:** In two `claim-001` (`READY_UNINSURED`) repeats, the model prepares the
  correct aid referral but declares `federal_assistance` as an existing compensation source.
- **Why it matters:** A referral is a next step, not an award. Conflating them can create a
  false overlap, distort a downstream ledger, or make a survivor appear already compensated.
- **Evidence:** `outcome_accuracy=1`, `source_coordination=0`, and
  `public_value_exact=0` in the affected repeats.
- **Reproduce:** Inspect `claim-001` in `results/eval_mistral-small-latest.json`.

### 2. Overlap review asks for the entire file again

- **What happens:** In all three `claim-005` (`OVERLAP_CONFLICT`) repeats, the model
  identifies both known sources and routes the correct human review, then requests all six
  evidence items already held.
- **Why it matters:** Duplicate paperwork cannot resolve a trusted-ledger conflict. It adds
  burden while delaying the reviewer who actually owns the decision.
- **Evidence:** The correct route and source set coexist with `burden_minimized=0`, so exact
  public value fails in every repeat.
- **Reproduce:** Inspect the `route_overlap_review` payload for `claim-005`.

### 3. An accessible evidence request turns into the wrong terminal action

- **What happens:** In `claim-006` (`ACCESSIBLE_SERVICE`), the model uses the saved channel
  but skips the required minimum-evidence request and prepares an insurer or aid packet.
- **Why it matters:** Correct accessibility does not repair missing evidence or an invented
  insurance track. Service obligations are conjunctive, not interchangeable.
- **Evidence:** `accessibility_respected=1` while burden, completion, recourse, or outcome
  fail across the repeats.
- **Reproduce:** Compare the gold contract and executed payloads for `claim-006`.

## Engineered baseline failure

The deterministic baseline scores 1.000 on route accuracy but 0.125 on exact public value.
It is intentionally source-blind and burden-blind, demonstrating why a successful queue
assignment is not yet a successful recovery service.
