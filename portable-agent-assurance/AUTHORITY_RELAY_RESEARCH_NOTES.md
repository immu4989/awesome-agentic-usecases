# Cross-protocol Authority Relay Gate

**Reviewed:** 2026-08-30

**Research question:** When an authenticated A2A task causes an MCP tool call, can the system show
that the subject, acting agent, task, tenant, route, resource, scope, audience, and accountable
human boundary stayed intact across the hop?

## The missing test boundary

A2A and MCP define important controls within their respective protocol boundaries. Neither
protocol, by itself, defines an application's complete authorization translation from an inbound
A2A skill to an outbound MCP tool. Testing both sides separately therefore cannot detect capability
laundering at the relay: a legitimate message can still become an over-broad tool call.

This gate makes that application-owned translation explicit. A strict profile maps each inbound
skill to one outbound tool/resource/scope tuple and records delegation continuity. It compiles two
legitimate twins and twenty-three single-change violations, runs them through an answer-blind
command adapter, and binds the exact profile and suite digests into the receipt.

## Primary-source basis and profile choices

| Source finding | Gate evidence |
|---|---|
| A2A 1.0 requires authentication on every request, authorization for every operation, tenant continuity, and caller-scoped resource access | A2A revision, inbound authn/authz, tenant, card digest, subject, actor, and task checks |
| A2A in-task `AUTH_REQUIRED` is not itself authorization for a later operation | Explicit route grant and separate approval fact for the consequential prepare route |
| MCP requires resource indicators and audience validation and forbids passing the inbound token through to an upstream API | Exact MCP server audience plus `TOKEN_PASSTHROUGH_FORBIDDEN` |
| OAuth token exchange can represent delegation with a subject and current actor; nested actors can express a chain | Separate subject, actor, delegation id, depth, and replay facts |
| The NIST NCCoE concept paper highlights access delegation, accountable user-to-agent links, logging, and data-flow provenance | Task/policy/monitor continuity and digest-bound metadata receipt |

The two allowed routes and the human approval requirement are conservative AAU application-policy
choices, not protocol mandates. The gate never assumes an Agent Card signature is required, never
passes or validates a credential, and never treats a self-reported MCP client/server name as an
authorization signal.

## Independent reproduction route

The committed 25-case suite is maintainer-generated evidence. It is not an independent result. The
separate [blind A2A-to-MCP challenge](../reproduction-challenges/a2a-mcp-authority-relay/) exposes
eight answer-free boundary decisions and the same four primary-source anchors while keeping its
source suite and oracle outside Git. A fork can freeze and attest its response bytes before a
separate reviewer receives the SHA-256-committed oracle.

The challenge does not increment the repository's independent-reproduction count merely by being
open or completed. That count remains zero until a human review confirms distinct role
commitments, declared relationship evidence, challenge blinding, and an adjudicated Exchange pack.

## Primary sources

- [A2A v1.0.1 specification](https://github.com/a2aproject/A2A/blob/v1.0.1/docs/specification.md)
- [MCP authorization revision 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
- [RFC 8693: OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693)
- [NIST NCCoE Software and AI Agent Identity and Authorization concept paper](https://www.nccoe.nist.gov/sites/default/files/2026-02/accelerating-the-adoption-of-software-and-ai-agent-identity-and-authorization-concept-paper.pdf)

## Non-claims

This is an offline metadata experiment. It contains no token, message, prompt, tool argument,
result, personal data, or live target. It does not resolve an Agent Card, perform OAuth or token
exchange, contact an agent, call a tool, validate production identity or ownership, prove
non-repudiation, establish A2A/MCP/OAuth/NIST conformance, determine security or compliance,
certify a system, authorize deployment, or grant an Authority to Operate.
