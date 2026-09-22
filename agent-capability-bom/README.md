# Agent Capability & Authority Bill of Materials

> An SBOM can tell you what software is present. An AABOM tells you what the agent can reach,
> what it may attempt, how long that authority lasts, where data may flow, who can stop it, and
> which evidence supports the release.

The **Agent Capability & Authority Bill of Materials (AABOM)** is an open, vendor-neutral
operational inventory for tool-using agents. It complements SBOM and AI/ML-BOM standards with the
runtime relationships that determine agent blast radius:

```text
model ──> tool ──> operation ──> resource scope ──> data route
              ╲          bound by          ╱
               authority lease + expiry + revocation
                              │
                    accountable human owner
                              │
                monitor + safe stop + rollback + evidence
```

It is deliberately **not** a credential, permission grant, live entitlement check, policy engine,
security assessment, certification, compliance record, deployment approval, or Authorization to
Operate. A valid inventory still resolves to `human_review_required`.

## See one authority change

The committed public synthetic pair changes a records tool from read-only to prepare-only and adds
one draft operation plus one resource scope. The model did not change. A generic model card or
dependency SBOM would miss the meaningful deployment delta; `aau bom diff` reports nine
authority-widening facts, including every newly reachable operation-scope relationship.

```bash
python -m pip install -e harness

aau bom validate agent-capability-bom/examples/candidate.json
aau bom diff \
  agent-capability-bom/examples/baseline.json \
  agent-capability-bom/examples/candidate.json
```

Expected derived status: `review_required`, with no trust score and no implied approval.

| Change found | Why an owner needs it |
|---|---|
| tool side effect `read → prepare` | The agent can now create consequential work product |
| tool operation added | A new callable action entered the deployment |
| tool resource scope added | The reachable object set widened |
| authority operation added | The lease now permits the action |
| authority resource scope added | The lease now permits the added object set |
| three tool operation-scope bindings added | The tool API now exposes three additional exact combinations |
| one authority operation-scope binding added | The agent lease can reach the draft action only at its draft scope |

If protected human approval is removed, the diff changes to `blocking_boundary_loss`. A moving
15-minute lease does not appear as an extension merely because its timestamps moved; only a longer
duration triggers `AUTHORITY_WINDOW_EXTENDED`.

## Stop accidental Cartesian authority

AABOM 1.1 keeps the readable `operations` and `resource_scopes` inventories, but requires exact
`operation_scope_bindings` at both the tool and authority layers. Their flattened unions must agree,
and an authority binding must exist in the referenced tool. A request can therefore be allowed for
`records.search @ cases/public/*` and `records.prepare_draft @ cases/public/drafts/*` without also
granting search over drafts or draft preparation over the broader public scope.

This is a practical response to the combination hazard described by OAuth Rich Authorization
Requests: values combined in one authorization object form a product, while separate objects can
express finer rights. The AABOM profile is not an OAuth authorization-details type, token, policy
engine, or enforcement point; it borrows the relationship lesson and makes it testable offline.

## Find excess authority without auto-removing it

The **Least-Authority Planner** compares one exact AABOM with privacy-bounded public, synthetic, or
authorized aggregate action observations. It finds the negative space—granted operations and
resource scopes that no allowed event used—then creates the evidence agenda required before a
human-owned narrowing change.

```bash
aau bom plan-reduction \
  agent-capability-bom/examples/candidate.json \
  agent-capability-bom/examples/authority-observation.json \
  --out /tmp/authority-reduction-plan.json

aau bom verify-reduction-plan \
  /tmp/authority-reduction-plan.json \
  agent-capability-bom/examples/candidate.json \
  agent-capability-bom/examples/authority-observation.json
```

The reference observation covers three reviewed synthetic scenarios and four metadata-only events.
It sees two of three granted operations, two of three scopes, and two of three exact relationships.
A blocked draft attempt does not count as legitimate use, so the planner flags one operation, one
scope, and their draft relationship for investigation—but removes **zero** permissions.

Every candidate requires six next proofs: domain-owner need review, representative holdout suite,
legitimate clean twin, staging denial test, rollback rehearsal, and separate change approval.
Absence in bounded traces never proves that a grant is unnecessary, scenario coverage never proves
production workload coverage, and the planner emits no executable policy.

