# Agent Boundary Protocol 0.2 — public standards contribution

Status: experimental open protocol and conformance vectors for feedback. This document does not
represent NIST, CISA, OMB, an agency, a standards body, or any cited organization.

## Problem statement

Agent authentication at session start does not establish that every later action remains inside
the human task grant. During a long run, tools, destinations, peers, task state, monitoring,
credentials, approvals, and policy can change. ABP defines a small evidence contract for asking at
each recorded decision point:

> Is this named agent still acting on this task, under this lease, at this policy epoch, with this
> tool, target, destination, peer, monitoring state, and human authority?

## Proposed interoperable objects

1. **Authority profile** — accountable issuer, agent, task, validity window, tools, resources,
   destinations, peers, protected actions, approvals, safe-stop states, logging, and claim boundary.
2. **Normalized runtime event** — identity and authority references, sequence, policy epoch,
   event kind, and the minimum action-specific fields.
3. **Stable decision** — `allow`, `block`, `pause`, or `safe_stop` plus machine-readable reasons.
4. **Runtime receipt** — profile and suite hashes, exact per-event decisions, state transitions,
   measurements, and an ordered SHA-256 result chain.
5. **Portable pack** — exact source objects, receipt, human-readable boundary, and byte manifest.

## Security properties tested

- Identity, task, lease, resource, and audience binding.
- Least privilege and destination restriction.
- Credential possession separated from authority.
- Parent-to-child and peer delegation ceilings.
- Safe stopping when task or control assumptions break.
- Pause on monitor loss, critical alerts, and evidence mutation.
- Human-issued restart with named restoration evidence.
- Sticky revocation and stale-policy-epoch rejection.
- Integrity and reproducibility of the public result.

## Deliberate non-goals

ABP does not define an identity provider, OAuth server, credential format, digital-signature
profile, network sandbox, policy language, secure log, model monitor, kill-switch implementation,
rollback system, or incident command structure. It supplies conformance events and evidence that
those systems can adapt.

## Open questions for collaborators

1. Which event fields are the minimum interoperable set across MCP, agent SDKs, workload identity,
   and policy engines?
2. How should policy epochs and revocation propagate across queued and delegated work?
3. Which external signing and transparency profiles can bind ABP receipts without creating a new
   identity standard?
4. How should a runtime prove that a block preceded—not followed—a consequential side effect?
5. Which sector profiles can share a common control without erasing domain-specific safe states?
6. What public evidence is sufficient for independent reproduction without leaking telemetry?

Feedback should include a synthetic conformance vector, expected outcome, source rationale, and
non-transfer conditions whenever possible.
