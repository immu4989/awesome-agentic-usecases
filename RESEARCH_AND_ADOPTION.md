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

November 19 candidate-family follow-up: [Predeclared candidate uncertainty](harness/README.md#reserve-uncertainty-across-all-planned-candidates)
reserves a single Bonferroni allocation across every planned candidate and scope, even when submissions
are missing. Complete submitted evaluations must match the approved scenario/scorer/configuration
fingerprints and census; failed repeats remain failed scenario bundles. Fixed benchmarks have no
population bounds. Synthetic examples and exact small-family outcome enumeration exercise the
mechanism, including correlated candidates and overlapping groups. This does not verify sampling,
preregistration, genuine execution, superiority, or government suitability; additional/adaptive
candidates and repeated looks are outside this finite fixed-horizon family.

November 19 paired-grader follow-up: [Grader comparison](harness/README.md#compare-grader-changes-without-mistaking-abstention-for-correction)
retains both judgment files against the same pinned reference/rubric/census and an independently pinned
baseline. It distinguishes corrections, new errors, lost decisions, and unresolved references on every
planned item/criterion pair. Common-decided agreement is shown beside full-census coverage; calibration,
validation, and overlapping groups are never pooled. Synthetic examples expose a perfect-agreement
abstention/omission trap and a net-score gain that conceals a new false failure. This is descriptive
change review, not statistical significance, grader certification, human-study evidence, or a release gate.
Independent domain validation and protected holdouts remain unresolved requirements.

November 19 coverage follow-up: [Declared condition coverage review](harness/README.md#find-untested-conditions-before-trusting-averages)
adds a full Cartesian condition grid over a supplied case inventory and audited evaluation rows.
Repeated attempts do not inflate distinct-case counts; missing classifications and unavailable
scenario fingerprints remain uncertain; explicit exclusions retain their rationale. A source-retaining
offline packet and three no-key examples distinguish coverage gaps, uncertainty, and a met declared
floor, even with identical perfect supplied scores. This implements a test-design bookkeeping layer,
not a representative sample, statistical-power analysis, quality threshold, or independent study.
The linked contract cites NIST AI RMF 1.0 and Apple's dataset-design guidance, and separates our
engineering choices from their recommendations. Independent reproduction remains the adoption gap.

November 19 update: [Inspect JSON import](harness/README.md#reuse-inspect-sample-scores-without-executing-the-log)
implements the first bounded native adapter: retained raw bytes, receiver-pinned mappings, exact
sample/epoch census, missing-score coverage, and rejection of unsupported error/edit states. An
upstream mock-model fixture declaring Inspect `0.3.100` is retained with its license, original hash,
and local hash after appending a final newline. This is one compatibility observation, not
all-version support or independent reproduction.
The next adapter work should extend real exporter/version coverage and preserve richer error/edit
evidence, rather than relax rejected logs into apparently successful results.

November 19 diagnostic follow-up: the existing Inspect command now retains a separate
[incomplete-evidence review packet](harness/README.md#review-incomplete-inspect-evidence-without-repairing-it).
It accounts for the entire planned sample/epoch grid, duplicates, outside-plan rows, scored errors,
limits, retry/invalidation markers, and score edits including unmapped scorers. The strict converter
is unchanged: the diagnostic never turns interrupted evidence into an evaluation. Source bytes and
JSON pointers make findings reproducible without running supplied code. The existing upstream mock
fixture is checked, plus synthetic failure mutations and a complete small census oracle; broader
native exporter/version coverage and independent reproduction are still pending.

November 19 handoff follow-up: [Pinned Inspect policy review](harness/README.md#hand-off-inspect-logs-through-a-receiver-pinned-policy-review)
connects both original logs to the existing policy/diagnostic/budget review in one folder. A single
independently retained request pin controls the exact baseline bytes, both mappings, policy,
diagnostics, and optional budget. Whole-folder replay checks cross-component relationships, not
just individually valid nested packs. The no-key examples retain an authorization failure despite
better completion, a met score policy, and an unknown required cost budget. This reduces manual
evidence assembly; it does not demonstrate reduced staff burden, genuine source execution, task
comparability, or adoption. Real-user observation and independent reproductions remain pending.

November 19 Promptfoo follow-up: [Native export import](harness/README.md#reuse-promptfoo-exports-without-confusing-failed-assertions-with-execution-errors)
adds a bounded second exporter profile. A pinned upstream version-3 export declaring Promptfoo
`0.118.10` is retained byte-for-byte with its license. The importer checks all planned test/column
pairs and explicit prompt/provider identities, projects one reviewer-selected column, and distinguishes
ASSERT failures from execution errors. Missing named scores remain absent; aggregates and inferred
operating/context data are excluded. Synthetic failure tests and a clean installed-wheel demo complement
the fixture. Broader exporter/version coverage, authentic execution, and independent reproduction remain
unproven; no Promptfoo code or model is executed by import.

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

November 25 source-linked index follow-up: the [evidence index](harness/README.md#hand-off-separate-reviews-with-a-receiver-pinned-evidence-index)
now routes four additional flat profiles: Inspect/Promptfoo conversions and diagnostics. Separate
source, plan, and evaluation byte roles prevent a valid diagnostic for another log or mapping from
standing in for the requested evidence. A diagnostic can verify while its source remains rejected
for conversion; required missing conversions stay missing. Policy intake's existing matching-context
requirement is unchanged, so source imports without that evidence remain incomplete for that request.
Eight new constructed examples expose those distinctions; native-producer probes exercise interrupted
delivery retention. This is bounded interoperability and bookkeeping, not reconstructed history,
independent reproduction, agency adoption, or measured burden reduction.

November 24 Promptfoo handoff follow-up: [Receiver-pinned policy review](harness/README.md#hand-off-promptfoo-exports-through-a-receiver-pinned-policy-review)
connects both original exports to the existing score-policy, diagnostics, and optional budget layers.
One independent request pin binds baseline bytes, selected columns, mappings, and requirements;
whole-folder replay rejects unrelated nested components even when their own manifests are valid.
Constructed examples retain an authorization regression and an unknown required operating budget.
Native compatibility checks select contrasting columns from one synthetic SDK export, not independent
systems or executions. This reduces manual assembly steps by construction; it is not measured staff
savings, scoring validity, government adoption, or deployment authorization. Domain review and
independent reproduction remain pending.

November 24 incomplete-evidence follow-up: [Promptfoo diagnostic review](harness/README.md#review-rejected-promptfoo-evidence-without-repairing-it)
preserves the entire planned test/column census and every supplied row, including malformed,
duplicate, and outside-plan evidence. Errors can coexist with available scores; summary counts
and repeat markers remain separate findings. The existing strict converter still rejects the same
unsupported states. The diagnostic has no evaluation output, and exact replay does not authorize
conversion or deployment. An exhaustive small census oracle and native producer-error/repeat checks
complement synthetic mutations. This supports reviewing rejected deliveries, not hidden-edit detection,
complete attempt history, valid grading, independent reproduction, or demonstrated staff savings.

November 22 prospective-design follow-up: [Fixed-horizon evaluation planning](harness/README.md#plan-a-fixed-horizon-evaluation-before-spending-on-runs)
separates a zero-failure sample reference from the chance of meeting a statistical criterion under
an assumed nonzero failure rate. Exact integer/rational search covers bounded sample sizes and failure
cutoffs, reserving error across declared candidate/scope cells without counting repeats as independent
cases. A 59-bundle zero-failure reference in the synthetic example has only 55.27% qualification
probability at its assumed rate; the requested 80% design instead needs 124 bundles with a cutoff of two.
These are hypothetical calculations, not measured benefits or validated sampling assumptions.
[GAO's acquisition report](https://files.gao.gov/reports/GAO-26-107859/index.html) identifies testing,
requirements, and overall-cost challenges; that motivates making study assumptions reviewable before
execution. [NIST's operating-characteristic method](https://www.itl.nist.gov/div898/handbook/pmc/section2/pmc232.htm)
supplies the binomial formulation, not endorsement of this tool. Joint scope feasibility, domain review,
actual candidate/rubric identity, approved sampling frames, and independent reproduction remain pending.

November 22 offline-transfer follow-up: [BagIt evidence transfer](harness/README.md#transfer-evidence-with-independently-checkable-bagit-checksums)
adds an interoperable directory envelope without interpreting payload claims. Research source:
[RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html), an informational specification, not an
Internet Standard or government approval. Our bounded canonical profile binds original file bytes,
empty directories, and a separately retained transfer pin. A [seven-case compatibility probe](harness/compatibility/bagit/README.md)
uses pinned Library of Congress `bagit` 1.9.0 to distinguish checksum corruption from directory loss
and a fully recomputed substitution. Full native evidence replay remains a separate step; a valid
transfer can retain a failed policy. No encryption, signatures, records qualification, or adoption
claim is made. Remaining work includes independently performed reproductions and receiver-defined
handling/retention requirements before any real agency evidence exchange.

November 22 evidence-handoff follow-up: the [receiver-pinned evidence index](harness/README.md#hand-off-separate-reviews-with-a-receiver-pinned-evidence-index)
joins existing policy, coverage, and paired-system workflows without combining their outcomes.
Every declared item is retained as verified, missing, control-mismatched, or verification-failed;
explicit byte bindings prevent silently treating different exported evaluations as the same input.
The whole receiver request is independently pinned. A complete example deliberately retains a
failed policy: successful delivery verification is not a successful system or agency approval.
Original files, including invalid packet contents, remain local and require disclosure review.

November 22 paired-system follow-up: [Paired candidate review](harness/README.md#compare-paired-systems-without-hiding-new-failures)
compares complete matched scenario bundles, preserving improvements, newly introduced failures,
shared passes, and shared failures. Optional exact conditional McNemar inference uses a predeclared
two-system/group family with Bonferroni adjustment; repeated runs never enlarge the paired sample.
Fixed benchmarks receive no p-values. Source bytes, summary mismatches, and failed repeats remain
available in an offline replayable packet. This is a diagnostic, not equivalence, practical-importance
evidence, an effect-size interval, a causal claim, or an acquisition/deployment decision.

November 24 native-producer follow-up: the [Promptfoo compatibility exercise](harness/compatibility/promptfoo/README.md)
executes locked Promptfoo `0.126.0` with fixed synthetic local providers and deterministic
assertions. Four native exports exercise complete scores, absent named metrics, execution
errors in an unselected column, and repeated observations. Seven importer/replay checks use
the installed AAU wheel; mapping controls are fixed independently of the received rows.
Network-denial tripwires recorded and blocked a telemetry-disabled notification attempt even
with the disable flag set. This is an observed pinned-release behavior, not zero attempted
network traffic or an OS-enforced air gap. Native files remain local. Broader producer coverage,
independent reproduction, scoring validity, and approved handling of real evidence remain pending.

November 20 native-producer follow-up: the [Inspect interoperability exercise](harness/compatibility/inspect/README.md)
executes pinned Inspect `0.3.291` with fixed mock tasks, checking native JSON scores/census, an official
binary-format round trip, strict rejection of interrupted evidence, and replay of its diagnostic.
It supplements the historical upstream fixture with actual producer execution and runs separately
from AAU's passive runtime importer. Local results passed all four checks; CI repeats the exercise
without inherited model credentials or publishing logs. Token usage is constructed, dependencies
are not fully hash-locked, and normal producer cache writes require filesystem permission. This is
bounded maintainer interoperability evidence, not live-model quality, independent reproduction,
all-version support, or evidence of government adoption.

November 19 report-access follow-up: [Offline report interaction checks](harness/browser-tests/README.md)
centralize named keyboard-scroll groups and row/column semantics across the principal review reports,
add policy section navigation, and exercise nineteen fixed synthetic reports at desktop and narrow widths,
including subsequent paired-grader, candidate-family, paired-system, and evidence-index reports.
Deliberately broken focus/name/header/reflow controls must be detected. The public synthetic packets
are regenerated with their matching manifests and archives; source scores and policy outcomes do not
change. This is targeted Chromium behavior testing, not assistive-technology usability evidence or
WCAG/Section 508 conformance. The linked manual-test checklist records the remaining evaluation work.

November 19 offline-adoption follow-up: the [offline installation kit](harness/README.md#prepare-an-offline-installation-kit)
connects the existing source/archive audit to a prepared local wheel, hash-locked no-index install,
standalone verification, and installed first-party source comparison. Python 3.11+ is the bounded
dependency-free profile; Python/pip/venv and organizational approval remain receiver prerequisites.
The verifier script and manifest each need an independently checked hash before executing transferred
code. A fresh-environment smoke test is included in CI. This is a maintainer-tested installation path,
not a public release, OS-enforced air-gap assessment, independent reproduction, or proof of agency use.

“Bring one synthetic example where your judge accepted a failure or rejected a valid result.
We will help make the disagreement reproducible, preserve uncertainty, and turn confirmed
scorer bugs into regression tests.”

Use the [contribution guide](CONTRIBUTING.md#help-test-the-judges). Prefer a small, reviewable
reproducer over a leaderboard submission. Credit outside contributors accurately and publish
negative findings as well as successes. No star/fork incentive should influence acceptance,
reference labels, or reported outcomes.
