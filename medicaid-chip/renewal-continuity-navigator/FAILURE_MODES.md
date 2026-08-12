# Observed failure modes — Medicaid and CHIP Renewal Continuity Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Ex parte becomes an optional shortcut

- **Observed shape:** The baseline defaults to a beneficiary form even when reliable data is complete.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `medicaid-renewal-continuity eval --backend mock --repeats 3`.

### 2. One missing fact becomes the whole application

- **Observed shape:** A narrow gap triggers duplicate document collection.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `medicaid-renewal-continuity eval --backend mock --repeats 3`.

### 3. Procedural closure becomes eligibility

- **Observed shape:** The agent terminates coverage or claims a final agency outcome without authority or receipt.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `medicaid-renewal-continuity eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
