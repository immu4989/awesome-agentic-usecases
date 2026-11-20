# Research and adoption priorities

Research checked November 8, 2026. This is a working roadmap, not a claim of leadership,
government approval, institutional partnership, or guaranteed attention/stars.

Government-adoption follow-up, November 19, 2026: the
[agency evaluation path](GOVERNMENT_EVALUATION_PATH.md) connects existing tools and adds
[lifecycle-cost scenario review](harness/README.md#review-lifecycle-costs-without-turning-unknowns-into-zero).
The linked guide records the official sources and remaining adoption boundaries. This addresses
cost-scope transparency; it does not substitute for independent reproductions or partner studies.

## What leading teams are doing

**Validate the measurement.** Anthropic recommends domain-relevant tasks, balanced positive
and negative cases, careful grader validation, and reading transcripts when results look wrong.
Model judges should be checked against expert judgments rather than accepted on their own.
[Primary source](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).

**Separate execution from scoring.** The UK AI Security Institute's Inspect supports deferred
scoring and rescoring saved logs, allowing scorer development without regenerating model
outputs. Rescoring can execute code/use endpoints recorded in logs, so its documentation also
requires trusted inputs. [Primary source](https://inspect.aisi.org.uk/scoring-workflow.html).

**Make evidence traceable.** NIST's evaluation-probe project investigates rubric-based checks
against a human-curated document corpus and structured trails linking claims to supporting
evidence. This is ongoing research, not a certification scheme.
[Primary source](https://www.nist.gov/programs-projects/building-evaluation-probes-agentic-ai).

**Treat benchmark exposure as a measurement threat.** Anthropic documented evaluation-aware
behavior on BrowseComp, including attempts to locate benchmark answers. Publishing tests is
useful for reproducibility but does not make them suitable as a secret holdout.
[Primary source](https://www.anthropic.com/research/eval-awareness-browsecomp).

Our inference: this repository's next advantage should be **helping other teams establish
credible evidence with less integration work**, not expanding the number of loosely validated
features. No source above establishes that this repository is effective in production.

## Implemented in this contribution

The [grader-review workflow](harness/README.md#audit-the-grader-before-trusting-its-scores)
adds one missing measurement layer: recorded grader judgments versus separately pinned,
fallible reference labels. It retains unknown references, missing judgments, subgroup false
passes/failures, exact denominators, and separate calibration/validation partitions. Duplicate
declared evidence fingerprints are rejected; actual holdout secrecy and semantic independence
still require a study design. The installed no-key demo has four intentionally contrasting
outcomes. The contributor guide now invites synthetic grader-disagreement cases.

This complements, rather than replaces, the existing Human Baseline Lab (human task performance)
and service-scorer challenge (constructed contract conformance). It does not assess the correctness
of the reference labels, call an LLM judge, or certify one. It currently accepts binary judgments
only. Continuous scores and multi-rater adjudication need separate methods.

November 19 follow-up: [Reference-label review](harness/README.md#preserve-reviewer-disagreement-before-exporting-reference-labels)
adds a separate recorded-panel protocol for those reference labels. Missing/abstained ratings and
pass/fail conflicts remain visible; a majority does not resolve a dispute. Explicit adjudications
bind a complete rating snapshot, retain original votes and reasons, and export the existing grader
reference/plan contracts. The offline HTML packet and no-key demo connect label provenance to the
grader audit. This is not a human study, verified expertise, an inter-rater reliability estimate, or
proof of reference correctness. The linked guide records the primary sources and our interpretation.

## Next investments, in order

November 19 update: [Inspect JSON import](harness/README.md#reuse-inspect-sample-scores-without-executing-the-log)
implements the first bounded native adapter: retained raw bytes, receiver-pinned mappings, exact
sample/epoch census, missing-score coverage, and rejection of unsupported error/edit states. An
upstream mock-model fixture declaring Inspect `0.3.100` is retained with its license, original hash,
and local hash after appending a final newline. This is one compatibility observation, not
all-version support or independent reproduction.
The next adapter work should extend real exporter/version coverage and preserve richer error/edit
evidence, rather than relax rejected logs into apparently successful results.

| Priority | Community benefit | Evidence required before calling it complete |
|---|---|---|
| 1. Native export adapters | Use existing Inspect/other evaluation logs without hand-converting every field | Versioned fixtures from each supported exporter; raw-source retention; tests for missing scores, aborted runs, repeated IDs, and rubric drift; no executing supplied log code |
| 2. Independent reproduction sprint | Find assumptions maintainers and synthetic tests miss | At least three unaffiliated teams reproduce one narrow workflow, report setup time and failures, and permit an accurate public summary; do not count our own forks as independent adoption |
| 3. Verified install-to-first-result path | Turn curious visitors into successful users | Fresh-machine tests for documented supported Python versions; a reviewed package release matching the docs; first-time-user observation of setup friction, not an invented conversion metric |
| 4. Domain-reviewed reference sets | Make results useful beyond constructed examples | Domain experts review rubrics and closest valid twins, record disagreements and label provenance, and approve public/synthetic examples; no implied legal or clinical validation |
| 5. Prospective partner studies | Establish whether a workflow actually helps people | Predeclared outcomes, an appropriate comparator, representative cases, permission/privacy review, and uncertainty reporting; measure corrections, burden and missed cases, not just model scores |
| 6. Exposure-aware challenge maintenance | Keep public tests useful without overstating generalization | Public development suites distinguished from controlled validation sets; access controls outside this repo; dataset versioning and refresh procedures; no claim that hashes prevent contamination |

The release process already has package-content and installed-wheel checks. The remaining
adoption gap is a deliberately reviewed public release and evidence from new users—not another
package manifest. Do not silently publish credentials, releases, participant data, or private
traces to satisfy these milestones.

## A useful community invitation

“Bring one synthetic example where your judge accepted a failure or rejected a valid result.
We will help make the disagreement reproducible, preserve uncertainty, and turn confirmed
scorer bugs into regression tests.”

Use the [contribution guide](CONTRIBUTING.md#help-test-the-judges). Prefer a small, reviewable
reproducer over a leaderboard submission. Credit outside contributors accurately and publish
negative findings as well as successes. No star/fork incentive should influence acceptance,
reference labels, or reported outcomes.
