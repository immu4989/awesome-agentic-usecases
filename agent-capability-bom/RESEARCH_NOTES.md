# AABOM research notes

Research snapshot: **2026-08-30**. This ledger separates primary-source facts from AAU design
choices. It is not legal advice, procurement guidance, a government position, or a standards
conformance claim.

## The tested gap

| Primary-source observation | What it supports | What it does not support |
|---|---|---|
| NIST's AI Agent Standards Initiative prioritizes secure interoperability, authentication, identity infrastructure, and security evaluations. | Identity, authority, and interoperable evidence are active agent-adoption problems. | NIST has not standardized this AABOM profile. |
| The NCCoE concept paper asks how identity, authorization, auditing, non-repudiation, and prompt-injection controls apply to agents with access to tools and data. | An operational inventory should bind agent, tools, data access, and authority. | An inventory is not authentication or live authorization. |
| NIST AI 800-5 reports broad agreement that agent security is an adoption barrier and established cybersecurity practices need agent-specific adaptation. | A small, implementable adaptation layer can help adoption. | The report does not endorse AAU or validate field effectiveness. |
| CISA's 2025 minimum elements emphasize component transparency, generation context, relationships, automation, and current interoperable formats including SPDX and CycloneDX. | Preserve generation context, relationships, machine readability, and an open projection. | A software-component BOM alone describes all active agent authority. |
| CycloneDX supports AI/ML models and datasets and offers extensible properties. | Reuse a maintained BOM ecosystem rather than inventing a sealed format. | `aau:agent:*` properties are registered CycloneDX taxonomy entries. |
| NIST SP 800-53 AC-6 applies least privilege to processes acting on behalf of users and privileges necessary for assigned organizational tasks. | Review agent leases at the operation and scope level. | A bounded non-use observation proves a privilege is unnecessary. |
| NIST SP 800-207A describes telemetry as an input for fine-tuning access rights and step-up authentication. | Use authorized observations to form a review hypothesis. | Telemetry alone should automatically rewrite access policy. |
| OpenTelemetry's GenAI conventions warn that tool arguments and results may contain sensitive information. | Keep the public observation profile metadata-only. | Metadata is risk-free or establishes trace integrity/completeness. |
| NIST's NCCoE agent concept asks how least privilege can be established when actions are unpredictable and how agent actions can be logged and audited. | Derive repeatable authority challenges from the declared inventory and retain bounded results. | A generated test proves the deployed policy is correct or complete. |
| MCP authorization requires audience-bound tokens and prohibits token passthrough; OAuth security guidance recommends sender-constrained, audience-restricted access tokens. | Test exact tool/scope/time/delegation bindings at the adapter boundary rather than accepting a bearer token as sufficient proof. | This generic compiler establishes MCP or OAuth conformance. |

## Design decisions

1. **Complement instead of replace.** The AAU JSON is optimized for strict agent-authority checks;
   the exporter projects models and tools into CycloneDX 1.7 and preserves agent-only facts as
   namespaced properties. It does not call the AAU contract an SBOM or ML-BOM standard.
2. **Relationships are the unit of risk.** A tool name without operations, scopes, lease, expiry,
   delegation, revocation, and routes cannot expose a meaningful blast radius.
3. **Widening is directional.** Diff findings identify added operations/scopes/routes, increased
   side effects/delegation/duration, enabled egress, and removed human approval. They do not collapse
   unlike changes into a risk score.
4. **A rotating lease is not an extension.** The diff compares lease duration, not absolute end
   time. Otherwise every normal credential rotation would generate a false widening alert.
5. **Public evidence has a hard privacy boundary.** The contract accepts only public or synthetic
   material and explicitly rejects claims of credentials, personal data, nonpublic configuration,
   controlled information, or verified production identity.
6. **Validity is not authority.** The clean reference remains `human_review_required`. Real systems
   must check current identity, authorization, revocation, context, and policy at action time.
