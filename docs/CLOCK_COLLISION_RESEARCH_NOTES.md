# Regulatory Clock Collision wave — research ledger

**Snapshot date:** 2026-08-10

This ledger records the official sources, machine-checkable distinctions, and premise
corrections used to construct seven synthetic benchmarks. It is research provenance—not
legal, medical, securities, housing, safety, nuclear, or regulatory advice.

## Selection test

A workflow shipped only when it had:

1. a concrete public, worker, patient, resident, investor, or economic benefit;
2. a current official rule with testable trigger, clock, recipient, or notice fields;
3. a clean twin where one fact changes one obligation;
4. a consequential judgment the agent must not own;
5. a receipt stage that can be compared with the executed tool trace.

## 1. Medical device safety

- FDA states that manufacturers generally report deaths, serious injuries, and qualifying
  malfunctions to FDA within 30 calendar days of awareness.
- Manufacturer events designated by FDA or requiring remedial action to prevent an
  unreasonable risk of substantial public-health harm follow a five-workday path.
- Importer recipient duties differ: deaths and serious injuries go to FDA and the
  manufacturer; qualifying malfunctions go to the manufacturer.
- FDA reports receiving more than two million suspected device-associated reports each
  year. The benchmark tests route fidelity, not the truth of any individual report.

Sources: [mandatory MDR requirements](https://www.fda.gov/medical-devices/postmarket-requirements-devices/mandatory-reporting-requirements-manufacturers-importers-and-device-user-facilities),
[MDR overview](https://www.fda.gov/medical-devices/medical-device-safety/medical-device-reporting-mdr-how-report-medical-device-problems),
[eMDR](https://www.fda.gov/medical-devices/mandatory-reporting-requirements-manufacturers-importers-and-device-user-facilities/emdr-electronic-medical-device-reporting).

## 2. Drug supply continuity

- Section 506C materials require covered manufacturers to notify FDA six months before a
  discontinuance or interruption likely to lead to meaningful disruption when possible.
- If six months is not possible, the duty is as soon as practicable, with a backstop no
  later than five business days after the interruption.
- The benchmark prevents the five-day backstop from becoming permission to wait when the
  event is already known.

Sources: [FDA notification non-compliance](https://www.fda.gov/drugs/drug-shortages/drug-shortages-non-compliance-notification-requirement),
[FDA shortage FAQ](https://www.fda.gov/drugs/drug-shortages/frequently-asked-questions-about-drug-shortages).

## 3. Mortgage servicing and housing stability

- Regulation X §1024.41 distinguishes applications received 45 days or more before a sale,
  complete applications received more than 37 days before a sale, and the 30-day
  evaluation period.
- Official interpretation says “more than 37 days” is not “37 days or less,” while noting
  that separate servicing duties can still apply to the latter.
- Foreclosure restrictions can require the servicer to instruct retained counsel; counsel's
  action or inaction does not erase the servicer's duty.

Source: [CFPB Regulation X §1024.41](https://www.consumerfinance.gov/rules-policy/regulations/1024/41/).

## 4. No Surprises Act Federal IDR

- CMS describes a required 30-business-day open-negotiation period followed by a
  four-business-day window to initiate an eligible Federal IDR dispute.
- Initiation, certified-entity selection, offer submission, determination, and payment are
  separate stages.
- CMS reported more than five million disputes since the program launched, making precise
  eligibility and clock handling economically material.

Sources: [Federal IDR process](https://www.cms.gov/nosurprises/help-resolve-payment-disputes/payment-disputes-between-providers-and-health-plans),
[IDR reports](https://www.cms.gov/nosurprises/policies-and-resources/Reports).

## 5. Public-company cyber disclosure

- SEC Item 1.05 requires disclosure within four business days after the registrant
  determines a cybersecurity incident is material—not four days after occurrence or
  discovery.
- Materiality must be determined without unreasonable delay by the registrant.
- Required disclosure focuses on material nature, scope, timing, and impact; it need not
  expose technical response or vulnerability detail that would impede remediation.

Sources: [SEC cybersecurity disclosure guidance](https://www.sec.gov/newsroom/speeches-statements/gerding-cybersecurity-disclosure-20231214),
[final rule](https://www.sec.gov/files/rules/final/2023/33-11216.pdf),
[Form 8-K interpretations](https://www.sec.gov/rules-regulations/staff-guidance/compliance-disclosure-interpretations/exchange-act-form-8-k).

## 6. Nursing-home resident rights

- CMS resident-rights material states that, except in emergencies, nursing homes generally
  provide 30-day written notice of a planned transfer or discharge.
- Notice includes the reason, effective date, destination, appeal rights, and assistance
  information.
- CMS operations guidance warns that a changed destination can indicate a changed basis,
  requiring a new notice and potentially additional appeal rights.

Sources: [CMS resident rights](https://downloads.cms.gov/medicare/your_resident_rights_and_protections_section.pdf),
[CMS State Operations Manual update](https://www.cms.gov/files/document/r225soma.pdf).

## 7. Nuclear reactor event notification

- 10 CFR 50.72 separates emergency notifications and non-emergency one-hour, four-hour,
  and eight-hour paths.
- Four-hour examples include specified required shutdowns and valid RPS/ECCS actuations,
  with preplanned test/operation exceptions in the rule text.
- NRC guidance links immediate notifications to later event-reporting records. The agent is
  deliberately denied all plant-control and emergency-declaration capabilities.

Sources: [10 CFR 50.72](https://www.law.cornell.edu/cfr/text/10/50.72),
[NRC NUREG-1022](https://www.nrc.gov/reading-rm/doc-collections/nuregs/staff/sr1022/index),
[NRC event assessment](https://www.nrc.gov/about-nrc/regulatory/event-assess).

## Premise corrections preserved in code

| Tempting premise | Correction encoded in scenarios |
|---|---|
| Every device reporter sends the same FDA report | Reporter role changes the recipient graph |
| Five days means a manufacturer may wait for the interruption | Earlier knowledge starts the as-soon-as-practicable duty |
| Exactly 37 days is “more than 37” | The strict milestone is preserved; separate duties remain visible |
| One month equals 30 business days | The committed calendar explicitly counts business days |
| The cyber clock starts when the incident is discovered | Authorized materiality determination starts Item 1.05 timing |
| A new destination is a clerical notice edit | A changed plan can require new notice and appeal rights |
| Any protection-system actuation follows the same clock | Event category, preplanned context, overlap, and earliest clock remain separate |

Every production adaptation must revalidate effective rules, jurisdiction, local
procedures, calendar logic, accountable owners, and receipt semantics.
