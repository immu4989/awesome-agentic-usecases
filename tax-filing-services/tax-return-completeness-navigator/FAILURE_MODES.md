# Observed failure modes — Tax Return Completeness Navigator

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Balanced means complete

- **Observed shape:** The baseline transfers the wage-only rule to a Marketplace return.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `tax-return-completeness eval --backend mock --repeats 3`.

### 2. Signature becomes metadata

- **Observed shape:** An unsigned authorization is treated as a clerical detail.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `tax-return-completeness eval --backend mock --repeats 3`.

### 3. Completeness becomes transmission

- **Observed shape:** The agent signs or files instead of handing off to the taxpayer and preparer.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `tax-return-completeness eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
