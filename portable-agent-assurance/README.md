# Portable Agent Assurance Envelope

> A credential says who presented it. An assurance envelope asks whether that identity is still
> acting on this task, under this authority, through this protocol, with current evidence.

The Portable Agent Assurance Envelope (PAAE) is an experimental, offline interoperability lab for
agent identity, temporary authority, MCP tool calls, A2A handoffs, delegation, monitoring, and
recomputable evidence. It joins controls that are usually tested separately without inventing a
new identity provider or a universal trust score.

```text
workload identity ─┐
operator binding ──┼─> expiring authority ─> MCP / A2A request ─> allow | block | pause
task + policy ─────┤                                      │
evidence digests ──┘                                      └─> receipt + OTel + in-toto
```

## Why this is different

An Agent Card can describe capabilities. A token can authenticate a caller. A policy engine can
allow an operation. An evaluation can measure behavior. PAAE binds their public evidence into one
short-lived, testable envelope while preserving the differences between them.

| Layer | What the reference verifies | What it does not claim |
|---|---|---|
| Identity fixture | Signature, issuer, audience, workload, operator, task, lease, policy epoch, time | Production identity, key custody, non-repudiation |
| Authority | Exact operation, resource, destination, peer, delegation ceiling, revocation state | A live authorization decision or ATO |
| Protocol | Recorded MCP `tools/call` and A2A request shapes | A complete protocol implementation or network sandbox |
| Evidence | Envelope, suite, receipt, result chain, OTel export, byte manifest | Certification, compliance, safety, or field effectiveness |
| Reproduction | Explicit evidence state | Independence unless a separate reviewed reproduction exists |

The committed identity token uses a deliberately public HS256 test secret. It is useful only for
testing signature and claim binding. Never copy it into an application.

Read the [0.1 specification](SPEC.md) for canonicalization, decision semantics, the complete stable
reason-code vocabulary, evidence outputs, versioning, and the production-adapter acceptance
checklist.

## Run the 18-case protocol collision suite

No account, API key, network connection, model call, framework, or third-party package is needed.

```bash
python3 portable-agent-assurance/aau_assurance.py validate \
  portable-agent-assurance/examples/synthetic-assurance-envelope.json

python3 portable-agent-assurance/aau_assurance.py evaluate \
  portable-agent-assurance/examples/synthetic-assurance-envelope.json \
  portable-agent-assurance/examples/mcp-a2a-conformance-suite.json \
  --out /tmp/aau-assurance-receipt.json

python3 portable-agent-assurance/aau_assurance.py verify \
  /tmp/aau-assurance-receipt.json \
  --envelope portable-agent-assurance/examples/synthetic-assurance-envelope.json \
  --suite portable-agent-assurance/examples/mcp-a2a-conformance-suite.json
```

The suite contains two legitimate twins and sixteen boundary collisions: signature tampering,
expiry, token passthrough, identity substitution, wrong authority, task substitution, stale policy,
lease expiry, monitor loss, scope escape, Agent Card drift, unknown peer, excessive delegation,
delegation widening, missing credentials, and unauthorized cancellation.

## Close the MCP 2026-07-28 authorization delta

The original envelope suite intentionally remains a stable `0.1` recorded MCP/A2A contract. A
separate current-revision gate tests the authorization and self-describing request changes that
landed after its MCP `2025-06-18` research basis:

```bash
python3 portable-agent-assurance/mcp_2026_delta.py generate \
  portable-agent-assurance/examples/mcp-2026-authorization-profile.json \
  --out /tmp/mcp-2026-suite.json

python3 portable-agent-assurance/mcp_2026_delta.py run \
  portable-agent-assurance/examples/mcp-2026-authorization-profile.json \
  /tmp/mcp-2026-suite.json \
  --adapter-command "python3 my_mcp_authorization_adapter.py" \
  --out /tmp/mcp-2026-receipt.json
```

The deterministic compiler produces **16 cases**: two legitimate clean twins and fourteen
single-delta violations. They test protocol revision, `Mcp-Method`/`Mcp-Name` bindings,
authorization-response issuer validation, issuer-bound client credentials, authorization and token
resource indicators, token audience, initial scope minimization, scope-union step-up, token
passthrough, and query-string token transport. The committed command adapter is 16/16 exact with
zero unsafe allows and zero legitimate blocks; allow-all and deny-all both fail.

Expected answers are not sent to command adapters. Records contain no bearer values, authorization
codes, PKCE verifiers, credentials, tool arguments, results, prompts, or personal data, and no
authorization request or tool is executed. The initial-scope check is an explicit conservative AAU
profile choice based on MCP's least-privilege `SHOULD`, not a claim that MCP requires every excess
scope request to be rejected.

This closes the repository's declared revision-evidence gap; it does not upgrade the older
envelope wire shape, operate an OAuth flow, validate SDK behavior, or establish MCP/OAuth
conformance, security, interoperability, compliance, certification, or deployment approval.
See the [current-revision research and premise checks](MCP_2026_AUTHORIZATION_DELTA.md).

## Migrate recorded A2A requests to 1.0

The stable envelope suite also preserves its historical pre-1.0 A2A operation names. A separate
version-pinned gate tests the migration without silently relabeling those fixtures:

```bash
python3 portable-agent-assurance/a2a_1_delta.py generate \
  portable-agent-assurance/examples/a2a-1-interface-authorization-profile.json \
  --out /tmp/a2a-1-suite.json

python3 portable-agent-assurance/a2a_1_delta.py run \
  portable-agent-assurance/examples/a2a-1-interface-authorization-profile.json \
  /tmp/a2a-1-suite.json \
  --adapter-command "python3 my_a2a_authorization_adapter.py" \
  --out /tmp/a2a-1-receipt.json
```

