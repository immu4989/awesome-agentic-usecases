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
The destination must not already exist. Each JSON input must be at most 2 MB. The composite passes
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

For service-channel or workflow-specific limits, approve a
[version-1.1 cohort policy](../../../harness/README.md#catch-regressions-concentrated-in-a-declared-cohort).
It declares group membership and constraints explicitly. The Action checks every global and cohort
constraint; a global improvement cannot override a failed group constraint. Policy approval must
include the memberships and limits, not just the metric names. These checks do not authenticate
group labels, infer sensitive attributes, or certify fairness. Version-1.0 policies remain supported.

## Results and sharing

- Exit **0**: approved pins and context matched, all supplied constraints met, pack verified.
- Exit **1**: pack verified, but one or more supplied constraints failed. The pack is retained.
- Exit **2**: invalid input, pin/context mismatch, unsafe path, occupied destination, or failed verification.

The `reports` output identifies the requested directory, not a guarantee that it exists. An
interrupted or invalid run may leave no complete pack; run `aau evaluation-pack verify` before
consumption. Do not treat `continue-on-error` as passing policy review. Configure any required PR
check separately; this Action does not change branch protection or grant deployment authority.

Open `review.html` locally for readable findings. Keep all six pack files for verification.
**The pack contains complete unsanitized evaluation details.** Nothing is uploaded automatically.
If your organization elects to upload an artifact, review its privacy and retention first, use a
reviewed pinned upload Action, and account for repository and artifact access permissions.
