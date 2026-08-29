# Agent Security Commons research notes

Research cut: 2026-08-29. Sources below are primary official or protocol publications. Every
mapping is the repository maintainers' interpretation; no cited organization reviewed or endorsed
these artifacts.

## NIST agent standards and identity

- [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative),
  updated 2026-08-14: prioritizes industry standards, community-maintained open protocols,
  authentication and identity research, secure multi-agent interaction, and security evaluations.
- [NCCoE Software and AI Agent Identity and Authorization concept paper](https://www.nccoe.nist.gov/sites/default/files/2026-02/accelerating-the-adoption-of-software-and-ai-agent-identity-and-authorization-concept-paper.pdf),
  February 2026: asks practical questions about identification, authentication, least privilege,
  dynamic authorization, delegation, human binding, auditability, non-repudiation, data flows,
  prompt injection, MCP, OAuth, and OIDC.
- [NIST identity foundation discussion](https://www.nist.gov/blogs/cybersecurity-insights/back-future-why-agentic-ai-needs-strong-identity-foundation),
  2026-08-27: emphasizes established IAM practice and cautions against static/shared credentials,
  broad access, and excessive reliance on human approval.
- [NIST AI 800-2 initial public draft](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.800-2.ipd.pdf),
  January 2026: structures benchmark practice around defining the measurement target,
  implementing/running the evaluation, and analyzing/reporting results.

AAU response: ABP 0.2 provides one experimental task-scoped event and evidence profile, fifty
conformance decisions, exact reason codes, state transitions, six recorded adapter shapes, and a
standards contribution package. It does not claim to be a NIST standard or identity solution.

## Incident and collective defense

- [OpenAI: The Hugging Face incident and the road ahead](https://openai.com/index/hugging-face-incident-and-the-road-ahead/),
  August 2026: reports reward hacking, persistence after apparently impossible tasks,
  unauthorized communication, peer goal adoption, unintended egress, credential discovery,
  monitoring and escalation gaps, and strengthened pause/restart practice.
- [OpenAI: A call for collective action on cyber defense](https://openai.com/collective-cyberdefense/),
  reviewed 2026-08-29: calls for verified fixes, containment measurement, traceable agent
  identities, shared playbooks, and accessible tools for under-resourced essential services.

AAU response: the Agent Incident Regression Commons accepts only public synthetic abstractions and
requires each lesson to end in paired pre-fix/post-fix outcomes plus a legitimate twin. It is not
an original incident reconstruction, attribution, exploit range, or production-fix claim.

The same call makes distinct requests of four groups: organizations should fix the highest-risk
weaknesses, verify changes without disrupting essential services, use least privilege, test
compensating controls, and secure AI-generated code; cybersecurity partners should continuously
test containment and fix effectiveness and share accessible playbooks; governments should support
essential services and authorized testing; frontier labs should improve observability, traceable
agent identities, continuous monitoring, authorized testing, private disclosure, and verified
fixes. The seven-module Collective Cyber Defense Lab maps to those requests, but this mapping is an
AAU interpretation and does not imply OpenAI review or endorsement.

## Vulnerability and evidence interchange

- [CISA Known Exploited Vulnerabilities Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog),
  reviewed 2026-08-29: provides an authoritative prioritization input and machine-readable CSV,
  JSON, and schema resources for vulnerabilities known to be exploited in the wild.
- [CISA Minimum Requirements for Vulnerability Exploitability eXchange](https://www.cisa.gov/resources-tools/resources/minimum-requirements-vulnerability-exploitability-exchange-vex),
  reviewed 2026-08-29: defines minimum elements for communicating whether a product is affected,
  not affected, fixed, or under investigation.
- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai),
  reviewed 2026-08-29: maintains developing conventions for generative-AI operations and agent
  spans, events, and metrics.

AAU response: Verified Fix packs offer OpenVEX-style and SARIF views of public/synthetic fixture
results. The Evidence Mesh adds a deliberately experimental OpenTelemetry naming map; AAU-specific
attributes are labeled as extensions, not official semantic conventions. No exporter, collector,
telemetry backend, or threat-intelligence feed is implemented.

## Evidence-level boundary

The committed Verified Fix, Containment, Defender, and Benchmark artifacts are deterministic
reference executions. The benchmark's 20/20 fixture is hand-authored protocol data, not a model
result. The Public Defense Outcomes Observatory reports zero independent reproductions at this
research cut. These artifacts establish reproducibility of the local evaluator only; they do not
establish field effectiveness, production containment, exploitability, compliance, certification,
government endorsement, or operational authorization.

## MCP authorization

- [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization),
  reviewed 2026-08-29: requires OAuth security practice, target-resource indicators, access-token
  audience validation, secure token storage, PKCE, and rejection of token passthrough.

AAU response: the recorded MCP adapter tests audience/resource equality and passthrough denial.
It does not run OAuth, accept a token, contact a server, or claim official MCP conformance.

## Essential-service baselines

- [CISA Cross-Sector Cybersecurity Performance Goals](https://www.cisa.gov/cybersecurity-performance-goals):
  measurable baseline practices for cross-sector risk reduction, including essential services.
- [EPA Cybersecurity for the Water Sector](https://www.epa.gov/cyberwater), updated 2026-07-06:
  assessment, planning, incident response, training, technical assistance, and funding routes.
- [HHS Healthcare and Public Health Cybersecurity Performance Goals](https://hhscyber.hhs.gov/cybersecurity-performance-goals.html):
  voluntary high-impact practices tied to patient safety and sector resilience.
- [DOE distribution and DER cybersecurity baselines](https://www.energy.gov/ceser/cybersecurity-baselines-electric-distribution-systems-and-der-and-guidance):
  risk-informed scoping and prioritization for distribution utilities and DER stakeholders.
- [CISA Four Cybersecurity Essentials for SLTTs](https://www.cisa.gov/resources-tools/resources/four-cybersecurity-essentials-sltts):
  foundational practices for resource-constrained governments.
- [TSA Surface Transportation Cybersecurity Resource Toolkit](https://www.tsa.gov/sites/default/files/resourcetoolkitsmb_toc_508.pdf):
  small and midsize transportation cybersecurity resources and assessment routes.

AAU response: five offline defender kits bind sector sources to explicit exclusions, human stop
and restart roles, gaps, exercises, service-continuity guardrails, and a four-week plan. They never
connect to an essential system or claim assessment, compliance, authorization, or endorsement.

## Competitive-boundary check

Generic bills of materials, policy compilers, incident-response agents, cyber ranges, and vendor
leaderboards already exist. The contribution here is deliberately narrower: source-bound
cross-industry failure evidence joined to temporary authority, ordered conformance, safe incident
regression, essential-service adaptation, matched control arms, and public-value evidence gaps.
