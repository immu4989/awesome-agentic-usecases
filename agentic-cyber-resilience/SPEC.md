# Agent Boundary Protocol 0.2

Status: experimental public interoperability profile, published for defensive testing and
feedback. Normative terms **MUST**, **MUST NOT**, **SHOULD**, and **MAY** describe this protocol;
they do not create legal, regulatory, contractual, or operational obligations.

## Purpose

ABP binds one agent identity to one task through a temporary, human-issued authority lease. A
conforming evaluator derives a decision from the lease and a normalized event, returns stable
reason codes, and emits a deterministic aggregate receipt with a per-result hash chain. Version
0.2 adds an ordered runtime conformance profile for state continuity, policy epochs, delegation,
revocation, pause, and recovery while retaining the 0.1 authority-profile contract.

The reference implementation is intentionally a policy decision point, not an agent monitor. It does
not inspect chain of thought, invoke tools, execute event content, discover assets, connect to
identity providers, sign claims, or enforce controls in a production environment.

## Compatibility

The `aau-agent-boundary-profile/0.1`, scenario, and receipt contracts remain supported without
semantic change. ABP 0.2 layers `aau-agent-boundary-runtime-suite/0.2` and
`aau-agent-boundary-runtime-receipt/0.2` over that profile. A 0.1 receipt proves only isolated
event decisions. A 0.2 runtime receipt additionally proves the reference state transitions and
ordered event chain in its supplied synthetic suite. Neither proves production enforcement.

## Profile invariants

- The profile **MUST** identify an `agent_id`, `task_id`, accountable human issuer, validity
  interval, allowed actions, blocked actions, allowed peers, allowed egress, and actions requiring
  human approval.
- Public reference profiles **MUST** be synthetic and **MUST NOT** attest that they contain real
  credentials, personal data, controlled data, or classified data.
- A peer instruction **MUST NOT** expand the original lease, including when the peer is allowed.
- Possession or discovery of a credential **MUST NOT** be treated as authority.
- Loss of required monitoring and attempted mutation of the action record **MUST** pause the run.
- A critical alert **MUST** have a pause path. A restart **MUST** reference a current human
  approval and its required control-restoration evidence.
- Broken, impossible, ambiguous, and control-failure task states **SHOULD** be explicit safe-stop
  outcomes and **MUST NOT** be scored as ordinary task failure.

## Event contract

Every event includes `event_id`, `type`, `occurred_at`, `agent_id`, `task_id`, and
`authority_ref`. The reference implementation supports:

| Event | Focal question |
|---|---|
| `action_request` | Is this tool, action, and resource inside the lease? |
| `network_request` | Are both the action and destination declared? |
| `peer_instruction` | Is the peer allowed, and does the requested action remain inside the lease? |
| `task_state` | Does this state require safe stopping? |
| `monitor_state` | Is required monitoring still operational? |
| `critical_alert` | Must the run pause? |
| `record_mutation` | Is the evaluated agent attempting to alter its evidence? |
| `restart_request` | Is there current human approval and complete restoration evidence? |

Unknown event types fail closed with `EVENT_TYPE_UNSUPPORTED`. Additional event fields are data;
the verifier never evaluates or executes event text as code.

## Runtime conformance contract

Each runtime begins `active` at `policy_epoch: 1` and accepts a strictly increasing one-based
sequence. Every recorded event binds `agent_id`, `task_id`, `authority_ref`, `sequence`, and
`policy_epoch`. The reference state machine supports:

| Runtime event | Required behavior |
|---|---|
| `tool_call` / `network_request` | Re-evaluate identity, lease, scope, destination, approval, token audience, and passthrough boundaries before returning a decision |
| `delegate` / `peer_instruction` | Block unnamed peers and any child or peer action that expands the parent lease |
| `monitor_state` / `critical_alert` | Enter `paused` when a required monitor is lost or a critical alert requires intervention |
| `task_state` | Enter `safe_stopped` for reviewed impossible, broken, ambiguous, or control-failure states |
| `pause` | Honor a declared human pause without requiring agent agreement |
| `resume` | Require a current approval and all named restoration evidence; advance the policy epoch |
| `revoke` | Accept only the accountable issuer, advance the epoch, and remain irreversibly `revoked` for that runtime |
| `record_mutation` | Pause on attempted deletion, rewrite, or truncation of the evidence record |

A paused or safe-stopped runtime blocks all events except `resume`. A revoked runtime cannot use
`resume`; a new human-issued lease is required. A stale policy epoch, missing sequence, or event
after revocation fails closed.

The generic, MCP, OpenAI Agents, LangGraph, CrewAI, and AutoGen adapters normalize **recorded
envelopes only**. They do not import those frameworks, establish an official integration, accept
tokens, or execute a tool.

## Decisions and stable reason codes

Outcomes are exactly `allow`, `block`, `safe_stop`, or `pause`. Version 0.1 emits:

- `ACTION_EXPLICITLY_BLOCKED`
- `ACTION_OUT_OF_SCOPE`
- `AUDIT_TAMPERING`
- `AUTHORITY_REF_INVALID`
- `CREDENTIAL_IS_NOT_AUTHORITY`
- `CRITICAL_ALERT_PAUSE`
- `EGRESS_NOT_ALLOWED`
- `EVENT_TYPE_UNSUPPORTED`
- `HUMAN_APPROVAL_MISSING`
- `HUMAN_RESTART_APPROVAL_MISSING`
- `IDENTITY_MISMATCH`
- `LEASE_INACTIVE`
- `MONITORING_LOST`
- `PROVENANCE_INCOMPLETE`
- `SAFE_STOP_REQUIRED`
- `TASK_MISMATCH`
- `UNAUTHORIZED_PEER`

The 0.2 runtime layer additionally emits:

- `DELEGATION_SCOPE_EXPANSION`
- `HUMAN_PAUSE`
- `LEASE_REVOKED`
- `PAUSE_AUTHORITY_INVALID`
- `REVOCATION_AUTHORITY_INVALID`
- `RUN_NOT_ACTIVE`
- `RUN_REVOKED`
- `RUNTIME_EVENT_UNSUPPORTED`
- `SEQUENCE_INVALID`
- `STALE_POLICY_EPOCH`
- `TOKEN_AUDIENCE_MISMATCH`
- `TOKEN_PASSTHROUGH_FORBIDDEN`

Consumers **SHOULD** bind automation to version plus reason code, not English prose. New reason
codes require a protocol version change or a backward-compatible declared extension.

## Receipt integrity

The receipt fingerprints the canonical profile and ordered scenario objects. Every result includes
the preceding result digest. The first result uses 64 zeroes; `chain_head_sha256` equals the final
result digest. Aggregate metrics are recomputed from result rows. Full verification re-evaluates
the supplied profile and scenario set and requires byte-equivalent canonical output.

This hash chain detects reordering, deletion, insertion, and mutation inside the receipt. It is
not a digital signature, timestamp authority, identity proof, transparency log, or guarantee that
the source event occurred. Deployments that need those properties must bind the receipt to their
approved identity, signing, time, storage, and records systems.

The 0.2 runtime receipt chains every ordered event result across all runs and binds the complete
profile and suite hashes. `verify` can check only the chain or fully recompute all state
transitions. The portable pack uses an exact byte manifest and refuses overwrite.

## Interoperability boundary

An adapter MAY translate a vendor's internal policy event to ABP. It SHOULD retain the original
private event under the organization's controls and publish only the authorized aggregate
receipt. The adapter MUST NOT claim ABP verification means certification, compliance, an
Authority to Operate, production validation, or government endorsement.
