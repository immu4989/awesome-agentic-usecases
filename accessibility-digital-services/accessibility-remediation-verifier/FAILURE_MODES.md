# Reproducible failure modes

These failures are engineered in the fictional comparison baseline. They are not claims
about an accessibility tool, tester, disabled person, organization, or deployed model.

### 1. A green scanner erases a keyboard trap

- **What happens:** The automated scan reports no issue, so the baseline records
  `record_no_defect` despite manual and source evidence of a keyboard trap.
- **Why it matters:** A service can remain impossible to complete while the dashboard is green.
- **Evidence:** Route, defect coverage, test coverage, and exact remediation all fail.
- **Reproduce:** Inspect the `access-005` family.

### 2. Conflicting evidence is flattened into a plan

- **What happens:** A contrast scanner flag becomes a normal remediation plan even though
  manual measurement and source evidence disagree.
- **Why it matters:** Treating one tool as authority can waste work and erase a reported barrier.
- **Evidence:** `route_accuracy=0` on every `CONFLICTING_EVIDENCE` story.
- **Reproduce:** Inspect the `access-006` family.

### 3. One fixed component becomes a conformance claim

- **What happens:** The baseline correctly recognizes the deployed and retested alt-text fix,
  then records `claim_conformance=true`.
- **Why it matters:** Bounded proof of fix does not establish whole-service or legal conformance.
- **Evidence:** Verification passes while `false_assurance_avoided=0`.
- **Reproduce:** Inspect the `access-007` family.

## Safety boundary

The lab records synthetic defect and test evidence. It never issues an accessibility
certification, legal conclusion, VPAT, ACR, or whole-service conformance statement.
