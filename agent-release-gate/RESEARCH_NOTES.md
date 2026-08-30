# Research and premise notes

Verified: **2026-08-30**. These notes explain design choices; they are not government guidance,
standards interpretation, compliance advice, or deployment authorization.

## Why change-specific evidence

Agent evaluation is often published as a static model score while deployment changes include tool
descriptions, Agent Cards, prompts, identity bindings, authority policy, destinations, dependency
versions, monitoring, and rollback. A release gate therefore starts with exact component bytes and
maps their declared impact to evaluation suites. It does not pretend to infer every behavioral
impact automatically.

## NIST agent initiative

NIST's AI Agent Standards Initiative names secure interoperability, open agent protocols, agent
identity, authorization, and security evaluations as current work areas. AAU responds with a small
experimental evidence contract; it is not a NIST profile or conformance test.

- https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative
- https://www.nccoe.nist.gov/publications/other/accelerating-adoption-software-and-ai-agent-identity-and-authorization-concept

## TEVV-Athlon

NIST AI 200-2 initial public draft frames TEVV as a contextual four-stage process rather than a
universal score. The release pack keeps the objective, changed material, events, measures,
evidence, findings, and gaps separate. A single passing suite remains bounded to its declared
release and context.

- https://www.nist.gov/artificial-intelligence/ai-research/tevv-athlon-framework-evaluating-ai-systems

## OSCAL

The OSCAL Assessment Results model provides machine-readable observations, findings, evidence, and
risks for assessment and continuous monitoring. The AAU exporter is a bridge for downstream review,
not a complete assessment or a claim that AAU release tags are NIST control objectives.

- https://pages.nist.gov/OSCAL/learn/concepts/layer/assessment/assessment-results/
- https://pages.nist.gov/OSCAL/about/

## Premise corrections

1. **A file hash is not behavior.** It proves exact bytes changed; a declared policy and executable
   suite are still required.
2. **An impacted-suite pass is not deployment authority.** Operational owners retain approval,
   production validation, change execution, and rollback.
3. **An approval record is not identity proof.** The public schema fixes identity verification to
   false.
4. **OSCAL serialization is not authorization.** An agency assessment plan, selected controls,
   authorized assessors, validation, risk acceptance, and authorization process remain external.
5. **A mock is not evidence of an agent.** Mock execution cannot reach `release_ready`.
