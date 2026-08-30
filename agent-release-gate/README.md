# AAU Agent Release Gate

> Test the change that is about to ship—not a generic model in isolation.

The Agent Release Gate turns an agent release into an inspectable evidence chain. It hashes the
declared model, policy, tools, identity, authority, egress, monitoring, rollback, and dependency
components; finds which boundaries changed; runs only the public or synthetic suites mapped to
those changes; preserves protected human approval; and emits a deterministic release pack.

```text
baseline ─┐
          ├─ component diff ─> impacted boundaries ─> exact suites ─> release evidence
candidate─┘                                            │                  │
                                                      twins         human approval
```

It does **not** deploy, sign, certify, approve, or continuously monitor an agent. A derived
`release_ready` status means only that the declared evidence contract passed. The organization
still owns identity verification, source review, production testing, change approval, deployment,
rollback, compliance, and authorization.

## Run the committed reference

```bash
python -m pip install -e harness

aau release assess \
  agent-release-gate/examples/baseline/release-manifest.json \
  agent-release-gate/examples/candidate/release-manifest.json \
  agent-release-gate/examples/release-policy.json \
  agent-release-gate/examples/evidence-plan.json \
  --command "python agent-release-gate/examples/reference_adapter.py" \
  --approval agent-release-gate/examples/approval.json \
  --out /tmp/aau-release-pack

aau release verify /tmp/aau-release-pack
```

The synthetic change moves a records tool from `human_only` to `prepare_only`, updates its exact
authority epoch, and tightens its policy. That change affects `authority`, `policy`, and `tools`, so
the gate runs one six-case suite with two legitimate twins and four stop/review paths. The
reference adapter scores 6/6, but the pack reaches `release_ready` only because a separate public
synthetic approval record names the protected human role. Its `identity_verified` field is
deliberately `false`.

## Commands

### Capture exact component bytes

```bash
aau release capture release-manifest.json --out release-snapshot.json
```

Paths must stay below the manifest directory. Symlinks, traversal, missing files, duplicate
components, oversized inputs, unsafe sharing flags, and unknown component or impact types fail
closed.

### Inspect a change before running anything

```bash
aau release diff baseline-snapshot.json candidate-snapshot.json --out release-diff.json
```

The diff reports added, changed, and removed components plus the union of their declared impact
tags. A required component removal is a blocking condition, even if every supplied suite passes.

### Exercise a real adapter

```bash
aau release assess baseline.json candidate.json policy.json evidence-plan.json \
  --command "python my_adapter.py" --approval approval.json --out release-pack
```

The same provider-neutral JSON request/response contract used by `aau evaluate` supports a local
command or HTTP endpoint. The request excludes expected answers and forbidden-action rules. Public
receipts exclude raw inputs, raw responses, reasoning, headers, credentials, and environment
variables.

`--mock` exists only to validate the protocol and pack. A mock result can never resolve to
`release_ready`; it is always held at `human_review_required`.

### Export government-oriented assessment evidence

Every pack contains `assessment-results.oscal.json`, an experimental, non-certifying mapping to
the NIST OSCAL Assessment Results shape. You can also export a decision separately:

```bash
aau release export-oscal release-decision.json \
  --assessment-plan https://example.gov/assessment-plan.json \
  --out assessment-results.oscal.json
```

The mapping preserves observations, findings, evidence digests, timestamps, unresolved reason
codes, and the AAU boundary. It is not a complete agency assessment plan, OSCAL validation,
control determination, FedRAMP authorization, FISMA determination, or Authority to Operate.

## Decision semantics

| Status | Exact meaning |
|---|---|
| `release_blocked` | Coverage, threshold, required-component, or mapping evidence failed |
| `human_review_required` | Tests passed but a protected review is absent, or the adapter was a mock |
| `release_ready` | Declared non-mock suites passed and the required approval-record structure is present |

`release_ready` is intentionally not called *approved*, *safe*, *compliant*, or *authorized*.

## Pack contents

| Artifact | Purpose |
|---|---|
| `baseline-snapshot.json` | Exact pre-change component digests |
| `candidate-snapshot.json` | Exact candidate component digests |
| `release-diff.json` | Recomputed change and impacted tags |
| `release-policy.json` | Tag-to-suite thresholds and protected review tags |
| `evidence-plan.json` | Public suite paths, tag coverage, and clean-twin counts |
| `receipts/*.json` | Privacy-bounded aggregate suite results |
| `approval.json` | Optional structural human-role record; identity remains unverified |
| `release-decision.json` | Fail-closed derived status and reason codes |
| `assessment-results.oscal.json` | Experimental non-certifying OSCAL mapping |
| `provenance.intoto.json` | Unsigned in-toto Statement binding the decision bytes |
| `manifest.json` | Exact bytes and SHA-256 for every other file |

`aau release verify` checks the file set, rejects symlinks and unmanifested files, verifies every
byte digest, recomputes snapshots' embedded hashes, recomputes the diff and decision, regenerates
the OSCAL mapping, and checks that the in-toto subject binds the exact decision bytes.

## Adopt it safely

1. Declare components whose change can alter behavior, authority, destinations, monitoring, or
   recovery. Do not publish private configuration merely to use the gate; publish hashes and safe
   synthetic suites.
2. Map every impact tag to an owned test suite. An unmapped change blocks.
3. Include legitimate twins so a deny-all adapter cannot pass.
4. Use a real command or endpoint adapter. Treat `--mock` only as a protocol test.
5. Keep approvals in your authoritative change system and bind an approved record digest. The AAU
   public fixture deliberately does not authenticate the approver.
6. Verify the pack, attach your organization-controlled signature or attestation, then apply your
   own deployment and rollback process.

For GitHub Actions, use the repository's
[`aau-release` composite action](../.github/actions/aau-release/) and pin it to an immutable commit
SHA. The action assesses the exact change, verifies the pack, and exposes its path for your own
artifact attestation or deployment workflow; it does not authorize the subsequent deployment.

Read the [1.0 contract](SPEC.md), [threat model](THREAT_MODEL.md), and
[research notes](RESEARCH_NOTES.md). The strict public manifest and policy schemas are available as
[`release-manifest.schema.json`](release-manifest.schema.json) and
[`release-policy.schema.json`](release-policy.schema.json).
