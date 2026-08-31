# Fork-to-Reproduce threat model

This model covers the public challenge workflow in a participant-controlled GitHub fork. Its goal
is narrow: produce origin-verified, oracle-free submission bytes and attach fork workflow
provenance without executing pull-request code or granting upstream authority.

## Protected assets and claims

| Asset or claim | Control | What the control does not prove |
|---|---|---|
| Public challenge origin | Protected `.aau` copies are compared byte-for-byte with the current upstream campaign | That the upstream challenge is correct, complete, or fit for deployment |
| Hidden oracle | Only commitments appear in the public campaign and prepared workspace | That a participant did not obtain the oracle elsewhere |
| Submission bytes | SHA-256 plus GitHub Artifact Attestation binds the artifact to a fork workflow run | That answers are true, independently produced, or endorsed upstream |
| Campaign state | The campaign lock binds both registries and every challenge/template byte | Confidentiality, availability, or the safety of code changed in a fork |
| Independence claim | Distinct role commitments plus separate human relationship review | Cryptographic proof of organizational or personal independence |

## Adversaries considered

- A malicious or mistaken fork owner who supplies path traversal, a symbolic link, stale protected
  files, self-recomputed template metadata, unfinished answers, or a replayed submission.
- A future maintainer who accidentally adds a pull-request trigger, expands token permissions,
  consumes a secret, persists checkout credentials, stops quoting the path input, or follows a
  mutable Action tag.
- A submitter who reuses a producer commitment, backdates review, weakens role separation, or
  presents a protocol demonstration as an independent result.
- A reviewer who mistakes fork provenance for upstream endorsement, correctness, certification,
  compliance, field effectiveness, or deployment authority.

## Enforced workflow invariants

`python3 reproduction-challenges/submit.py verify-campaign` fails closed unless the workflow:

1. is triggered only through `workflow_dispatch` with one workspace-path input;
2. has exactly `contents: read`, `id-token: write`, and `attestations: write` permissions;
3. consumes no GitHub secret and does not persist checkout credentials;
4. passes the untrusted input once through an environment variable and quotes it at execution;
5. runs campaign verification and protected-origin `build-prepared`; and
6. pins every third-party Action to a full 40-character commit SHA.

The workspace verifier also rejects checkout escape, symbolic links, protected-byte drift, stale or
closed challenges, changed task sets, oversized JSON, unfinished templates, and destructive output
overwrite. Acceptance separately rejects duplicate producers/submissions, noncanonical chronology,
unreviewed packs, challenge mismatch, and more than one accepted blind result per revealed oracle.

## Trust boundaries and residual risk

Fork owners control their repository and can change or bypass its workflow. An attestation from
their fork is evidence about the exact artifact and workflow identity shown by GitHub, not evidence
that upstream ran or approved it. Review the attestation issuer, repository, workflow ref, commit,
subject digest, campaign lock, and submitted role commitments before adjudication.

No repository control can prove that the oracle remained unknown, a transcript is exhaustive, role
holders are independent, or evidence is truthful. Those remain explicit human-review findings.
Do not place names, credentials, targets, personal data, CUI, classified data, confidential
relationships, raw production traces, or exploit instructions in a workspace or artifact.

## Safe failure and reporting

If any origin, digest, workflow, chronology, or relationship check is unclear, do not accept the
submission. Preserve only safe public artifacts, open a private security report for exploitable
repository defects, and issue a fresh challenge commitment if oracle confidentiality may have been
lost. See the repository [security policy](../SECURITY.md) for reporting routes.
