# OTLP trace exports to whole-task retry evidence

Research checked November 3, 2026. This is an offline integration profile, not an
OpenTelemetry standard, complete OTLP validator, collector, or deployment certification.

## Sources and implications

1. [OTLP JSON encoding](https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding)
   specifies hexadecimal trace/span IDs, lower-camel-case field names, and integer or decimal
   string encodings for 64-bit integers. The bridge normalizes ID case, validates selected
   timestamps, and subtracts integer nanoseconds before converting durations to seconds.
   It preserves unconsumed fields rather than interpreting them. It is not a network receiver
   and does not claim complete conformance validation of unrelated payload fields.
2. [OpenTelemetry file serialization](https://opentelemetry.io/docs/specs/otel/protocol/file-exporter/)
   specifies newline-delimited trace objects and does not guarantee ordering. The bridge
   supports an explicit JSONL mode, indexes spans by identity rather than arrival order, and
   requires the reviewer to declare attempt order. A bounded complete task must occupy one
   resource entry; it does not assemble distributed or cross-batch task fragments.
3. [GenAI client-span guidance](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
   describes logical operations that may include automatic retries. Therefore a generic
   GenAI span cannot safely be assumed to represent exactly one physical call. This bridge
   requires explicit single-attempt instrumentation and makes no automatic classification.
   That guidance also discusses sensitive captured content; raw exports must be inspected
   before sharing, even when the projection ignores the content.

## Repository gap addressed

The existing retry importer accepted a hand-authored ledger. Teams with trace exports had no
source-retaining conversion into it. Manually copying only the final span can erase an earlier
harm, omit failed-call costs, and substitute a short final-call duration for whole-task elapsed
time. Counting nested spans as independent attempts can instead double count costs.

The new `aau otlp-retries` command retains the raw export, reviewer mapping, projection report,
complete derived retry pack, and outer manifest. All supplied spans have exactly one declared
role: task, attempt, or explicitly excluded detail. Selected task children cannot be excluded.
Every downstream artifact is recomputed from the export, not trusted merely because an
attacker updated a hash. The API and CLI can also bind the output to an existing review's
ledger and normalized evaluation. The source pack must travel alongside that review.

## Controlled experiment and negative cases

`harness/examples/evaluation-review/otlp_retries.py` emits two fictional task spans, four
attempt spans, and one nested detail span in reversed export order. It deliberately includes
an earlier unauthorized-action score, eventual completion, a ten-second task, and a nested
detail with an exaggerated cost that must not enter the attempt sum. All values are synthetic.
No collector, provider, model, or agency is exercised. Assertions cover the derived scores,
costs, timings, exclusion count, exact raw bytes, and a failed downstream policy/budget handoff.

Failure tests include a one-nanosecond overlap, a one-nanosecond duration at an epoch too large
for exact floating-point representation, an excluded direct-child failure, nested tasks,
parent cycles, duplicate span identities/JSON keys, wrong resources, missing repeats, string
scores, absent measurements, and rehashed member substitutions. An isolated-wheel smoke test
checks the installed command outside the repository and rejects a changed nested ledger.

## Limits that remain

- A complete supplied-span census is not proof of complete external telemetry. Sampling,
  instrumentation gaps, manipulated declarations, and falsified scores remain possible.
- Resource co-location and declared time order do not prove clock integrity or execution
  authenticity. Cross-resource, cross-record task fragments, nested task scopes, parallel
  attempts, and hedged requests are deliberately unsupported in this version.
- Attribute names are explicit reviewer choices, not standardized score or billing claims.
  Missing costs stay unknown; no token pricing, invoice verification, status-based scoring,
  currency conversion, or inferred API-call count occurs.
- Original bytes may contain sensitive data in any field. No sanitization or outbound
  transmission occurs. Identifiers and unmapped attribute names also appear in saved reports.
- Conversion exit 0 is not a policy pass. Independent approval of mapping, census, reducers,
  scoring context, policy, budget, and exclusions remains necessary before using a release gate.
