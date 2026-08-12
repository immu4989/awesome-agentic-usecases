# Start here

This repository is a lab for answering a narrower, more useful question than “can an
agent do this?”:

> **How often does it work, what does a run cost, and what breaks when the world stops
> cooperating?**

You do not need an API key to begin. Pick the route that matches the job you are doing.

If you have a workflow but do not know which lab fits, start with
**[AAU Studio](https://immu4989.github.io/awesome-agentic-usecases/#studio)**. It matches
your description to the full verified catalog, explains the evidence behind each result,
compares up to three architectures, and creates a fork-ready evaluation brief locally in
your browser. No workflow text is uploaded.

Once Studio gives you a match, download the evaluation brief and run
`aau forge <brief.json> --name <your-eval>` to generate and verify a runnable adaptation.
Forge keeps domain truth explicitly unvalidated until a qualified owner replaces the
generic rules. See [AAU Forge](AAU_FORGE.md).

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

Every observation is cross-linked in the [Failure Taxonomy](FAILURE_TAXONOMY.md), which
groups 275 observed failures into 17 recurring patterns.

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
