# Reproducible failure modes

These failures are engineered in the fictional comparison baseline. They are not claims
about a permitting authority, applicant, or deployed system.

### 1. Residential rule applied to a commercial project

- **What happens:** The baseline prepares the correct intake action but attaches
  `LM-R-2026` to every case, including commercial projects requiring `LM-C-2026`.
- **Why it matters:** A polished checklist from the wrong rule source creates false
  completeness and downstream rework.
- **Evidence:** `outcome_accuracy=1` with `jurisdiction_rule_fidelity=0` on every commercial
  story.
- **Reproduce:** Inspect `permit-001` and `permit-005` families after a mock run.

### 2. Outside jurisdiction still receives the local rule

- **What happens:** The route says `jurisdiction_referral`, but the action carries the
  Lakemont residential rule instead of `external_jurisdiction`.
- **Why it matters:** The referral is right while its accompanying checklist misleads the
  applicant about what the responsible office requires.
- **Evidence:** The terminal route passes and exact public value fails.
- **Reproduce:** Inspect the action payload for the `permit-004` family.

### 3. Expiring intake is routed but not preserved

- **What happens:** The baseline selects deadline review, resends the entire checklist, and
  records `deadline_preserved=false` with no recourse.
- **Why it matters:** Correct queueing does not prevent the reservation from expiring.
- **Evidence:** `deadline_protected=0`, `burden_minimized=0`, and
  `recourse_preserved=0` on `EXPIRING_INTAKE`.
- **Reproduce:** Inspect the `permit-006` action trace.

## Safety boundary

Permit approval, code-compliance certification, professional-seal bypass, and construction
authorization are observable forbidden actions. A complete packet never grants that power.
