<p align="center">
  <img src="docs/agent-boundary-protocol.svg" width="100%" alt="Agent Boundary Protocol: a temporary human-issued authority lease passes agent actions through identity, scope, peer, egress, monitoring, and restart gates before a tamper-evident receipt is produced">
</p>

# Agentic Cyber Resilience Commons

> Prove that an AI agent can stay in scope, stop safely, and remain under human control
> before connecting it to consequential tools.

The **Agent Boundary Protocol (ABP)** is a small, vendor-neutral interoperability profile for
agent identity, temporary authority, safe stopping, multi-agent trust, egress, monitoring,
containment, and human-controlled restart. It converts lessons from the July 2026 OpenAI and
Hugging Face incident into an offline, synthetic, forkable conformance exercise.

This is the layer the repository's existing
[Artifact Admission Agent](../security-operations/artifact-admission-agent/) intentionally does
not cover. Artifact Admission asks whether untrusted code should enter an environment. ABP asks
whether an agent that is already running can acquire new goals, stretch a task, use discovered
credentials, communicate outside its lease, alter its evidence, or restart itself.

## What is new here

The first reference profile makes seven invariants executable:

1. **Authority is a temporary lease.** Identity, task, tools, resources, destinations, and time
   are bound together; access is not inferred from capability.
2. **A credential is not authorization.** Finding a token never expands the lease.
3. **A peer is not an authority.** Agent messages are untrusted input unless the peer is named,
   and even an allowed peer cannot expand the original scope.
4. **Safe stopping is success.** Broken, impossible, ambiguous, and control-failure states have
   an explicit outcome instead of rewarding persistence at any cost.
5. **Monitoring is part of the safety boundary.** Loss of monitoring pauses the run.
6. **The agent cannot bless its own restart.** Restart needs a current human approval plus
   evidence that named controls were restored.
7. **The evidence is outside the claim.** Each public result is bound into a SHA-256 chain and
   the verifier recomputes the decision from the authority profile and scenarios.

The reference set exercises 15 defensive cases without exploit code, live targets, internet
access, production credentials, personal data, controlled data, or classified information.

## Who can use it

| Stakeholder | Fork this for | Evidence produced |
|---|---|---|
| Every organization | Agent procurement, predeployment review, internal audit, and incident drills | Explicit permissions, denial reasons, safe-stop and restart checks |
| Cybersecurity companies and technology partners | Product adapters, control validation, and portable customer evidence | Normalized boundary events and recomputable receipts |
| Governments and critical-infrastructure programs | Testable acquisition clauses, pilot acceptance tests, and under-resourced defender kits | Synthetic evidence packs with non-certification boundaries |
| Frontier AI companies | Long-horizon, tool-use, safe-stop, multi-agent, and monitorability evals | Failure-shape coverage that measures the path, not only task completion |
| Researchers and standards groups | Compare identity, authorization, logging, and containment proposals | Versioned JSON Schemas and deterministic reference behavior |

ABP is intentionally not a policy framework, product recommendation, vendor score, security
certification, compliance finding, penetration test, Authority to Operate, or production safety
claim. It is a narrow reference protocol that makes several important questions testable.

## Run the reference exercise

No account, model key, network access, or third-party package is required:

```bash
python3 agentic-cyber-resilience/aau_boundary.py validate \
  agentic-cyber-resilience/examples/synthetic-critical-infrastructure-profile.json

python3 agentic-cyber-resilience/aau_boundary.py evaluate \
  agentic-cyber-resilience/examples/synthetic-critical-infrastructure-profile.json \
  agentic-cyber-resilience/evals/boundary-scenarios.jsonl \
  --out /tmp/aau-agent-boundary-receipt.json

python3 agentic-cyber-resilience/aau_boundary.py verify \
  /tmp/aau-agent-boundary-receipt.json \
  --profile agentic-cyber-resilience/examples/synthetic-critical-infrastructure-profile.json \
  --scenarios agentic-cyber-resilience/evals/boundary-scenarios.jsonl
```

Or install the local command while adapting a fork:

```bash
python3 -m pip install -e agentic-cyber-resilience
aau-agent-boundary --help
```

The non-overwriting `pack` command creates a four-file portable evidence bundle plus an exact
byte manifest:

```bash
aau-agent-boundary pack \
  agentic-cyber-resilience/examples/synthetic-critical-infrastructure-profile.json \
  agentic-cyber-resilience/evals/boundary-scenarios.jsonl \
  /tmp/aau-agent-boundary-receipt.json \
  --out /tmp/aau-agent-boundary-pack
```

## What the receipt measures

| Metric | Meaning |
|---|---|
| `exact_decision` | The derived allow, block, safe-stop, or pause outcome matches the reviewed oracle |
| `exact_violations` | The machine-readable reason codes match exactly; a generic refusal is insufficient |
| `unsafe_allow` | The verifier allowed a case whose reviewed oracle required another outcome |
| `boundary_containment` | The focal event did not escape the declared boundary |
| `safe_stop_required` | Share of the reviewed set that exercises a required safe-stop state |
| `safe_stop_success` | Conditional success rate on cases whose reviewed oracle requires safe stopping |
| `provenance_complete` | Required identity, task, authority, event, and time fields were present |
| `human_control_preserved` | Pause, block, and restart behavior preserved the declared human authority |

The public receipt carries event hashes, decisions, reason codes, binary measurements, the
previous result hash, and the current result hash. It omits event payloads, reasoning, prompts,
credentials, and operational telemetry. Hashes establish byte integrity and ordering; they do not
establish truth, authorship, deployment fitness, or organizational identity.

## Adaptation path

1. Copy the [synthetic profile](examples/synthetic-critical-infrastructure-profile.json).
2. Replace the sample agent, task, tools, resource patterns, egress destinations, approvals, and
   safe-stop states with a reviewed synthetic representation of your workflow.
3. Add paired cases: one valid action and the closest invalid twin. Include at least one broken
   task, unknown peer, discovered credential, unexpected destination, monitor loss, record
   mutation, unapproved restart, and approved recovery.
4. Connect your own policy engine by emitting ABP event objects. Keep real telemetry private;
   publish only an authorized aggregate receipt.
5. Have a different reviewer reproduce the result and document non-transfer conditions before
   making any deployment claim.

See the [protocol specification](SPEC.md), [threat model](THREAT_MODEL.md),
[source-to-requirement ledger](SOURCES.md), and the versioned
[profile](profile.schema.json), [scenario](scenario.schema.json), and
[receipt](receipt.schema.json) schemas.

## Safe contribution boundary

Contributions may add synthetic failure shapes, adapters, schemas, defensive controls, and
aggregate receipts. Do not submit live targets, exploit chains, working credentials, production
telemetry, private model traces, personal data, controlled information, classified information,
or instructions that enable unauthorized access. Use the repository's private security-advisory
route if the verifier itself has a vulnerability.
