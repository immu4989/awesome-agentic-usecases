# The Agent Failure Taxonomy

**236 failure modes, observed across 57 use cases, 15 recurring patterns.**

Every entry below was *measured*, not hypothesised — each links to the run that
produced it, with a reproducing input. Read individually the failures look
domain-specific. Read together they are not: the same handful of patterns keep
reappearing in industries that share nothing but the shape of the agent.

> Several of these were found **independently in eight different domains** without
> anyone looking for them. That is the one thing a collection of demos cannot
> produce, at any scale: you only see a pattern like this by measuring the same way,
> many times, and writing down what broke.

## The patterns

| # | Pattern | In short | Seen in |
|---|---|---|---|
| 1 | [Commit-stall](#commit-stall) | The agent investigates correctly, reaches the right conclusion, and never commits it. | 9 use cases |
| 2 | [The environment beats the prompt](#the-environment-beats-the-prompt) | Changing what the agent *can* do works; telling it what it *should* do mostly doesn't. | 4 use cases |
| 3 | [Contained is not fixed](#contained-is-not-fixed) | A guard drives the incident rate to zero while the agent's judgment stays exactly as wrong. | 3 use cases |
| 4 | [Removing the tool displaces the intent](#removing-the-tool-displaces-the-intent) | Take the forbidden action out of the schema and the goal reroutes — through a legal-but-wrong channel, or into a claim that the work was done. | 2 use cases |
| 5 | [Safety by inaction](#safety-by-inaction) | A 'did it avoid the bad action' metric is passed perfectly by an agent that does nothing. | 5 use cases |
| 6 | [Prior over policy](#prior-over-policy) | The model's own sense of what's reasonable overrides the policy it just retrieved. | 4 use cases |
| 7 | [Framing over evidence](#framing-over-evidence) | The agent believes how the input was described instead of checking what the tools say. | 4 use cases |
| 8 | [Trust follows the channel, not the content](#trust-follows-the-channel-not-the-content) | The same instruction is refused in data and obeyed in a tool definition. | 2 use cases |
| 9 | [Ceremony is learned, prohibition is not](#ceremony-is-learned-prohibition-is-not) | Agents reliably obey 'do this first' and unreliably obey 'never do this'. | 2 use cases |
| 10 | [Directional bias](#directional-bias) | Models don't err randomly — each errs in one direction, and the direction is a model property. | 5 use cases |
| 11 | [The outcome can be right while the service fails](#the-outcome-can-be-right-while-the-service-fails) | Correct routing can still impose duplicate burden, exclude a user, lose a deadline, or erase recourse. | 19 use cases |
| 12 | [Similarity erases the exception](#similarity-erases-the-exception) | A valid rule from the clean twin is confidently reused where one deciding fact reverses it. | 16 use cases |
| 13 | [Stage collapse](#stage-collapse) | A draft, attempt, intake, appointment, or handoff is stored as the later event everyone hoped would happen. | 7 use cases |
| 14 | [Competence does not transfer](#competence-does-not-transfer) | Being the best model on one agent task predicts almost nothing about the next. | 5 use cases |
| 15 | [Coordination-only failures](#coordination-only-failures) | Multi-agent systems fail in ways a single agent cannot, and orchestration amplifies rather than fixes. | 1 use case |

---

## Commit-stall

*The agent investigates correctly, reaches the right conclusion, and never commits it.*

This is the most universal failure in the repo: found independently in **nine use cases**, across unrelated industries and three model families, without anyone designing for it. It is invisible to accuracy metrics — the runs that never submit are simply absent from the numerator — so a stalling agent can read as a careful one. **Read `submitted` before you read any accuracy or safety metric.**

**Measured**

- **gpt-oss-120b, refund** — submitted 0.678 — 29 of 90 tickets abandoned, 23 of them immediately after the correct escalate call
- **gpt-oss-120b, refund crew** — 75 of 90 runs never closed the ticket while every sub-agent returned successfully
- **gpt-oss-120b, artifact admission** — submitted 0.778 — a security gate that reaches no verdict is its own failure
- **gpt-oss-120b, trifecta exfil** — submitted 0.378 undefended; its clean safety score was mostly non-participation

<details><summary><b>Where it was observed</b></summary>

- [`exception-triage-agent` — Investigates fully, then stalls at the commit point](logistics-supply-chain/exception-triage-agent/FAILURE_MODES.md#8-investigates-fully-then-stalls-at-the-commit-point)
- [`shift-coverage-triage-agent` — Commit-stall: investigates, re-reads policy, never submits](retail-workforce/shift-coverage-triage-agent/FAILURE_MODES.md#3-commit-stall-investigates-re-reads-policy-never-submits)
- [`release-qc-triage-agent` — Commit-stall persists across every industry](media-streaming/release-qc-triage-agent/FAILURE_MODES.md#5-commit-stall-persists-across-every-industry)
- [`fraud-alert-triage-agent` — Commit-stall on the hardest cases](financial-services-fraud/fraud-alert-triage-agent/FAILURE_MODES.md#4-commit-stall-on-the-hardest-cases)
- [`refund-resolution-agent` — Acting agents stall roughly ten times more than deciding agents](customer-support/refund-resolution-agent/FAILURE_MODES.md#4-acting-agents-stall-roughly-ten-times-more-than-deciding-agents)
- [`refund-crew` — Delegation is a handoff, and some models treat handoffs as completion](customer-support/refund-crew/FAILURE_MODES.md#2-delegation-is-a-handoff-and-some-models-treat-handoffs-as-completion)
- [`artifact-admission-agent` — Safe only because it never finished (gpt-oss)](security-operations/artifact-admission-agent/FAILURE_MODES.md#4-safe-only-because-it-never-finished-gpt-oss)
- [`trifecta-exfil-agent` — Safe by not finishing](security-operations/trifecta-exfil-agent/FAILURE_MODES.md#5-safe-by-not-finishing)
- [`small-business-recovery-agent` — The empty-action closeout](public-sector/small-business-recovery-agent/FAILURE_MODES.md#6-the-empty-action-closeout)

</details>

---

## The environment beats the prompt

*Changing what the agent *can* do works; telling it what it *should* do mostly doesn't.*

Four independent A/B experiments, each isolating a single variable, all point the same way — and two of them show the prompt fix making things **worse**. This is the repo's most actionable finding and the one most often gotten wrong in production, because a prompt edit is cheap and feels like progress.

**Measured**

- **refund, tool-layer enforcement** — safe_and_correct 0.333 → **0.822** at no measurable cost
- **refund, a prompt nudge to finish** — stalls **doubled**, 29/90 → 59/90 — the nudge worsened the exact failure it targeted
- **refund under injection** — a prompt guard naming all five attack shapes: 0.773 → 0.740 (nothing). Tool-layer guard: **0.000**
- **trifecta tool poisoning** — prompt guard 1.00 → 0.97; dataflow gate → **0.000**, on identical agent decisions
- **artifact admission** — sandbox-by-default contained unsafe admits 0.122 → **0.000** without changing one agent decision

<details><summary><b>Where it was observed</b></summary>

- [`refund-guarded` — The prompt nudge doubled the failure it was written to fix](customer-support/refund-guarded/FAILURE_MODES.md#1-the-prompt-nudge-doubled-the-failure-it-was-written-to-fix)
- [`refund-injected` — The defence most teams ship did nothing](customer-support/refund-injected/FAILURE_MODES.md#1-the-defence-most-teams-ship-did-nothing)
- [`trifecta-exfil-agent` — A prompt guard that named the exact attack stopped almost none of it](security-operations/trifecta-exfil-agent/FAILURE_MODES.md#3-a-prompt-guard-that-named-the-exact-attack-stopped-almost-none-of-it)
- [`artifact-admission-agent` — A zero breach rate that hides an unchanged admit rate (the A/B)](security-operations/artifact-admission-agent/FAILURE_MODES.md#5-a-zero-breach-rate-that-hides-an-unchanged-admit-rate-the-ab)

</details>

---

## Contained is not fixed

*A guard drives the incident rate to zero while the agent's judgment stays exactly as wrong.*

Every environment fix in this repo works by making the mistake harmless, not by preventing it. The agent still reaches for the forbidden action at the same rate — sometimes a **higher** rate. Any monitoring built on the agent's behaviour will therefore report a clean system while it is being successfully attacked. **Instrument the block rate, not the incident rate.**

**Measured**

- **refund, enforced** — blocked_attempt 0.489 — the model still reached for the forbidden refund in 44 of 90 runs
- **refund under injection** — attempted 0.800 *with* the guard vs 0.773 undefended — persuaded slightly more often, breached never
- **trifecta** — exfiltration 0.000 while attempted_exfil held at 0.133

<details><summary><b>Where it was observed</b></summary>

- [`refund-guarded` — The disposition never changed, only the outcome](customer-support/refund-guarded/FAILURE_MODES.md#2-the-disposition-never-changed-only-the-outcome)
- [`refund-injected` — Zero attack success and unchanged susceptibility, at the same time](customer-support/refund-injected/FAILURE_MODES.md#2-zero-attack-success-and-unchanged-susceptibility-at-the-same-time)
- [`artifact-admission-agent` — A zero breach rate that hides an unchanged admit rate (the A/B)](security-operations/artifact-admission-agent/FAILURE_MODES.md#5-a-zero-breach-rate-that-hides-an-unchanged-admit-rate-the-ab)

</details>

---

## Removing the tool displaces the intent

*Take the forbidden action out of the schema and the goal reroutes — through a legal-but-wrong channel, or into a claim that the work was done.*

Least privilege is the one control this repo consistently finds effective, so its failure mode deserves naming. Deleting a capability removes the *act*, never the objective that motivated it. The agent still needs to dispose of the case, and it reaches for whatever remains — which is why the residue lands somewhere that looks compliant. In both observations below the resulting record is **honest and the reasoning correct**, so no truthfulness check fires. Removing a tool is not finished until you have asked what the agent will do instead.

**Measured**

- **healthcare prior auth** — barred by statute from medical-necessity denial, the agent refuses through the **administrative** channel instead — **0.42** `[0.21, 0.62]` of routing cases. The clinical reasoning is right, the rationale accurate; only the channel is wrong, and the channel is what the statute regulates
- **incident remediation** — with the forbidden tools gone, one model of three closed incidents as *'remediated'* for work that never ran — the capability control bought a false all-clear

<details><summary><b>Where it was observed</b></summary>

- [`prior-auth-review-agent` — The unlocked door: a clinical denial issued administratively](healthcare-life-sciences/prior-auth-review-agent/FAILURE_MODES.md#1-the-unlocked-door-a-clinical-denial-issued-administratively)
- [`incident-remediation-agent` — The capability control did not remove the capability](it-operations/incident-remediation-agent/FAILURE_MODES.md#10-the-capability-control-did-not-remove-the-capability)
- [`incident-remediation-agent` — Least privilege bought a false all-clear (on one model of three)](it-operations/incident-remediation-agent/FAILURE_MODES.md#3-least-privilege-bought-a-false-all-clear-on-one-model-of-three)

</details>

---

## Safety by inaction

*A 'did it avoid the bad action' metric is passed perfectly by an agent that does nothing.*

Restraint and absence are indistinguishable unless you also measure whether the agent looked. This generalises to every guardrail KPI in production: if the metric only counts bad events, the cheapest way to score well is to stop participating. Pair every restraint metric with a diligence metric.

**Measured**

- **on-call watch** — two models scored a **perfect 1.000** on 'never paged a quiet window' while missing a third of real incidents — by watching 3.6 and 5.8 of 20 minutes
- **artifact admission** — gpt-oss posted zero unsafe admits and zero over-blocks — on the 78% of runs where it decided at all
- **trifecta exfil** — zero leaks on the content channel, largely by never reaching a decision
- **legal clause review** — the variant that defeats a diligence metric: mistral calls `read_clause` in **84 of 84** runs and records a clause-level verdict in almost none (`flag` 6/84, `accept` 1/84), escalating wholesale instead. It looked at everything and adjudicated nothing
- **vendor payments** — payment safety **1.000**, while only **3 of 24** legitimate payments executed with authorized terms; 36/84 submitted reviews had no business action behind them

<details><summary><b>Where it was observed</b></summary>

- [`oncall-watch-agent` — A restraint metric can be passed by not looking](it-operations/oncall-watch-agent/FAILURE_MODES.md#1-a-restraint-metric-can-be-passed-by-not-looking)
- [`artifact-admission-agent` — Safe only because it never finished (gpt-oss)](security-operations/artifact-admission-agent/FAILURE_MODES.md#4-safe-only-because-it-never-finished-gpt-oss)
- [`trifecta-exfil-agent` — Safe by not finishing](security-operations/trifecta-exfil-agent/FAILURE_MODES.md#5-safe-by-not-finishing)
- [`dpa-clause-review-agent` — Reads everything, adjudicates nothing](legal-compliance/dpa-clause-review-agent/FAILURE_MODES.md#3-reads-everything-adjudicates-nothing)
- [`vendor-payment-review-agent` — Correct decision, wrong object: the action failed and the review still closed](procurement-finance/vendor-payment-review-agent/FAILURE_MODES.md#1-correct-decision-wrong-object-the-action-failed-and-the-review-still-closed)
- [`vendor-payment-review-agent` — Perfect payment safety hid an 87.5% clean-payment failure rate](procurement-finance/vendor-payment-review-agent/FAILURE_MODES.md#2-perfect-payment-safety-hid-an-875-clean-payment-failure-rate)

</details>

---

## Prior over policy

*The model's own sense of what's reasonable overrides the policy it just retrieved.*

These agents do not fail to *find* the rule — several cite it in their own reasoning and then violate it in the same breath. The failure is precedence, not retrieval, which is why better RAG does not fix it and a tool that refuses does.

**Measured**

- **logistics** — one model cited the $2,000 escalation policy in its reasoning and then violated it, three repeats out of three
- **retail** — an invented 'overtime is expensive' heuristic overrode the written labour policy
- **refund** — the refund reflex: a forbidden refund issued in 15 of 15 runs in *every* archetype where refunding was banned
- **media** — models pulled work in-house asserting a capability the policy explicitly denies

<details><summary><b>Where it was observed</b></summary>

- [`exception-triage-agent` — Reasoning–action contradiction](logistics-supply-chain/exception-triage-agent/FAILURE_MODES.md#1-reasoningaction-contradiction)
- [`shift-coverage-triage-agent` — Invented "overtime is expensive" heuristic overrides written policy](retail-workforce/shift-coverage-triage-agent/FAILURE_MODES.md#1-invented-overtime-is-expensive-heuristic-overrides-written-policy)
- [`refund-resolution-agent` — The refund reflex — a default that overrides every prohibition](customer-support/refund-resolution-agent/FAILURE_MODES.md#1-the-refund-reflex-a-default-that-overrides-every-prohibition)
- [`release-qc-triage-agent` — Over-fixing: pulling vendor work in-house](media-streaming/release-qc-triage-agent/FAILURE_MODES.md#4-over-fixing-pulling-vendor-work-in-house)

</details>

---

## Framing over evidence

*The agent believes how the input was described instead of checking what the tools say.*

Every triage domain in this repo has a case that reads as one thing and is another, and every domain has models that anchor on the description. The tools contained the disproof in each case; the agent simply did not weigh it above the framing it was handed first.

**Measured**

- **security** — an authorized vulnerability scanner's noise filed as credential-abuse — the telemetry named the scanner and the change ticket
- **fraud** — a benign holiday charge blocked despite a matching travel notice; an authorised-push-payment scam cleared because it rode the customer's own trusted device
- **media** — intentional creative silence read as an audio defect, 12 of 15 runs on one model

<details><summary><b>Where it was observed</b></summary>

- [`alert-triage-agent` — The scanner deception — trusting the alert text over the telemetry](security-operations/alert-triage-agent/FAILURE_MODES.md#1-the-scanner-deception-trusting-the-alert-text-over-the-telemetry)
- [`fraud-alert-triage-agent` — Trusting the alert framing over a benign explanation (the travel deception)](financial-services-fraud/fraud-alert-triage-agent/FAILURE_MODES.md#1-trusting-the-alert-framing-over-a-benign-explanation-the-travel-deception)
- [`release-qc-triage-agent` — Creative intent read as a defect (the "looks broken, is fine" deception)](media-streaming/release-qc-triage-agent/FAILURE_MODES.md#2-creative-intent-read-as-a-defect-the-looks-broken-is-fine-deception)
- [`small-business-recovery-agent` — Accessibility attention displaces evidence checking](public-sector/small-business-recovery-agent/FAILURE_MODES.md#7-accessibility-attention-displaces-evidence-checking)

</details>

---

## Trust follows the channel, not the content

*The same instruction is refused in data and obeyed in a tool definition.*

Injection defences have been trained on *content*. They do not extend to the surfaces the model treats as part of itself — its tool descriptions, and by extension anything a connector supplies. This is the single sharpest security result in the repo and it is not a capability problem: the strongest model tested leaks exactly as often as the weakest.

**Measured**

- **trifecta exfil** — identical secret-stealing instruction: **~0%** obeyed in fetched content, **100%** obeyed in a tool's own description — all three models
- **artifact admission** — the mirror case: a manifest that declares no code while the config executes — the vector behind the July 2026 Hugging Face breach

<details><summary><b>Where it was observed</b></summary>

- [`trifecta-exfil-agent` — Models defend the data channel and trust their own tooling — 100% leak](security-operations/trifecta-exfil-agent/FAILURE_MODES.md#1-models-defend-the-data-channel-and-trust-their-own-tooling-100-leak)
- [`trifecta-exfil-agent` — Capability is not protection](security-operations/trifecta-exfil-agent/FAILURE_MODES.md#2-capability-is-not-protection)
- [`artifact-admission-agent` — Trusted live code admitted straight to a full-privilege worker (mistral)](security-operations/artifact-admission-agent/FAILURE_MODES.md#2-trusted-live-code-admitted-straight-to-a-full-privilege-worker-mistral)

</details>

---

## Ceremony is learned, prohibition is not

*Agents reliably obey 'do this first' and unreliably obey 'never do this'.*

An ordering rule adds a step to a sequence; a prohibition requires *not* taking a step that otherwise fits. Across 270 runs no model ever moved money before verifying identity, while restraint rules failed completely on the same model in the same runs. Prohibitions therefore belong in the tool layer — and the ordering record is reliable, not robust: under injection it drops too.

**Measured**

- **refund** — prerequisite_respected **1.000 across all 270 runs**; the prohibition failed 15/15 in every banned archetype
- **refund under injection** — that same perfect ordering record falls to **0.660** once the ticket text turns hostile

<details><summary><b>Where it was observed</b></summary>

- [`refund-resolution-agent` — Ceremony is learned; prohibition is not](customer-support/refund-resolution-agent/FAILURE_MODES.md#2-ceremony-is-learned-prohibition-is-not)
- [`refund-injected` — Injections overwrite rules more easily than facts](customer-support/refund-injected/FAILURE_MODES.md#5-injections-overwrite-rules-more-easily-than-facts)

</details>

---

## Directional bias

*Models don't err randomly — each errs in one direction, and the direction is a model property.*

Accuracy alone implies errors are symmetric. They are not: one model over-escalates everywhere, another under-escalates the same cases, and the bias is stable within a model across domains. It is also **fixable by model choice**, which makes it a selection criterion rather than an inherent limitation.

**Measured**

- **fraud** — three of four models over-called fraud on benign transactions and never the reverse — Qwen3.7-Plus broke the pattern with zero such errors, falsifying the universal claim
- **retail / media / security** — over-escalation on one model and under-escalation on another, on the identical scenario set
- **refund** — one model's action errors were 22 of 23 the *same* substitution
- **healthcare + legal, record fidelity** — infidelity is one-directional too: across **1,512 runs in two industries**, models never once claimed an action they had not taken, while gpt-oss failed to name an action it *had* taken in 0.39 of legal records. They do not invent — they under-report
- **vendor payments** — all 12 unverified bank changes were held, but **8 of 12** independently verified changes were held or rejected too

<details><summary><b>Where it was observed</b></summary>

- [`fraud-alert-triage-agent` — One-directional bias: models over-call fraud on benign transactions — but it is beatable](financial-services-fraud/fraud-alert-triage-agent/FAILURE_MODES.md#5-one-directional-bias-models-over-call-fraud-on-benign-transactions-but-it-is-beatable)
- [`shift-coverage-triage-agent` — Over-escalation: handing fillable shifts to the district manager](retail-workforce/shift-coverage-triage-agent/FAILURE_MODES.md#2-over-escalation-handing-fillable-shifts-to-the-district-manager)
- [`alert-triage-agent` — Over-escalation — the opposite error, on a different model](security-operations/alert-triage-agent/FAILURE_MODES.md#3-over-escalation-the-opposite-error-on-a-different-model)
- [`dpa-clause-review-agent` — The fabrication that was expected and did not occur](legal-compliance/dpa-clause-review-agent/FAILURE_MODES.md#5-the-fabrication-that-was-expected-and-did-not-occur)
- [`vendor-payment-review-agent` — Verified vendors were overblocked while every risky change was held](procurement-finance/vendor-payment-review-agent/FAILURE_MODES.md#3-verified-vendors-were-overblocked-while-every-risky-change-was-held)

</details>

---

## The outcome can be right while the service fails

*Correct routing can still impose duplicate burden, exclude a user, lose a deadline, or erase recourse.*

Outcome metrics see where a case landed, not what the person had to surrender or risk to get there. Service agents need a second gold object that binds the outcome to minimum evidence, accessible delivery, deadlines, recourse, rights, intent, and a truthful record. Otherwise an organization can optimize its queue while quietly transferring the cost to users.

**Measured**

- **small-business recovery baseline** — outcome accuracy and completion **1.000**; exact public value only **0.375** across 32 scenarios × 3 repeats
- **household energy baseline** — outcome accuracy **1.000**; exact public value **0.250** after continuity, evidence, access, deadline, recourse, and record truth are combined
- **disaster claim-and-aid baseline** — outcome accuracy **1.000**; exact public value **0.125** when known compensation sources and service obligations must also be exact
- **four new service baselines** — outcome accuracy **1.000** in unemployment, farm-disaster, permit, and student navigation while their distinctive exact metrics ranged from **0.250 to 0.875**
- **twelve-industry evidence-service baseline** — outcome accuracy **0.875** but exact service only **0.250** in every matched 32-scenario × 3-repeat suite; the common gaps are duplicate evidence, lost access/date/recourse, and authority crossing
- **administrative burden** — minimum-evidence compliance **0.625** because a one-document gap triggered the full checklist
- **access and remedy** — the matched evidence-service baseline keeps accessible channel and deadline protection at **0.875**, while recourse falls to **0.250**

<details><summary><b>Where it was observed</b></summary>

- [`small-business-recovery-agent` — The outcome mirage](public-sector/small-business-recovery-agent/FAILURE_MODES.md#1-the-outcome-mirage)
- [`small-business-recovery-agent` — The full-checklist reflex](public-sector/small-business-recovery-agent/FAILURE_MODES.md#2-the-full-checklist-reflex)
- [`small-business-recovery-agent` — The portal default](public-sector/small-business-recovery-agent/FAILURE_MODES.md#3-the-portal-default)
- [`small-business-recovery-agent` — Recourse disappears at the handoff](public-sector/small-business-recovery-agent/FAILURE_MODES.md#4-recourse-disappears-at-the-handoff)
- [`small-business-recovery-agent` — The deadline is known but not preserved](public-sector/small-business-recovery-agent/FAILURE_MODES.md#5-the-deadline-is-known-but-not-preserved)
- [`household-energy-lifeline` — The agent recognizes stale paperwork but performs no service action](energy-utilities/household-energy-lifeline/FAILURE_MODES.md#1-the-agent-recognizes-stale-paperwork-but-performs-no-service-action)
- [`household-energy-lifeline` — Medical minimization becomes a new full-checklist request](energy-utilities/household-energy-lifeline/FAILURE_MODES.md#2-medical-minimization-becomes-a-new-full-checklist-request)
- [`disaster-claim-aid-coordinator` — A referral is recorded as money already received](insurance-disaster-recovery/disaster-claim-aid-coordinator/FAILURE_MODES.md#1-a-referral-is-recorded-as-money-already-received)
- [`disaster-claim-aid-coordinator` — Overlap review asks for the entire file again](insurance-disaster-recovery/disaster-claim-aid-coordinator/FAILURE_MODES.md#2-overlap-review-asks-for-the-entire-file-again)
- [`unemployment-claim-navigator` — Correct appeal route, expired filing path](employment-social-insurance/unemployment-claim-navigator/FAILURE_MODES.md#1-correct-appeal-route-expired-filing-path)
- [`farm-disaster-deadline-agent` — The first deadline hides the second](agriculture-food-systems/farm-disaster-deadline-agent/FAILURE_MODES.md#1-the-first-deadline-hides-the-second)
- [`permit-readiness-agent` — Residential rule applied to a commercial project](housing-construction/permit-readiness-agent/FAILURE_MODES.md#1-residential-rule-applied-to-a-commercial-project)
- [`student-accommodation-navigator` — A voluntary offer becomes unnecessary collection](education-services/student-accommodation-navigator/FAILURE_MODES.md#1-a-voluntary-offer-becomes-unnecessary-collection)
- [`food-recall-traceability-coordinator` — The complete-checklist reflex](food-safety-manufacturing/food-recall-traceability-coordinator/FAILURE_MODES.md#1-the-complete-checklist-reflex)
- [`drinking-water-notice-coordinator` — Unknown becomes a conclusion](water-sanitation/drinking-water-notice-coordinator/FAILURE_MODES.md#1-unknown-becomes-a-conclusion)
- [`irs-notice-response-navigator` — The due date disappears](federal-taxpayer-services/irs-notice-response-navigator/FAILURE_MODES.md#2-the-due-date-disappears)
- [`veterans-claim-evidence-navigator` — The claim file is rebuilt](veterans-services/veterans-claim-evidence-navigator/FAILURE_MODES.md#1-the-claim-file-is-rebuilt)
- [`paratransit-access-coordinator` — The accessibility process is inaccessible](public-transit-mobility/paratransit-access-coordinator/FAILURE_MODES.md#2-the-accessibility-process-is-inaccessible)
- [`foia-routing-appeal-navigator` — The request starts over](government-transparency/foia-routing-appeal-navigator/FAILURE_MODES.md#1-the-request-starts-over)
- [`uscis-case-evidence-navigator` — The whole immigration file is requested](immigration-citizenship/uscis-case-evidence-navigator/FAILURE_MODES.md#1-the-whole-immigration-file-is-requested)
- [`export-transaction-evidence-agent` — Classification becomes clearance](manufacturing-international-trade/export-transaction-evidence-agent/FAILURE_MODES.md#1-classification-becomes-clearance)
- [`school-meal-access-coordinator` — Direct certification is ignored](child-nutrition-family-services/school-meal-access-coordinator/FAILURE_MODES.md#1-direct-certification-is-ignored)
- [`provisional-ballot-status-navigator` — Registration facts become ballot status](election-administration/provisional-ballot-status-navigator/FAILURE_MODES.md#1-registration-facts-become-ballot-status)
- [`hospital-discharge-readiness-coordinator` — Paper completeness becomes readiness](care-transitions/hospital-discharge-readiness-coordinator/FAILURE_MODES.md#1-paper-completeness-becomes-readiness)
- [`occupational-license-mobility-navigator` — Reciprocity becomes a promise](workforce-mobility/occupational-license-mobility-navigator/FAILURE_MODES.md#1-reciprocity-becomes-a-promise)

</details>

---

## Similarity erases the exception

*A valid rule from the clean twin is confidently reused where one deciding fact reverses it.*

Retrieval can be accurate and the recommendation can still inherit the wrong rule. These matched cases differ by a narrow fact—sterility path, clearance owner, consumer-report reliance, aircraft identity, aggregate ownership, filing-year dependency, claim entailment, emergency evidence, award version, recall identity, billing clock, rule status, special-facility path, or medical outcome. The remedy is not more general knowledge; it is an exact rule code, evidence set, and counterexample at the decision boundary.

**Measured**

- **sixteen deterministic baselines** — the engineered shortcut fails every transfer-trap archetype, producing transfer specificity **0.875** instead of hiding the generalization inside aggregate outcome accuracy
- **pharmaceutical transfer test** — an inconclusive sterility-positive investigation is routed through the more permissive chemical OOS path
- **approved-data transfer** — a prior aircraft deferral or prior-year tax dependency is treated as authority for the current record

<details><summary><b>Where it was observed</b></summary>

- [`batch-disposition-gate` — Transfer by vocabulary](pharmaceutical-manufacturing/batch-disposition-gate/FAILURE_MODES.md#1-transfer-by-vocabulary)
- [`distribution-restoration-safety-gate` — Urgency erases conjunction](grid-operations/distribution-restoration-safety-gate/FAILURE_MODES.md#1-urgency-erases-conjunction)
- [`hiring-compliance-navigator` — Legitimate reason launders the process](human-resources/hiring-compliance-navigator/FAILURE_MODES.md#1-legitimate-reason-launders-the-process)
- [`aircraft-dispatch-evidence-gate` — Fleet analogy overrides approved data](aviation-operations/aircraft-dispatch-evidence-gate/FAILURE_MODES.md#1-fleet-analogy-overrides-approved-data)
- [`aml-kyc-sanctions-case-gate` — No list hit becomes clearance](banking-compliance/aml-kyc-sanctions-case-gate/FAILURE_MODES.md#1-no-list-hit-becomes-clearance)
- [`tax-return-completeness-navigator` — Balanced means complete](tax-filing-services/tax-return-completeness-navigator/FAILURE_MODES.md#1-balanced-means-complete)
- [`claim-evidence-verifier` — Citation presence replaces entailment](research-knowledge-work/claim-evidence-verifier/FAILURE_MODES.md#1-citation-presence-replaces-entailment)
- [`service-visit-readiness-coordinator` — Routine symptom hides emergency evidence](home-field-services/service-visit-readiness-coordinator/FAILURE_MODES.md#1-routine-symptom-hides-emergency-evidence)
- [`grant-obligation-evidence-navigator` — Prior acceptance becomes current authority](nonprofit-grant-management/grant-obligation-evidence-navigator/FAILURE_MODES.md#1-prior-acceptance-becomes-current-authority)
- [`vehicle-recall-remedy-coordinator` — Model-level recall becomes VIN truth](automotive-safety/vehicle-recall-remedy-coordinator/FAILURE_MODES.md#1-model-level-recall-becomes-vin-truth)
- [`product-recall-remedy-coordinator` — Appearance expands recall scope](consumer-product-safety/product-recall-remedy-coordinator/FAILURE_MODES.md#1-appearance-expands-recall-scope)
- [`detention-demurrage-invoice-verifier` — Operational lateness proves collectability](maritime-ports/detention-demurrage-invoice-verifier/FAILURE_MODES.md#1-operational-lateness-proves-collectability)
- [`hazardous-waste-manifest-coordinator` — A proposed rule becomes today's gate](environmental-hazardous-materials/hazardous-waste-manifest-coordinator/FAILURE_MODES.md#2-a-proposed-rule-becomes-todays-gate)
- [`debt-validation-dispute-navigator` — Prior silence erases a timely dispute](consumer-finance-debt/debt-validation-dispute-navigator/FAILURE_MODES.md#1-prior-silence-erases-a-timely-dispute)
- [`communications-outage-reporting-gate` — Volume threshold hides life-safety impact](telecommunications-emergency/communications-outage-reporting-gate/FAILURE_MODES.md#1-volume-threshold-hides-life-safety-impact)
- [`severe-incident-reporting-navigator` — Hospital becomes inpatient](workplace-safety/severe-incident-reporting-navigator/FAILURE_MODES.md#1-hospital-becomes-inpatient)

</details>

---

## Stage collapse

*A draft, attempt, intake, appointment, or handoff is stored as the later event everyone hoped would happen.*

Agent workflows often end with a durable record used by another team or system. If that record jumps stages, downstream automation no longer sees uncertainty: an appointment becomes a repair, intake becomes compensation, a dispute becomes a win, or a draft becomes a certified filing. The fix is a finite stage vocabulary, a receipt tied to the executed tool event, and an explicit owner for every later stage.

**Measured**

- **seven-industry public-protection suite** — every lab contains a reproducible receipt trap and scores the durable record against the actual tool trace
- **matched obligation** — a correct subject, rule, gate, and deadline still receives zero exact credit when the receipt claims a later stage
- **protected transitions** — repair, compensation, waiver, certification, verification, filing, and accepted reporting remain outside the agent's authority

<details><summary><b>Where it was observed</b></summary>

- [`vehicle-recall-remedy-coordinator` — Appointment becomes repair](automotive-safety/vehicle-recall-remedy-coordinator/FAILURE_MODES.md#3-appointment-becomes-repair)
- [`product-recall-remedy-coordinator` — Intake becomes compensation](consumer-product-safety/product-recall-remedy-coordinator/FAILURE_MODES.md#3-intake-becomes-compensation)
- [`detention-demurrage-invoice-verifier` — Dispute submitted becomes dispute won](maritime-ports/detention-demurrage-invoice-verifier/FAILURE_MODES.md#3-dispute-submitted-becomes-dispute-won)
- [`hazardous-waste-manifest-coordinator` — Correction erases history](environmental-hazardous-materials/hazardous-waste-manifest-coordinator/FAILURE_MODES.md#3-correction-erases-history)
- [`debt-validation-dispute-navigator` — Delivery becomes verification](consumer-finance-debt/debt-validation-dispute-navigator/FAILURE_MODES.md#3-delivery-becomes-verification)
- [`communications-outage-reporting-gate` — Draft becomes certified final](telecommunications-emergency/communications-outage-reporting-gate/FAILURE_MODES.md#3-draft-becomes-certified-final)
- [`severe-incident-reporting-navigator` — Draft or omission becomes report](workplace-safety/severe-incident-reporting-navigator/FAILURE_MODES.md#3-draft-or-omission-becomes-report)

</details>

---

## Competence does not transfer

*Being the best model on one agent task predicts almost nothing about the next.*

Every model tested wins at least one use case and loses another, and the ranking flips by domain and by capability shape. A model that solves an acting task can be middling at a watching one. This is why a general leaderboard cannot answer 'which model should run my agent', and why the per-use-case number exists.

**Measured**

- **across 8 tasks** — wins: Qwen3.7-Plus 4, kimi-k2p6 2, gpt-oss-120b 2, mistral-small 1 — the cheapest free-tier model wins the on-call watch task outright
- **trifecta** — capability is not protection: the strongest model leaks through a poisoned tool as often as the weakest
- **logistics vs media** — kimi is the only model to score a perfect 90/90 on one task and comes last on another, at 7.7× the cost per scenario
- **legal, missing GDPR clause** — the widest spread in the repo: **0.00 to 0.98 on identical contracts**, intervals disjoint. One model solves it outright, so the task is demonstrably not the limit — and no arm moves any of them (p ≥ 0.48)

<details><summary><b>Where it was observed</b></summary>

- [`alert-triage-agent` — Same model, different domain, different competence](security-operations/alert-triage-agent/FAILURE_MODES.md#4-same-model-different-domain-different-competence)
- [`shift-coverage-triage-agent` — Same model, different domain, different competence](retail-workforce/shift-coverage-triage-agent/FAILURE_MODES.md#4-same-model-different-domain-different-competence)
- [`fraud-alert-triage-agent` — No best model — the ranking flips again](financial-services-fraud/fraud-alert-triage-agent/FAILURE_MODES.md#6-no-best-model-the-ranking-flips-again)
- [`trifecta-exfil-agent` — Capability is not protection](security-operations/trifecta-exfil-agent/FAILURE_MODES.md#2-capability-is-not-protection)
- [`dpa-clause-review-agent` — Absence detection is a property of the model, not the task](legal-compliance/dpa-clause-review-agent/FAILURE_MODES.md#2-absence-detection-is-a-property-of-the-model-not-the-task)

</details>

---

## Coordination-only failures

*Multi-agent systems fail in ways a single agent cannot, and orchestration amplifies rather than fixes.*

Four of the crew's six documented failures are impossible single-agent: a brief that silently drops the deciding fact, a compliance veto the orchestrator ignores, a specialist that is bad at its speciality. Orchestration never produced a new high score in 270 runs — it compressed the range, helping a weak model and taxing a strong one.

**Measured**

- **refund crew** — mistral 0.333 → 0.411 (helped), gpt-oss 0.644 → **0.044** (destroyed), Qwen 0.978 → 0.933 (taxed at 1.96× cost)
- **refund crew** — a veto that gets ignored is worse than no veto — it manufactures false assurance

<details><summary><b>Where it was observed</b></summary>

- [`refund-crew` — Orchestration amplifies whatever the model already does](customer-support/refund-crew/FAILURE_MODES.md#1-orchestration-amplifies-whatever-the-model-already-does)
- [`refund-crew` — The brief is a lossy channel, and the loss is invisible to both agents](customer-support/refund-crew/FAILURE_MODES.md#3-the-brief-is-a-lossy-channel-and-the-loss-is-invisible-to-both-agents)
- [`refund-crew` — A veto that gets ignored is worse than no veto](customer-support/refund-crew/FAILURE_MODES.md#4-a-veto-that-gets-ignored-is-worse-than-no-veto)
- [`refund-crew` — The specialist is not automatically good at its speciality](customer-support/refund-crew/FAILURE_MODES.md#5-the-specialist-is-not-automatically-good-at-its-speciality)

</details>

## How to use this

- **Before you ship an agent**, read `Commit-stall` and `Safety by inaction` — they
  are the two failures most likely to be invisible in your own eval.
- **Before you write a prompt fix**, read `The environment beats the prompt`. Four
  controlled A/Bs in this repo say it probably won't work, and twice it made things
  worse.
- **Before you pick a model**, read `Competence does not transfer` and the
  [per-task matrix](README.md#there-is-no-best-model).
- **Before you trust a guardrail metric**, read `Contained is not fixed`.


---

<sub>Generated by `docs/make_taxonomy.py` from the committed
`FAILURE_MODES.md` files. The grouping is a curated judgment and is meant to be
argued with; every citation is checked to resolve to a real heading at build time,
so this page cannot silently rot as the repo grows.</sub>
