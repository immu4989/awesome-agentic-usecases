# Portable Agent Assurance Envelope 0.1

**Status:** experimental interoperability profile.

**Scope:** public or synthetic recorded MCP/A2A fixtures.

**Normative implementation:** **aau_assurance.py** plus the three JSON Schemas in this directory.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** describe this AAU experimental
profile only. They do not add requirements to MCP, A2A, SPIFFE, OpenTelemetry, in-toto, NIST, or
any other project or standard.

## 1. Assurance statement

An implementation evaluates this question:

> Did this named recorded request present the expected synthetic identity fixture and remain
> inside the envelope's current task authority, protocol scope, peer boundary, delegation ceiling,
> and monitoring condition at the declared event time?

An **allow** answers only that fixture question. It MUST NOT be represented as production identity
verification, a live authorization, certification, compliance, an Authority to Operate, proof that
a block preceded a side effect, or proof that an event record is complete or true.

## 2. Required bindings

The envelope binds six layers that MUST remain distinct:

| Layer | Required binding | Failure must not be hidden by |
|---|---|---|
| Workload identity | SPIFFE-form subject, agent id, issuer, audience, synthetic signature | Operator or capability labels |
| Operator | Explicit operator reference in envelope and token | Agent identity alone |
| Live authority | Lease, task, policy epoch, time window, revocation, human owner | Credential possession |
| Protocol scope | Protocol, operation, resource, destination, A2A peer/card or MCP passthrough rule | Broad tool or agent capability |
| Delegation | Depth ceiling and strict operation subset | Parent authentication |
| Evidence | Exact source digests, result chain, receipt, telemetry boundary, statement, manifest | A badge or aggregate score |

The public reference accepts only synthetic data, no live system, and test credentials. A
production adapter needs its own reviewed identity, key custody, revocation delivery,
authorization, protocol, telemetry, and deployment controls outside this profile.

## 3. Canonical binding

Envelope, suite, result-row, and receipt digests use UTF-8 JSON with:

- keys sorted lexicographically;
- separators comma and colon with no insignificant whitespace;
- Unicode preserved rather than ASCII-escaped; and
- SHA-256 over the resulting bytes.

The suite MUST carry the canonical envelope digest. Each result carries the preceding result digest,
starting with 64 zeroes. **result_chain_head_sha256** MUST equal the final result digest. The receipt
digest covers the receipt before **receipt_sha256** is added. Verification recomputes the complete
receipt; matching selected fields is insufficient.

The portable pack manifest uses SHA-256 over the exact emitted file bytes, not canonical JSON. The
in-toto Statement v1 subject similarly binds the exact canonical receipt bytes and is explicitly
unsigned.

## 4. Synthetic identity fixture

The reference JWT header MUST contain exactly **alg**, **kid**, and **typ**; **alg** MUST be
**HS256**. The claims MUST contain exactly:

**iss, aud, sub, agent_id, operator_ref, authority_ref, task_id, policy_epoch, jti, iat, exp,**
and **synthetic_fixture**.

The verifier requires strict base64url, an exact header, valid HMAC, exact claim bindings, an
integer non-empty interval, current time inside the token interval, and token validity inside the
envelope interval. Extra signed claims fail because an adapter must not smuggle unbound authority
through a role, scope, or capability field.

The committed shared secret is deliberately public. It MUST NOT be reused, protected as if it were
confidential, or accepted by a live system.

## 5. Recorded protocol contract

Every record has exactly **protocol**, **context**, and **request**. Context has the event time,
agent, authority, task, policy epoch, synthetic token, monitor state, delegation depth, and
delegated operations. Unknown fields fail rather than being silently interpreted by another
component.

### 5.1 MCP

The reference accepts a recorded JSON-RPC **tools/call** with a tool-and-operation name. It
normalizes the name, resource, destination, optional peer, and token-passthrough flag. The exact
MCP operation, resource, and destination tuple MUST appear in **allowed_actions**, and token
passthrough MUST remain false.

This is not an MCP client, server, transport, OAuth flow, or protocol conformance test.

### 5.2 A2A

The reference accepts recorded **message/send**, **tasks/get**, and **tasks/cancel** operations.
The exact A2A operation, resource, and destination tuple MUST be granted, the peer MUST be listed,
the Agent Card digest MUST match, the token MUST be evaluated for this request, and passthrough
MUST remain false.

