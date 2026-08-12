# Rights Continuity and Critical Event Fan-Out — research ledger

**Snapshot date:** 2026-08-11

This ledger records the official-source distinctions used to construct six synthetic
benchmarks. It is research provenance—not benefits, insurance, disability, emergency,
privacy, clinical, legal, or regulatory advice.

## Selection test

A workflow shipped only when it had:

1. a direct benefit to a person, public system, or accountable organization;
2. a current official source with a machine-checkable trigger, clock, actor, recipient,
   evidence-burden, or receipt distinction;
3. a clean twin where one narrow fact changes the route or obligation graph;
4. a consequential decision the agent must not own; and
5. an exact failure that ordinary task-completion scoring would hide.

## 1. Medicaid and CHIP renewal continuity

- CMS renewal materials require states to begin with an ex-parte review using reliable
  information available to the agency before requesting a renewal form.
- When the available record cannot support renewal, the service should request the
  unresolved information rather than duplicate proof already held.
- CMS guidance also distinguishes renewal, procedural termination, reconsideration, fair
  hearing, and the agency's final eligibility action.

Sources: [CMS eligibility-renewals overview](https://www.medicaid.gov/sites/default/files/2024-09/eligibility-renewals-overview.pdf),
[CMS ex-parte renewal guidance](https://www.medicaid.gov/federal-policy-guidance/2024-11-26/173191),
[CMS eligibility and enrollment guidance](https://www.medicaid.gov/federal-policy-guidance/downloads/cib050924-comb.pdf).

## 2. Health-plan denial and appeal rights

- CMS consumer materials preserve at least 180 days to request internal appeal in the
  covered workflow while decision timing branches by urgent, pre-service, and post-service
  status.
- Urgent-care review may run on an expedited path, and qualifying urgent internal and
  external review can proceed concurrently rather than through the routine sequence.
- Filed, received, under review, upheld, overturned, authorized, and paid are distinct states.

Sources: [CMS appealing health-plan decisions](https://www.cms.gov/cciio/resources/fact-sheets-and-faqs/indexappealinghealthplandecisions),
[CMS appeals workflow](https://www.cms.gov/cciio/resources/fact-sheets-and-faqs/appeals06152012a),
[CMS internal and external appeals overview](https://www.cms.gov/marketplace/technical-assistance-resources/internal-claims-and-appeals.pdf).

## 3. Social Security medical-cessation continuity

- Current SSA POMS separates the medical-cessation appeal period from the shorter election
  for statutory benefit continuation.
- The loaded synthetic snapshot models the POMS 60-day appeal path and 15-calendar-day
  continuation path (10 days plus presumed mailing) as separate clocks.
- A writing that clearly expresses disagreement can establish appeal intent; a phone request
  for explanation alone does not preserve the filing date. SSA owns good cause and payment.

Sources: [SSA POMS DI 12027.008](https://secure.ssa.gov/poms.nsf/lnx/0412027008),
[SSA POMS DI 12026.020](https://secure.ssa.gov/apps10/poms.NSF/lnx/0412026020),
[SSA POMS DI 12026.015](https://secure.ssa.gov/poms.nsf/lnx/0412026015).

## 4. Pipeline incident response and notification

- PHMSA incident-reporting material states that qualifying hazardous-material pipeline
  releases require National Response Center notification at the earliest practicable
  moment, but no later than one hour after confirmed discovery.
- Operators must provide a follow-up update within 48 hours of the initial telephonic report.
- Emergency action, initial notification, update, and final report records remain independent.

Source: [PHMSA incident reporting](https://www.phmsa.dot.gov/incident-reporting).

## 5. HIPAA breach recipient graph

- HHS distinguishes business-associate notice to a covered entity from the covered entity's
  notices to affected individuals, HHS, and—in specified large local events—the media.
- Individual notice remains applicable while timing of HHS reporting branches for breaches
  affecting 500 or more people versus fewer than 500.
- Insufficient contact information can create a substitute-notice branch; drafted, approved,
  delivered, and regulator-accepted are different stages.

Source: [HHS Breach Notification Rule](https://www.hhs.gov/hipaa/for-professionals/breach-notification/index.html).

## 6. Clinical-trial IND safety reporting

- FDA materials distinguish an unexpected fatal or life-threatening suspected adverse
  reaction on the seven-calendar-day path from other qualifying 15-day reports.
- A serious adverse event is not automatically a suspected adverse reaction. Seriousness,
  expectedness, and evidence suggesting a causal relationship require qualified review.
- Relevant follow-up information creates another reporting stage; an initial report does
  not close the safety record or authorize trial action.

Sources: [FDA IND safety reports](https://www.fda.gov/drugs/investigational-new-drug-ind-application/ind-application-reporting-ind-safety-reports),
[FDA safety considerations in clinical drug development](https://www.fda.gov/media/185120/download).

## Premise corrections preserved in code

| Tempting premise | Correction encoded in scenarios |
|---|---|
| Every renewing household should complete a form | Reliable agency data is tested first; only the unresolved set is requested |
| One appeal deadline preserves every protection | Primary review and companion continuity rights retain independent clocks |
| Internal review must always finish before external review | Supported urgent cases preserve the concurrent expedited route |
| A timely disability appeal keeps benefits flowing | Benefit continuation requires a separate, shorter election or good-cause review |
| Containing a pipeline release closes the incident | Response, one-hour notification, 48-hour update, and receipts remain separate |
| Five hundred is one universal HIPAA threshold | Actor, individual, HHS, media, geography, and contact branches remain distinct |
| Every serious trial event is automatically a rapid safety report | Expectedness, suspected relationship, outcome, aggregate evidence, and qualified judgment matter |
| Approval or a prepared script proves notification | Only the executed recipient receipt can advance the durable stage |

Every production adaptation must revalidate effective rules, jurisdiction, local procedure,
accessible channels, source reliability, privacy controls, and accountable owners. The
committed scenarios contain fictional people, organizations, systems, facts, and receipts.
