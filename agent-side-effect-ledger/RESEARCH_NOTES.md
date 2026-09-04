# Agent Side-Effect Ledger research notes

Research checked on 2026-09-03. These notes record the premise errors that would otherwise turn a
useful retry guard into a false exactly-once claim.

## Source-to-requirement ledger

| Source fact | Executable requirement | Non-claim |
|---|---|---|
| RFC 9110 limits automatic retry of non-idempotent requests unless idempotence is known or non-application can be detected | `timeout_unknown` can only enter reconciliation; an immediate retry is held | HTTP alone does not provide exactly-once delivery |
| CloudEvents permits a resent duplicate to carry the same `source + id` | Event IDs and idempotency keys identify replay candidates | An event ID is not authorization and does not bind the payload by itself |
| W3C Trace Context links requests across distributed systems | The reference intent records a syntactically valid `traceparent` | A trace ID is correlation metadata, not identity, approval, or policy |
| NIST SP 800-53 provides adaptable least-privilege, audit, and change-control objectives | Agent/task/authority/policy bindings and append-only result evidence remain explicit | This synthetic mapping is not a control assessment or compliance result |
| The IETF Idempotency-Key draft described fault tolerance for non-idempotent POST/PATCH | The profile binds an idempotency key to the canonical intent digest | The latest draft is expired and is not cited as a standard |

## Premise checks

1. **Idempotency is not exactly once.** A durable deduplication record can prevent a repeated
   effect only inside the scope, atomicity, and retention window of the enforcing adapter.
2. **A key without a payload binding is unsafe.** Reusing the same key for a new amount, target,
   tool, or policy context must be a conflict, not a cache hit.
3. **A timeout is an epistemic state.** It cannot be represented as success or failure until the
   target of record is queried or another authorized recovery process resolves it.
4. **Approval must bind bytes, not prose.** A human role approves the prepared canonical intent;
   a later change requires a new preparation and approval.
5. **Compensation is not erasure.** A cancellation, refund, or correction is another external
   action with its own authority, approval, idempotency key, and evidence.
6. **Observability is not authority.** `traceparent` can make a transaction inspectable, but its
   presence cannot authorize a side effect.
7. **Atomicity remains local.** The reference runner never claims that the journal and an external
   system commit atomically. Production adapters must prove or disclose that boundary.
8. **A visible test needs oracle isolation.** Conformance requests expose the transparent synthetic
   scenario but remove expected outcomes and reason codes. This catches accidental echo adapters;
   it does not make the public suite a secret benchmark or prevent deliberate overfitting.
9. **Adapter evidence is not target evidence.** Running a staging policy adapter shows how that
   command answered the declared cases. It does not prove the production binary, configuration,
   identity system, journal, target API, or deployment follows the same path.
10. **A command label is not artifact evidence.** Matrix 0.5 requires `argv[0]` or the `argv[1]`
    supported-interpreter target to resolve to a declared workspace-relative entrypoint, records the position,
    normalizes that token to the declared absolute path, hashes the file on both sides of execution,
    and copies its original bytes. Python targets also capture transitive static-local imports,
    reject obvious dynamic loading, and expose unresolved names. Equal observations do not prove
    continuous immutability. CPython targets separately digest workspace reads across every expected
    process and expose runtime-only paths without embedding their content. Python audit hooks remain
    bypassable and neither static nor observed material captures the interpreter, installed packages,
    outside-workspace access, environment variables, container, builder, or live runtime identity.

## Official sources

- [RFC 9110 — HTTP Semantics, §9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
- [CloudEvents specification v1.0.2](https://github.com/cloudevents/spec/blob/ce@v1.0.2/cloudevents/spec.md)
- [W3C Trace Context Recommendation](https://www.w3.org/TR/trace-context/)
- [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)
- [Expired IETF HTTPAPI Idempotency-Key draft 07](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)
- [Python language reference — the import system](https://docs.python.org/3/reference/import.html)
- [SLSA 1.2 build provenance](https://slsa.dev/spec/v1.2/build-provenance)
- [Python runtime audit hooks](https://docs.python.org/3/library/sys.html#sys.addaudithook)
