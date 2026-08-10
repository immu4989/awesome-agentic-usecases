# Observed failure modes — Debt Validation and Dispute Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Prior silence erases a timely dispute

- **Observed shape:** The baseline treats an undisputed history as consent after a written dispute arrives.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `debt-validation-dispute eval --backend mock --repeats 3`.

### 2. Most fields become a complete notice

- **Observed shape:** A plausible notice passes despite a missing required identity or itemization field.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `debt-validation-dispute eval --backend mock --repeats 3`.

### 3. Delivery becomes verification

- **Observed shape:** The navigator records the debt as proven when only the dispute receipt exists.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `debt-validation-dispute eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
