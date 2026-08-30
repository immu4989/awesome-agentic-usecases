# Portable Agent Assurance research notes

Verified: **2026-08-30**. These notes state the primary-source basis, design transfer, and limits of
the experimental envelope. They are not standards guidance or endorsement.

## Identity is not authority

NIST's August 27, 2026 identity discussion identifies credential sharing, long-lived credentials,
excessive access, and identity ambiguity as barriers to accountable agent deployment. It describes
agents as first-class entities with unique identifiers, credentials, entitlements, and bindings to
the person or system operating them.

PAAE encodes a subject workload identifier and operator reference separately, then requires a
short-lived task authority. Possessing the token never adds an operation, resource, destination,
peer, delegation, or policy epoch to that authority.

**Premise check:** a public HS256 fixture demonstrates deterministic signature and claim checks. It
does not demonstrate asymmetric key custody, workload attestation, issuer trust, revocation
delivery, a production identity provider, or non-repudiation. The machine-readable result therefore
fixes `production_identity_verified` to false.

## MCP authorization

The MCP authorization specification requires resource indicators and token audience validation and
forbids token passthrough. The suite keeps a legitimate resource-bound read beside an otherwise
identical passthrough case. PAAE parses recorded JSON-RPC `tools/call` objects; it never starts an MCP
client or server.

## A2A authorization

The A2A specification requires authentication schemes to be declared and authorization to be
checked on protocol operations. The reference binds the exact public Agent Card bytes, the named
peer, method, resource, and destination. A changed card, unknown peer, or ungranted cancellation
fails closed. The fixture is not an A2A conformance certification.

## SPIFFE and workload identity

SPIFFE defines portable workload identifiers and verifiable identity documents. PAAE uses a
normalized SPIFFE ID as the subject name but does not retrieve a Workload API response, validate an
SVID chain, operate a trust domain, or federate trust bundles. Production adapters must perform
those functions outside this reference and bind their evidence explicitly.

## Evidence and observability

The OpenTelemetry export includes only decision metadata—never prompts, tokens, credentials, or
personal data. Attribute names under `aau.assurance.*` are experimental and are not official
OpenTelemetry semantic conventions. The in-toto Statement v1 binds exact receipt bytes but is
unsigned; a separate verified Sigstore or GitHub attestation is required for workflow identity.

## Claims deliberately withheld

PAAE does not prove:

- production identity, operator identity, organizational independence, or signer authority;
- that a recorded request preceded a real side effect;
- that an omitted event, tool, peer, or credential never existed;
- correct deployment of MCP, A2A, OAuth, OIDC, SPIFFE, OpenTelemetry, in-toto, or Sigstore;
- safety, security, field effectiveness, compliance, certification, procurement fitness,
  government endorsement, or authorization to operate.
