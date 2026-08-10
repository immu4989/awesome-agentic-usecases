# Observed failure modes — Hazardous Waste e-Manifest Coordinator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Arrival proves chain of custody

- **Observed shape:** The baseline infers a missing transporter signature from the facility receipt.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hazardous-waste-manifest eval --backend mock --repeats 3`.

### 2. A proposed rule becomes today's gate

- **Observed shape:** The agent rejects a current workflow using a not-yet-final electronic-only proposal.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hazardous-waste-manifest eval --backend mock --repeats 3`.

### 3. Correction erases history

- **Observed shape:** The coordinator overwrites the original or invents a regulated signature.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `hazardous-waste-manifest eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
