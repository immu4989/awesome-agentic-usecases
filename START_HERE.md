# Start here

This repository is a lab for answering a narrower, more useful question than “can an
agent do this?”:

> **How often does it work, what does a run cost, and what breaks when the world stops
> cooperating?**

You do not need an API key to begin. Pick the route that matches the job you are doing.

## I want to see a real agent failure

Start with one of these four. Each takes the same shape—scenario, tools, agent, exact
scorer—but exposes a different class of failure.

| Failure you want to understand | Start here | What it demonstrates |
|---|---|---|
| The model reasons correctly but never finishes | [Exception Triage](logistics-supply-chain/exception-triage-agent/) | Why `submitted` belongs beside every accuracy metric |
| The model chooses an unsafe irreversible action | [Refund Resolution](customer-support/refund-resolution-agent/) | Why acting agents must be scored on the route, not only the result |
| The model follows an injection from its tooling | [Trifecta Exfil](security-operations/trifecta-exfil-agent/) | Why a prompt guard and a dataflow gate are not equivalent |
| The outcome is right but the service burdens the user | [Small Business Recovery](public-sector/small-business-recovery-agent/) | Why evidence, accessibility, deadlines, recourse, rights, and record truth need their own contract |

Every observation is cross-linked in the [Failure Taxonomy](FAILURE_TAXONOMY.md), which
groups 143 observed failures into 13 recurring patterns.

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
| adversarial A/B | attack consequence, clean-task success, defence cost | [Refund Injected](customer-support/refund-injected/), [Trifecta Exfil](security-operations/trifecta-exfil-agent/) |

If no entry fits, check the [Real-world Use-case Radar](USE_CASE_RADAR.md),
[request a use case](https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=use-case-request.yml),
or propose one using the contribution template.
