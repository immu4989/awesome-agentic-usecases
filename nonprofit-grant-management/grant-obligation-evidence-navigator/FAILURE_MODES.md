# Observed failure modes — Nonprofit Grant Obligation Evidence Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Prior acceptance becomes current authority

- **Observed shape:** The baseline copies obligations from a similar earlier award and misses the current notice's extra proof.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `grant-obligation-evidence eval --backend mock --repeats 3`.

### 2. Budget category replaces cost support

- **Observed shape:** A plausible category hides missing allocation and source documentation.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `grant-obligation-evidence eval --backend mock --repeats 3`.

### 3. Checklist becomes certification

- **Observed shape:** The navigator signs or submits instead of preserving the authorized official's accountability.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `grant-obligation-evidence eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
