# Agent Release Gate 1.0

**Status:** experimental public interoperability contract.

**Normative implementation:** `aau_harness.release_gate` in `aau-harness`.

The key words MUST, MUST NOT, SHOULD, and MAY describe this AAU contract only. They add no
requirements to NIST, OSCAL, MCP, A2A, OpenTelemetry, in-toto, a model provider, a regulator, or an
organization's deployment process.

## 1. Claim

The gate answers one narrow question:

> Did the declared public or synthetic candidate change receive every suite and structural human
> review required by the declared release policy, and did those suite receipts meet the declared
> exact-outcome and forbidden-execution thresholds?

It does not determine whether component declarations are complete or true, authenticate an
approver, observe a production side effect, authorize deployment, establish field effectiveness,
or determine compliance.

## 2. Component capture

A manifest MUST name one agent and one release, use a timezone-qualified effective timestamp, and
explicitly attest the public/synthetic sharing boundary. Each component MUST declare:

- a unique component id;
- one supported kind;
- a relative, non-traversing, non-symlink path below the manifest directory;
- one or more supported impact tags; and
- whether removal is prohibited by the release contract.

Capture records the SHA-256 and byte length of the exact source bytes. It does not normalize JSON,
Markdown, prompts, or configuration. A formatting change is therefore visible.

## 3. Change impact

Components are joined by `component_id`. Addition, removal, digest change, or kind change is a
release change. The impacted tag set is the union of the before and after tags for every changed
component. Every impacted tag MUST have a release-policy mapping. An unmapped tag blocks.

A component required by the policy MUST be present in the candidate. Removal of any component
marked required in the baseline blocks even if its kind is otherwise present under another id.

## 4. Suite evidence

The evidence plan binds suite ids to relative suite files, impact tags, and a declared clean-twin
count. The suite file is validated through the existing `aau-byo-agent-suite/1.0` contract.

Only suites intersecting the impacted tag set run. A requirement passes only when:

- its suite was planned for the same impact tag;
- the receipt suite id matches exactly;
- `exact_rate` meets the declared threshold;
- `no_forbidden_execute_rate` meets the declared threshold; and
- the evidence plan declares at least one clean twin.

The public adapter request MUST exclude the oracle and forbidden-action list. A command adapter
MUST execute without a shell. A mock protocol self-test MUST NOT produce `release_ready`.

## 5. Protected human review

If an impacted tag appears in `protected_review_tags`, the gate MUST receive a structurally valid
approval record for the exact candidate release. The role MUST begin with `human:` and the record
MUST keep `identity_verified: false` because this public contract has no identity proof.

Organizations SHOULD replace the fixture with an authenticated change-system record and attach an
organization-controlled signature or attestation outside this local profile.

## 6. Status

- `release_blocked`: any required mapping, component, suite, or threshold fails.
- `human_review_required`: no blocker exists, but protected review is absent or the run is mock.
- `release_ready`: all declared non-mock requirements pass and any structural approval record is
  present.

The status MUST be interpreted together with its boundary. No status is deployment authority.

## 7. Evidence pack

The pack MUST include snapshots, diff, policy, plan, decision, suite receipts, non-certifying OSCAL
mapping, unsigned in-toto Statement, README, and byte manifest. `approval.json` is conditional.

Verification MUST reject:

- missing, duplicate, unmanifested, nested-unexpected, oversized, or modified files;
- symbolic links or traversal;
- broken snapshot, diff, decision, receipt, OSCAL, statement, or manifest binding; and
- overwrite attempts during pack creation.

The manifest and in-toto statement bind bytes. They do not prove authorship.

## 8. OSCAL boundary

The exporter emits an OSCAL Assessment Results-shaped JSON serialization with deterministic UUIDs,
observations, findings, evidence URNs, timestamps, and AAU remarks. It does not validate against an
agency-selected OSCAL schema, create an assessment plan, select controls, supply an authorized
assessor, or make a control finding. Consumers MUST validate and contextualize it within their own
assessment system before use.

## 9. Versioning

Changing the meaning of a status, component kind, impact tag, threshold, required field,
canonicalization rule, or pack-verification rule requires a new contract version. New surrounding
tools MAY be added without changing 1.0 semantics.
