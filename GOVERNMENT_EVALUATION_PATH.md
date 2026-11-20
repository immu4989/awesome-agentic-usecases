# An evaluation path for government teams

Research checked November 19, 2026. Start with a bounded mission and reproducible evidence,
not a claim that an open-source repository is “government ready.” This project has **not
established adoption by government agencies, independent accreditation, FedRAMP authorization,
an Authority to Operate, compliance, or demonstrated public savings**. Agencies retain their
own acquisition, security, privacy, accessibility, records, and operational decisions.

## Start offline, with no agency data

From a reviewed, trusted current checkout using Python 3.10 or newer:

```bash
pip install -e harness
aau grader-demo --out /tmp/agency-grader-example
aau lifecycle-cost-demo --out /tmp/agency-cost-example
aau evaluation-demo --out /tmp/agency-evidence-example
aau inspect-pack /tmp/agency-evidence-example/repaired --expect evaluation-review
```

Use new output paths if those directories already exist. Installation may need network access
for build/runtime dependencies; the demo and review commands themselves work offline. These
features require the current checkout/local wheel, not the older public PyPI release. Do not
install software or copy evidence onto agency systems without the necessary authorization.

The first two demo directories include a readable `README.md` and exact replay commands.
All demonstrations are constructed examples, not government field trials. A successful
synthetic run verifies the mechanism, not mission suitability or deployment authorization.

## Follow one mission through the evidence

| Question | Existing capability | What still requires accountable human review |
|---|---|---|
| What decision and affected users are in scope? | [Federal Mission Assurance](federal-mission-assurance/) and [Pilot Launch Pack](federal-pilot-kit/pilot-launch/) | Intended use, prohibited decisions, responsible roles, data permissions, appropriate impact determination |
| Does the grader reject real failures and accept legitimate solutions? | [Grader review](harness/README.md#audit-the-grader-before-trusting-its-scores) | Expert reference labels, ambiguity resolution, held-out design, and real-world relevance |
| Did the supplier use the requested requirements and baseline? | [Pinned evidence intake](harness/README.md#check-delivered-evidence-against-a-receiving-team-request) | Independent control of expected hashes; requirements that actually reflect the mission |
| What costs lie outside the model call? | [Lifecycle cost scenarios](harness/README.md#review-lifecycle-costs-without-turning-unknowns-into-zero) | Complete cost scope, credible quantities/rates, contract minimums, nonlinear prices, uncertainty, and affordability |
| Can the human-review process keep up? | [Finite queue replay](harness/README.md#replay-a-finite-review-queue-without-inventing-human-capacity) | Actual review quality, availability, accessibility, working conditions, and protected decision authority |
| Did a later pass hide an earlier failure or missing test? | [Ordered evidence history](harness/README.md#preserve-failed-and-missing-checkpoints-across-an-evidence-history) | Authentic chronology, incident handling, live monitoring, and whether retesting is adequate |
| What did the pilot teach us, including failures? | [Federal AI Lessons Exchange](federal-pilot-kit/lessons/) | Domain validity, disclosure/records review, and which lessons can transfer to another mission |

Do not merge these layers into one “approved” score. A valid evidence pack can document failure.
A fully computed cost scenario can describe an unaffordable or ineffective system. A simulated
review interval does not establish a correct human decision. Human reference labels can be wrong.

## Why this sequence

[GAO's AI acquisition review](https://files.gao.gov/reports/GAO-26-107859/index.html)
identifies challenges in technical expertise, requirements, early and ongoing testing, and
understanding AI costs. It also calls for systematic acquisition lessons. These findings motivate
making the existing tools usable as one review path; they do not demonstrate that our tools solve
those challenges in practice.

[OMB M-25-22](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf)
discusses competition, portability, testing, and evaluating ongoing value and costs. This guide
is not contract language or a determination of applicability; agency acquisition/counsel staff
must review current governing requirements.

[GSA's published AI strategy/compliance plan](https://www.gsa.gov/super-intelligence/resources/ai-strategies-and-compliance-plan)
describes independent evaluation, real-world-context testing, and continuing review for high-impact
uses. Our synthetic tests cannot substitute for those activities or for GSA's own approval process.

[GAO's Cost Estimating and Assessment Guide](https://www.gao.gov/products/gao-20-195g)
emphasizes scope, assumptions, data, sensitivity/risk analysis, documentation, and updates. The
new lifecycle-cost command implements only transparent linear scenario arithmetic and missing-cost
disclosure. It does not implement that entire methodology or establish conformity with it.

## What we need before claiming agency usefulness

1. An outside evaluator reproduces a bounded workflow from a clean environment and reports
   setup failures as well as successes. Our own CI is not independent reproduction.
2. A qualified domain team reviews the mission rubric, closest valid counterexamples, reference
   labels, and data representativeness. Protect independent validation data from tuning teams.
3. Authorized reviewers define a small pilot, explicit stop conditions, an appropriate comparator,
   and outcomes that include user burden, errors, recourse, accessibility, and whole-workflow cost.
4. A permitted, privacy-reviewed study measures those outcomes with uncertainty and reports
   adverse findings. No private-data collection, external outreach, or agency representation is
   performed automatically by this repository.
5. Only approved, accurate public summaries become case studies. Synthetic counts, GitHub stars,
   test totals, and model scores must never be presented as adoption or public-benefit evidence.

For now, contribute a public/synthetic reproducer through [CONTRIBUTING.md](CONTRIBUTING.md).
Never publish protected case records, procurement material, credentials, controlled information,
or personal data. A scanner's clean result is not authorization to disclose.