7. **Non-use is a question, not an answer.** The planner identifies unobserved grants but produces
   no executable policy and removes nothing. Each candidate requires owner review, a representative
   holdout, a legitimate clean twin, staging denial test, rollback rehearsal, and separate change
   approval.
8. **Denied attempts do not justify privilege.** Only allowed events count as observed use. A
   blocked or errored request remains evidence about enforcement, not evidence that the agent needs
   the requested grant.
9. **Compile both sides of every boundary.** Violation-only suites reward deny-all systems, so each
   reachable authority intersection first produces a legitimate clean twin. Each negative twin
   then changes one normalized boundary and preserves the rest of the case.
10. **Do not leak the oracle to adapters.** Command adapters receive the case identifier and input,
    never the expected decision or reason codes. The public protocol carries no credentials, tool
    arguments, results, prompts, reasoning, or operational payloads and cannot execute a tool.
11. **Conformance is scoped evidence.** A reference run only self-tests the compiler. A real adapter
    run shows behavior on the exact generated suite, not correctness of the source inventory,
    completeness of policy, production enforcement, safety, compliance, certification, or approval.

## Transfer-failure checks

- A model card can identify a model but not every runtime tool entitlement.
- An SBOM can identify software components but not prove current agent authority.
- A workload identity can identify a subject but not prove that a specific operation is still in
  scope for a specific task.
- A signed BOM can bind bytes and signer identity but not prove that the deployment is safe,
  compliant, effective, approved, or currently authorized.
- A `read` tool becoming `prepare` is consequential even if model bytes are unchanged.
- Absolute expiry moving forward is ordinary lease rotation; duration increasing is widening.
- A suite of prohibited requests alone cannot distinguish safe enforcement from destructive
  deny-all behavior; legitimate clean twins are required.
- Matching decisions without exact reason codes can hide a different boundary implementation;
  the reference contract scores both.
- Independent operation and scope declarations can produce a Cartesian test intersection. Systems
  with conditional operation/scope relationships need a future relationship profile rather than
  treating this 1.0 compiler as a complete policy model.

## Primary sources

- NIST, [AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative), updated 2026-08-14.
- NIST NCCoE, [Accelerating the Adoption of Software and AI Agent Identity and Authorization](https://www.nccoe.nist.gov/publications/other/accelerating-adoption-software-and-ai-agent-identity-and-authorization-concept), draft published 2026-02-05.
- NIST AI 800-5, [Summary Analysis of Responses Regarding Security Considerations for AI Agents](https://www.nist.gov/publications/summary-analysis-responses-request-information-regarding-security-considerations-ai), published 2026-05-18.
- NIST, [SP 800-53 Revision 5.1, AC-6 Least Privilege](https://csrc.nist.gov/Projects/risk-management/sp800-53-controls/downloads), current derivative downloads accessed 2026-08-30.
- NIST, [SP 800-207 Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final), final published 2020-08-11.
- NIST, [SP 800-207A Zero Trust Access Control for Cloud-Native Applications](https://csrc.nist.gov/pubs/sp/800/207/a/final), final published 2023-09-13.
- CISA, [2025 Minimum Elements for a Software Bill of Materials](https://www.cisa.gov/resources-tools/resources/2025-minimum-elements-software-bill-materials-sbom), August 2025.
- OWASP CycloneDX, [Machine Learning Bill of Materials](https://cyclonedx.org/capabilities/mlbom/), accessed 2026-08-30.
- OWASP CycloneDX, [official 1.7 JSON Schema](https://github.com/CycloneDX/specification/blob/master/schema/bom-1.7.schema.json), accessed 2026-08-30.
- in-toto, [Attestation Framework Specification](https://github.com/in-toto/attestation/blob/main/spec/README.md), accessed 2026-08-30.
- OpenTelemetry, [Generative AI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/), accessed 2026-08-30.
- Model Context Protocol, [Authorization specification 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), accessed 2026-08-30.
- IETF, [RFC 8707: Resource Indicators for OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707), February 2020.
- IETF, [RFC 9700: Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700), January 2025.
