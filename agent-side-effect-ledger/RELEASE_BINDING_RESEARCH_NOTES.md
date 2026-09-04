# Side-Effect Release Binding research notes

Research checked on 2026-09-04. This profile addresses a narrow evidence-substitution problem:
testing one adapter snapshot and then associating the receipt with a different release, tool,
operation, or adapter. It binds copied bytes; it does not establish what is actually running.

## Source-to-control ledger

| Primary source fact | Executable design choice | Explicit non-claim |
|---|---|---|
| SLSA 1.2 defines provenance as verifiable information for tracing an artifact through the supply chain | The pack hashes the AABOM, binding plan, complete matrix manifest, matrix receipt, and three exact adapter snapshots | The pack is not SLSA provenance and has no builder identity or signature |
| NIST SP 800-53 Rev. 5 AC-6 applies least privilege to users and processes acting for users | Every AABOM write or irreversible operation must have a declared binding and matching authority | A declared authority is not a verified live credential or authorization decision |
| NIST SP 800-53 Rev. 5 CM controls treat configuration and change evidence as an organizational responsibility | Agent ID, release ID, tool ID, operation, authority, evidence digest, and adapter bytes are joined in one recomputable receipt | A byte match is not production equivalence, change approval, compliance, or an ATO |
| The matrix separately tests semantics, crash recovery, and concurrency and carries the entrypoint, static-local Python materials, and CPython-observed workspace reads for each command | A consequential operation is fully bound only when it is the exact pair covered by all three matrix gates and every release path, entrypoint digest, static material-set digest, and observed-runtime digest agrees | Other semantic-suite tools do not inherit crash or race coverage; static plus observed workspace inputs are not a complete runtime dependency graph |
| SLSA 1.2 records known resolved dependencies while describing dependency completeness as best effort | The binding pack preserves matrix-side static material sets and digest-only release snapshots for observed runtime paths, then holds on any mismatch | This unsigned pack is not SLSA provenance and has no builder or workload identity |

## Premise checks

1. **A path is a declaration, not provenance.** The pack copies and hashes adapter bytes. The
   original workspace path remains useful context, but cannot prove where the bytes came from.
2. **A hash is not identity.** SHA-256 detects changes to committed pack bytes; it does not identify
   a builder, signer, workload, process, cloud account, or production deployment.
3. **One tested operation cannot cover a tool family.** Coverage is calculated on the exact
   `tool_id + operation` pair. Every consequential AABOM operation is evaluated separately.
4. **Inventory cannot grant authority.** AABOM authority fields are checked for complete references
   and human-approval requirements, but the binder never mints, validates, or exercises credentials.
5. **A valid failure remains portable evidence.** Missing coverage or human approval produces a
   deterministic `binding_held` pack and exit code 1. Malformed structure or tampering uses exit
   code 2, so CI can preserve behavioral diagnostics without accepting them.
6. **The matrix remains bounded.** Even a byte-perfect binding to a passing public-synthetic matrix
   is not evidence about real data, target atomicity, workload identity, production equivalence,
   safety, compliance, certification, release approval, or an Authorization to Operate.
7. **Test-to-release binding is byte equality, not execution identity.** Matrix 0.5 proves its
   command referenced one declared entrypoint and carries those original bytes plus a static-local
   Python material set and a digest-only CPython workspace-read observation. Release Binding 0.4
   compares the path, entrypoint digest, material-set digest, and every observed workspace digest.
   It does not prove the packaged files were deployed or capture interpreters, installed packages,
   outside-workspace access, containers, or builders.
8. **Unchanged entrypoint bytes are insufficient.** A changed statically imported local module
   produces `ADAPTER_MATERIALS_DIFFER_FROM_MATRIX` even when the release entrypoint digest matches.
9. **Unchanged source bytes are also insufficient.** A changed workspace policy observed during the
   matrix run produces `RUNTIME_MATERIALS_DIFFER_FROM_MATRIX` even when entrypoint and static
   material-set digests still match.

## Official sources

- [SLSA 1.2 — Provenance](https://slsa.dev/spec/v1.2/provenance)
- [SLSA 1.2 — Build provenance](https://slsa.dev/spec/v1.2/build-provenance)
- [Python language reference — the import system](https://docs.python.org/3/reference/import.html)
- [Python documentation — runtime audit hooks](https://docs.python.org/3/library/sys.html#sys.addaudithook)
- [NIST SP 800-53 Rev. 5 — Security and Privacy Controls](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)
- [AWS Agentic AI Lens — deterministic idempotency and conditional writes](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel06-bp04.html)
