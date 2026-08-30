# Real-world use-case radar

This is the public backlog for problems worth turning into verified agent evaluations. It
exists to answer two questions clearly:

1. **What would genuinely help a person or operating team?**
2. **Can the right behavior be scored exactly without exposing private data?**

The radar is intentionally not a list of fashionable demos. A candidate rises when it has
a clear beneficiary, an owned decision, a costly failure, programmatic ground truth, and a
safe synthetic world. [Request a missing workflow](https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=use-case-request.yml)
even if you do not know how to implement it.

## Why these areas

Current usage evidence points beyond coding demos toward operational work:

- OpenAI reports customer service and content generation at roughly 20% of API activity,
  with agentic workflow automation among the leading enterprise API use cases.
- Anthropic's Economic Index finds substantial usage in office/administrative, education,
  business/financial, and life-science tasks; business API use is predominantly automation.
- OpenAI names procurement, customer support, revenue operations, financial forecasting,
  and regulatory workflows as production-agent targets.
- The FBI's 2025 report gives the consequence a number: Business Email Compromise produced
  24,768 complaints and $3.046B in reported losses.

Sources: [OpenAI enterprise AI report](https://openai.com/business/guides-and-resources/the-state-of-enterprise-ai-2025-report/),
[Anthropic Economic Index](https://www.anthropic.com/research/the-anthropic-economic-index),
[Anthropic enterprise adoption report](https://www.anthropic.com/research/anthropic-economic-index-september-2025-report),
[OpenAI Frontier use cases](https://openai.com/business/frontier/), and
[FBI IC3 2025 report](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf).

These sources identify demand, not ground truth. Each lab still needs a domain owner to
define the actual policy and decide which decisions must remain human.

## Cross-organization evidence operations — shipped

The repository now covers the lifecycle around the 71 domain labs, not only the labs themselves:

| Operational gap | Shipped contribution | Honest boundary |
|---|---|---|
| A candidate changes but its old benchmark is rerun indiscriminately | **[Agent Release Gate](agent-release-gate/)** captures exact components, maps the diff to impacted suites, blocks missing coverage, and emits a deterministic pack plus experimental OSCAL Assessment Results | `release_ready` is not deployment authority, certification, production safety, or an ATO |
| Outside teams cannot test a claim without receiving the answers | **[Fork-to-Reproduce](reproduction-challenges/)** opens three six-task challenges with hidden-oracle commitments and attested submission bytes | Cryptography binds bytes; human review determines result and independence |
| Public agent-security lessons remain prose instead of regressions | **[Agent Incident Exchange](agent-incident-exchange/)** binds safe incident abstractions to clean-twin artifacts and exports SARIF, OpenVEX, and experimental CSAF/OCSF bridges | No active-incident intake, attribution, exploit content, regulator feed, or field-effectiveness claim |
| Policy-dependent tests silently age | **[Policy Freshness Radar](policy-freshness/)** watches nine allowlisted official sources and maps a byte or visible-text change to artifact owners | It detects content and review dates; it never interprets policy or automatically changes a test |

This creates a concrete handoff for organizations, government teams, cybersecurity partners, and
frontier labs: test a release, expose the remaining boundary, reproduce it outside the authoring
workflow, safely exchange the regression, and reopen review when an official source changes.

## Federal Mission Assurance release — shipped

Public teams can now turn an AI proposal into an inspectable, non-certifying evidence
handoff before procurement or deployment authority is exercised:

| Release | What it gives users | Trust boundary |
|---|---|---|
| **[Federal Mission Studio](https://immu4989.github.io/awesome-agentic-usecases/#federal-mission)** | A browser-local intake, 17-practice OMB/NIST/GAO crosswalk, visible gaps, and a hashed 12-file assurance pack | Zero uploads; browser-entered plans are never labeled as evidence |
| **[Federal Mission Assurance Profile](federal-mission-assurance/)** | An open JSON Schema, dated source ledger, worked acquisition profile, validator, packager, verifier, and semantic diff | Not an ATO, FedRAMP authorization, FISMA determination, certification, legal conclusion, or approval |
| **[Federal AI Acquisition Performance Gate](federal-ai-acquisition/acquisition-performance-gate/)** | A 32-scenario benchmark for intended-environment tests, data rights, training-use conflicts, portability, pricing, monitoring, and award authority | The agent may assemble and test evidence; accountable officials rank, select, accept risk, obligate funds, and award |
| **[Federal AI Lessons Exchange](https://immu4989.github.io/awesome-agentic-usecases/#lessons-exchange)** | Searchable success, change, and stop closeouts with bounded practices, non-transfer conditions, privacy preflight, policy drift, and deterministic manifests | Public synthetic memory—not vendor ranking, award recommendation, certification, universal best practice, or permission to disclose |

The profile is designed as a versioned interoperability layer, not a static checklist.
Teams can generate the same pack in the public site or command line, verify its byte-level
manifest, and review a semantic profile diff without sending mission information to this
repository. The [dated research ledger](docs/FEDERAL_MISSION_RESEARCH_NOTES.md) records the
scope decisions and primary-source checks behind the map.

The [Federal Pilot Kit](federal-pilot-kit/) now closes the loop: a seven-file closeout turns
the assessment into a signed-scope lesson while retaining canonical evidence hashes instead of
republishing source records. Four public synthetic lessons demonstrate succeeded, changed, and
stopped outcomes so teams can learn from a stop—not quietly delete it.

## Committed industry expansion queue

This is the repository's recorded build order. Research may refine a lab's synthetic
policy, but new ideas do not silently displace an earlier commitment.

| Order | New industry | Flagship lab | Status | Distinctive proof |
|---:|---|---|---|---|
| 1 | Energy & Utilities | **[Household Energy Lifeline](energy-utilities/household-energy-lifeline/)** | **Shipped** | Preserve essential-service options, minimum evidence, accessibility, deadlines, recourse, and truthful completion together |
| 2 | Insurance & Disaster Recovery | **[Disaster Claim and Aid Coordinator](insurance-disaster-recovery/disaster-claim-aid-coordinator/)** | **Shipped** | Coordinate insurer and public-aid paths without double-counting compensation or deciding entitlement |
| 3 | Employment & Social Insurance | **[Unemployment Claim Navigator](employment-social-insurance/unemployment-claim-navigator/)** | **Shipped** | Explain status and protect appeal and weekly-certification paths without adjudicating eligibility or identity exceptions |
| 4 | Agriculture & Food Systems | **[Farm Disaster Deadline Agent](agriculture-food-systems/farm-disaster-deadline-agent/)** | **Shipped** | Preserve the exact set of program-specific notice windows while reusing held farm records and never inventing an award |
| 5 | Housing & Construction | **[Permit Readiness Agent](housing-construction/permit-readiness-agent/)** | **Shipped** | Bind the packet to the exact jurisdiction and project rule without claiming the permit will be approved |
| 6 | Education Services | **[Student Accommodation Navigator](education-services/student-accommodation-navigator/)** | **Shipped · domain review required** | Minimize sensitive evidence and preserve a timely, accessible human accommodation decision |

### Trust and access release wave

| Order | New industry | Flagship lab | Status | Distinctive proof |
|---:|---|---|---|---|
| 1 | Identity & Access | **[Account Recovery Assurance Agent](identity-access/account-recovery-assurance-agent/)** | **Shipped · security review required** | Match recovery to account assurance while containing takeover, minimizing PII, and notifying the subscriber |
| 2 | Accessibility & Digital Services | **[Accessibility Remediation Verifier](accessibility-digital-services/accessibility-remediation-verifier/)** | **Shipped · affected-user review required** | Join scans, manual paths, source, deployment, and post-fix tests without turning bounded evidence into conformance |
| 3 | Privacy & Data Governance | **[Privacy Rights Orchestrator](privacy-data-governance/privacy-rights-orchestrator/)** | **Shipped · counsel review required** | Cover the exact data-system set while minimizing verification burden, preserving clocks, and refusing false completion |

### Decision-gate industry wave — shipped

Six requested industries now share one [Decision Gate Contract](DECISION_GATE_CONTRACT.md)
and matched [cross-industry report](DECISION_GATE_REPORT.md). Each lab preserves the named
human authority and tests a different rule-transfer failure.

| Industry | Flagship lab | Distinctive proof | Review required |
|---|---|---|---|
| Pharmaceutical Manufacturing | **[Batch Disposition Gate](pharmaceutical-manufacturing/batch-disposition-gate/)** | Chemical OOS discretion does not transfer to an inconclusive sterility-positive investigation | Quality/GMP owner |
| Grid Operations | **[Distribution Restoration Safety Gate](grid-operations/distribution-restoration-safety-gate/)** | Every re-energization conjunct and clearance owner survives outage urgency | Qualified utility safety owner |
| Human Resources & Hiring | **[Hiring Compliance Navigator](human-resources/hiring-compliance-navigator/)** | AEDT and consumer-report procedures remain distinct from the selection reason | Employment counsel + hiring owner |
| Aviation Operations | **[Aircraft Dispatch Evidence Gate](aviation-operations/aircraft-dispatch-evidence-gate/)** | Only aircraft/operator-specific approved MEL evidence reaches dispatch review | Certificated operator, dispatcher + PIC |
| Banking Compliance | **[AML, KYC & Sanctions Case Gate](banking-compliance/aml-kyc-sanctions-case-gate/)** | CIP, aggregate ownership, SAR basis/clock, and SAR secrecy do not collapse into one alert | BSA/AML and sanctions officers |
| Tax Filing Services | **[Tax Return Completeness Navigator](tax-filing-services/tax-return-completeness-navigator/)** | Filing-year dependencies and authorization are detected without signing or transmission | Tax professional |

The dated [research notes](docs/DECISION_GATE_RESEARCH_NOTES.md) record the primary anchors
and three premise corrections made before implementation, including that a draft EU GMP
Annex 22 was not treated as an operative final annex.

### Rights Continuity wave — shipped

Three person-centered services now share the
[Rights Continuity Contract](RIGHTS_CONTINUITY_CONTRACT.md) and matched
[real-model report](RIGHTS_CONTINUITY_REPORT.md). Each case keeps primary and companion
rights, evidence burden, accessible channels, recourse, protected authority, and receipts
independently true.

| Industry | Flagship lab | Distinctive proof | Review required |
|---|---|---|---|
| Medicaid & CHIP Coverage Continuity | **[Renewal Continuity Navigator](medicaid-chip/renewal-continuity-navigator/)** | Reliable agency data is used before a form; only unresolved evidence is requested | State eligibility/program owner and beneficiary advocates |
| Health Insurance Appeals | **[Denial & Appeal Rights Navigator](health-insurance-appeals/denial-appeal-rights-navigator/)** | Urgent, pre-service, post-service, internal, and external paths remain distinct | Plan, clinician, consumer-assistance, and legal owners |
| Social Security Disability | **[Cessation & Benefit Continuation](social-security-disability/cessation-benefit-continuation-navigator/)** | The 60-day appeal and shorter benefit-continuation election remain separate | SSA program owner and claimant representatives |

### Critical Event Fan-Out wave — shipped

Three critical systems now share the
[Critical Event Fan-Out Contract](CRITICAL_EVENT_FANOUT_CONTRACT.md) and matched
[real-model report](CRITICAL_EVENT_FANOUT_REPORT.md). A successful response or initial
notification never closes another live recipient, clock, update, follow-up, or receipt.

| Industry | Flagship lab | Distinctive proof | Review required |
|---|---|---|---|
| Pipeline Safety | **[Incident Notification Coordinator](pipeline-safety/incident-notification-coordinator/)** | Emergency response, one-hour NRC path, 48-hour update, and receipts remain separate | Qualified operator, emergency, and regulatory owners |
| Health Data Privacy | **[HIPAA Breach Notification Graph](health-data-privacy/hipaa-breach-notification-graph/)** | Actor, population, geography, contact state, people, HHS, and media shape the recipient graph | Privacy officer, counsel, affected-person review |
| Clinical Trial Safety | **[IND Safety Reporting Coordinator](clinical-trial-safety/ind-safety-reporting-coordinator/)** | Seriousness, expectedness, suspected relationship, seven-/15-day routes, and follow-up stay distinct | Sponsor medical, investigator, IRB, and regulatory owners |

The [dated research ledger](docs/NEXT_IMPACT_RESEARCH_NOTES.md) records official sources
and eight premise corrections. Both contracts also ship vendor-neutral JSON Schemas and
worked examples for teams that want the data model without this repository's harness.

The first lab also extends the [Public Value Contract](PUBLIC_VALUE_CONTRACT.md) with an
optional, exact **essential-service continuity** obligation. That reusable specialty is
intended for energy, water, communications, housing, healthcare access, and other services
where a correct referral can still arrive too late to prevent immediate harm.

## Shipped now

| People served | Verified workflow | Real failure the lab exposes |
|---|---|---|
| AP teams, small businesses, and legitimate suppliers | [Vendor Payment Review](procurement-finance/vendor-payment-review-agent/) | Invoice reconciliation succeeds, but money is sent to an email-only bank change |
| Support customers | [Refund Resolution](customer-support/refund-resolution-agent/) | Correct outcome through an unsafe or unverified action path |
| On-call engineers and affected users | [On-Call Watch](it-operations/oncall-watch-agent/) | A “quiet” agent stops observing before the outage becomes clear |
| Patients and utilization-review teams | [Prior Auth Review](healthcare-life-sciences/prior-auth-review-agent/) | A constrained review denies through the wrong channel or creates an unfaithful record |
| Security teams and downstream users | [Trifecta Exfil](security-operations/trifecta-exfil-agent/) | Untrusted instructions move secrets through a real egress tool |
| Small-business owners, workers, and service teams | [Small Business Recovery](public-sector/small-business-recovery-agent/) | Correct outcome hides duplicate evidence, inaccessible delivery, lost deadlines, or missing recourse |
| Households facing loss of essential energy service | [Household Energy Lifeline](energy-utilities/household-energy-lifeline/) | Correct emergency routing omits continuity, repeats evidence, or overstates what was approved |
| Disaster survivors moving across insurers and aid programs | [Disaster Claim and Aid Coordinator](insurance-disaster-recovery/disaster-claim-aid-coordinator/) | Correct next-step routing hides compensation sources, duplicates a shared file, or invents an award |
| Claimants navigating unemployment services | [Unemployment Claim Navigator](employment-social-insurance/unemployment-claim-navigator/) | A correct status explanation omits an appeal, weekly certification, accessible channel, or evidence already on file |
| Producers recovering from crop, livestock, and grazing losses | [Farm Disaster Deadline Agent](agriculture-food-systems/farm-disaster-deadline-agent/) | The first helpful deadline hides another applicable program clock or repeats farm records |
| Small builders and permit applicants | [Permit Readiness Agent](housing-construction/permit-readiness-agent/) | A complete-looking packet is bound to the wrong jurisdiction, project class, or current intake rule |
| Students, families, and school teams | [Student Accommodation Navigator](education-services/student-accommodation-navigator/) | The route over-collects sensitive records, loses the timely review, or implies the agent decided the accommodation |
| People locked out of important accounts | [Account Recovery Assurance Agent](identity-access/account-recovery-assurance-agent/) | An urgent story turns a new destination or insufficient method into an account-takeover path |
| Disabled users, testers, and content teams | [Accessibility Remediation Verifier](accessibility-digital-services/accessibility-remediation-verifier/) | A clean scan hides a manual-path barrier, or one fixed component becomes a conformance claim |
| Data subjects and accountable privacy teams | [Privacy Rights Orchestrator](privacy-data-governance/privacy-rights-orchestrator/) | A CRM-only task graph omits archives or processors and claims completion without receipts |
| Food manufacturers, distributors, retailers, and recall teams | [Food Recall Traceability Coordinator](food-safety-manufacturing/food-recall-traceability-coordinator/) | A plausible lot relationship becomes an invented trace edge or an unnecessarily broad record request |
| Water customers, utilities, and public-health teams | [Drinking Water Notice Coordinator](water-sanitation/drinking-water-notice-coordinator/) | An unknown service-line state becomes a false safety claim, inaccessible notice, or lost clock |
| Taxpayers and authorized taxpayer-service teams | [IRS Notice Response Navigator](federal-taxpayer-services/irs-notice-response-navigator/) | A correct-looking reply loses the notice deadline, appeal route, or minimum-evidence boundary |
| Veterans, accredited representatives, and claim-support teams | [Veterans Claim Evidence Navigator](veterans-services/veterans-claim-evidence-navigator/) | Evidence already filed is requested again or an administrative navigator implies a claim rating |
| Disabled riders and transit access teams | [Paratransit Access Coordinator](public-transit-mobility/paratransit-access-coordinator/) | A correct route ignores an accessible channel, processing clock, trip condition, or appeal path |
| Records requesters and public transparency teams | [FOIA Routing and Appeal Clock Navigator](government-transparency/foia-routing-appeal-navigator/) | A request reaches a plausible component while tracking, proactive disclosure, or appeal state disappears |
| Applicants and administrative case-support teams | [USCIS Case and Evidence Navigator](immigration-citizenship/uscis-case-evidence-navigator/) | Requested evidence or a notice date is lost, or administrative support becomes legal advice |
| Manufacturers, exporters, and trade-compliance teams | [Export Transaction Evidence Agent](manufacturing-international-trade/export-transaction-evidence-agent/) | Classification alone is treated as clearance while end user, end use, screening, or rule version remains unresolved |
| Students, families, and school-nutrition teams | [School Meal Access Coordinator](child-nutrition-family-services/school-meal-access-coordinator/) | Direct-certification evidence is ignored, the whole form is requested again, or eligibility is implied |
| Voters and nonpartisan election-service teams | [Provisional Ballot Status Navigator](election-administration/provisional-ballot-status-navigator/) | Official status and cure routing blur into eligibility judgment or voter influence |
| Patients, caregivers, clinicians, and receiving providers | [Hospital Discharge Readiness Coordinator](care-transitions/hospital-discharge-readiness-coordinator/) | Complete paperwork hides an absent caregiver, equipment receipt, transport, follow-up, or clinical gate |
| Licensed workers, employers, and state mobility teams | [Occupational License Mobility Navigator](workforce-mobility/occupational-license-mobility-navigator/) | A compact or endorsement path is confused with licensure and current authority provenance is lost |

The committed public-value, trust-and-access, evidence-service, decision-gate, and
proof-before-action waves are complete. The public-protection wave below is also shipped.
New candidates remain below so domain owners can
see the next service gaps.

## Regulatory Clock Collision wave — shipped

Seven industries now share one [Obligation Graph Contract](OBLIGATION_GRAPH_CONTRACT.md)
and matched [real-model report](CLOCK_COLLISION_REPORT.md). Instead of predicting one
status, each lab reconstructs every applicable duty, trigger, clock origin, deadline,
recipient/channel, protected owner, and executed receipt.

| New industry | Flagship lab | Collision the benchmark exposes | Protected boundary |
|---|---|---|---|
| Medical Device Safety | **[Adverse-Event Reporting Gate](medical-device-safety/adverse-event-reporting-gate/)** | Reporter role changes the FDA/manufacturer recipient graph and 5-workday versus 30-calendar-day path | Qualified medical and regulatory judgment |
| Pharmaceutical Supply Continuity | **[Drug Shortage Notification](pharmaceutical-supply/drug-shortage-notification-coordinator/)** | A five-business-day backstop is misused to delay a foreseeable advance notice | Manufacturer filing and FDA shortage status |
| Mortgage Servicing & Housing Stability | **[Loss-Mitigation Foreclosure Gate](mortgage-servicing/loss-mitigation-foreclosure-gate/)** | 45 days, more than 37 days, exactly 37 days, and a 30-day evaluation collapse | Eligibility, counsel, courts, and foreclosure action |
| Healthcare Payment | **[No Surprises Act IDR Navigator](healthcare-payment/no-surprises-idr-deadline-navigator/)** | 30 calendar days is substituted for 30 business days, or initiation becomes determination | Parties and certified IDR entity |
| Securities & Cyber Disclosure | **[Material Cyber Disclosure Gate](securities-cyber-disclosure/material-cyber-incident-disclosure-gate/)** | Discovery replaces the human materiality determination as the four-business-day clock origin | Disclosure committee and authorized filer |
| Long-Term Care & Resident Rights | **[Transfer and Discharge Navigator](long-term-care/nursing-home-transfer-discharge-navigator/)** | A changed destination reuses an old notice and erases appeal rights | Resident, facility, clinician, and appeal body |
| Nuclear Operations & Public Safety | **[Reactor Event Notification Gate](nuclear-operations/reactor-event-notification-gate/)** | Overlapping one-, four-, and eight-hour categories select the slower plausible route | Licensed operators, emergency director, and NRC caller |

## Public Protection wave — shipped

Seven new industries share one [Protection Receipt Contract](PROTECTION_RECEIPT_CONTRACT.md)
and matched [real-model report](PUBLIC_PROTECTION_REPORT.md). The benchmark follows the
workflow beyond a good recommendation: exact subject, rule, gates, clock/channel, human
owner, and executed receipt must all agree.

| New industry | Flagship lab | Failure the benchmark exposes | Protected boundary |
|---|---|---|---|
| Automotive Safety | **[Vehicle Recall Remedy Coordinator](automotive-safety/vehicle-recall-remedy-coordinator/)** | A neighboring model-year campaign is transferred to the VIN, or an appointment becomes a completed repair | Manufacturer/dealer and qualified repair owner |
| Consumer Product Safety | **[Consumer Product Recall Remedy Coordinator](consumer-product-safety/product-recall-remedy-coordinator/)** | Appearance expands recall scope, a warning is dropped, or intake becomes compensation | CPSC notice and recalling-firm remedy |
| Maritime & Ports | **[Detention & Demurrage Invoice Verifier](maritime-ports/detention-demurrage-invoice-verifier/)** | A late container makes a day-31 or duplicate-party invoice look collectible | Contract/billing owner and dispute adjudicator |
| Environmental & Hazardous Materials | **[Hazardous Waste e-Manifest Coordinator](environmental-hazardous-materials/hazardous-waste-manifest-coordinator/)** | A proposal is enforced as present law or a correction invents/erases custody history | Registered signers and environmental authority |
| Consumer Finance & Debt Collection | **[Debt Validation & Dispute Navigator](consumer-finance-debt/debt-validation-dispute-navigator/)** | Prior silence defeats a timely dispute or delivery becomes debt verification | Consumer, collector, court, regulator, and counsel |
| Telecommunications & Emergency Communications | **[911 & 988 Outage Reporting Gate](telecommunications-emergency/communications-outage-reporting-gate/)** | Low user-minutes hide a special-facility route, or a draft becomes a certified filing | Designated officials and authorized NORS filer |
| Workplace Safety & Injury Reporting | **[Severe Incident Reporting Navigator](workplace-safety/severe-incident-reporting-navigator/)** | “Hospital” becomes inpatient, a clock is lost, or an attempt becomes an accepted report | Employer, OSHA/State Plan, and authorized reporter |

## Proof Before Action wave — shipped

Three suggestions that were previously marked ready are now complete runnable labs. They
hold the same eight archetypes and exact Decision Gate Contract constant, but change the
proof boundary, protected action, source record, visual story, and industry language.

| New industry | Flagship lab | Transfer failure the benchmark exposes | Protected boundary |
|---|---|---|---|
| Research & Knowledge Work | **[Claim & Citation Evidence Verifier](research-knowledge-work/claim-evidence-verifier/)** | A valid, relevant citation is treated as entailment for a stronger drafted claim | A human editor owns interpretation and publication |
| Home & Field Services | **[Service Visit Readiness Coordinator](home-field-services/service-visit-readiness-coordinator/)** | A routine no-heat booking path survives after gas odor or a CO alarm changes the case | Emergency response stays outside routine diagnosis, repair, and booking |
| Nonprofit Grant Management | **[Grant Obligation Evidence Navigator](nonprofit-grant-management/grant-obligation-evidence-navigator/)** | An accepted prior-award packet is treated as proof for the current award or cost | The authorized official owns allowability, certification, and submission |

See the [matched model report](PROOF_ACTION_REPORT.md) and dated
[primary-source research notes](docs/PROOF_ACTION_RESEARCH_NOTES.md).

## Highest-value next labs

`Ready` means the workflow has a tractable synthetic world. `Domain partner needed` means
the repo should not invent the policy on its own.

| Priority | Who it helps | Agent job | What must be measured | Boundary | Readiness / closest shape |
|---:|---|---|---|---|---|
| 1 | Patients navigating referrals | Find an in-network provider, assemble referral requirements, and route scheduling blockers | directory freshness, requirement completeness, wrong-network suggestion, escalation latency | Never diagnose, select treatment, or invent coverage | **Domain partner needed** · fork [Prior Auth](healthcare-life-sciences/prior-auth-review-agent/) |
| 2 | People applying for public benefits | Turn an application status into a missing-document checklist and next safe step | statutory source fidelity, minimum burden, deadline, recourse, accessible explanation | Never make the eligibility determination or fabricate agency policy | **Domain partner needed** · fork the [Public Value Contract](PUBLIC_VALUE_CONTRACT.md) reference lab |
| 3 | Patients requesting medication refills | Check identity, remaining authorization, recent changes, and route the request | wrong-patient action, expired authorization, interaction omission, escalation | Never prescribe, change dosage, or override a clinician | **Domain partner needed** · plan + act |

## Evidence-service expansion wave — shipped

Twelve previously proposed high-consequence workflows are now runnable, tested labs rather
than roadmap promises. Every lab shares the same exact contract and eight archetypes, while
its evidence vocabulary, trusted sources, terminals, protected decision, story, failure
cards, and visual identity remain domain-specific.

| New industry | Flagship lab | Distinctive exact proof | Official grounding |
|---|---|---|---|
| Food Safety & Manufacturing | **[Food Recall Traceability](food-safety-manufacturing/food-recall-traceability-coordinator/)** | Exact lot-to-recipient evidence without invented edges | [FDA traceability rule](https://www.fda.gov/food/food-safety-modernization-act-fsma/fsma-final-rule-requirements-additional-traceability-records-certain-foods) |
| Water & Sanitation | **[Drinking Water Notice](water-sanitation/drinking-water-notice-coordinator/)** | Inventory, sample, notice, delivery, assistance, and replacement evidence without false safety claims | [EPA service-line inventory](https://www.epa.gov/ground-water-and-drinking-water/planning-and-developing-service-line-inventory) |
| Federal Taxpayer Services | **[IRS Notice Response](federal-taxpayer-services/irs-notice-response-navigator/)** | Notice-specific action, minimum evidence, delivery, deadline, and recourse | [IRS notices](https://www.irs.gov/individuals/understanding-your-irs-notice-or-letter) |
| Veterans Services | **[Veterans Claim Evidence](veterans-services/veterans-claim-evidence-navigator/)** | Held-versus-requested evidence and correct claim-stage channel | [VA claim status](https://www.va.gov/resources/claim-status-tool-faqs/) |
| Public Transit & Accessible Mobility | **[Paratransit Access](public-transit-mobility/paratransit-access-coordinator/)** | Accessible application, clock, trip-condition, and appeal service | [FTA ADA guidance](https://www.transit.dot.gov/regulations-and-guidance/civil-rights-ada/ada-regulations) |
| Government Transparency | **[FOIA Routing and Appeal Clock](government-transparency/foia-routing-appeal-navigator/)** | Component, disclosure, tracking, fee, response, and appeal state | [DOJ FOIA guidance](https://www.justice.gov/oip/submit-and-track-request-or-appeal) |
| Immigration & Citizenship Services | **[USCIS Case and Evidence](immigration-citizenship/uscis-case-evidence-navigator/)** | Administrative status, requested evidence, notice, channel, and deadline | [USCIS case status](https://www.uscis.gov/tools/checking-your-case-status-online) |
| Manufacturing & International Trade | **[Export Transaction Evidence](manufacturing-international-trade/export-transaction-evidence-agent/)** | Item, destination, end user, end use, screening, and rule-version binding | [BIS end-use controls](https://www.bis.gov/licensing/guidance-on-end-user-and-end-use-controls-and-us-person-controls) |
| Child Nutrition & Family Services | **[School Meal Access](child-nutrition-family-services/school-meal-access-coordinator/)** | Direct-certification reuse and minimum missing household evidence | [USDA model application](https://www.fns.usda.gov/schoolmeals/model-application) |
| Election Administration | **[Provisional Ballot Status](election-administration/provisional-ballot-status-navigator/)** | Official status and cure routing without eligibility judgment or influence | [EAC election-law resources](https://www.eac.gov/election-officials/clearinghouse-resources-election-law-policy/overview-federal-election-laws) |
| Care Transitions | **[Hospital Discharge Readiness](care-transitions/hospital-discharge-readiness-coordinator/)** | Received caregiver, medication, equipment, transport, follow-up, and provider handoffs | [CMS discharge planning](https://www.cms.gov/files/document/qso-25-24-hospitals.pdf) |
| Workforce Mobility | **[Occupational License Mobility](workforce-mobility/occupational-license-mobility-navigator/)** | Occupation, origin license, destination authority, compact, evidence, fee, and clock | [DOL mobility framework](https://www.dol.gov/sites/dolgov/files/ETA/grants/pdfs/FOA-ETA-18-06.pdf) |

These are synthetic evaluation worlds, not operational guidance. Domain owners and the
named accountable authorities still own policy validation and every protected decision.

## How a candidate becomes a lab

The repository uses a service-first gate:

| Gate | Required evidence |
|---|---|
| A person benefits | Name the user and the delay, cost, risk, or exclusion reduced |
| A decision is owned | Specify what the agent may decide or execute and who owns the policy |
| The failure is observable | Score the consequence or state transition, not suspicious language |
| The answer is exact | Generator and scorer call one programmatic gold function |
| Safety has a clean twin | Include a legitimate case that requires the risky capability |
| Privacy is preserved | Synthetic/public scenarios reproduce the decision shape without real records |
| A human boundary exists | State what the agent must escalate and may never decide |

If you know one of these workflows, the most valuable contribution may be a policy review,
not code. Open a [use-case request](https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=use-case-request.yml)
and describe the real decision, trusted records, and failure that matters.
