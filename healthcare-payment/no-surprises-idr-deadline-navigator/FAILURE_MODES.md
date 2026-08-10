# Observed failure modes — No Surprises Act IDR Deadline Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Calendar time opens the wrong window

- **Observed shape:** The baseline treats 30 calendar days as 30 business days.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `no-surprises-idr-deadline eval --backend mock --repeats 3`.

### 2. The right clock attaches to the wrong claim

- **Observed shape:** A service-identity mismatch disappears once negotiation is complete.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `no-surprises-idr-deadline eval --backend mock --repeats 3`.

### 3. Initiation becomes determination

- **Observed shape:** A portal receipt is recorded as a selected offer or paid claim.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `no-surprises-idr-deadline eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
