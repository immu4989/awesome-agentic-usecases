# Human Baseline Lab — research and boundary notes

Last verified: **2026-08-27**

Next source review: **2026-11-27**

## Why this release

The repository already measures agent exactness, completion, safety, cost, latency, repeated-run
uncertainty, provenance, acquisition evidence, and public value. Its largest stated measurement
gap was the absence of a human comparator. Without one, an agent score cannot show whether the
system improves on the existing process, shifts burden, changes abstention, or merely looks good
beside other models.

Three current federal evidence needs make this more than a benchmark feature:

1. **Contextual evaluation is a distinct layer.** NIST AI 700-2 describes ARIA's model testing,
   red teaming, and field testing as separate sources of evidence. Field testing used scenarios,
   participant interaction, questionnaires, trained annotation, and a measurement crosswalk.
2. **Benefits need an existing-process comparator.** OMB M-25-21 says a high-impact AI impact
   assessment should state intended purpose and expected benefit with metrics or qualitative
   analysis, including costs, customer experience, or positive outcomes compared with existing
   agency processes. It also requires lifecycle reassessment and periodic human review where
   feasible.
3. **People are not just another test backend.** NIST's published ARIA materials describe human
   research-protection review. HHS explains that “evaluation” or “quality improvement” labels do
   not by themselves decide whether an activity is research involving human subjects; the purpose,
   design, jurisdiction, and institutional determination matter.

## Primary sources

- [NIST AI 700-2 — Assessing Risks and Impacts of AI: Pilot Evaluation Report](https://doi.org/10.6028/NIST.AI.700-2)
- [NIST Human-Centered AI program](https://www.nist.gov/programs-projects/human-centered-ai)
- [OMB M-25-21 — Accelerating Federal Use of AI through Innovation, Governance, and Public Trust](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf)
- [GAO AI Accountability Framework overview](https://www.gao.gov/artificial-intelligence)
- [HHS Federal Policy for the Protection of Human Subjects](https://www.hhs.gov/ohrp/regulations-and-policy/regulations/common-rule/index.html)
- [HHS OHRP: What is Human Subjects Research?](https://www.hhs.gov/ohrp/education-and-outreach/online-education/human-research-protection-training/lesson-2-what-is-human-subjects-research/index.html)
- [HHS OHRP Quality Improvement Activities FAQs](https://www.hhs.gov/ohrp/regulations-and-policy/guidance/faq/quality-improvement-activities/index.html)

## Source-to-feature map

| Source signal | Implemented response | Deliberate limit |
|---|---|---|
| NIST separates model, adversarial, and field evidence | The site and study contract keep all three layers conceptually distinct | AAU does not call its small local protocol a NIST ARIA field test |
| NIST uses scenarios, post-task questions, trained review, and measurement crosswalks | Blinded cases collect outcome, confidence, and task time against declared measures | The public schema omits demographics, dialogue logs, and free text to minimize public data |
| OMB asks for benefit compared with existing processes | Aggregate reports can bind the same suite to human and agent evidence | The delta is descriptive; no causal or savings claim is inferred |
| OMB calls for periodic human review and real-world target variables | The pack names reassessment and human-context evidence as required adaptation work | A synthetic practice cannot satisfy production monitoring |
| HHS assigns human-subjects determinations to responsible institutions | Human-observed sessions require a recorded institutional basis | AAU cannot verify or substitute for that determination |
| GAO emphasizes governance, data, performance, and monitoring | Reports preserve scope, uncertainty, privacy, and non-decision boundaries | No composite “trust score” is created |

## Premise corrections made before implementation

1. **“A human baseline is field testing.” — Incorrect.** A small blinded baseline can contribute
   contextual evidence, but NIST ARIA field testing is a much richer research design.
2. **“Synthetic tasks mean no human-subjects issue.” — Incorrect.** The task data may be synthetic
   while the collection still records information about living people. The institution decides
   applicability and review.
3. **“Anonymous means publishable.” — Incorrect.** Removing direct identifiers does not eliminate
   privacy, consent, labor, re-identification, or institutional obligations. AAU publishes only
   aggregate reports by default.
4. **“Human minus agent accuracy proves superiority.” — Incorrect.** A raw delta ignores sampling,
   task representativeness, dependence, workflow effects, harms, and operational context.
5. **“Generated reference sessions are a human baseline.” — Incorrect.** They test schemas,
   aggregation, privacy, and UI behavior. Every surface labels them synthetic.

## Human-protection gate

The generated study starts with `review_status: not_determined`. The CLI accepts real observed
session artifacts only when `protection_basis` records either an institutional determination or
institutional review. This is a fail-closed workflow field—not verification that the review was
adequate, authentic, or applicable.

The public browser is limited to an individual practice receipt. It never emits a publishable
participant session, stores progress, sends telemetry, or uploads answers. Organizations that
conduct a study must use their own approved consent, accessibility, withdrawal, retention,
security, labor, records, and incident processes.

## Interpretation boundary

The Human Baseline Lab is not an IRB tool, legal opinion, Common Rule determination, NIST
certification, OMB compliance assessment, workforce analytics product, employee-ranking system,
causal study, or deployment authority. It must not be used for hiring, firing, promotion,
performance management, protected-trait inference, or staffing-reduction decisions.
