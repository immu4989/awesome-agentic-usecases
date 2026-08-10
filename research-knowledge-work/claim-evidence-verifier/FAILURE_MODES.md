# Observed failure modes — Claim and Citation Evidence Verifier

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Citation presence replaces entailment

- **Observed shape:** The baseline credits a real, relevant source for a claim the cited passage does not support.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `claim-evidence-verifier eval --backend mock --repeats 3`.

### 2. Freshness disappears behind authority

- **Observed shape:** An authoritative but superseded source is treated as current for a time-sensitive assertion.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `claim-evidence-verifier eval --backend mock --repeats 3`.

### 3. Verification becomes publication

- **Observed shape:** The agent converts a review packet into a truth certification and crosses the editor's boundary.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `claim-evidence-verifier eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
