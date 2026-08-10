# Observed failure modes — Workplace Severe Incident Reporting Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Hospital becomes inpatient

- **Observed shape:** The baseline maps any hospital visit to a reportable inpatient admission.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `severe-incident-reporting eval --backend mock --repeats 3`.

### 2. Outcome without event window

- **Observed shape:** A qualifying medical label is advanced without resolving when it occurred relative to the incident.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `severe-incident-reporting eval --backend mock --repeats 3`.

### 3. Draft or omission becomes report

- **Observed shape:** The navigator suppresses a severe outcome or records an unaccepted submission as complete.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `severe-incident-reporting eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
