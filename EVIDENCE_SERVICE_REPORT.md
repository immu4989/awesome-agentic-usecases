# Evidence Service Contract — matched industry report

**12 industries · 32 committed scenarios per lab · 8 balanced archetypes · 3 repeats
per benchmark arm.**

This is the cross-industry view of the [Evidence Service Contract](EVIDENCE_SERVICE_CONTRACT.md).
It asks whether an agent gets the terminal, exact missing evidence, access channel, deadline,
recourse, authority boundary, and executed record right **together**. Current committed
real providers: `deepseek / deepseek-v4-flash`, `mistral / mistral-small-latest`.

These are synthetic smoke suites, not production rankings or claims about any agency,
company, program, model family, or real-world prevalence. The same scenario shapes make
transfer visible; domain owners still decide whether each fictional contract resembles the
service they operate.

## Exact service matrix

| Industry / lab | Deterministic baseline | deepseek / deepseek-v4-flash | mistral / mistral-small-latest |
|---|---:|---:|---:|
| **Food Safety & Manufacturing**<br>[Food Recall Traceability Coordinator](food-safety-manufacturing/food-recall-traceability-coordinator/) | 0.250 | 0.958 | 0.833 |
| **Water & Sanitation**<br>[Drinking Water Notice and Service-Line Coordinator](water-sanitation/drinking-water-notice-coordinator/) | 0.250 | 0.958 | 0.875 |
| **Federal Taxpayer Services**<br>[IRS Notice Response Navigator](federal-taxpayer-services/irs-notice-response-navigator/) | 0.250 | 1.000 | 0.708 |
| **Veterans Services**<br>[Veterans Claim Evidence Navigator](veterans-services/veterans-claim-evidence-navigator/) | 0.250 | 0.917 | 0.375 |
| **Public Transit & Accessible Mobility**<br>[Paratransit Access Coordinator](public-transit-mobility/paratransit-access-coordinator/) | 0.250 | 0.917 | 0.792 |
| **Government Transparency**<br>[FOIA Routing and Appeal Clock Navigator](government-transparency/foia-routing-appeal-navigator/) | 0.250 | 1.000 | 0.750 |
| **Immigration & Citizenship Services**<br>[USCIS Case and Evidence Navigator](immigration-citizenship/uscis-case-evidence-navigator/) | 0.250 | 0.958 | 0.917 |
| **Manufacturing & International Trade**<br>[Export Transaction Evidence Agent](manufacturing-international-trade/export-transaction-evidence-agent/) | 0.250 | 1.000 | 0.792 |
| **Child Nutrition & Family Services**<br>[School Meal Access Coordinator](child-nutrition-family-services/school-meal-access-coordinator/) | 0.250 | 0.958 | 0.917 |
| **Election Administration**<br>[Provisional Ballot Status Navigator](election-administration/provisional-ballot-status-navigator/) | 0.250 | 1.000 | 0.708 |
| **Care Transitions**<br>[Hospital Discharge Readiness Coordinator](care-transitions/hospital-discharge-readiness-coordinator/) | 0.250 | 0.917 | 1.000 |
| **Workforce Mobility**<br>[Occupational License Mobility Navigator](workforce-mobility/occupational-license-mobility-navigator/) | 0.250 | 0.875 | 1.000 |

## What the aggregate hides

| Suite mean | Deterministic baseline | deepseek / deepseek-v4-flash | mistral / mistral-small-latest |
|---|---:|---:|---:|
| Outcome | 0.875 | 0.955 | 0.875 |
| Minimum evidence | 0.625 | 1.000 | 0.934 |
| Access | 0.875 | 1.000 | 0.882 |
| Deadline | 0.875 | 1.000 | 0.990 |
| Recourse | 0.250 | 1.000 | 0.899 |
| Rights | 0.875 | 1.000 | 1.000 |
| Exact | 0.250 | 0.955 | 0.806 |
| Median p50 latency | 0.00s | 11.55s | 6.14s |
| Total measured cost | $0.0000 | $0.1433 | $0.0696 |

Means are calculated across the 12 lab-level means so one industry cannot dominate the
suite. Confidence intervals remain in each lab's committed Markdown result. Cost uses
measured tokens and the repository's list-price table; provider free-tier billing may differ.
p50 includes provider and network conditions from the collection runs; do not read it as a
controlled or uncontended production-latency benchmark.

## One reproducible miss per industry

| Industry | Provider | Scenario | Failed exact obligations |
|---|---|---|---|
| Food Safety & Manufacturing | deepseek / deepseek-v4-flash | `foodtrace-007` | terminal |
| Water & Sanitation | deepseek / deepseek-v4-flash | `water-007` | terminal |
| Federal Taxpayer Services | mistral / mistral-small-latest | `taxnotice-005` | terminal |
| Veterans Services | deepseek / deepseek-v4-flash | `veteran-007` | terminal |
| Public Transit & Accessible Mobility | deepseek / deepseek-v4-flash | `paratransit-007` | terminal |
| Government Transparency | mistral / mistral-small-latest | `foia-004` | terminal, evidence |
| Immigration & Citizenship Services | deepseek / deepseek-v4-flash | `uscis-007` | terminal |
| Manufacturing & International Trade | mistral / mistral-small-latest | `export-004` | terminal, evidence, access, recourse, record |
| Child Nutrition & Family Services | deepseek / deepseek-v4-flash | `schoolmeal-007` | terminal |
| Election Administration | mistral / mistral-small-latest | `ballot-002` | terminal |
| Care Transitions | deepseek / deepseek-v4-flash | `discharge-007` | terminal |
| Workforce Mobility | deepseek / deepseek-v4-flash | `license-007` | terminal |

Open the linked lab, then inspect its `results/*.json` row for the exact predicted record,
executed tool trace, metrics, model reasoning, usage, and provenance. A missing row above
means the provider result was not committed or contained a provider error; it is never
silently converted into a model score.

## How to use this report

1. **Pick the nearest evidence shape**, not merely the nearest industry name.
2. **Run the deterministic baseline** to verify generation, tools, trace, and scoring at $0.
3. **Replay the committed scenario IDs** on the candidate models and interventions.
4. **Inspect directional misses**—especially authority traps and deadlines—before averages.
5. **Replace fictional policy only with a domain owner**, preserving the exact contract.

<sub>Generated by `docs/make_evidence_service_report.py` from committed catalog and result
JSON. Edit the labs or their evidence; do not hand-edit this report.</sub>
