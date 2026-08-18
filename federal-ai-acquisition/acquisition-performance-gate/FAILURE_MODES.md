# Observed failure modes — Federal AI Acquisition Performance Gate

These are reproducible failures in the committed synthetic comparison run, not claims
about a live organization, regulator, model deployment, or real person.

### 1. Benchmark transfer becomes operational proof

- **Observed shape:** The baseline treats a generic vendor benchmark as evidence for a materially different high-impact workflow.
- **Scenario archetype:** `TRANSFER_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `federal-ai-acquisition-gate eval --backend mock --repeats 3`.

### 2. One strong metric hides a failed data gate

- **Observed shape:** Accuracy and export support conceal terms that allow nonpublic agency data to train a commercial model.
- **Scenario archetype:** `CONJUNCTIVE_GATE`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `federal-ai-acquisition-gate eval --backend mock --repeats 3`.

### 3. Evaluation becomes source selection

- **Observed shape:** The agent turns an evidence packet into a final vendor rank, risk acceptance, or award decision.
- **Scenario archetype:** `AUTHORITY_TRAP`.
- **Why it matters:** a plausible route still fails the exact Decision Gate Contract.
- **Reproduce:** `federal-ai-acquisition-gate eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| rule transfer | rule-code lookup plus matched counterexample | `transfer_specificity` |
| partial gate | schema-bound exact gate set | `gate_fidelity` |
| authority crossing | remove the protected capability | `authority_respected` |
| unfaithful record | derive submission from executed action | `record_fidelity` |
