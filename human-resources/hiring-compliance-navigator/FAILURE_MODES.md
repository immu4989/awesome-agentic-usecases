# Observed failure modes — Hiring Compliance Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Legitimate reason launders the process

- **Observed shape:** The baseline advances because the criterion is job-related while required procedure is absent.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hiring-compliance-navigator eval --backend mock --repeats 3`.

### 2. Ten business days becomes a suggestion

- **Observed shape:** Screening urgency drops the candidate notice clock.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hiring-compliance-navigator eval --backend mock --repeats 3`.

### 3. Navigator becomes decision-maker

- **Observed shape:** The agent issues the adverse decision instead of preserving accountable review.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hiring-compliance-navigator eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
