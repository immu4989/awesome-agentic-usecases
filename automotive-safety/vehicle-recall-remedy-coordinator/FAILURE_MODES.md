# Observed failure modes — Vehicle Recall Remedy Coordinator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Model-level recall becomes VIN truth

- **Observed shape:** The baseline transfers a nearby model-year campaign to the exact vehicle.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `vehicle-recall-remedy eval --backend mock --repeats 3`.

### 2. Authorized remedy is treated as optional

- **Observed shape:** A correct recall match routes to a location that cannot perform the campaign remedy.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `vehicle-recall-remedy eval --backend mock --repeats 3`.

### 3. Appointment becomes repair

- **Observed shape:** The coordinator records safety and completion before qualified repair personnel act.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `vehicle-recall-remedy eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
