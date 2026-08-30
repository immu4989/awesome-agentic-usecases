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
dependency SBOM would miss the meaningful deployment delta; `aau bom diff` reports all five
authority-widening facts.

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

If protected human approval is removed, the diff changes to `blocking_boundary_loss`. A moving
15-minute lease does not appear as an extension merely because its timestamps moved; only a longer
duration triggers `AUTHORITY_WINDOW_EXTENDED`.

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
It sees two of three granted operations and two of three scopes. A blocked draft attempt does not
count as legitimate use, so the planner flags one operation and one scope for investigation—but
removes **zero** permissions.

Every candidate requires six next proofs: domain-owner need review, representative holdout suite,
legitimate clean twin, staging denial test, rollback rehearsal, and separate change approval.
Absence in bounded traces never proves that a grant is unnecessary, scenario coverage never proves
production workload coverage, and the planner emits no executable policy.

The transport shape is published as
[`authority-observation.schema.json`](authority-observation.schema.json). It intentionally excludes
arguments, results, prompts, reasoning, credentials, and operational payloads; OpenTelemetry warns
that tool-call arguments and results may contain sensitive information, so this public profile
retains only normalized identifiers, sequence, operation, scope class, and decision.

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
- missing expiry or revocation, invalid time windows, or excessive delegation depth;
- removed human release authority or a public claim of verified production identity;
- personal data, credentials, nonpublic configuration, or controlled information in a public BOM;
- private/traversing evidence paths, unrecognized fields, oversized files, and overwrite attempts;
- consequential write/irreversible authority without declared human approval.
- allowed observation events outside the declared authority, noncontiguous run sequences, false
  run/scenario counts, and observation/BOM release mismatches.

The strict CLI is the normative 1.0 validator. The readable
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
5. Verify identity, current authorization, revocation, destination, and policy again at action
   time. An inventory is a snapshot, not an enforcement point.
6. Attach organization-controlled signatures or attestations after verification and preserve the
   actual approval in the authoritative change system.
7. Pair the inventory with the [Agent Release Gate](../agent-release-gate/),
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
The AABOM is an experimental AAU profile, not a NIST, CISA, OWASP, Ecma, CycloneDX, SPDX, or
government standard and not an assertion of conformance by those organizations.

See the [premise-checked research notes](RESEARCH_NOTES.md) for the gap analysis, design decisions,
transfer limits, and primary-source ledger.
