# Observed failure modes — Detention and Demurrage Invoice Verifier

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Operational lateness proves collectability

- **Observed shape:** The baseline ignores the invoice issuance clock because the container was late.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `detention-demurrage-verifier eval --backend mock --repeats 3`.

### 2. One charge reaches two parties

- **Observed shape:** A timely invoice passes even though the same charge is duplicated across billed parties.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `detention-demurrage-verifier eval --backend mock --repeats 3`.

### 3. Dispute submitted becomes dispute won

- **Observed shape:** The verifier invents a waiver or refund from a portal receipt.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `detention-demurrage-verifier eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
