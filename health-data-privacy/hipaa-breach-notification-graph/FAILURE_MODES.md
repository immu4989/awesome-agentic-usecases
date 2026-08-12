# Observed failure modes — HIPAA Breach Notification Recipient Graph

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Actor role disappears

- **Observed shape:** The baseline routes every incident as if the covered entity discovered it.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hipaa-breach-notification eval --backend mock --repeats 3`.

### 2. Five hundred becomes one universal threshold

- **Observed shape:** HHS, media, and individual duties collapse despite different facts.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hipaa-breach-notification eval --backend mock --repeats 3`.

### 3. Approval becomes notification

- **Observed shape:** The agent suppresses or certifies notices without the protected decision and receipt.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hipaa-breach-notification eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