This is not an A2A client, server, Agent Card resolver, transport, or protocol certification.

## 6. Decision semantics

Evaluation produces one of three outcomes:

- **allow** — no reason code was produced;
- **pause** — **MONITORING_UNAVAILABLE** is the only reason; or
- **block** — any other single or combined reason set.

Reason codes are sorted and de-duplicated. A monitoring failure plus any identity, authority,
scope, or record failure MUST block rather than pause.

| Family | Stable reason codes |
|---|---|
| Token structure and signature | IDENTITY_TOKEN_MALFORMED, IDENTITY_TOKEN_HEADER_INVALID, IDENTITY_TOKEN_CLAIMS_INVALID, IDENTITY_SIGNATURE_INVALID |
| Identity bindings | IDENTITY_ISSUER_MISMATCH, TOKEN_AUDIENCE_MISMATCH, WORKLOAD_IDENTITY_MISMATCH, AGENT_IDENTITY_MISMATCH, OPERATOR_BINDING_MISMATCH |
| Token authority and time | TOKEN_AUTHORITY_MISMATCH, TOKEN_TASK_MISMATCH, TOKEN_POLICY_EPOCH_MISMATCH, TOKEN_FIXTURE_MARKER_MISSING, TOKEN_JTI_MISSING, TOKEN_NOT_YET_VALID, TOKEN_EXPIRED, TOKEN_INTERVAL_INVALID, TOKEN_INTERVAL_OUTSIDE_ENVELOPE |
| Live authority | AUTHORITY_LEASE_INACTIVE, AUTHORITY_REVOKED, AUTHORITY_REF_INVALID, TASK_MISMATCH, STALE_POLICY_EPOCH, ACTION_OUTSIDE_AUTHORITY |
| Protocol boundary | TOKEN_PASSTHROUGH_FORBIDDEN, AGENT_CARD_DRIFT, UNAUTHORIZED_PEER |
| Delegation | DELEGATION_DEPTH_INVALID, DELEGATION_DEPTH_EXCEEDED, DELEGATION_SCOPE_INVALID, DELEGATION_SCOPE_WIDENED |
| Monitoring | MONITORING_STATE_INVALID, MONITORING_UNAVAILABLE |

Adding or changing the meaning of a reason code requires a profile-version review. Consumers MUST
use the structured code, not parse human titles.

## 7. Legitimate twins

A suite MUST contain at least two cases marked **clean_twin**. Every clean twin MUST precommit
**allow** with an empty reason list. The reference suite includes one MCP and one A2A twin. This
prevents a deny-all implementation from appearing effective merely because it blocks every risky
fixture.

Security outcomes and legitimate-action preservation MUST be reported separately.

## 8. Evidence outputs

The pack contains only these root files: **README.md, envelope.json, suite.json, receipt.json,
otel-events.json, statement.intoto.json,** and **manifest.json**.

Verification rejects missing or extra files, symlinks, non-regular entries, oversized files,
manifest drift, receipt drift, telemetry drift, statement drift, and overwrite attempts. The
OpenTelemetry-compatible export includes decision metadata but no token, prompt, credential, or
personal-data field. Its **aau.assurance.*** names are experimental rather than official semantic
conventions.

## 9. Adapter acceptance checklist

Before calling an adaptation production-relevant, the accountable organization SHOULD document:

- how workload and operator identity are verified and how key custody is protected;
- how per-request authority, revocation, task changes, and policy epochs reach every agent;
- how MCP resources and A2A peers/cards are resolved without trusting self-asserted input;
- how child and queued work stop when parent authority changes;
- how a policy decision is proven to precede a consequential side effect;
- which telemetry fields are collected, minimized, retained, and disclosed;
- who reviews the oracle, clean twins, transfer limits, and protected human decisions; and
- which independent party can reproduce a held-out version without access to the answer key.

Until that evidence exists, **production_identity_verified** MUST remain false and the result MUST
remain a synthetic or protocol demonstration.

## 10. Versioning

Version 0.1 is intentionally narrow. A compatible implementation MAY add tooling around the
contract, but MUST NOT add unrecognized envelope, suite, record, claim, or pack fields. A semantic
change to required bindings, decisions, reason-code meaning, canonicalization, or pack verification
requires a new profile version and a new suite digest.