The compiler produces **17 recorded cases**: two legitimate twins and fifteen single-delta
violations. They exercise the required `A2A-Version: 1.0` negotiation, exact selected
`AgentInterface` version/binding/endpoint/tenant tuple, pinned Agent Card bytes, PascalCase
JSON-RPC methods, per-operation authentication and authorization, declared application authority,
and caller-scoped task access. The committed answer-blind command adapter is 17/17 exact with zero
unsafe allows and zero legitimate blocks; allow-all and deny-all both fail.

The watched standard now resolves to immutable A2A specification release `v1.0.1`, while the
protocol revision correctly remains `1.0` because patch releases do not affect negotiation.
See the [source mapping, premise checks, and non-claims](A2A_1_RESEARCH_NOTES.md).

## Test the A2A → MCP authority relay

Passing the A2A and MCP gates independently still leaves one consequential boundary untested: the
application-owned translation from an inbound agent task to an outbound tool call. The Authority
Relay Gate makes that hop executable:

```bash
python3 portable-agent-assurance/authority_relay.py generate \
  portable-agent-assurance/examples/a2a-mcp-authority-relay-profile.json \
  --out /tmp/authority-relay-suite.json

python3 portable-agent-assurance/authority_relay.py run \
  portable-agent-assurance/examples/a2a-mcp-authority-relay-profile.json \
  /tmp/authority-relay-suite.json \
  --adapter-command "python3 my_authority_relay_adapter.py" \
  --out /tmp/authority-relay-receipt.json
```

The compiler produces **25 cases**: two legitimate A2A-to-MCP routes and twenty-three isolated
violations. It preserves the delegated subject, acting agent, task, tenant, Agent Card, delegation
identifier/depth/window, policy epoch, route, tool, resource, OAuth scope, MCP audience, monitor,
and human approval boundary. The committed answer-blind command adapter is 25/25 exact with zero
unsafe allows and zero legitimate blocks; allow-all and deny-all both fail.

This tests a declared application policy where the two protocols meet; it is not a new protocol or
a claim that A2A or MCP defines the full translation. Read the [research basis and exact
non-claims](AUTHORITY_RELAY_RESEARCH_NOTES.md).

## Run all current gates in one CI matrix

The [local composite GitHub Action](../.github/actions/aau-assurance/) can now run the historical
envelope plus all three current command-adapter gates. Its matrix runner writes three receipts, one
aggregate receipt, a human-readable job summary, and a SHA-256 manifest into a non-overwriting
workspace directory, then verifies every byte again:

```bash
python3 portable-agent-assurance/assurance_matrix.py run \
  --workspace . --out assurance-result/current-matrix \
  --mcp-profile assurance/mcp-profile.json --mcp-suite assurance/mcp-suite.json \
  --mcp-adapter-command "python assurance/adapters/mcp.py" \
  --a2a-profile assurance/a2a-profile.json --a2a-suite assurance/a2a-suite.json \
  --a2a-adapter-command "python assurance/adapters/a2a.py" \
  --relay-profile assurance/relay-profile.json --relay-suite assurance/relay-suite.json \
  --relay-adapter-command "python assurance/adapters/relay.py"
```

The reference matrix is **58/58 exact** across six clean twins and fifty-two violations, with zero
unsafe allows and zero legitimate blocks. All adapter commands are project code and must be treated
as executable, reviewed input; the documented workflow uses read-only repository permissions, no
secrets, quoted environment variables, a full-SHA Action pin, and caller-controlled artifact
retention.

## Build a portable pack

```bash
python3 portable-agent-assurance/aau_assurance.py pack \
  portable-agent-assurance/examples/synthetic-assurance-envelope.json \
  portable-agent-assurance/examples/mcp-a2a-conformance-suite.json \
  --out /tmp/aau-assurance-pack

python3 portable-agent-assurance/aau_assurance.py verify-pack /tmp/aau-assurance-pack
```

The non-overwriting pack contains the source envelope and suite, deterministic receipt,
metadata-only OpenTelemetry-compatible events, an unsigned in-toto Statement v1, a README, and a
byte-level manifest. The verifier rejects symlinks, extra files, oversized files, manifest drift,
receipt drift, telemetry drift, and statement drift.

## Run the hermetic container demonstration

```bash
docker compose -f portable-agent-assurance/compose.yaml up --build --abort-on-container-exit
```

The container has no published port, credential mount, or network dependency. It evaluates the
committed synthetic fixtures and verifies the result before exiting.

## Standards relationship

This experimental profile draws from—not conforms to or represents:

- [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative)
- [NIST agent identity foundation discussion](https://www.nist.gov/blogs/cybersecurity-insights/back-future-why-agentic-ai-needs-strong-identity-foundation)
- [NIST NCCoE Software and AI Agent Identity and Authorization](https://www.nccoe.nist.gov/projects/software-and-ai-agent-identity-and-authorization)
- [MCP authorization 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
- [A2A 1.0 specification, release v1.0.1](https://github.com/a2aproject/A2A/blob/v1.0.1/docs/specification.md)
- [SPIFFE workload identity](https://spiffe.io/docs/latest/spiffe-specs/)
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
- [in-toto Statement v1](https://in-toto.io/Statement/v1)

Read [the research and premise checks](RESEARCH_NOTES.md) and the
[0.1 specification](SPEC.md) before adapting the profile.

## Hard boundary

This project does not issue or validate production credentials, contact an identity provider,
execute a tool, connect agents, authorize a live action, prove operator identity, establish
non-repudiation, certify a system, determine compliance, grant an Authority to Operate, or represent
NIST, CISA, OMB, a government agency, a protocol project, or any cited organization.
