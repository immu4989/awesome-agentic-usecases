# Federal Pilot Kit — research and premise notes

Verified: **2026-08-18** · Review due: **2026-11-18**

These notes document why the Pilot Kit exists and which conclusions it deliberately does not make.
They are not legal or acquisition advice. Agencies and vendors must verify current law, policy,
contract terms, agency implementation, exceptions, and authorization boundaries.

## Problem statement

GAO-26-107859 reports strategic and programmatic federal AI-acquisition challenges involving access
to subject-matter experts, government data and intellectual-property protections, requirements and
contract terms, early testing and continuous evaluation, and pricing and overall cost. GAO also
found that selected agencies were not yet systematically collecting acquisition lessons learned;
its recommendations to DOD, DHS, GSA, and VA call for policies that require collection and sharing.

OMB M-25-22 connects many of those gaps to the acquisition lifecycle: cross-functional engagement,
market research, performance-based requirements, pricing transparency, data and model portability,
government-data and intellectual-property terms, testing proposed systems, ongoing monitoring, and
rights and data handling at contract exit. GSA’s Buy AI guidance reinforces a mission-needs and
solution-testing approach.

The repository already shipped a mission assurance profile. The missing handoff was a common,
machine-readable way for an agency request, a responder claim, an evidence artifact, a synthetic
test result, a human authority boundary, a commercial response, and a reusable lesson to remain
linked without becoming a vendor score or award recommendation.

## Version 0.4 problem — pilots end, but public learning often does not begin

GAO-26-107859 found that selected agencies were not systematically collecting lessons learned from
AI acquisitions, including discontinued efforts. Officials described repeated challenges involving
technical expertise, requirements and contract terms, government data and intellectual property,
early testing and continuous evaluation, pricing, and overall cost. GAO recommended that DOD, DHS,
GSA, and VA establish processes to collect and submit lessons to a GSA-managed repository.

The Lessons Exchange is not that repository and does not claim to satisfy an agency policy. It is a
portable public schema and local toolchain that helps a team prepare a bounded, redacted,
evidence-linked record for authorized sharing or future export. Its public examples are synthetic.
The format refuses vendor comparison and makes stopped pilots first-class because a precisely
documented stop condition can prevent another team from repeating the same unsafe design.

GAO-26-107681 separately identifies AI privacy risks and gaps involving audits, sensitive-data
separation, metrics, consent, technical protections, privacy impact assessments, and information
sharing. The v0.4 scanner therefore acts only as a narrow pre-publication backstop. It cannot
determine that material is releasable; the schema requires named human redaction and publication
roles, explicit negative sharing attestations, data-minimization and retention statements, and a
warning that zero findings are not disclosure authorization.

## Design decisions

1. **Three documents, not one self-attestation.** Agency, responder, and test artifacts have
   distinct versions and schemas. Cross-validation detects missing claims, unknown requirements,
   missing test cases, and mismatched pilot identifiers.
2. **Exact fields stay conjunctive.** Outcome, reason-code set, named human authority, authority
   preservation, and evidence references must all pass for a case to be exact.
3. **No universal or comparative score.** Requirement states and exact-case counts remain separate.
   The tool does not rank, shortlist, select, or recommend a responder.
4. **Critical gaps stay visible.** A critical requirement reaches `tested` only when the support
   claim has evidence and every linked submitted synthetic case passes.
5. **Synthetic success is narrow.** The report states that a match proves only agreement between a
   submitted result and a declared synthetic oracle—not independent reproduction or deployment
   performance.
6. **Commercial evidence is first-class.** Pricing units, volume scenarios, government-data use,
   portability, knowledge transfer, and exit support are exported beside technical tests.
7. **Lessons are designed for safe reuse.** The pack includes a redaction warning and empty
   lessons-learned prompts; it never auto-publishes or uploads acquisition content.
8. **Review prompts are not clauses.** Source-linked questions help a cross-functional team inspect
   missing topics without pretending one clause fits every procurement.
9. **Lessons are not rankings.** Outcome states describe one bounded pilot; no success percentage,
   vendor identity, comparative score, shortlist, or award signal is produced.
10. **A stopped pilot is a result.** A critical authority or side-effect failure is published as a
    stop lesson instead of being averaged into an otherwise attractive score.
11. **Reuse needs a negative boundary.** Every lesson names where the practice may apply, where it
    must not transfer, prerequisites, limitations, and a required transfer test.
12. **Public scans reveal labels, not matches.** Scanner receipts contain codes, field paths, and
    short digests—not the suspected sensitive value.
13. **Sources expire visibly.** Policy dependencies carry dated ledger entries, review dates, and
    revalidation triggers. A current ledger is not a legal-applicability finding.

## Premises checked

- The kit does **not** claim OMB or GAO requires this particular schema or tool.
- The kit does **not** claim every federal AI use is high-impact.
- The kit does **not** turn a synthetic test into an Authority to Operate or compliance finding.
- The kit does **not** assume a responder’s evidence was independently produced or reproduced.
- The kit does **not** calculate legal FOIA deadlines, make cost-allowability decisions, decide
  benefits, or determine which acquisition method or clause applies.
- The reference responders are invented and their prices are illustrative—not quotations or offers.
- SHA-256 manifests prove byte integrity only.

## Primary official sources

- [OMB M-25-21 — Accelerating Federal Use of AI through Innovation, Governance, and Public Trust](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf)
- [OMB M-25-22 — Driving Efficient Acquisition of Artificial Intelligence in Government](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf)
- [GAO-26-107859 — Artificial Intelligence Acquisitions](https://www.gao.gov/products/gao-26-107859)
- [GAO-26-107681 — Artificial Intelligence: OMB Action Needed to Address Privacy-Related Gaps in Federal Guidance](https://www.gao.gov/products/gao-26-107681)
- [GSA — Buy AI](https://www.gsa.gov/artificial-intelligence/buy-ai)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST — AI Test, Evaluation, Validation and Verification](https://www.nist.gov/ai-test-evaluation-validation-and-verification-tevv)
- [DOJ Office of Information Policy — Guide to the Freedom of Information Act](https://www.justice.gov/oip/doj-guide-freedom-information-act-0)
- [2 CFR Part 200](https://www.ecfr.gov/current/title-2/subtitle-A/chapter-II/part-200)
- [FAR Subpart 32.9 — Prompt Payment](https://www.acquisition.gov/far/subpart-32.9)
