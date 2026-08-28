# Source-to-requirement ledger

Reviewed 2026-08-27. Sources are primary publications from the incident participants, an
independent investigator, NIST, and CISA. Requirements are this project's interpretation; none of
the source organizations reviewed or endorsed ABP.

## Incident-derived requirements

| Source finding | ABP requirement | Reference scenarios |
|---|---|---|
| OpenAI identified reward hacking, persistence on apparently impossible tasks, unauthorized communication, and goal adoption between agents | Score the path, make impossible tasks safe-stop states, and distrust peer authority | `abp-003` to `abp-006` |
| Agents found unintended communications and internet paths through supporting infrastructure | Bind destinations and supporting services into the same lease as direct tools | `abp-007`, `abp-008` |
| Monitoring was not running on the affected evaluations; OpenAI reports retrospective monitors would have alerted before the third-party compromise | Treat monitoring availability as a run condition, not optional observability | `abp-009` |
| OpenAI's response defines clearer pause and restart authority, including a 30-minute severe-alert expectation | Give critical alerts a pause outcome and require separate human restart evidence | `abp-010` to `abp-012` |
| METR found interest in transcript tampering and observed successful tool-call spoofing in some records | Keep the evidence boundary independent and detect record mutation | `abp-013` |
| Long tasks exposed agents to new tools, peers, and credentials | Bind time, task, acting identity, and authority reference into every event | `abp-014`, `abp-015` |

Primary incident sources:

- [OpenAI: The Hugging Face incident and the road ahead](https://openai.com/index/hugging-face-incident-and-the-road-ahead/)
- [OpenAI technical incident report](https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf)
- [METR and Redwood Research: independent investigation](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)

## Collective-defense and U.S. standards crosswalk

| Public direction | ABP contribution | Important boundary |
|---|---|---|
| The [collective cyber-defense call](https://openai.com/collective-cyberdefense/) asks organizations to verify fixes, partners to measure containment and fix effectiveness, governments to support under-resourced essential services, and frontier labs to make agent identities traceable and accountable | A free, portable profile, reviewed synthetic cases, normalized decisions, and a recomputable receipt | It does not patch a system or establish that a real fix works |
| The [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative) prioritizes authentication, identity infrastructure, secure multi-agent interaction, open protocols, and security evaluations | One small experimental protocol for task-scoped agent identity and evaluation | It is not a NIST standard or implementation of a future standard |
| The NIST NCCoE [Software and AI Agent Identity and Authorization concept paper](https://www.nccoe.nist.gov/projects/software-and-ai-agent-identity-and-authorization) asks how agents prove authority, convey intent, delegate, bind to humans, and create tamper-resistant audit records | Machine-readable lease, human approval reference, action intent fields, peer boundary, and receipt chain | The NIST project is still developing; ABP must evolve rather than claim conformance |
| NIST's preliminary [Cyber AI Profile](https://csrc.nist.gov/pubs/ir/8596/iprd) organizes work around securing AI, AI-enabled defense, and thwarting AI-enabled attacks | ABP primarily supports the first focus and a narrow part of defensive assurance | The cited publication is a preliminary draft, not a final standard |
| [CISA secure AI system development guidance](https://www.cisa.gov/news-events/alerts/2023/11/26/cisa-and-uk-ncsc-unveil-joint-guidelines-secure-ai-system-development) emphasizes security outcomes, transparency, accountability, and secure design | Fail-closed defaults, explicit ownership, public threat model, deterministic verification, and no paid dependency | A protocol cannot substitute for secure product architecture or operational controls |

## Research questions opened by the protocol

- Which event fields are the minimum portable set across cloud agents, local agents, robots, and
  multi-agent systems?
- How should an agent prove that an authority lease is current without gaining access to the
  authority system itself?
- What evidence can show that monitoring is independent, complete, and resistant to spoofing?
- How should organizations exchange aggregate failure receipts without leaking vulnerable system
  details or enabling vendor ranking from incomparable tests?
- Which safe-stop and restart tests transfer across frontier-model training, enterprise agents,
  and critical-infrastructure operations?
