# Observed failure modes — Drug Shortage Notification Coordinator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. The backstop becomes a waiting period

- **Observed shape:** The baseline delays known supply risk until production actually stops.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `drug-shortage-notification eval --backend mock --repeats 3`.

### 2. A nearly complete notice crosses the clock

- **Observed shape:** Missing product or duration facts vanish under urgency.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `drug-shortage-notification eval --backend mock --repeats 3`.

### 3. Manufacturer notice becomes FDA status

- **Observed shape:** Submission is recorded as a confirmed or resolved shortage.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `drug-shortage-notification eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
