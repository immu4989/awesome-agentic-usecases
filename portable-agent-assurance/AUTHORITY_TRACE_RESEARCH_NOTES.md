# Privacy-bounded Cross-protocol Authority Trace

**Reviewed:** 2026-08-30

## Operational question

Can an incident responder correlate an inbound A2A request, the authority decision, and an outbound
MCP dispatch without collecting the prompt, message, tool arguments/results, bearer token, raw
subject, or personal data?

The reference exporter projects the 25-case Authority Relay receipt into 25 deterministic synthetic
traces. Every trace has an A2A receive span and authority-decision span. Only the two allowed cases
receive an MCP client span; all 23 blocked cases stop before dispatch. Identifiers for the task,
delegation, tenant, route, tool, resource, scope set, and audience are one-way SHA-256 references.

## Source-grounded choices

- [W3C Trace Context](https://www.w3.org/TR/trace-context/) standardizes portable `traceparent`
  correlation and prohibits putting personally identifiable or otherwise sensitive information in
  `traceparent` or `tracestate`. The public export includes structurally valid synthetic
  `traceparent` values, no `tracestate`, and no production-randomness claim.
- [W3C Baggage](https://www.w3.org/TR/baggage/) warns that baggage can propagate user-identifiable
  or private data across systems. The public profile emits no baggage field.
- [OpenTelemetry semantic conventions 1.44.0](https://opentelemetry.io/docs/specs/semconv/)
  provide a versioned attribute vocabulary. The exporter records the exact basis and uses the
  development GenAI operation values `invoke_agent` and `execute_tool` only where they apply.
- OpenTelemetry warns that input messages, output messages, tool-call arguments, and tool-call
  results can contain sensitive information. Those keys and payloads are prohibited, not merely
  truncated.
- OpenTelemetry's common specification recommends attribute count and value-length limits to
  prevent runaway telemetry. This profile caps each span at 16 attributes and each string at 160
  characters.

There are no standardized A2A-to-MCP authority-trace semantic conventions cited here. All
`aau.*` fields are explicitly experimental profile attributes, not an OpenTelemetry proposal or a
claim of ecosystem adoption.

## Non-claims

The export is generated from synthetic recorded fixtures. It is not live instrumentation, an OTLP
implementation, evidence that a production request or tool call occurred, trusted identity,
non-repudiation, a security boundary, A2A/MCP/OpenTelemetry/W3C conformance, compliance,
certification, deployment approval, government endorsement, or an Authority to Operate. Hashing an
identifier reduces direct disclosure in this public fixture; it does not guarantee anonymity or
make production identifiers safe to share.
