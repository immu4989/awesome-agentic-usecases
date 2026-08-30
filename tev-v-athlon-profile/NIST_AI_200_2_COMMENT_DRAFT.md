# Draft public comment on NIST AI 200-2 ipd

**Status:** maintainer draft for public review; **not submitted**.

**Prepared:** August 30, 2026.

**Subject:** NIST AI 200-2 — practical support for agentic-system TEVV.

Awesome Agentic Use Cases (AAU) is an independent Apache-2.0 open-source project. This comment is
not submitted on behalf of an employer, agency, standards organization, protocol project, model
provider, or any cited organization. The supporting example is synthetic and public.

## Summary

The four-stage TEVV-Athlon structure usefully connects organizational goals to Blocks, Events,
Tools, evidence, analysis, and decisions. Applying the draft to an executable MCP/A2A agent
authority testbed exposed six areas where additional agent-specific examples or guidance could
improve practical utility without making the framework prescriptive.

## Evidence-backed observations

### 1. Treat identity, credential, authority, and task as separate measurement concepts

For agentic systems, successful authentication at session start does not establish that each later
tool call or peer handoff remains authorized. Our example required separate Blocks for workload and
operator binding, live task authority, and protocol scope. A useful agentic example could show an
Event where a valid credential is paired with an expired lease, stale policy epoch, changed task,
or widened delegation.

### 2. Include state transitions and ordering in Event design

Agent behavior unfolds across delegated work, queued effects, revocation, monitor loss, and
recovery. Evaluation reports should state whether an observed block occurred before a side effect
and whether parent revocation reached child and queued work. A recorded transcript alone cannot
prove that ordering; the limitation should remain visible.

### 3. Require legitimate twins for restrictive controls

A security control can appear effective by denying every action. The example therefore places a
valid MCP read and valid A2A handoff beside their closest unsafe variants and reports legitimate
action preservation separately. TEVV guidance could explicitly recommend such paired Events when
measuring access, policy, refusal, or containment controls.

### 4. Distinguish structural reproducibility from independent reproduction

Deterministic recomputation, byte manifests, and signed workflow provenance do not establish that
an outside organization reproduced a result or that a hidden oracle remained secret. Reports could
use separate fields for artifact integrity, executor identity, oracle control, relationship review,
and independent reproduction.

### 5. Make Goodhart controls executable where possible

The draft appropriately warns about Goodhart's Law. For agentic systems, some protections can be
made machine-checkable: prohibit one universal score, keep Blocks and Events visible, report clean-
twin availability separately, bind exact suite versions, and reject outcome labels that exceed the
supporting artifact state.

### 6. Provide a minimal machine-readable interchange example

Organizations need flexibility, but a non-normative JSON example for goals, Blocks, Events, Tools,
artifact digests, joint analysis, decision owner, transfer limits, and claim boundaries could reduce
translation cost. The accompanying AAU profile is one experimental implementation offered for
discussion, not a proposed NIST schema.

## Supporting public artifacts

- Machine-readable profile: `examples/agent-assurance-tevva.json`
- Deterministic validator and packer: `aau_tevva.py`
- Experimental assurance specification: `../portable-agent-assurance/SPEC.md`
- Portable Agent Assurance evaluator: `../portable-agent-assurance/aau_assurance.py`
- Eighteen-case MCP/A2A suite and recomputable receipt under `../portable-agent-assurance/examples/`

The example reports **three unresolved evidence gaps**: no held-out material in the revealed public
suite, no observed outside production-adapter event, and no observed independent reproduction.

## Requested clarification

We would welcome additional draft guidance on:

1. representing stateful and multi-party Events;
2. distinguishing a Tool used to elicit behavior from infrastructure used to enforce policy;
3. reporting missing or planned evidence without converting coverage into a compliance score;
4. binding changing system, policy, tool, and deployment versions to reassessment triggers; and
5. documenting when human or field evidence cannot be safely published.

Thank you for the opportunity to comment on the initial public draft.
