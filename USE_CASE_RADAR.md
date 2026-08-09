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

## Committed industry expansion queue

This is the repository's recorded build order. Research may refine a lab's synthetic
policy, but new ideas do not silently displace an earlier commitment.

| Order | New industry | Flagship lab | Status | Distinctive proof |
|---:|---|---|---|---|
| 1 | Energy & Utilities | **[Household Energy Lifeline](energy-utilities/household-energy-lifeline/)** | **Shipping** | Preserve essential-service options, minimum evidence, accessibility, deadlines, recourse, and truthful completion together |
| 2 | Insurance & Disaster Recovery | **[Disaster Claim and Aid Coordinator](insurance-disaster-recovery/disaster-claim-aid-coordinator/)** | **Shipping** | Coordinate insurer and public-aid paths without double-counting compensation or deciding entitlement |
| 3 | Employment & Social Insurance | **[Unemployment Claim Navigator](employment-social-insurance/unemployment-claim-navigator/)** | **Shipping** | Explain status and protect appeal and weekly-certification paths without adjudicating eligibility or identity exceptions |
| 4 | Agriculture & Food Systems | **[Farm Disaster Deadline Agent](agriculture-food-systems/farm-disaster-deadline-agent/)** | **Shipping** | Preserve the exact set of program-specific notice windows while reusing held farm records and never inventing an award |
| 5 | Housing & Construction | **[Permit Readiness Agent](housing-construction/permit-readiness-agent/)** | **Shipping** | Bind the packet to the exact jurisdiction and project rule without claiming the permit will be approved |
| 6 | Education Services | **[Student Accommodation Navigator](education-services/student-accommodation-navigator/)** | **Shipping · domain review required** | Minimize sensitive evidence and preserve a timely, accessible human accommodation decision |

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

The committed six-industry queue is now complete. New candidates remain below so domain
owners can see the next service gaps without displacing work that was already promised.

## Highest-value next labs

`Ready` means the workflow has a tractable synthetic world. `Domain partner needed` means
the repo should not invent the policy on its own.

| Priority | Who it helps | Agent job | What must be measured | Boundary | Readiness / closest shape |
|---:|---|---|---|---|---|
| 1 | Patients navigating referrals | Find an in-network provider, assemble referral requirements, and route scheduling blockers | directory freshness, requirement completeness, wrong-network suggestion, escalation latency | Never diagnose, select treatment, or invent coverage | **Domain partner needed** · fork [Prior Auth](healthcare-life-sciences/prior-auth-review-agent/) |
| 2 | People applying for public benefits | Turn an application status into a missing-document checklist and next safe step | statutory source fidelity, minimum burden, deadline, recourse, accessible explanation | Never make the eligibility determination or fabricate agency policy | **Domain partner needed** · fork the [Public Value Contract](PUBLIC_VALUE_CONTRACT.md) reference lab |
| 3 | People locked out of important accounts | Recover access through the least invasive verified route | takeover rate, legitimate recovery, PII disclosure, escalation | Never weaken identity requirements because the story sounds urgent | **Ready** · fork [Refund Resolution](customer-support/refund-resolution-agent/) |
| 4 | Privacy teams and data subjects | Intake and route deletion/access/correction requests across systems | identity prerequisite, jurisdiction, system coverage, deadline, truthful completion record | Legal exceptions and final denial remain with the accountable privacy team | **Ready with counsel** · fork [DPA Review](legal-compliance/dpa-clause-review-agent/) |
| 5 | Disabled users and content teams | Find accessibility defects and create a remediation plan | issue coverage, false assurance, severity, verified fix state | Never claim conformance from automated checks alone | **Ready** · investigate + gate |
| 6 | Patients requesting medication refills | Check identity, remaining authorization, recent changes, and route the request | wrong-patient action, expired authorization, interaction omission, escalation | Never prescribe, change dosage, or override a clinician | **Domain partner needed** · plan + act |
| 7 | Families coordinating home or field service | Diagnose scheduling and parts prerequisites, then book or escalate safely | wrong dispatch, repeat visit, unsafe DIY advice, completion fidelity | Emergency and safety-critical conditions escalate immediately | **Ready** · fork [Exception Triage](logistics-supply-chain/exception-triage-agent/) |
| 8 | Small nonprofits | Match grant obligations to evidence and draft a submission checklist | requirement omission, unsupported claim, deadline, source provenance | Never fabricate outcomes or certify a filing | **Ready** · fork [DPA Review](legal-compliance/dpa-clause-review-agent/) |
| 9 | Knowledge workers and researchers | Verify claims against cited sources before a report ships | citation entailment, source freshness, unsupported claim, correction coverage | Human owns interpretation and publication | **Ready** · investigate + decide |

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
