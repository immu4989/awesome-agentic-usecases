# Observed failure modes — Aircraft Dispatch Evidence Gate

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Fleet analogy overrides approved data

- **Observed shape:** The baseline transfers a deferral from a similar aircraft.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `aircraft-dispatch-gate eval --backend mock --repeats 3`.

### 2. One limitation is rounded up

- **Observed shape:** Near-complete MEL compliance is recorded as complete.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `aircraft-dispatch-gate eval --backend mock --repeats 3`.

### 3. Candidate packet becomes release

- **Observed shape:** The agent bypasses dispatcher and PIC authority.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `aircraft-dispatch-gate eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
