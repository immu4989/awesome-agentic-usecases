# Human Baseline Lab

> Compare an agent with the existing human process—without turning people into a leaderboard.

Most AI evaluations answer whether one model beats another on a task. They do not answer whether
the system improves the process people use today, changes workload, encourages overconfidence, or
creates new abstention and review patterns. The Human Baseline Lab adds that missing comparator.

[Run the eight-task browser practice](https://immu4989.github.io/awesome-agentic-usecases/#human-baseline-lab)
or build a blinded study from any AAU public/synthetic suite with `aau-harness`.

## What ships

- A dependency-free `aau baseline` CLI in `aau-harness==1.4.0`.
- A deterministic preparer that splits participant-visible `study.json` from local
  `answer-key.json` and refuses to overwrite an existing study.
- Identifier-free session and aggregate-report contracts with three strict JSON Schemas.
- Exact outcome, abstention, median and p90 task time, confidence-calibration gap, Wilson interval,
  per-scenario modal agreement, and Fleiss' kappa.
- An optional same-suite agent-receipt comparison that rejects protocol mocks and makes no
  significance, causality, worker-replacement, or superiority claim.
- A browser-local eight-task practice that hides ground truth until completion and downloads only
  an aggregate individual practice receipt.
- Five **generated synthetic sessions** that test the aggregation protocol. They are not people
  and are never presented as observed human performance.

## Prepare a blinded study

```bash
python -m pip install aau-harness==1.4.0

aau baseline prepare ../harness/examples/byo-agent-suite.json \
  --id service-routing-human-baseline \
  --title "Service Routing Human Baseline" \
  --purpose "Compare the reviewed synthetic task with the existing process" \
  --out ./service-routing-human-baseline

aau baseline validate ./service-routing-human-baseline
```

The pack starts in `review_status: not_determined`. Synthetic protocol checks can proceed, but
real participant collection requires the responsible institution to decide what review,
consent, accessibility, withdrawal, privacy, labor, and records obligations apply. AAU does not
make or verify that determination.

## Record without collecting identity

Keep session files local and use random lowercase hexadecimal `anonymous_session_id` values. The
contract has no fields for names, email addresses, demographics, free text, employee identifiers,
or production records. A human-observed session is rejected unless its `protection_basis` records
an institutional determination or review.

The contract is intentionally narrow. An institution may need a richer approved instrument, but
those additional records should not be forced into a public open-source contribution format.

## Publish only aggregate evidence

```bash
aau baseline summarize ./service-routing-human-baseline \
  --session ./private-sessions/session-01.json \
  --session ./private-sessions/session-02.json \
  --agent-receipt ./public-agent-receipt.json \
  --out ./public-human-baseline-report.json

aau baseline validate ./public-human-baseline-report.json
```

The report contains session hashes and aggregate metrics, but no session identifier, outcome
choice, confidence response, raw timing row, or free text. Session hashes support local source
binding; they do not authenticate a participant or prove review.

## Read the comparison correctly

| Measure | What it can show | What it cannot show alone |
|---|---|---|
| Outcome exact rate + Wilson interval | Same-suite task correctness and uncertainty | Production accuracy or general capability |
| Abstain rate | How often the evaluator declines the available routes | Whether abstention was operationally appropriate outside the declared key |
| Median and p90 time | Task burden within the protocol | Workforce savings or causal efficiency |
| Confidence-calibration gap | Whether declared confidence tracks correctness in aggregate | Individual competence or employment fitness |
| Fleiss' kappa | Agreement beyond chance under the declared categories | Ground-truth validity or fairness |
| Human-minus-agent exact rate | A descriptive same-suite delta | Statistical superiority, replacement value, or a deployment decision |

Never use the Lab to rank employees, screen applicants, monitor individual productivity, infer
protected traits, or justify staffing reductions. Those uses are outside the contract.

## Reference artifacts

- [Eight-case synthetic suite](reference-suite.json)
- [Blinded five-file reference pack](reference-pack/)
- [Five generated protocol sessions](sessions/)
- [Engineered same-suite agent receipt](reference-agent-receipt.json)
- [Aggregate reference report](reference-report.json)
- [Study schema](human-baseline-study.schema.json)
- [Session schema](human-baseline-session.schema.json)
- [Aggregate report schema](human-baseline-report.schema.json)
- [Research and source ledger](../docs/HUMAN_BASELINE_RESEARCH_NOTES.md)

## Research boundary

NIST ARIA evaluates AI through separate model-testing, red-teaming, and field-testing layers and
uses questionnaires and trained assessment to study real-world interaction. OMB M-25-21 asks
agencies to state expected benefits using metrics or analysis compared with existing agency
processes. HHS explains that whether an evaluation is human-subjects research depends on its
purpose and context—not the label attached to it.

The Lab implements the portable evidence spine those sources motivate. It does not reproduce the
full NIST ARIA protocol, make an HHS Common Rule determination, provide legal advice, or claim
government approval.
