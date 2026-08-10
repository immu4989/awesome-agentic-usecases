# Observed failure modes — Medical Device Adverse-Event Reporting Gate

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Reporter identity disappears

- **Observed shape:** The baseline routes every device event as if the manufacturer received it.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `device-adverse-event-gate eval --backend mock --repeats 3`.

### 2. The 5-day path inherits 30 days

- **Observed shape:** A public-health remedial action loses the expedited clock.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `device-adverse-event-gate eval --backend mock --repeats 3`.

### 3. Prepared becomes accepted

- **Observed shape:** The gate records an FDA report without an accepted submission receipt.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `device-adverse-event-gate eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
