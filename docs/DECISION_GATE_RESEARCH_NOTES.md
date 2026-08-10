# Decision-gate research notes

Retrieved and revalidated **2026-08-09**. These notes explain the primary-source anchors
behind the six synthetic labs and document premise corrections made before implementation.
They are research provenance, not legal, regulatory, safety, employment, financial, tax,
manufacturing, or aviation advice.

## Method

- Prefer current agency pages and eCFR text over summaries.
- Freeze the executable benchmark into an explicitly fictional policy version.
- Test a narrow, machine-checkable decision boundary rather than claiming full compliance.
- Preserve applicability, interpretation, local procedure, and the final decision for domain
  owners, counsel, regulators, certificated operators, or accountable professionals.

## 1. Pharmaceutical manufacturing

Primary anchors:

- [FDA: Investigating Out-of-Specification Test Results for Pharmaceutical Production](https://www.fda.gov/media/158416/download)
- [FDA: Sterile Drug Products Produced by Aseptic Processing](https://www.fda.gov/media/71026/download)
- [21 CFR 211.188 — Batch production and control records](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211/subpart-J/section-211.188)
- [European Commission: EudraLex Volume 4](https://health.ec.europa.eu/medicinal-products/eudralex/eudralex-volume-4_en)

Benchmark anchor: FDA OOS guidance distinguishes a confirmed OOS result, which leads to
rejection, from an inconclusive laboratory investigation, after which the Quality Unit must
consider the full investigation in its batch disposition. FDA aseptic guidance uses a
stricter default for a sterility-positive investigation whose evidence remains inconclusive.

Premise correction: a draft “EU GMP Annex 22” was suggested as if it were an operative rule.
The current official EudraLex Volume 4 annex index does not list a final Annex 22. The lab
therefore does **not** claim that draft language is in force and grounds the transfer test in
current FDA materials instead.

## 2. Grid switching and restoration

Primary anchor:

- [OSHA 29 CFR 1910.269 — Electric power generation, transmission, and distribution](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.269)

Benchmark anchor: paragraph (m) makes clearance ownership and re-energization conditions
operationally testable. Clearance release remains with the requesting employee unless the
formal transfer process is followed. Re-energization depends on all specified conditions,
including removal of protective grounds, release of clearances, employees being clear, and
removal of tags.

Scope correction: the lab tests the OSHA clearance/re-energization gate. It does not use a
DOE emergency-report form or 18 U.S.C. §1001 as a generic restoration rule; reporting
applicability is a separate question that would require its own scoped benchmark.

## 3. Employer-side hiring

Primary anchors:

- [NYC Department of Consumer and Worker Protection: Automated Employment Decision Tools](https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page)
- [FTC and EEOC: Background Checks — What Employers Need to Know](https://www.ftc.gov/business-guidance/resources/background-checks-what-employers-need-know)

Benchmark anchor: for a qualifying AEDT, NYC's official guidance describes the bias-audit,
public-summary, and candidate-notice conditions, including notice ten business days before
use. When an employer relies on a consumer report, the FTC/EEOC guidance describes the
pre-adverse copy of the report and FCRA rights summary, followed by the post-action process.

Applicability correction: AEDT and FCRA gates are not merged. The consumer-report process
appears only in cases that actually rely on such a report. The final employment decision
remains outside agent authority.

## 4. Aviation dispatch

Primary anchors:

- [14 CFR 121.628 — Inoperable instruments and equipment](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-G/part-121/subpart-U/section-121.628)
- [14 CFR 121.533 — Responsibility for operational control](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-G/part-121/subpart-T/section-121.533)

Benchmark anchor: §121.628 ties operation with inoperative equipment to an approved MEL,
operations-specification authorization, records available to the pilot, and applicable MEL
conditions and limitations. §121.533 assigns joint preflight/dispatch-release responsibility
to the pilot in command and dispatcher and preserves the pilot in command's in-flight
authority.

Scope correction: the synthetic MEL is an aircraft/operator-specific policy fixture. The lab
does not imply that a generic FAA list authorizes dispatch, and the agent can prepare only a
candidate evidence packet.

## 5. Banking AML, KYC, and sanctions

Primary anchors:

- [31 CFR 1020.220 — Customer identification programs](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1020/subpart-B/section-1020.220)
- [31 CFR 1020.320 — Suspicious activity reports](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1020/subpart-C/section-1020.320)
- [OFAC FAQ 401 — 50 Percent Rule](https://ofac.treasury.gov/faqs/401)

Benchmark anchor: the CIP rule supplies minimum identifying information and a risk-based,
reasonable-belief verification standard. The SAR rule supplies the bank threshold, timing,
and confidentiality anchors. OFAC FAQ 401 supplies aggregate direct/indirect blocked-person
ownership for the synthetic sanctions transfer trap.

Premise correction: an SDN-name match is not treated as the same fact as aggregate ownership,
CIP failure, or a SAR determination. Those paths have distinct evidence and reason codes.
The agent never decides to block property or file a SAR, and a customer-facing action never
reveals SAR consideration.

## 6. Tax return completeness

Primary anchors:

- [IRS: Instructions for Form 1040 and 1040-SR](https://www.irs.gov/instructions/i1040gi)
- [IRS: About Form 8879](https://www.irs.gov/forms-pubs/about-form-8879)

Benchmark anchor: the filing-year-specific Form 1040 instructions provide deterministic
form dependencies and the filing deadline. The 2025 instructions link Marketplace advance
premium tax credit reconciliation to Form 8962 and describe Schedule B and capital-asset
reporting paths. Form 8879 is the electronic filing authorization anchor.

Scope correction: the benchmark detects absence from a synthetic packet. It does not compute
tax, decide eligibility, sign for the taxpayer, transmit a return, or claim IRS acceptance.
Every rule is bound to the filing-year snapshot so a superficially similar prior-year packet
cannot silently substitute.

## What the sources do—and do not—prove

The sources justify narrow gold labels and transfer traps. They do not validate the synthetic
records, authorize deployment, replace internal procedures, or establish that the benchmark
covers every applicable rule. A production adaptation needs dated source capture, domain
review, jurisdiction and operator scoping, controlled change management, privacy/security
assessment, and independent validation.
