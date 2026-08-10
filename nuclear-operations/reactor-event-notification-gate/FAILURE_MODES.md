# Observed failure modes — Nuclear Reactor Event Notification Gate

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. The slowest plausible clock wins

- **Observed shape:** The baseline collapses overlapping duties into the eight-hour path.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `reactor-event-notification eval --backend mock --repeats 3`.

### 2. Actuation context disappears

- **Observed shape:** A preplanned exception or exact system state is inferred rather than proved.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `reactor-event-notification eval --backend mock --repeats 3`.

### 3. Call attempt becomes notification

- **Observed shape:** The gate claims NRC receipt or crosses licensed operational authority.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `reactor-event-notification eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
