# A2A 1.0 interface and authorization delta

**Reviewed:** 2026-08-30

**Pinned source:** A2A Protocol specification release `v1.0.1`

**Protocol compatibility revision:** `1.0` (`Major.Minor`; patch releases do not change protocol compatibility)

## Why this companion gate exists

The original AAU envelope suite is a stable historical contract. Its recorded A2A request shape
uses the pre-1.0 JSON-RPC names `message/send`, `tasks/get`, and `tasks/cancel`; it does not record
the `A2A-Version` service parameter or an `AgentInterface` version. Relabeling those fixtures as A2A
1.0 would destroy reproducibility and hide a migration failure.

This companion gate instead records the A2A 1.0 delta explicitly. It tests two legitimate twins
and fifteen one-change violations through an answer-blind command adapter. Expected answers never
cross the adapter boundary. The resulting receipt is digest-bound to the exact profile and suite.

## Primary-source requirements represented

| Source requirement | Recorded check | Failure code |
|---|---|---|
| Clients must send `A2A-Version` with every request; `Major.Minor` selects semantics | Header present and exactly `1.0` | `A2A_VERSION_MISSING`, `A2A_VERSION_MISMATCH` |
| A selected `AgentInterface` binds URL, protocol binding, protocol version, and optional tenant | Exact interface tuple and card digest | `AGENT_INTERFACE_*`, `PROTOCOL_BINDING_MISMATCH`, `TENANT_ROUTING_MISMATCH`, `AGENT_CARD_DRIFT` |
| JSON-RPC uses PascalCase operation names matching gRPC | `SendMessage`, `GetTask`, `CancelTask` only | `A2A_1_METHOD_INVALID` |
| Servers must authorize every protocol operation before resource access | Authentication, declared scheme, caller authority, and pre-query check | `AUTHENTICATION_REQUIRED`, `AUTHORIZATION_PRECHECK_REQUIRED`, `SECURITY_SCHEME_MISMATCH`, `CALLER_OUTSIDE_AUTHORITY` |
| Task operations must be scoped to resources visible to the authenticated caller | Exact resource and synthetic task owner | `RESOURCE_OUTSIDE_AUTHORITY`, `TASK_AUTHORIZATION_SCOPE_MISMATCH` |

The profile deliberately grants `SendMessage` and `GetTask`, but not `CancelTask`. That makes
operation expansion observable without pretending the protocol prescribes this application's
authorization model.

## Sources and premise checks

- [A2A v1.0.1 release](https://github.com/a2aproject/A2A/releases/tag/v1.0.1) is the latest stable
  specification patch reviewed here. The raw source watcher is pinned to that tag rather than the
  mutable `main` branch.
- [A2A v1.0.1 specification](https://github.com/a2aproject/A2A/blob/v1.0.1/docs/specification.md)
  defines version negotiation, interface selection, binding method maps, and per-operation
  authorization requirements.
- Patch `1.0.1` is a document release, while the interoperable protocol revision remains `1.0`.
- `application/a2a+json` is a **SHOULD** for the HTTP+JSON binding, not a universal MUST. This
  reference uses JSON-RPC and does not incorrectly turn that recommendation into a blocker.
- Signed Agent Cards are not treated as mandatory. The test binds the exact already-selected card
  bytes; it does not assert signature validation or trusted discovery occurred.

## Non-claims

This is an offline, synthetic, recorded-delta experiment. It does not implement JSON-RPC, resolve
an Agent Card, validate TLS or credentials, send messages, retrieve or cancel tasks, prove caller
ownership, certify A2A conformance, determine security or compliance, or approve deployment.