The transport shape is published as
[`authority-observation.schema.json`](authority-observation.schema.json). It intentionally excludes
arguments, results, prompts, reasoning, credentials, and operational payloads; OpenTelemetry warns
that tool-call arguments and results may contain sensitive information, so this public profile
retains only normalized identifiers, sequence, operation, scope class, and decision.

## Compile the inventory into executable authority twins

To start integrating your own policy engine, generate a workspace:

```bash
aau bom init-adapter agent-capability-bom/examples/candidate.json --out my-authority-adapter
```

The workspace includes the copied inventory, generated suite, adapter stub, and runnable commands.
Implement the stub's `decide()` function using your staging policy. It initially blocks every
case with `ADAPTER_NOT_IMPLEMENTED`, so creating a starter never manufactures passing evidence.
Existing directories are not overwritten. Use the current repository harness for this command.

An inventory becomes more useful when its claims can challenge an enforcement point. The
**Authority Conformance Compiler** deterministically turns every authority/tool intersection into
legitimate clean twins, then changes one boundary at a time: time window, revocation, delegation
depth, human approval, operation, resource scope, or operation-scope relationship.

```bash
aau bom generate-conformance \
  agent-capability-bom/examples/candidate.json \
  --out /tmp/authority-suite.json

aau bom run-conformance \
  agent-capability-bom/examples/candidate.json \
  /tmp/authority-suite.json \
  --command "python my_authority_adapter.py" \
  --adapter-artifact my_authority_adapter.py \
  --workspace . \
  --out /tmp/authority-receipt.json

aau bom verify-conformance \
  /tmp/authority-receipt.json \
  agent-capability-bom/examples/candidate.json \
  /tmp/authority-suite.json \
  --adapter-artifact my_authority_adapter.py \
  --workspace .
```

The committed synthetic candidate compiles to **19 cases**: 3 legitimate clean twins and 16
single-boundary violations. Two relationship twins prove that independently recognized operations
and scopes remain blocked when their exact combination is absent. The public command adapter
returns 19/19 exact decisions with zero
unsafe allows and zero legitimate blocks. A deny-all adapter fails because the clean twins catch
availability destruction; an allow-all adapter fails on the violation twins.

The adapter receives only `protocol_version`, `case_id`, and the normalized authority input.
The request `case_id` is a fresh random UUID: it never carries the suite's readable failure label,
and adapters must not use it as an answer lookup key. The receipt retains the original readable
suite ID so reviewers can trace failures. Request IDs are not retained and do not affect receipt
reproducibility. This removes a label shortcut; the public inputs and suite remain visible, so it
does not create a hidden benchmark or prevent deliberate memorization. The adapter
never receives expected answers, credentials, arguments, results, prompts, or tool payloads, and
the compiler never invokes a tool. The command is parsed without a shell. The committed
[`reference-conformance-suite.json`](examples/reference-conformance-suite.json) and
[`reference-conformance-receipt.json`](examples/reference-conformance-receipt.json) are bound to
the exact BOM, suite, and executed adapter bytes. Receipt 1.2 records a workspace-relative artifact
path, SHA-256, byte length, launch position, and before/after equality; the runner rejects a command
that names some other file, a symbolic/out-of-workspace artifact, or an adapter that changes while
the cases run. Verification recomputes case coverage, expected decisions, reason codes, exactness,
both asymmetric failure counts, and the current artifact digest.

The readable suite and receipt schemas publish their transport shapes. The strict CLI remains the
normative validator because it also recomputes cross-file and semantic invariants. Reference
adapter success is a protocol self-test. Command-adapter success is bounded evidence against the
declared synthetic contract—not proof of production enforcement, policy correctness, safety,
identity, provenance, compliance, certification, deployment approval, or an ATO. The command text
is deliberately omitted; equal file observations before and after a run do not prove continuous
immutability or that those bytes were deployed.

For CI, both `run-conformance` and `verify-conformance` exit **0** for passing evidence, **1** for
a valid receipt recording failed evaluations, and **2** for malformed or mismatched evidence.
Verification recomputes a receipt; it does not rerun the adapter. Preserve a failed receipt for
diagnosis, but require exit 0 before accepting the conformance gate. Reference-adapter results
remain protocol self-tests regardless of exit status.

Command `--timeout` is a per-case duration in seconds, greater than zero and at most 300.
Non-finite values and invalid types are rejected before launch. The default remains 10 seconds;
this is a per-process timeout, not a whole-suite deadline or process-tree sandbox.

