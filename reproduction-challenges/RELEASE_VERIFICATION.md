# Verify a Fork-to-Reproduce submission

Use the participant's fork identity—not the upstream repository identity—when verifying its GitHub
Artifact Attestations. Download `reproduction-submission.json`,
`reproduction-verification.json`, and `SHA256SUMS` from the same workflow artifact without renaming
them. In that directory, verify the downloaded bytes:

```bash
sha256sum --check SHA256SUMS
gh attestation verify reproduction-submission.json --repo FORK_OWNER/awesome-agentic-usecases
gh attestation verify reproduction-verification.json --repo FORK_OWNER/awesome-agentic-usecases
```

On macOS use `shasum -a 256 --check SHA256SUMS`. Inspect both attestation outputs and confirm the
expected fork owner, repository, workflow path, commit, issuer, and subject digest. Then, from a
current clean checkout of the upstream repository, recompute the portable receipt:

```bash
python3 reproduction-challenges/submit.py verify-receipt \
  --receipt /path/to/reproduction-verification.json \
  --submission /path/to/reproduction-submission.json
```

This command validates the submission against the named public challenge and recomputes its embedded
digest. It also requires an open challenge and exact matches for the current challenge digest,
campaign-lock digest, reviewed workflow digest, and explicit boundary declarations. A stale,
tampered, superseded, or differently governed bundle fails closed.

Only after all three checks pass should a maintainer freeze the submission digest. Oracle reveal
and independence adjudication happen later and separately. These checks establish byte integrity,
fork workflow provenance, and current public-campaign binding. They do not establish oracle secrecy,
truth, independence, certification, compliance, field effectiveness, upstream endorsement, or
deployment authority. Follow the [threat model](THREAT_MODEL.md) before adjudication.
