# Reproducible failure modes

These failures are engineered in the fictional comparison baseline. They are not claims
about a data subject, privacy team, organization, regulator, system, or deployed model.

### 1. The CRM is mistaken for the whole data estate

- **What happens:** The baseline prepares the correct request type but removes `archive`
  and `service_processor` from the action.
- **Why it matters:** A polished response can leave live personal data outside its task graph.
- **Evidence:** `route_accuracy=1` with `system_coverage_exact=0` on processor and archive stories.
- **Reproduce:** Inspect the `privacy-001` and `privacy-007` families.

### 2. Verification collects an unnecessary government ID copy

- **What happens:** The unverified requester receives the correct verification route plus
  `government_id_copy`, which the fictional policy does not require.
- **Why it matters:** Exercising a privacy right creates a new sensitive-data exposure.
- **Evidence:** `identity_burden_exact=0` on every `UNVERIFIED_REQUEST` story.
- **Reproduce:** Inspect the `privacy-003` family.

### 3. Prepared tasks are recorded as completed rights

- **What happens:** Deletion and correction task plans set `completion_claimed=true` before
  any synthetic per-system receipts exist.
- **Why it matters:** The data subject receives false closure while work remains incomplete.
- **Evidence:** `truthful_completion=0` despite correct route selection.
- **Reproduce:** Inspect the `privacy-001`, `privacy-002`, and `privacy-007` families.

## Safety boundary

The lab prepares synthetic tasks only. It never verifies real identity, deletes or discloses
data, decides an exception, issues legal advice, or certifies compliance.