## Diagnose a failed authority evaluation

```bash
aau bom explain-conformance receipt.json inventory.json suite.json \
  --adapter-artifact adapter.py --workspace . --out failure-report.json
```

This verifies the receipt and current adapter bytes before producing a deterministic JSON report.
It separates unsafe allows, legitimate actions blocked, and reason-code mismatches; each mismatch
lists missing and unexpected reason codes without copying request inputs. Receipt, inventory, and
suite digests identify the exact evidence explained. A failed evaluation still exits 1 after
writing the report; malformed evidence exits 2 without generating a report. It does not rerun the
adapter or infer production causes. The current repository harness provides this command.

## Compare a fix against its baseline

```bash
aau bom compare-conformance before.json after.json inventory.json suite.json \
  --before-artifact baseline/adapter.py --after-artifact candidate/adapter.py \
  --workspace . --out comparison.json
```

Use this after evaluating two adapter versions against the **same inventory and suite**.
Keep both entrypoints at their recorded workspace-relative paths; command receipts require
both corresponding artifacts. The comparison verifies each receipt and artifact before writing.
It lists introduced, resolved, changed, and persistent failures case by case, catching regressions
that an unchanged aggregate score would hide. Unchanged passing cases are omitted.

The report retains evidence digests and before/after counts, not request payloads. Exit 0 means
the candidate passed every synthetic case; exit 1 means candidate failures remain, even if no
new failures appeared. Invalid or mismatched evidence exits 2 without writing a new report.
Existing output files are never overwritten. This is an offline evidence comparison, not a
rerun, causal explanation, or deployment approval. Changes to the inventory or suite require a
separate evaluation; they cannot be treated as a like-for-like comparison here. Available in
the current repository harness.

## Share an offline reviewer report

Both `explain-conformance` and `compare-conformance` accept `--format html`:

```bash
aau bom explain-conformance receipt.json inventory.json suite.json \
  --adapter-artifact adapter.py --workspace . --format html --out review.html
```

Open the file locally in a browser or print it to PDF. The single-file report uses no scripts,
fonts, images, or external requests. It presents case-level findings, reason differences,
artifact-check status, evidence digests, and the limits of the evaluation. Supplied values are
HTML-escaped. JSON remains the default for automation; HTML preserves the same exit codes and
refusal to overwrite existing files. Invalid evidence cannot generate a new HTML report.

The page is a readable presentation, **not a signed or independently verified artifact**. Keep
the original inventory, suite, receipts, and adapter files for CLI verification. Request inputs
are omitted, but identifiers and reason codes remain visible: review them before sharing.

## Publish results to your CI test viewer

```bash
aau bom export-conformance-junit receipt.json inventory.json suite.json \
  --adapter-artifact adapter.py --workspace . --out authority-results.xml
```

This verifies the recorded evidence and writes deterministic JUnit-style XML with one test case
for **every** suite case, including passes. Failed cases include the mismatch category and
expected/observed decisions and reason differences. Suite properties retain source digests,
adapter-check status, and the synthetic-evidence boundary. No execution time is invented.

Configure your CI system's JUnit consumer to collect `authority-results.xml`, including on
failed jobs. Export exits 1 after writing behavioral failures, 0 for passing evidence, and 2 for
invalid evidence (no new report). Do not suppress that exit code just to upload a report; use
your CI's always-run artifact/test-result collection step. An invalid receipt is a job error,
not a zero-test success. Existing files are not overwritten. This export does not execute the
adapter or certify its behavior; retain original evidence for re-verification. Review case IDs
and reason codes before sharing. Available in the current repository harness.

## Build a portable evidence pack

```bash
aau bom export-cyclonedx agent-capability-bom/examples/candidate.json \
  --out /tmp/agent-bom.cdx.json

aau bom pack agent-capability-bom/examples/candidate.json \
  --out /tmp/agent-bom-pack
aau bom verify /tmp/agent-bom-pack
```

The pack contains:

| Artifact | Purpose |
|---|---|
| `agent-capability-bom.json` | Exact models, tools, leases, routes, controls, evidence, and owner |
| `authority-review.json` | Recomputed boundary violations and visible owner-review status |
| `cyclonedx-1.7.json` | Standards-compatible projection; agent-only fields use `aau:agent:*` properties |
| `provenance.intoto.json` | Unsigned in-toto Statement v1 binding the exact artifact bytes |
| `manifest.json` | Byte length and SHA-256 of every other file |

