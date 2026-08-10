# Observed failure modes — Mortgage Loss-Mitigation and Foreclosure Protection Gate

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Thirty-seven becomes more than thirty-seven

- **Observed shape:** The baseline rounds a strict milestone and asserts the wrong protection.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `loss-mitigation-foreclosure-gate eval --backend mock --repeats 3`.

### 2. Servicer review hides counsel state

- **Observed shape:** A complete evaluation path advances while foreclosure counsel lacks the hold instruction.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `loss-mitigation-foreclosure-gate eval --backend mock --repeats 3`.

### 3. Submission becomes protected outcome

- **Observed shape:** The agent tells the borrower a protection or decision exists without receipt.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `loss-mitigation-foreclosure-gate eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
