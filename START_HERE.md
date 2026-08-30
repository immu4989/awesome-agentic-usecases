# Start here

This repository is a lab for answering a narrower, more useful question than “can an
agent do this?”:

> **How often does it work, what does a run cost, and what breaks when the world stops
> cooperating?**

You do not need an API key to begin. Pick the route that matches the job you are doing.

If you already operate an agent, connect it without rewriting the application:

```bash
pip install -e harness
aau evaluate harness/examples/byo-agent-suite.json \
  --command "python harness/examples/byo_agent_adapter.py" \
  --out aau-agent-receipt.json
```

The command/HTTP adapter protocol is provider-neutral. Its public receipt contains aggregate
measurements and scenario IDs—not prompts, expected answers, agent responses, reasoning, headers,
or credentials. See the [BYO-agent guide](harness/README.md#evaluate-an-existing-agent).

If you have a reviewed task but no comparator for the process people use today, open the
**[Human Baseline Lab](https://immu4989.github.io/awesome-agentic-usecases/#human-baseline-lab)**.
The browser runs an individual eight-task synthetic practice and keeps responses in the tab. The
CLI splits any public/synthetic AAU suite into a blinded study and separate answer key, then
aggregates identifier-free sessions into exactness, uncertainty, abstention, task-time,
calibration, and agreement evidence. Real participant collection requires the responsible
institution's own human-protection determination; the Lab does not rank workers, support
employment actions, prove causal benefit, or authorize replacement or deployment. See the
[complete study kit](human-baseline-lab/).

If the agent and human process are measured but you still cannot answer whether the service became
better, open the **[Evidence Commons](https://immu4989.github.io/awesome-agentic-usecases/#evidence-commons)**.
Its Impact Capsule binds the reviewed suite, aggregate agent receipt, human comparator,
predeclared public-value measures, bounded observation, and independent reproduction. Missing
links remain visible; status is derived without a trust score. Start with one of three open partner
pilots in [FOIA routing, accessible digital services, or nonprofit grants](evidence-commons/).
Use only public synthetic and aggregate artifacts, and obtain the responsible organization's
determinations before observing people or using operational records.

If you have a public or synthetic AI inventory, open the
**[Federal AI Portfolio Observatory](https://immu4989.github.io/awesome-agentic-usecases/#portfolio-observatory)**.
It surfaces documentation gaps and possible-overlap questions, binds before/after public-value
measurements to limitations and cost, checks three independent TEV&V layers, and maps acquisition
obligations to tests and evidence. It does not rank investments, recommend budgets or awards,
claim savings, certify compliance, or make a protected decision.

If you are shaping or acquiring AI for a public-sector mission, start with
**[Federal Mission Studio](https://immu4989.github.io/awesome-agentic-usecases/#federal-mission)**.
It keeps your draft in the browser, maps mission impact, testing, human authority,
acquisition terms, monitoring, remedy, and cease-use evidence to a dated OMB/NIST/GAO
crosswalk, and exports a non-certifying 12-file pack with a SHA-256 manifest. Use only
synthetic or public information on the public site.

If the mission is already defined and you need a reproducible agency–responder handoff, use the
**[Federal Pilot Desk](https://immu4989.github.io/awesome-agentic-usecases/#federal-pilot)**.
It keeps the agency intake, responder claims and evidence, and exact synthetic test manifest
separate; recomputes visible gaps locally; and exports an aggregate assessment without ranking a
vendor or recommending an award. Start from one of three complete public synthetic exchanges in
the [Federal Pilot Kit](federal-pilot-kit/), then use its
[30-Day Agency Pilot Launch Pack](federal-pilot-kit/pilot-launch/) to assign decision rights,
security/privacy intake, weekly evidence gates, success metrics, and an exit rehearsal. Before
running a tagged bundle, follow the [release verification procedure](federal-pilot-kit/RELEASE_VERIFICATION.md).

If a pilot is ending and the next team needs to learn from it, open the
**[Federal AI Lessons Exchange](https://immu4989.github.io/awesome-agentic-usecases/#lessons-exchange)**.
Search public closeouts across success, change, and stop outcomes; inspect the exact scope,
human decision, non-transfer conditions, and dated policy dependencies; then scan a forked
lesson locally before publication. The browser sends nothing, and the exchange never ranks
vendors, recommends awards, or turns one pilot's result into a universal practice.

If you already have an `eval_*.json`, start with
**[Receipt Lab](https://immu4989.github.io/awesome-agentic-usecases/#receipt-lab)**. It opens
the artifact locally, recomputes its structural evidence, keeps interval and provenance gaps
visible, and exports an aggregate-only inspection receipt. Nothing is uploaded. A passing
inspection means structurally coherent—not independently reproduced or domain validated.

If an MCP or A2A agent can authenticate but you still need to prove what it may do now, open
**[Portable Agent Assurance](https://immu4989.github.io/awesome-agentic-usecases/#agent-assurance)**.
The experimental offline verifier binds a deliberately public synthetic identity fixture to its
operator, task, short-lived authority lease, policy epoch, exact protocol operation, destination,
peer, delegation ceiling, monitor state, and evidence. Its 18-case suite preserves two legitimate
twins while testing sixteen identity, authority, MCP, A2A, and delegation collisions.

```bash
python3 portable-agent-assurance/aau_assurance.py evaluate \
  portable-agent-assurance/examples/synthetic-assurance-envelope.json \
  portable-agent-assurance/examples/mcp-a2a-conformance-suite.json \
  --out /tmp/aau-assurance-receipt.json
python3 portable-agent-assurance/aau_assurance.py verify \
  /tmp/aau-assurance-receipt.json \
  --envelope portable-agent-assurance/examples/synthetic-assurance-envelope.json \
  --suite portable-agent-assurance/examples/mcp-a2a-conformance-suite.json
```

For evaluation planning, use the companion [TEVV-Athlon profile](tev-v-athlon-profile/). It maps
the same artifacts to all four stages of the NIST AI 200-2 initial public draft while keeping
planned events, revealed material, and absent independent reproduction visible. It is an
experimental profile—not NIST conformance, certification, production identity validation, live
authorization, compliance, or an Authority to Operate.

If your agent already has consequential tools and the question is whether its authority remains
bounded over a long or multi-agent task, start with the
**[Agent Security Commons](https://immu4989.github.io/awesome-agentic-usecases/#agent-security-commons)**.
Its experimental Agent Boundary Protocol 0.2 binds identity, task, policy epoch, sequence, tools,
targets, destinations, peers, delegation, monitoring, safe-stop, and human restart into a
temporary lease. Run the 50-event runtime conformance suite, replay a public incident as exact
regressions, compare matched control arms, or choose an essential-service defender kit. The
reference tools are offline and dependency-free; receipts are recomputable evidence, not
certification, compliance, production validation, or an Authority to Operate. Start with the
[runtime](agentic-cyber-resilience/), [incident commons](agent-incident-regression-commons/),
[defender kits](essential-services-defender-kits/),
[control observatory](agent-control-observatory/), or
[public-value pilot network](public-value-pilot-network/).

If your job starts with a vulnerability notice, an agent-security incident, an essential service,
or a defensive AI capability, open the
**[Collective Cyber Defense Lab](https://immu4989.github.io/awesome-agentic-usecases/#collective-cyber-defense)**.
Use Verified Fix Commons to preserve the legitimate twin and service while closing a safe-fixture
regression; use the Containment Drill Runner to measure parent, child, and queued-work stops; use
Defender-in-a-Box to plan locally from public, synthetic, or authorized inventory; or evaluate a
provider-neutral response file against 20 safe defensive tasks. Publish only the aggregate receipt
through the Evidence Mesh. To reproduce outside the maintainer workflow, use the
[Independent Reproduction Exchange](independent-reproduction-exchange/): the issuer commits a
hidden oracle, the reproducer receives only the answer-free challenge, and a separate reviewer
reveals and adjudicates the run. The 0.2 Evidence Mesh accepts `independently_reproduced` only when
that adjudication binds the exact artifact bytes and passes the reviewed role/relationship gate.
The observatory keeps unlike measurements separate and never ranks vendors, agencies, or models.

If you have a workflow but do not know which lab fits, start with
**[AAU Studio](https://immu4989.github.io/awesome-agentic-usecases/#studio)**. It matches
your description to the full verified catalog, explains the evidence behind each result,
compares up to three architectures, and creates a fork-ready evaluation brief locally in
your browser. No workflow text is uploaded.

Once Studio gives you a match, download the evaluation brief and run
`aau forge <brief.json> --name <your-eval>` to generate and verify a runnable adaptation.
Forge keeps domain truth explicitly unvalidated until a qualified owner replaces the
generated rules. For Decision Gate, Rights Continuity, and Critical Event Fan-Out it also
builds a contract-specific graph and scorecard. See [AAU Forge](AAU_FORGE.md), then run
`aau forge doctor <generated-lab>` to inspect the publication gaps.

If you have adapted a lab, visit the
**[Community Forge Gallery](https://immu4989.github.io/awesome-agentic-usecases/#gallery)**.
It makes useful forks discoverable and derives their public evidence level from committed
artifacts. Run `aau gallery list` to inspect the references or
`aau gallery validate <entry-id>` before submitting yours. See the
[Gallery contribution guide](gallery/README.md).

## I want to see a real agent failure

Start with one of these ten. Each takes the same shape—scenario, tools, agent, exact
scorer—but exposes a different class of failure.

| Failure you want to understand | Start here | What it demonstrates |
|---|---|---|
| The model reasons correctly but never finishes | [Exception Triage](logistics-supply-chain/exception-triage-agent/) | Why `submitted` belongs beside every accuracy metric |
| The model chooses an unsafe irreversible action | [Refund Resolution](customer-support/refund-resolution-agent/) | Why acting agents must be scored on the route, not only the result |
| The model follows an injection from its tooling | [Trifecta Exfil](security-operations/trifecta-exfil-agent/) | Why a prompt guard and a dataflow gate are not equivalent |
| The outcome is right but the service burdens the user | [Small Business Recovery](public-sector/small-business-recovery-agent/) | Why evidence, accessibility, deadlines, recourse, rights, and record truth need their own contract |
| Recovery succeeds through an attacker-controlled route | [Account Recovery Assurance](identity-access/account-recovery-assurance-agent/) | Why legitimate recovery and takeover containment must be measured together |
| The scanner is green but the service is unusable | [Accessibility Remediation Verifier](accessibility-digital-services/accessibility-remediation-verifier/) | Why automated coverage and proof of fix are different claims |
| The request is routed but an archive survives | [Privacy Rights Orchestrator](privacy-data-governance/privacy-rights-orchestrator/) | Why exact system coverage and truthful completion need receipts |
| The recommendation is right but the gate or authority is wrong | [Batch Disposition Gate](pharmaceutical-manufacturing/batch-disposition-gate/) | Why a nearby valid rule cannot substitute for exact evidence, procedure, owner, and action trace |
| The main appeal survives but its companion protection expires | [Disability Cessation Continuity](social-security-disability/cessation-benefit-continuation-navigator/) | Why primary and companion rights need independent triggers, clocks, owners, and receipts |
| Emergency response succeeds but another duty stays open | [Pipeline Incident Notification](pipeline-safety/incident-notification-coordinator/) | Why containment, initial notification, update, follow-up, and receipts cannot share one status |
| A polished AI proposal is treated as mission-ready evidence | [Federal AI Acquisition Performance Gate](federal-ai-acquisition/acquisition-performance-gate/) | Why intended-environment testing, data rights, portability, pricing, monitoring, and warranted award authority must remain distinct |

Every observation is cross-linked in the [Failure Taxonomy](FAILURE_TAXONOMY.md), which
groups 278 observed failures into 17 recurring patterns.

## I want to run an eval without an API key

```bash
git clone https://github.com/immu4989/awesome-agentic-usecases.git
cd awesome-agentic-usecases
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install -e harness

aau start exception-triage             # prints the exact commands
python -m pip install -e logistics-supply-chain/exception-triage-agent
exception-triage-agent eval --backend mock
```

The mock is a deterministic stand-in with a deliberate mistake. It checks that generation,
tools, scoring, repeats, cost accounting, and reporting work end to end. It is not a model
benchmark and is always labelled as such.

Useful discovery commands:

```bash
aau list                               # all verified use cases
aau list --industry security
aau list --capability act
aau find "memory adversarial"
aau show refund-guarded
aau doctor                             # verify the checkout is internally consistent
```

## I want to compare models on my task

1. Pick the closest decision shape with `aau find <terms>`.
2. Run its mock once to verify your environment.
3. Run the same committed scenarios with at least three repeats per model.
4. Compare the task metric, `submitted`, cost, latency, and directional failures together.

```bash
export MISTRAL_API_KEY=...
exception-triage-agent eval --backend mistral --repeats 3

export OPENROUTER_API_KEY=...
exception-triage-agent eval --backend openrouter --model <model-id> --repeats 3
```

The [model matrix](README.md#there-is-no-best-model) demonstrates why the use-case match
matters: every tested model wins somewhere and loses somewhere else.

## I want to harden an agent

Do not begin with a generic guardrail. Begin with the consequence you need to prevent and
measure it against an unchanged baseline.

| Risk | Controlled comparison | Practical starting point |
|---|---|---|
| Forbidden irreversible action | [Refund Guarded](customer-support/refund-guarded/) | Enforce policy in the tool that performs the action |
| Prompt injection in user content | [Refund Injected](customer-support/refund-injected/) | Score whether the forbidden consequence occurred |
| Secret exfiltration through poisoned tooling | [Trifecta Exfil](security-operations/trifecta-exfil-agent/) | Track sensitive data to every egress |
| Long or multi-agent work expands its own authority | [Agent Boundary Protocol](agentic-cyber-resilience/) | Bind identity, task, time, tools, targets, peers, egress, safe stopping, monitoring, and restart evidence into one lease |
| Poisoned long-term memory | [Refund Memory](customer-support/refund-memory/) | Gate writes with source provenance |
| Stale or conflicting context | [Exception Triage Drift](logistics-supply-chain/exception-triage-drift/) | Enforce freshness at the read boundary |
| False success after a blocked action | [Incident Remediation](it-operations/incident-remediation-agent/) | Compare the record against actions that actually succeeded |
| Invoice or email changes where money is sent | [Vendor Payment Review](procurement-finance/vendor-payment-review-agent/) | Compare supplied bank details with a separately verified system of record |
| Correct service outcome with avoidable user burden | [Small Business Recovery](public-sector/small-business-recovery-agent/) | Score the full [Public Value Contract](PUBLIC_VALUE_CONTRACT.md), not only the terminal label |
| Correct utility route after the service deadline | [Household Energy Lifeline](energy-utilities/household-energy-lifeline/) | Score essential-service continuity separately from referral accuracy |
| Correct recovery route with a hidden or invented payment source | [Disaster Claim and Aid Coordinator](insurance-disaster-recovery/disaster-claim-aid-coordinator/) | Bind the action to the exact compensation sources in trusted records |
| Correct unemployment status after an appeal or certification clock is lost | [Unemployment Claim Navigator](employment-social-insurance/unemployment-claim-navigator/) | Score every live claim path separately from the status explanation |
| Correct farm program with an incomplete disaster-deadline map | [Farm Disaster Deadline Agent](agriculture-food-systems/farm-disaster-deadline-agent/) | Require the exact set of applicable program notices, with no invented deadline |
| Complete permit packet bound to the wrong jurisdiction or project rule | [Permit Readiness Agent](housing-construction/permit-readiness-agent/) | Score the rule identifier and source authority, not checklist completion alone |
| Timely accommodation route that over-collects a student's records | [Student Accommodation Navigator](education-services/student-accommodation-navigator/) | Make sensitive-data minimization an exact service outcome |
| Urgent recovery route weakens assurance | [Account Recovery Assurance](identity-access/account-recovery-assurance-agent/) | Intersect presented methods with trusted account state and score takeover consequence |
| Automated accessibility checks produce false assurance | [Accessibility Remediation Verifier](accessibility-digital-services/accessibility-remediation-verifier/) | Join manual evidence, source inspection, deployment, and retest state |
| Privacy workflow silently omits systems or closes early | [Privacy Rights Orchestrator](privacy-data-governance/privacy-rights-orchestrator/) | Make system coverage and receipt-backed completion exact |
| A plausible service route requests the wrong evidence or crosses authority | [Food Recall Traceability](food-safety-manufacturing/food-recall-traceability-coordinator/) | Run one of 12 matched Evidence Service Contract labs and compare the same obligations across industries |
| A correct-looking recommendation applies the clean twin's rule to an exception | [Batch Disposition Gate](pharmaceutical-manufacturing/batch-disposition-gate/) | Run the matched [Decision Gate Contract](DECISION_GATE_CONTRACT.md) and score reason, evidence, gates, procedure, authority, and record truth together |
| A linked source is real but does not support the drafted claim | [Claim & Citation Evidence Verifier](research-knowledge-work/claim-evidence-verifier/) | Require passage-level entailment and freshness before handing the draft to its human editor |
| A routine service request contains gas or carbon-monoxide danger | [Service Visit Readiness Coordinator](home-field-services/service-visit-readiness-coordinator/) | Make emergency evidence change the channel before appointment optimization begins |
| A prior grant packet is accepted as proof for the current award | [Grant Obligation Evidence Navigator](nonprofit-grant-management/grant-obligation-evidence-navigator/) | Bind each obligation, deadline, and cost record to the current notice of award |
| An appointment, draft, intake, or dispute receipt is treated as the completed protection | [Vehicle Recall Remedy](automotive-safety/vehicle-recall-remedy-coordinator/) | Run one of seven matched [Protection Receipt Contract](PROTECTION_RECEIPT_CONTRACT.md) labs and test subject, rule, gates, clock/channel, authority, and receipt truth together |
| One event creates several duties, but the agent returns one familiar route | [Medical Device Adverse-Event Reporting](medical-device-safety/adverse-event-reporting-gate/) | Run the matched [Obligation Graph Contract](OBLIGATION_GRAPH_CONTRACT.md) and score obligation set, clock origin, time semantics, recipient, owner, and receipt together |

The [Practical Playbooks](PLAYBOOKS.md) turn these experiments into metric and design
recipes you can apply to another agent.

## I want to build or fork my own use case

If a nearby example exists, adapt it; preserving a tested shape is faster than starting
from a blank file. If your decision shape is new, use the generator:

```bash
aau-new-use-case --industry insurance --name claim-escalation-agent --seed 67
```

It creates a runnable package, seeded scenarios, shared gold rules, a mock with an
engineered gap, tests, result folders, and documentation templates. Continue with
[Build Your Own](BUILD_YOUR_OWN.md), which explains what to change and what not to weaken.

## Choose by capability

| Agent shape | What must be measured | Examples |
|---|---|---|
| `investigate` + `decide` | retrieval coverage, decision accuracy, directional error | [Logistics](logistics-supply-chain/exception-triage-agent/), [Fraud](financial-services-fraud/fraud-alert-triage-agent/) |
| `plan` + `act` | prerequisite order, irreversible actions, final outcome | [Refund Resolution](customer-support/refund-resolution-agent/) |
| `investigate` + `plan` + `act` | cross-record match, trusted identity, irreversible action, over-block | [Vendor Payment Review](procurement-finance/vendor-payment-review-agent/) |
| `watch` | observation coverage, patience, false page, missed incident | [On-Call Watch](it-operations/oncall-watch-agent/) |
| `gate` | unsafe admit, over-block, escalation, decision coverage | [Artifact Admission](security-operations/artifact-admission-agent/), [Prior Auth](healthcare-life-sciences/prior-auth-review-agent/) |
| `multi-agent` | end-to-end outcome plus handoff loss | [Refund Crew](customer-support/refund-crew/) |
| `public-value` | outcome, minimum evidence, accessibility, deadline, recourse, rights, continuity, record truth, and domain-specific fidelity | [Small Business Recovery](public-sector/small-business-recovery-agent/), [Energy Lifeline](energy-utilities/household-energy-lifeline/), [Disaster Coordination](insurance-disaster-recovery/disaster-claim-aid-coordinator/), [Unemployment](employment-social-insurance/unemployment-claim-navigator/), [Farm Disaster](agriculture-food-systems/farm-disaster-deadline-agent/), [Permits](housing-construction/permit-readiness-agent/), [Student Accommodation](education-services/student-accommodation-navigator/) |
| `evidence-service` | exact terminal, missing-set evidence, accessible channel, deadline, recourse, protected authority, and executed record together | [Food Recall](food-safety-manufacturing/food-recall-traceability-coordinator/), [Water Notice](water-sanitation/drinking-water-notice-coordinator/), [IRS Notice](federal-taxpayer-services/irs-notice-response-navigator/), or any lab in the [matched 12-industry wave](USE_CASE_RADAR.md#evidence-service-expansion-wave--shipped) |
| `decision-gate` | exact outcome, rule-specific reason, held/missing evidence, satisfied conjuncts, procedure, protected authority, and executed record | [Pharma](pharmaceutical-manufacturing/batch-disposition-gate/), [Grid](grid-operations/distribution-restoration-safety-gate/), [Hiring](human-resources/hiring-compliance-navigator/), [Aviation](aviation-operations/aircraft-dispatch-evidence-gate/), [Banking](banking-compliance/aml-kyc-sanctions-case-gate/), [Tax](tax-filing-services/tax-return-completeness-navigator/) |
| `federal-mission-assurance` | impact determination, intended-environment tests, acquisition terms, human authority, monitoring, remedy, cease use, and evidence manifest | [Federal AI Acquisition Performance Gate](federal-ai-acquisition/acquisition-performance-gate/) and [Federal Mission Studio](https://immu4989.github.io/awesome-agentic-usecases/#federal-mission) |
| `federal-pilot-exchange` | agency outcome, responder claim, declared evidence, exact synthetic test, critical gap, pricing, portability, exit, monitoring, and protected award authority | [Federal Pilot Kit](federal-pilot-kit/) and [Federal Pilot Desk](https://immu4989.github.io/awesome-agentic-usecases/#federal-pilot) |
| `federal-ai-lesson` | evidence-linked outcome, human closeout decision, public-sharing attestations, policy dependencies, bounded reuse, non-transfer conditions, revalidation triggers, and a deterministic manifest | [Federal AI Lessons Exchange](https://immu4989.github.io/awesome-agentic-usecases/#lessons-exchange) and [lesson schema](federal-pilot-kit/lesson-record.schema.json) |
| `proof-before-action` | exact outcome, source- or record-specific proof, transfer specificity, protected authority, and truthful executed record | [Claims](research-knowledge-work/claim-evidence-verifier/), [Field service](home-field-services/service-visit-readiness-coordinator/), [Grants](nonprofit-grant-management/grant-obligation-evidence-navigator/) |
| `public-protection` | exact subject, current rule, complete gates, live clock/channel, protected authority, and truthful receipt | [Vehicle recalls](automotive-safety/vehicle-recall-remedy-coordinator/), [911/988 outages](telecommunications-emergency/communications-outage-reporting-gate/), [Worker incidents](workplace-safety/severe-incident-reporting-navigator/) |
| `obligation-graph` | complete obligation set, exact trigger and clock origin, deadline semantics, recipient/channel, protected owner, and truthful receipt | [Medical devices](medical-device-safety/adverse-event-reporting-gate/), [Mortgage protection](mortgage-servicing/loss-mitigation-foreclosure-gate/), [Cyber disclosure](securities-cyber-disclosure/material-cyber-incident-disclosure-gate/), or any lab in the [matched report](CLOCK_COLLISION_REPORT.md) |
| `identity` + `act` | assurance match, established method, takeover containment, notification, PII minimization | [Account Recovery Assurance](identity-access/account-recovery-assurance-agent/) |
| `accessibility` + `verification` | defect coverage, matching test, deploy state, proof of fix, false assurance | [Accessibility Remediation](accessibility-digital-services/accessibility-remediation-verifier/) |
| `privacy` + `system-coverage` | identity gap, exact system set, jurisdiction, deadline, recourse, truthful completion | [Privacy Rights Orchestration](privacy-data-governance/privacy-rights-orchestrator/) |
| adversarial A/B | attack consequence, clean-task success, defence cost | [Refund Injected](customer-support/refund-injected/), [Trifecta Exfil](security-operations/trifecta-exfil-agent/) |

If no entry fits, check the [Real-world Use-case Radar](USE_CASE_RADAR.md),
[request a use case](https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=use-case-request.yml),
or propose one using the contribution template.
