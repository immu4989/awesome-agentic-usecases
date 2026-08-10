# Observed failure modes — Nursing Home Transfer and Discharge Rights Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. An old notice follows a new destination

- **Observed shape:** The baseline treats a changed basis and location as a clerical edit.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `nursing-home-transfer-discharge eval --backend mock --repeats 3`.

### 2. Thirty days hides missing appeal content

- **Observed shape:** A timely notice passes without a usable appeal route.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `nursing-home-transfer-discharge eval --backend mock --repeats 3`.

### 3. Notice becomes discharge

- **Observed shape:** The navigator records removal or waived rights when only a notice exists.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `nursing-home-transfer-discharge eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
