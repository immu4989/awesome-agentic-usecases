# Fork-to-Reproduce Challenge Network

Run a public, oracle-free challenge in a fork without granting the workflow deployment authority.
The [threat model](THREAT_MODEL.md) defines the protected assets, attacker capabilities, executable
workflow invariants, review obligations, and residual risks before you submit evidence.

Four public challenges are open and one source-superseded artifact is retained as closed history.
Their answer keys are committed by SHA-256 but are not in Git.
Fork the repository, produce a challenge-bound submission, and use the dedicated workflow to attach
GitHub's build identity to the exact submission bytes.

| Challenge | Tasks | Status | Decision boundary | Inspect |
|---|---:|---|---|---|
| Portable Agent Assurance, revision locked | 6 | Open | Identity, task, token audience, peer/card, monitoring | [Inspect](portable-agent-assurance-2026-02/challenge.json) |
| Grid restoration | 6 | Open | Restoration conditions, clearance ownership, urgency, monitoring | [Inspect](grid-restoration/challenge.json) |
| Pharmaceutical batch disposition | 6 | Open | Chemical OOS, sterility, record conflict, transfer limits | [Inspect](pharma-batch-disposition/challenge.json) |
| A2A-to-MCP authority relay | 8 | Open | Protocol, identity, delegation, resource, audience, monitoring, approval | [Inspect](a2a-mcp-authority-relay/challenge.json) |
| Portable Agent Assurance, original | 6 | Closed · source superseded | Historical MCP 2025 and mutable A2A source link | [Inspect history](portable-agent-assurance/challenge.json) |

Open challenges cannot cite mutable GitHub branch URLs. The original portable challenge is retained
for byte-history and is not accepted by the submission builder; its revision-locked successor uses
A2A `v1.0.1`, MCP `2026-07-28`, and the dated February 2026 NIST NCCoE paper.

[`campaign-lock.json`](campaign-lock.json) gives the complete public campaign one deterministic
digest. It binds the exact campaign and accepted-result registry bytes plus the exact bytes of every
challenge, response template, and metadata template, while carrying each source-suite and oracle
commitment. Campaign verification rejects any drift, including edits that leave task ids unchanged.

## Reproduce one

Fastest path—prepare an oracle-free workspace without copying files by hand:

```bash
python3 reproduction-challenges/submit.py prepare \
  --challenge-id a2a-mcp-authority-relay-2026-01 \
  --out my-reproduction
```

Edit `my-reproduction/responses.json` and `metadata.json`, leave its `.aau/` origin directory
unchanged, then run `python3 reproduction-challenges/submit.py check-prepared my-reproduction`.
The checker recomputes the protected origin manifest, embedded challenge digest, current campaign
status, source-suite and oracle commitments, and final submission shape. It detects template drift,
symlinks, challenge closure or supersession, missing tasks, and unfinished `TODO` values.

1. Fork the repository.
2. Run `list-open`, choose a challenge, and create a workspace with `prepare`.
3. Read only `.aau/challenge.json` and its named public sources.
4. Replace every `TODO` in `responses.json` and `metadata.json`. Generate a private random role
   secret, publish only its SHA-256 commitment, and retain the role mapping outside the public pack.
5. Run `check-prepared`, commit the oracle-free workspace to your fork, then open
   **Actions → Fork-to-Reproduce submission → Run workflow** and enter its directory path.
6. The workflow runs `build-prepared`, rechecking protected origin bytes and current campaign
   status immediately before it builds and attests the submission.
7. Download the attested `aau-reproduction-submission` artifact and follow the
   [verification procedure](RELEASE_VERIFICATION.md) before sharing its digest.
8. Open the [reproduction contribution issue](https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=independent-reproduction.yml)
   with the fork workflow URL and submission digest. Do not send an oracle, raw trace, identity
   document, credential, target, personal data, or confidential relationship evidence.

The workflow never receives the oracle. It validates the oracle-free challenge and your declared
public response, binds the submission to the challenge digest, creates a SHA-256 checksum, and
generates a GitHub Artifact Attestation. It runs only on manual dispatch; upstream pull requests do
not execute contributor adapters or responses.

## What happens next

The maintainer freezes the first valid submission, reveals the previously committed oracle to a
separate reviewer, and uses the existing
[Independent Reproduction Exchange](../independent-reproduction-exchange/) to adjudicate it. A
public pack can reach `independence_reviewed` only after the three role commitments are distinct and
the reviewer records no issuer/producer relationship. This is human-reviewed relationship evidence,
not cryptographic proof of organizational independence.

Accepted results are listed in [`accepted-reproductions.json`](accepted-reproductions.json). Its
count is not a badge or manually maintained claim: campaign verification recomputes every listed
Exchange pack, requires `independence_reviewed`, binds it to the current challenge digest, rejects
duplicate submissions and producer commitments, and requires the campaign count to equal the
verified registry length. The empty registry therefore means exactly zero accepted independent
reproductions—not “unknown” and not an inferred success.

An accepted pack reveals the committed oracle, so that exact challenge must change to `closed` and
can have only one accepted blind reproduction. Further testing requires a new challenge id and new
source-suite and oracle commitments. The verifier rejects an accepted pack for an open challenge
and rejects a second accepted result against an already revealed challenge.

After the separate reviewer builds an Exchange pack, generate a non-mutating acceptance plan:

```bash
python3 reproduction-challenges/submit.py plan-accept \
  --challenge-id CHALLENGE_ID \
  --pack PATH_TO_REVIEWED_PACK \
  --entry-id PUBLIC_ENTRY_SLUG \
  --accepted-on YYYY-MM-DD \
  --out /tmp/aau-acceptance-plan
```

The planner first recomputes the complete pack and rejects protocol demonstrations, stale challenge
digests, invalid dates and ids, an already closed challenge, duplicate producers/submissions, or a
result that would violate the proposed registry. It writes proposed campaign and registry files,
an acceptance record, proposed campaign lock, instructions, and SHA-256 checksums without copying the oracle-bearing pack
or modifying the checkout. A human must review the plan, run `shasum -c SHA256SUMS` inside it, and
copy the exact verified pack.

No submission becomes a model ranking, certification, compliance finding, production-safety claim,
government endorsement, or permission to automate the protected decision.

## Verify campaign integrity

```bash
python reproduction-challenges/submit.py verify-campaign
```

This checks the registry, every challenge's embedded digest and oracle commitment shape, the absence
of gold fields, all template task ids, the declared public boundary, every accepted pack, and the
single campaign lock over all public artifacts.
