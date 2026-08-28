# Agentic Cyber Resilience threat model

This threat model covers the open-source ABP verifier and its synthetic reference files. It does
not cover a production agent, identity provider, monitor, model, policy engine, security product,
critical-infrastructure system, or government network.

## Assets and trust boundaries

Protect the integrity of the authority profile, reviewed scenario oracle, event ordering, derived
decisions, receipt chain, and non-certification claims. Treat profiles, JSONL scenarios, receipts,
forks, and downloaded packs as untrusted until verified.

The verifier reads local files and writes only the explicitly named receipt or non-existing pack
directory. It makes no network request, loads no plugin, reads no environment variable, imports no
third-party package, launches no subprocess, and executes no event field.

## Abuse cases and controls

| Threat | Consequence | Reference control | Residual owner |
|---|---|---|---|
| Malformed or oversized JSON | Resource exhaustion or ambiguous parsing | File-size and scenario-count limits; exact top-level structures | Deployment sets stricter platform limits |
| Symbolic-link substitution | Verifier reads an unintended file | Input symlinks are rejected | Operator protects the working directory |
| Profile weakens pause or restart authority | Unsafe behavior appears conforming | Human pause/restart booleans and tamper response fail closed | Accountable risk owner reviews the real policy |
| Peer or credential expands authority | Lateral agent behavior escapes the task | Original lease remains authoritative; explicit denial codes | Runtime enforcement remains external |
| Agent tampers with its transcript | False evidence or hidden activity | Mutation scenario pauses; receipt rows are hash chained | Logs must live outside agent control |
| Result is edited after evaluation | False aggregate claim | Summary, row digests, chain head, profile, and suite recompute | Digital signing and transparency are external |
| Synthetic pass is presented as production proof | Unsafe procurement or deployment claim | Machine-checked non-certification boundaries in profiles and receipts | Reviewer enforces claim discipline |
| Pack contains secrets or operational traces | Public disclosure | Reference data is synthetic-only and schemas reject affirmative sensitive-data flags | Authorized human review remains required |
| Defensive example becomes offensive guidance | Unauthorized access | No exploit code, live target, real credential, or scanning capability | Maintainers reject unsafe contributions |

## Security invariants

- Event content is parsed as data and never executed.
- A public reference profile contains only synthetic data and negative sensitive-data attestations.
- The verifier never infers authority from a credential, tool availability, peer message, urgency,
  or prior success.
- An invalid identity, task, authority reference, time window, action, destination, or approval
  cannot produce `allow`.
- Monitor loss, critical alerts, and record mutation have a pause path.
- Receipt verification detects modification, deletion, insertion, or reordering of result rows.
- Output never claims certification, compliance, authorization, government endorsement, or
  production fitness.

## Out of scope

Cryptographic identity issuance, key custody, signatures, revocation infrastructure, live model
monitoring, chain-of-thought access, exploit detection, malware analysis, network enforcement,
endpoint isolation, vulnerability scanning, incident command, legal interpretation, classified
processing, operational authorization, and recovery of a compromised system are out of scope.
