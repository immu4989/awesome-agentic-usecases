# Fork-to-Reproduce Challenge Network

Four public challenges are open. Their answer keys are committed by SHA-256 but are not in Git.
Fork the repository, produce a challenge-bound submission, and use the dedicated workflow to attach
GitHub's build identity to the exact submission bytes.

| Challenge | Tasks | Decision boundary | Open challenge |
|---|---:|---|---|
| Portable Agent Assurance | 6 | Identity, task, token audience, peer/card, monitoring | [Inspect](portable-agent-assurance/challenge.json) |
| Grid restoration | 6 | Restoration conditions, clearance ownership, urgency, monitoring | [Inspect](grid-restoration/challenge.json) |
| Pharmaceutical batch disposition | 6 | Chemical OOS, sterility, record conflict, transfer limits | [Inspect](pharma-batch-disposition/challenge.json) |
| A2A-to-MCP authority relay | 8 | Protocol, identity, delegation, resource, audience, monitoring, approval | [Inspect](a2a-mcp-authority-relay/challenge.json) |

## Reproduce one

1. Fork the repository.
2. Choose one challenge and read only its `challenge.json` plus the named public sources.
3. Copy `responses.template.json` to `responses.json` and replace every `TODO` value.
4. Copy `metadata.template.json` to `metadata.json`. Generate a private random role secret, publish
   only its SHA-256 commitment, and retain the role mapping outside the public pack.
5. In your fork, open **Actions → Fork-to-Reproduce submission → Run workflow**.
6. Download the attested `aau-reproduction-submission` artifact.
7. Open the [reproduction contribution issue](https://github.com/immu4989/awesome-agentic-usecases/issues/new?template=independent-reproduction.yml)
   with the fork workflow URL and submission digest. Do not send an oracle, raw trace, identity
   document, credential, target, personal data, or confidential relationship evidence.

The workflow never receives the oracle. It validates the answer-free challenge and your declared
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

No submission becomes a model ranking, certification, compliance finding, production-safety claim,
government endorsement, or permission to automate the protected decision.

## Verify campaign integrity

```bash
python reproduction-challenges/submit.py verify-campaign
```

This checks the registry, every challenge's embedded digest and oracle commitment shape, the absence
of gold fields, all template task ids, and the declared public boundary.
