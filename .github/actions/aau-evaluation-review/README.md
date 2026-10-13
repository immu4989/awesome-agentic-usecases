# Saved evaluation review Action

Review a candidate's saved metrics against independently approved baseline/policy files. This
Action requires matching declared benchmark context, applies every metric constraint, creates an
offline reviewer pack, and verifies that pack before reporting a result. It runs no agent, model,
adapter, installation, or upload. Python 3.10+ and Bash must already be available on the runner.
The harness is imported from the same Action checkout, not downloaded from a package registry.

## Adopt in a trusted workflow

Select and audit a full commit SHA containing this Action. Replace `REVIEWED_FULL_COMMIT_SHA` below;
it is intentionally not a floating tag. GitHub documents [immutable Action pinning and input-injection precautions](https://docs.github.com/en/actions/reference/security/secure-use).

```yaml
- name: Review saved evaluation evidence
  uses: immu4989/awesome-agentic-usecases/.github/actions/aau-evaluation-review@REVIEWED_FULL_COMMIT_SHA
  with:
    policy: evaluations/approved-policy.json
    policy-sha256: ${{ vars.APPROVED_EVAL_POLICY_SHA256 }}
    baseline: evaluations/approved-baseline.json
    baseline-sha256: ${{ vars.APPROVED_EVAL_BASELINE_SHA256 }}
    candidate: evaluations/candidate.json
    output: evaluation-review-pack
```

Check out the evaluation files into the workspace first, using a separately reviewed immutable
checkout Action. Use read-only repository permissions and a no-secrets, isolated runner job for
untrusted contributions. Do not use `pull_request_target` to execute pull-request code.

All paths must be inside the workspace, relative, without `..`, control characters, or symlinks.
The destination must not already exist. Each JSON or CSV input must be at most 2 MB. The composite passes
inputs through environment variables rather than interpolating them into executable shell text.
It emits only constant labels, status, and numeric counts in the GitHub step summary; raw IDs,
metric names, source details, and input error text are not echoed there.

## Approve the baseline and policy independently

The two required SHA-256 values are hashes of **exact file bytes**, not the semantic JSON hashes
inside a review. Calculate them during review with `sha256sum` on Linux or `shasum -a 256` on macOS,
then store the approved values in a workflow-controlled location such as protected repository
variables. Whitespace changes invalidate these pins. Deliberately review and approve replacements.

Before replacing a policy pin, use
[`aau compare-eval-policies`](../../../harness/README.md#review-changed-obligations-before-approving-a-replacement-policy)
to identify relaxed limits, removed metrics/cohorts, changed membership, or reversed metric
directions. Exit 1 requests review; exit 0 is not approval. This diagnostic never changes the
approved variables or grants authority to update them. Review the complete policy as well as
the structural differences, including any newly added obligations.

**Do not compute the approved hashes from candidate-controlled files in the same production job.**
That merely blesses whatever the candidate supplies. The repository smoke test does this only to
exercise plumbing with synthetic fixtures, not to demonstrate independent approval. Protect the
workflow and variable administration separately; a contributor who can change both a file and
its approved hash can bypass this check. Repository variables are not secrets or signatures.

Both evaluations must contain matching, valid `evaluation_context` fingerprints. Missing legacy
context fails closed here; use the descriptive CLI for separately reviewed legacy comparisons.
Fingerprint equality does not prove execution, dependency completeness, or authentic measurements.
Synthetic fixtures and freely chosen limits do not establish production suitability.

### Review recorded observations without a separate import job

Set `input-format: recordings` when `baseline` and `candidate` use the
[`aau-recorded-observations` contract](../../../harness/README.md#import-recorded-scores-from-your-existing-evaluation-system)
(1.0 for scores only; 1.1 also retains optional per-attempt USD costs, elapsed seconds, and API-call counts).
The default remains `evaluations`; unknown formats fail rather than being guessed. The baseline
approval hash must match the **original recording file bytes**, not a precomputed normalized export.
The policy hash is unchanged. Approve those pins independently, as above.

Both recordings must explicitly carry matching evaluation context. The Action never invents
context, scoring, or runtime measurements. It imports locally, checks the same constraints, and
preserves an eight-file version-1.1 pack containing the original recording values and normalized
evaluations. Verification recomputes both conversions and the entire review. Outside the Action,
use `aau evaluation-pack verify PATH --require-recordings` when that chain is required.

The pack reserializes recording JSON values; it does not retain original input whitespace or byte
encoding. Preserve the original files separately for independent comparison against approved
file-byte hashes. No provenance, signer, collector identity, or actual execution is authenticated.

For service-channel or workflow-specific limits, approve a
[version-1.1 cohort policy](../../../harness/README.md#catch-regressions-concentrated-in-a-declared-cohort).
It declares group membership and constraints explicitly. The Action checks every global and cohort
constraint; a global improvement cannot override a failed group constraint. Policy approval must
include the memberships and limits, not just the metric names. These checks do not authenticate
group labels, infer sensitive attributes, or certify fairness. Version-1.0 policies remain supported.

## Produce a reviewer dossier from an independently approved diagnostic plan

Supply both `diagnostics` and `diagnostics-sha256` to retain the policy review alongside
repeated-run consistency and operating-cost views. Omitting both preserves the existing
policy-only workflow. Supplying just one, a wrong hash, an invalid plan, or an unsafe path fails
before the pack is created. The same workspace, symlink, control-character, and size restrictions
apply to this input.

```yaml
- name: Review evidence and preserve a diagnostic dossier
  uses: immu4989/awesome-agentic-usecases/.github/actions/aau-evaluation-review@REVIEWED_FULL_COMMIT_SHA
  with:
    policy: evaluations/approved-policy.json
    policy-sha256: ${{ vars.APPROVED_EVAL_POLICY_SHA256 }}
    baseline: evaluations/approved-baseline.json
    baseline-sha256: ${{ vars.APPROVED_EVAL_BASELINE_SHA256 }}
    candidate: evaluations/candidate.json
    diagnostics: evaluations/approved-diagnostics.json
    diagnostics-sha256: ${{ vars.APPROVED_EVAL_DIAGNOSTICS_SHA256 }}
    output: evaluation-dossier
```

The [diagnostic plan and complete offline example](../../../harness/README.md#hand-off-one-complete-offline-review-dossier)
define the joint observation criteria, recorded-subset sizes, and declared cost basis for each
source. Review these independently, including any difference from policy/cohort obligations.
Store its **file-byte** hash in the same independently controlled approval process used for the
baseline and policy. Do not calculate the approved hash from a candidate-controlled plan in a
production job. Protect the workflow inputs as well: removing both diagnostic inputs deliberately
selects policy-only mode, so a reviewer requiring a dossier should verify with
`aau evaluation-pack verify PATH --require-diagnostics`.

The Action produces and recomputes all eleven version-2.0 dossier files before success/failure
is reported. With `input-format: recordings`, it retains thirteen files and rechecks the complete
recording-to-review chain. Metric-only recordings do not acquire fabricated operating data;
version-1.1 measurements are validated and retained, with missing values kept unknown. The cost
bases in the approved diagnostic plan remain declarations, not invoice verification. Invalid
operating fields fail before a pack is created, including when diagnostics are omitted.
Use `--require-recordings --require-diagnostics` when both are required outside the Action.

**Diagnostics never override the policy gate.** The Action still exits 1 and retains failure
evidence when policy constraints fail, even if all diagnostic criteria pass. Favorable retry or
cost statistics grant no permission to deploy. A plan hash binds declared criteria and cost
labels, not their suitability, preregistration, authenticity, or reviewer authority.

The GitHub summary adds only a fixed dossier-status message. It does not echo diagnostic metric
names, source IDs, scores, cost labels, or invalid input text. No new token permissions, provider
credentials, network calls, package installations, or automatic artifact uploads are introduced.

## Gate scored CSV exports without losing their source chain

Set `input-format: csv` to create the
[28-file CSV review handoff](../../../harness/README.md#hand-off-two-csv-exports-as-one-verifiable-review)
directly in the Action. The default remains `evaluations`; existing normalized and recording
workflows keep their output formats. CSV mode requires **five independently approved byte pins**:
policy, baseline CSV, baseline mapping plan, candidate mapping plan, and diagnostics. The changing
candidate CSV is reviewed against those inputs; it is not an approved baseline.

```yaml
- name: Review scored CSV evidence against approved meanings and limits
  uses: immu4989/awesome-agentic-usecases/.github/actions/aau-evaluation-review@REVIEWED_FULL_COMMIT_SHA
  with:
    input-format: csv
    policy: evaluations/approved-policy.json
    policy-sha256: ${{ vars.APPROVED_EVAL_POLICY_SHA256 }}
    baseline: evaluations/approved-baseline.csv
    baseline-sha256: ${{ vars.APPROVED_EVAL_BASELINE_CSV_SHA256 }}
    candidate: evaluations/candidate.csv
    baseline-plan: evaluations/approved-baseline-map.json
    baseline-plan-sha256: ${{ vars.APPROVED_EVAL_BASELINE_MAP_SHA256 }}
    candidate-plan: evaluations/approved-candidate-map.json
    candidate-plan-sha256: ${{ vars.APPROVED_EVAL_CANDIDATE_MAP_SHA256 }}
    diagnostics: evaluations/approved-diagnostics.json
    diagnostics-sha256: ${{ vars.APPROVED_EVAL_DIAGNOSTICS_SHA256 }}
    output: csv-review-handoff
```

The [mapping-plan contract](../../../harness/README.md#convert-scored-csv-exports-without-losing-the-original-evidence)
declares the complete scenario census, repeat count, column meanings, and collection context.
The two maps may differ in header names but **both need independent approval**: an unreviewed
candidate mapping could reinterpret an unsafe-action column as a harmless score. Pinning only the
raw baseline CSV would not bind that meaning. Likewise, review metric units, policy thresholds,
diagnostic criteria, and cost-basis declarations. A byte pin records your review decision; it does
not prove the decision was sound.

Both mapping plans must contain valid, **matching declared evaluation context**. The Action
does not synthesize missing context. The repository's basic CSV examples deliberately omit it
and therefore work in the descriptive CLI but **do not pass this CI gate as-is**. Recover context
from collection; do not invent a shared fingerprint merely to make a check pass. Matching
declarations do not prove identical real-world conditions or authenticate observations.

CSV mode refuses missing maps/pins, absent diagnostics, changed approved bytes (including
whitespace), malformed rows, missing declared observations, context mismatch, unsafe paths,
and occupied destinations before creating output. Mapping inputs in non-CSV mode are rejected
rather than silently ignored. Existing CSV parsing, measurement, census, and size limits apply.
There is no inference, filtering, currency conversion, scoring, agent execution, or upload.

The complete folder retains both original CSV byte streams, both mappings, conversion evidence,
and the thirteen-file recorded-observation diagnostic review. Creation verifies the whole handoff
before returning the policy result. **A valid conversion or favorable diagnostic cannot override
a failed policy**. Verify outside GitHub using the matching harness:

```bash
aau csv-review verify csv-review-handoff
```

Open `csv-review-handoff/review/review.html`; keep all 28 files. Running `evaluation-pack verify`
on just the nested `review/` folder does not verify the outer CSV-to-recording links. The summary
adds only a fixed mapping/chain-verification message, never raw CSV headers or values. Original
CSV can contain sensitive data or spreadsheet formulas: it is not sanitized, and untrusted files
should not be opened in spreadsheet software. Source JSON values are reserialized, so keep
original approved JSON files separately if independently checking their **file-byte** pins later.
The handoff is unsigned; coordinated source-and-output replacement can still verify offline.
No new permissions, credentials, external Actions, or automatic uploads are introduced.

## Results and sharing

- Exit **0**: approved pins and context matched, all supplied constraints met, pack verified.
- Exit **1**: pack verified, but one or more supplied constraints failed. The pack is retained.
- Exit **2**: invalid input, pin/context mismatch, unsafe path, occupied destination, or failed verification.

The `reports` output identifies the requested directory, not a guarantee that it exists. An
interrupted or invalid run may leave no complete pack; run `aau evaluation-pack verify` before
consumption (`aau csv-review verify` for CSV handoffs). Do not treat `continue-on-error` as passing policy review. Configure any required PR
check separately; this Action does not change branch protection or grant deployment authority.

Open `review.html` locally for readable findings (`review/review.html` in CSV mode). Keep all six pack files for verification
(eight in recordings mode), or all eleven/thirteen files when diagnostics are requested; CSV mode requires all 28 files.
**The pack contains complete unsanitized evaluation details.** Nothing is uploaded automatically.
If your organization elects to upload an artifact, review its privacy and retention first, use a
reviewed pinned upload Action, and account for repository and artifact access permissions.