`verify` rejects symlinks, extra or missing files, byte drift, stale review output, stale CycloneDX
projection, and mismatched provenance subjects. The unsigned statement establishes integrity
linkage only—not who generated, reviewed, or authorized the deployment.

## What fails closed

- unknown or duplicate model, tool, authority, route, or evidence identifiers;
- an authority operation or scope that exceeds its referenced tool declaration;
- a missing, duplicate, inconsistent, or tool-exceeding operation-scope relationship;
- missing expiry or revocation, invalid time windows, or excessive delegation depth;
- removed human release authority or a public claim of verified production identity;
- personal data, credentials, nonpublic configuration, or controlled information in a public BOM;
- private/traversing evidence paths, unrecognized fields, oversized files, and overwrite attempts;
- consequential write/irreversible authority without declared human approval.
- allowed observation events outside the declared authority, noncontiguous run sequences, false
  run/scenario counts, and observation/BOM release mismatches.
- stale or hand-edited conformance suites, duplicate/missing case coverage, adapter answer-shape
  drift, receipt identity/digest mismatch, command/artifact substitution, artifact byte drift, and
  non-recomputable exactness or failure counts.

The strict CLI is the normative AABOM 1.1 validator.
JSON evidence files and command responses reject duplicate object keys at every nesting level and
non-standard numeric constants (`NaN`, `Infinity`, and `-Infinity`). Contradictory repeated decision
or approval fields therefore fail before semantic validation instead of silently retaining one value.

The readable
[`agent-capability-bom.schema.json`](agent-capability-bom.schema.json) publishes the transport
shape; cross-reference, interval, and authority-subset invariants are enforced by the CLI.

## Adopt it without creating false assurance

1. Generate the AABOM at build time from authoritative configuration; do not hand-type production
   entitlements when automation is available.
2. Keep secrets and private configuration out. Publish digests or a public synthetic profile and
   retain the sensitive inventory in the organization's controlled system.
3. Diff every release and require an accountable owner to review each widening finding.
4. Use authorized aggregate or reviewed synthetic observations to locate review candidates. Never
   remove a permission merely because a bounded window did not exercise it.
5. Compile clean and violation twins and run them against the real authorization adapter. Keep
   adapter evidence distinct from the reference protocol self-test.
6. Verify identity, current authorization, revocation, destination, and policy again at action
   time. An inventory is a snapshot, not an enforcement point.
7. Attach organization-controlled signatures or attestations after verification and preserve the
   actual approval in the authoritative change system.
8. Pair the inventory with the [Agent Release Gate](../agent-release-gate/),
   [Portable Agent Assurance](../portable-agent-assurance/), and
   [Containment Drills](../agent-containment-drills/) for test, runtime, and recovery evidence.

## Standards relationship

The design starts from the current [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative),
the NCCoE [agent identity and authorization concept](https://www.nccoe.nist.gov/publications/other/accelerating-adoption-software-and-ai-agent-identity-and-authorization-concept),
CISA's [2025 SBOM Minimum Elements](https://www.cisa.gov/resources-tools/resources/2025-minimum-elements-software-bill-materials-sbom),
and CycloneDX [AI/ML-BOM](https://cyclonedx.org/capabilities/mlbom/) and
[1.7 JSON Schema](https://github.com/CycloneDX/specification/blob/master/schema/bom-1.7.schema.json).
The least-authority workflow is informed by NIST SP 800-53 AC-6 and NIST SP 800-207/207A, including
the use of telemetry to refine access rights; those sources do not endorse this implementation or
make short-window non-use sufficient evidence for removal.
The exact relationship profile is informed by NIST SP 800-205's subject/object/operation model and
RFC 9396's explicit treatment of combined fields as a product; it does not claim conformance to
either source.
The command-artifact binding is informed by NIST SSDF's release-integrity and provenance practices
and SLSA's requirement to verify that an attestation subject matches the artifact digest. It is a
local unsigned observation, not SSDF or SLSA conformance and not builder or deployment provenance.
The AABOM is an experimental AAU profile, not a NIST, CISA, OWASP, Ecma, CycloneDX, SPDX, or
government standard and not an assertion of conformance by those organizations.

See the [premise-checked research notes](RESEARCH_NOTES.md) for the gap analysis, design decisions,
transfer limits, and primary-source ledger.
