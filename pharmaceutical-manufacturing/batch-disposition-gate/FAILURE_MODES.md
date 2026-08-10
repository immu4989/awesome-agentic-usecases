# Observed failure modes — Pharmaceutical Batch Disposition Gate

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Transfer by vocabulary

- **Observed shape:** The baseline maps sterility-positive inconclusive to the familiar chemical path.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `batch-disposition-gate eval --backend mock --repeats 3`.

### 2. Complete summary, incomplete audit trail

- **Observed shape:** A persuasive packet confirms an integrity gate that the record does not support.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `batch-disposition-gate eval --backend mock --repeats 3`.

### 3. Routing becomes release

- **Observed shape:** Shipment pressure turns a preparation tool into an unauthorized batch decision.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `batch-disposition-gate eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
