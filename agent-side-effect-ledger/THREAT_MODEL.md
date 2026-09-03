# Threat model

| Failure or attack | Consequence | Reference control | Residual boundary |
|---|---|---|---|
| Retry after a lost response | Duplicate payment, notice, order, or permission change | Unknown outcomes require authoritative reconciliation | Atomicity with the real target must be established by the adapter |
| Same key with changed payload | A prior approval is stretched to a different effect | Key is bound to the canonical intent SHA-256 | Canonicalization must be identical across production components |
| Agent self-approval | Capability becomes authority | Exact accountable human role and expiry | Identity proof is outside this synthetic runner |
| Stale policy or lease | A once-allowed action commits after conditions changed | Policy epoch and authority expiry are checked again at commit | Clock and policy-distribution integrity are deployment concerns |
| False success after timeout | Records and reality diverge | Unresolved effects remain visible until reconciliation | Target queries can themselves be stale or incomplete |
| Invented rollback | Original harm disappears from the audit story | Compensation is separate and unavailable for irreversible tools | A declared compensation may still fail in a real system |
| Evidence mutation or reordering | Reviewers see a false sequence | Every result is hash-chained and the receipt is recomputed | Local hashes do not establish authorship or external truth |
| Trace-ID trust | Attacker-controlled correlation metadata is treated as permission | Trace context is never an authorization input | Production telemetry needs separate trust and privacy controls |

The executable accepts only public-synthetic input, never opens the network, never invokes a tool,
and never performs a side effect. Do not place credentials, personal data, protected records,
production targets, private traces, controlled information, or classified information in a public
suite or receipt.
