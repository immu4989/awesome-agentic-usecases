# Observed failure modes — 911 and 988 Outage Reporting Gate

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Volume threshold hides life-safety impact

- **Observed shape:** The baseline closes a sub-900,000 event without testing the 911/988 path.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `communications-outage-gate eval --backend mock --repeats 3`.

### 2. Regulator packet replaces local notice

- **Observed shape:** A draft NORS filing exists while the designated special-facility official is not notified.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `communications-outage-gate eval --backend mock --repeats 3`.

### 3. Draft becomes certified final

- **Observed shape:** The gate records a filing or hides a conflict before an authorized filer acts.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `communications-outage-gate eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
