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
| Oracle leakage to an adapter | A hard-coded test double appears conformant | Command requests omit every expected outcome and reason code | The public suite remains visible; this is transparent conformance, not a secret benchmark |
| Malformed or partial adapter output | Missing failures disappear from the score | Exact event order, coverage, outcome vocabulary, and sorted reason codes fail closed | Schema-valid output can still be dishonest |
| Untrusted command adapter | Local code steals data or performs an unintended action | Commands are shell-free and must receive public-synthetic staging data only | The runner executes the named program; users must trust and sandbox it |
| Adapter/target substitution | A test double passes while production behaves differently | Receipt identifies command-adapter evidence and rejects production claims | Independent deployment binding and target evidence remain necessary |
| Tested/deployed adapter substitution | A passing matrix is attached to different source bytes or a different release label | Release binding copies and hashes all three adapter snapshots with the exact AABOM, release, matrix manifest, tool, and operation | The unsigned pack does not identify or observe a live workload |
| Coverage inheritance by association | One tested operation makes every operation in the tool or AABOM appear covered | Every write or irreversible AABOM operation is checked separately; only the exact three-gate pair is fully bound | Organizations need additional matrices for additional consequential operations |
| Workspace path presented as provenance | A declared filename is mistaken for proof of origin or execution | The receipt labels source paths as declarations and binds only copied bytes | Builder identity, signatures, deployment attestations, and runtime observation remain separate |
| Crash after target commit but before result persistence | A restarted worker repeats an already-applied effect | Two-process crash cases require target reconciliation and result replay | The synthetic files do not prove distributed atomicity |
| Lost journal, unavailable lookup, or expired retention | Recovery invents certainty and resumes unsafely | Unknown effect counts remain visible and the next action is a manual hold | An operator still needs an authorized system-specific recovery procedure |
| Process-exit result presented as power-loss proof | Reviewers over-trust a green crash test | Receipt states that exit code 86 does not prove storage durability | Hardware, filesystems, database failover, and replication need separate fault testing |
| Concurrent check-then-act | Multiple workers observe absence and each applies the effect | Multi-process races plus post-race target inspection count durable effects | A local launch barrier does not prove cross-host scheduler overlap or linearizability |
| Adapter lies in responses | Duplicate effects are labeled as replays | Inspection result is compared with committed response count and the expected aggregate | A dishonest inspection implementation can still fabricate its state |
| Deny-all concurrency guard | Duplication is prevented by destroying availability | Distinct-key and mixed-authority cases require legitimate commits | Workload coverage remains bounded to the public synthetic suite |

The reference evaluator accepts only public-synthetic input, never opens the network, never invokes
a tool, and never performs a side effect. The conformance runners start explicitly named local
adapter commands; they do not constrain what those programs can do. The release binder reads and
copies the declared adapter files but does not execute them. Run only trusted, staging-only adapters
in an appropriate sandbox. Do not place credentials, personal data, protected records, production
targets, proprietary adapter code, private traces, controlled information, or classified
information in a public suite, adapter request, receipt, or binding pack.
