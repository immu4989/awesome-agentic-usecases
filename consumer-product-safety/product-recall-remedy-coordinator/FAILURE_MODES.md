# Observed failure modes — Consumer Product Recall Remedy Coordinator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Appearance expands recall scope

- **Observed shape:** The baseline treats brand and visual similarity as exact inclusion.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `product-recall-remedy eval --backend mock --repeats 3`.

### 2. The warning drops behind the remedy

- **Observed shape:** A correct form link reaches the user without the official stop-use instruction.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `product-recall-remedy eval --backend mock --repeats 3`.

### 3. Intake becomes compensation

- **Observed shape:** A submitted request is recorded as a completed refund or replacement.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `product-recall-remedy eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
