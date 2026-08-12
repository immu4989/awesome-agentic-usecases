# Observed failure modes — Social Security Disability Cessation and Benefit Continuation Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Sixty days overwrites fifteen

- **Observed shape:** The baseline treats a timely appeal as a timely continuation election.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `disability-cessation-continuity eval --backend mock --repeats 3`.

### 2. A phone explanation becomes a filing

- **Observed shape:** Intent is inferred without the written event that protects the date.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `disability-cessation-continuity eval --backend mock --repeats 3`.

### 3. Election becomes payment

- **Observed shape:** The navigator guarantees continued cash or Medicare without SSA action.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `disability-cessation-continuity eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
