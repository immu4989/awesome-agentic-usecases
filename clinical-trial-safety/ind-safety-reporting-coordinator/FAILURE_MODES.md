# Observed failure modes — Clinical Trial IND Safety Reporting Coordinator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Serious event becomes automatic SUSAR

- **Observed shape:** The baseline skips expectedness and qualified causality judgment.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `ind-safety-reporting eval --backend mock --repeats 3`.

### 2. Fifteen days overwrites seven

- **Observed shape:** A fatal or life-threatening qualifying event inherits the slower familiar route.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `ind-safety-reporting eval --backend mock --repeats 3`.

### 3. Initial report closes follow-up

- **Observed shape:** The agent claims a final submission or changes the trial without sponsor authority.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `ind-safety-reporting eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
