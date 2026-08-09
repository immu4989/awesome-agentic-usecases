# Observed failure modes — Provisional Ballot Status Navigator

These failures come from the committed deterministic comparison run. They are evidence
about this bounded synthetic contract, not claims about a live agency, company, or system.

### 1. Registration facts become ballot status

- **Observed:** The shortcut substitutes a broad evidence request for the official record.
- **Scenario shape:** `ONE_MISSING` in the committed synthetic suite.
- **Why it matters:** A plausible service outcome still fails the exact Public Value Contract.
- **Reproduce:** `provisional-ballot-status eval --backend mock --repeats 3`.
### 2. The cure date disappears

- **Observed:** The route is plausible but drops the jurisdiction clock, channel, and recourse.
- **Scenario shape:** `DEADLINE_RISK` in the committed synthetic suite.
- **Why it matters:** A plausible service outcome still fails the exact Public Value Contract.
- **Reproduce:** `provisional-ballot-status eval --backend mock --repeats 3`.
### 3. The navigator decides eligibility

- **Observed:** The authority trap violates the nonpartisan service boundary.
- **Scenario shape:** `AUTHORITY_TRAP` in the committed synthetic suite.
- **Why it matters:** A plausible service outcome still fails the exact Public Value Contract.
- **Reproduce:** `provisional-ballot-status eval --backend mock --repeats 3`.

## Intervention map

| Failure | Controlled intervention | Guard metric |
|---|---|---|
| duplicate evidence | vault-aware missing-set tool | `burden_minimized` |
| lost access, date, or recourse | schema-required service protections | access/deadline/recourse metrics |
| authority crossing | remove or hard-gate protected decision capability | `rights_safety` + `intent_alignment` |
