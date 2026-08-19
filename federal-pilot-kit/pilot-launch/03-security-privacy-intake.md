# 03 — Security, privacy, and data intake

Stop the pilot if any required answer is unknown and the designated owner has not accepted a
bounded investigation path.

## Data and environment gate

- [ ] Every data source, owner, classification, provenance, permitted use, retention period,
  deletion route, and access group is recorded in an approved system.
- [ ] The public repository, issues, browser desk, and examples receive only public or synthetic
  information.
- [ ] Test data is minimized and cannot be joined to re-identify a person.
- [ ] Training, fine-tuning, retrieval, logging, human review, telemetry, subcontractor, and model-
  provider uses are explicitly allowed or prohibited.
- [ ] Records, legal hold, deletion, access/correction, accessibility, and incident routes are
  assigned to human owners.
- [ ] The pilot environment, network paths, identities, secrets, logs, exports, backups, and
  administrative access have an agency-approved control path.

## Abuse-case gate

Test malformed input, prompt/tool injection, unauthorized retrieval, data leakage, cross-tenant
access, privilege escalation, excessive agency, denial of service, audit-log gaps, unsafe fallback,
poisoned evidence, and attempts to bypass the protected human decision. Record exact inputs,
observed actions, evidence, impact, and disposition.

## Stop now when

Classified, controlled, procurement-sensitive, source-selection, privileged, credential, or real
personal information enters an unapproved path; a protected action can occur without its human
owner; an incident cannot be contained and reconstructed; or a required security/privacy owner is
unavailable. Preserve evidence through the approved incident process—never through a public issue.
