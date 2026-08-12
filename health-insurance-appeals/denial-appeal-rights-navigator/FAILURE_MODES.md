# Observed failure modes — Health Insurance Denial and Appeal Rights Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Urgency inherits the routine sequence

- **Observed shape:** The baseline preserves the wrong clock while the patient's usable care window closes.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `health-plan-appeal-rights eval --backend mock --repeats 3`.

### 2. Internal review erases external review

- **Observed shape:** A final denial is treated as the end of the rights graph.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `health-plan-appeal-rights eval --backend mock --repeats 3`.

### 3. Submitted becomes overturned

- **Observed shape:** The agent claims authorization or payment from an appeal receipt.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `health-plan-appeal-rights eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
