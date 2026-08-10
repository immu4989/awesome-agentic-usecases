# Public Protection wave — research ledger

**Snapshot date:** 2026-08-10

This ledger records why the seven workflows were selected, the official sources used to
shape their synthetic policies, and the premise corrections that keep the benchmark from
turning a proposed or neighboring rule into ground truth. It is research provenance, not
legal, compliance, safety, emergency, or financial advice.

## Selection test

A candidate shipped only when it had all five:

1. a concrete person, business, worker, or public system that benefits;
2. a primary-source rule or official workflow with machine-checkable facts;
3. a clean twin and a nearby transfer trap;
4. a protected decision or certification the agent must not own;
5. a durable receipt whose stage can be tested against the executed event.

## 1. Automotive safety — recall remedy

- NHTSA reported 997 vehicle/equipment recalls covering more than 29 million vehicles in
  2025 and notes that millions of recalled vehicles remain unrepaired each year.
- Official recall status is checked through NHTSA's VIN lookup; manufacturer and dealer
  records determine the actual remedy path.
- Benchmark distinction: model/component similarity is not VIN applicability, and a booked
  appointment is not proof of repair.

Sources: [NHTSA recall lookup](https://www.nhtsa.gov/recalls),
[Vehicle Safety Recalls Week](https://www.nhtsa.gov/recalls/vehicle-safety-recalls-week),
[NHTSA recall process](https://www.nhtsa.gov/vehicle-safety/vehicle-recalls).

## 2. Consumer product safety — recall remedy

- CPSC's FY2024 report records 333 voluntary recalls involving about 41 million product
  units, alongside more than 56,000 takedown requests and 58,000 removed product listings.
- CPSC provides an official recall corpus and published recall-remedy channels.
- Benchmark distinction: brand/appearance is not model/date-code inclusion; official
  stop-use language must survive the route; intake is not remedy completion.

Sources: [CPSC FY2024 Annual Performance Report](https://www.cpsc.gov/s3fs-public/FY-2024-APR.pdf),
[CPSC recalls](https://www.cpsc.gov/Recalls),
[Fast-Track Recall Program](https://www.cpsc.gov/Business--Manufacturing/Recall-Guidance/CPSC-Fast-Track-Recall-Program),
[reporting guidance](https://www.cpsc.gov/Regulations-Laws--Standards/Unregulated-Products).

## 3. Maritime and ports — detention and demurrage invoices

- FMC reports $15.4 billion in detention and demurrage collected from April 1, 2020 through
  March 31, 2025.
- The 2024 final-rule summary says only the contracted person or consignee may be billed,
  the same charge may not be billed to multiple parties, and invoices generally must be
  issued within 30 calendar days.
- Benchmark distinction: operational lateness does not prove a day-31 or duplicate-party
  invoice is collectible; a dispute receipt is not a waiver.

Sources: [FMC detention and demurrage](https://www.fmc.gov/detention-and-demurrage/),
[FMC final-rule summary](https://www.fmc.gov/articles/fmc-publishes-final-rule-on-detention-and-demurrage-billing-practices/),
[Federal Register final rule](https://www.federalregister.gov/documents/2024/02/26/2024-02926/demurrage-and-detention-billing-requirements).

## 4. Environmental protection — hazardous-waste e-Manifest

- EPA's December 2025 export integration brought roughly 22,000 annual export manifests
  into e-Manifest and published current registration, correction, and exception workflows.
- Corrections must remain attributable; the original chain cannot be silently rewritten.
- Benchmark distinction: EPA's March 2026 move toward fully electronic manifests was a
  **proposal** at the snapshot date and is deliberately not encoded as current law.

Sources: [EPA e-Manifest](https://www.epa.gov/e-manifest),
[manifest corrections](https://www.epa.gov/e-manifest/requirement-to-correct-errors-manifest-data-submitted-epa),
[user registration](https://www.epa.gov/e-manifest/e-manifest-user-registration),
[export integration final rule](https://www.epa.gov/e-manifest/final-rule-integrating-e-manifest-exports-and-other-manifest-related-reports-pcb).

## 5. Consumer finance — debt validation and disputes

- CFPB's 2025 FDCPA report says the most common 2024 debt-collection issue was an attempt to
  collect debt not owed; within that issue, reported reasons included not their debt,
  identity theft, already paid, and bankruptcy.
- Current Regulation F §1006.34 defines validation information and a validation period that
  ends 30 days after receipt or assumed receipt. A timely written dispute or original-
  creditor request can trigger a cease-until-verification path under the rule's conditions.
- Benchmark distinction: a prior undisputed state does not erase a timely current dispute;
  delivery of the dispute does not verify the debt.

Sources: [Regulation F §1006.34](https://www.consumerfinance.gov/rules-policy/regulations/1006/34/),
[CFPB 2025 FDCPA annual report](https://files.consumerfinance.gov/f/documents/cfpb_fdcpa-2025-annual-report_2025-11.pdf),
[CFPB consumer resources](https://www.consumerfinance.gov/consumer-tools/debt-collection/).

## 6. Emergency communications — 911 and 988 outages

- FCC materials define distinct outage-reporting paths. A 30-minute event with at least
  900,000 user-minutes follows a general path; potential impact to a covered 911 or 988
  special facility can activate a separate, faster path even below that volume.
- Special-facility workflows include notice to the designated official as well as NORS
  reporting. Final reports must remain accurate and complete.
- Benchmark distinction: “below 900,000” is not a complete non-reportability test; a draft
  or notification attempt is not an accepted, certified filing.

Sources: [FCC 911 outage reporting order](https://docs.fcc.gov/public/attachments/DA-12-2027A1_Rcd.pdf),
[FCC 988 outage reporting order](https://docs.fcc.gov/public/attachments/FCC-23-57A1.pdf),
[FCC 2024 enforcement order](https://docs.fcc.gov/public/attachments/DA-24-708A1.pdf).

## 7. Workplace safety — severe incident reporting

- OSHA's federal reporting table specifies an eight-hour fatality route and a 24-hour route
  for inpatient hospitalization, amputation, or eye loss, with separate event-window and
  employer-knowledge facts.
- OSHA distinguishes formal inpatient admission from emergency-room treatment and provides
  State Plan routing. Related outcomes may require updating the record to the most serious
  result without fabricating a new event history.
- Benchmark distinction: a hospital visit is not automatically inpatient admission; a
  draft or phone attempt is not an accepted report.

Sources: [OSHA reporting table](https://www.osha.gov/recordkeeping/2014/reporting-table),
[OSHA reporting portal](https://www.osha.gov/report),
[OSHA related-event interpretation](https://www.osha.gov/laws-regs/standardinterpretations/2021-01-08).

## Premise corrections preserved in code

| Tempting premise | Correction encoded in the scenarios |
|---|---|
| A recognizable recalled model is enough | Vehicle applicability stays bound to the VIN and official campaign |
| A visually identical product inherits a recall | Model/date/lot scope stays exact |
| If the container was late, the bill is valid | Billed party, duplicate billing, issue clock, events, and free time are separate gates |
| EPA is already fully electronic | A March 2026 proposal is not enforced as current law |
| An old undisputed debt stays undisputed | The current validation notice, delivery, clock, and dispute control the path |
| Under 900,000 user-minutes means no outage report | 911/988 special-facility impact is separately classified |
| Any hospital treatment is inpatient hospitalization | Formal admission, exact severe outcome, event window, and employer knowledge remain distinct |

Every production adaptation must revalidate these sources, jurisdiction, effective dates,
local procedures, and accountable owners.
