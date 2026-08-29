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
