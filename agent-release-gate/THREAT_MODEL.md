# Threat model

The Agent Release Gate processes repository files and can execute a caller-selected local adapter.
It is designed for public or synthetic evidence, not secrets or production configuration.

## Security invariants

- Component, suite, and pack paths remain below their declared roots.
- Symlinks, traversal, oversized inputs, malformed structures, and unknown fields fail closed.
- A local command is split into argv and runs with `shell=False`.
- Expected answers and forbidden-action rules are not sent to the adapter.
- Public receipts exclude raw case inputs, raw responses, reasoning, credentials, headers, and
  environment variables.
- Every impacted tag has an explicit suite requirement; silence cannot mean coverage.
- Required component removal blocks.
- A mock run never returns `release_ready`.
- An approval record never claims cryptographically verified identity.
- The verifier recomputes decisions and derived exports instead of trusting stored summaries.

## Threats and mitigations

| Threat | Consequence | Mitigation | Residual boundary |
|---|---|---|---|
| Manifest omits a behavior-changing component | Change appears smaller than it is | Required component kinds and human-owned manifest review | AAU cannot discover an undeclared component |
| Impact tag is omitted or narrowed | Relevant suite does not run | Unknown impacted tags block; before/after tags are unioned | A dishonest tag declaration remains possible |
| Candidate deletes monitoring or rollback | Passing behavior test hides loss of recovery | Required kinds and required-component removal gates | Presence is not operational effectiveness |
| Deny-all adapter passes attacks | Legitimate work is silently disabled | Every planned suite declares one or more clean twins | Declared count is structural; domain review owns twin quality |
| Mock result is shown as deployment evidence | Protocol self-test becomes false assurance | Mock is always held at human review | Screenshots can still be misrepresented outside the pack |
| Approval fixture impersonates a person | Automated evidence appears authorized | `identity_verified` is fixed to false; role is structural only | Organizations need their own authenticated approval system |
| Adapter exfiltrates local data | Test execution leaks information | AAU sends only suite requests and runs without a shell | A caller-selected adapter is code; run it only when trusted |
| Pack file is replaced | Reviewer sees a different result | Exact manifest, recomputed decision, and in-toto byte subject | Unsigned local statement does not prove publisher identity |
| OSCAL file is treated as compliance | Government decision is overstated | Explicit non-certifying remarks and deterministic derivation | Downstream systems must preserve the boundary |

## Out of scope

- Sandboxing, authenticating, or authorizing a production agent
- Verifying completeness of the declared software bill of materials
- Protecting secret prompts, credentials, CUI, classified data, or production logs
- Determining legal, regulatory, procurement, safety, or employment compliance
- Signing a release or verifying the identity or independence of a reviewer
- Deploying, rolling back, stopping, or restarting a system
