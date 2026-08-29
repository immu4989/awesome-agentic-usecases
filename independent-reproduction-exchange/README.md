# Independent Reproduction Exchange

The repository used to accept an `independent_reproduction: true` declaration. This protocol asks for evidence instead: an issuer commits to a hidden oracle, a separate reproducer works from the answer-free challenge, and a third reviewer adjudicates the revealed run. Every file is hash-bound. No private trace, target, credential, or participant name belongs in the public pack.

## One blind exchange

```bash
# 1. Issuer: publish challenge.json; keep oracle.json outside the shared workspace.
AAU_ISSUER_COMMITMENT="$(openssl rand -hex 32)"
python aau_reproduction.py issue \
  ../frontier-defense-benchmark/examples/collective-defense-suite.json \
  --challenge-id your-public-challenge-v1 \
  --issuer-commitment "$AAU_ISSUER_COMMITMENT" \
  --challenge-out /tmp/challenge.json \
  --oracle-out /secure-local-path/oracle.json

# 2. Reproducer: answer the challenge and publish a challenge-bound submission.
python aau_reproduction.py submit /tmp/challenge.json responses.json metadata.json \
  --out /tmp/submission.json

# 3. Separate reviewer: reveal the oracle only after submission, then adjudicate.
python aau_reproduction.py adjudicate /tmp/challenge.json /secure-local-path/oracle.json \
  /tmp/submission.json review.json --out /tmp/reproduction-pack

# 4. Anyone can recompute the receipt, role gate, statement, and byte manifest.
python aau_reproduction.py verify-pack /tmp/reproduction-pack

# Optional: create deterministic release bytes before adding a signed workflow attestation.
python aau_reproduction.py bundle /tmp/reproduction-pack --out /tmp/reproduction-pack.zip
```

The committed [`examples/revealed-protocol-demo`](examples/revealed-protocol-demo/) is deliberately **not** an independent reproduction: all three simulated roles belong to the maintainer reference workflow. Its oracle is public because it teaches the protocol after reveal. Never use it as a live blind challenge.

Generate role commitments from high-entropy random secrets and keep any role mapping outside the
public pack. Do not hash a name, email, account id, or other guessable identifier.

The repository's manual `Reproduction protocol bundle` workflow verifies and deterministically
bundles that walkthrough, then creates a signed GitHub Artifact Attestation for the ZIP. That signed
workflow identity does not change the pack's `protocol_demonstration` evidence level. See
[`RELEASE_VERIFICATION.md`](RELEASE_VERIFICATION.md).

## What is and is not proved

| Claim | Enforcement |
|---|---|
| The public challenge omitted the gold answers | Machine-checkable structure |
| The revealed oracle is the one committed at issue time | SHA-256 commitment |
| The receipt is exactly recomputable from challenge, oracle, and response | Deterministic verifier |
| The in-toto statement binds the receipt bytes | SHA-256 subject digest |
| Issuer, reproducer, and reviewer used distinct commitments | Machine-checkable |
| Those roles are actually organizationally independent | Human-reviewed relationship evidence; **not cryptographic proof** |
| A named identity signed the result | Not provided by the local statement; attach and verify a GitHub Artifact Attestation or Sigstore attestation |
| The system is safe, compliant, or effective in the field | **Not claimed** |

## Federate without a leaderboard

```bash
python aau_reproduction.py federate /path/to/pack-* \
  --minimum-cell-size 3 --out /tmp/federated-report.json
```

Only packs whose role and relationship gate reaches `independence_reviewed` enter aggregate cells. Cells smaller than three are suppressed; role commitments and names never appear; measurements from different challenges are never combined into a universal score. Protocol demonstrations remain visible as demonstrations and do not advance the independent count.

## Protocol basis

- [NIST AI 800-2](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.800-2.ipd.pdf) — transparent, valid, reproducible automated benchmark evaluation.
- [NIST AITE](https://www.nist.gov/news-events/news/2026/07/announcing-nists-artificial-intelligence-technology-evaluation-aite) — blind data in a sequestered environment to reduce contamination.
- [NIST practices for evaluation cheating](https://www.nist.gov/caisi/cheating-ai-agent-evaluations/4-practices-detecting-and-preventing-evaluation-cheating) — preserve held-out cases, declare affordances, and review transcripts.
- [in-toto Statement v1](https://in-toto.io/Statement/v1) — bind immutable subjects to a typed predicate by digest.
- [SLSA provenance](https://slsa.dev/spec/v1.2/provenance) — describe where, when, and how an artifact was produced.
- [GitHub Artifact Attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations) — add a signed build identity layer and verify it with GitHub CLI.

This protocol is for public or synthetic defensive evaluation. It is not a disclosure channel, identity service, threat-intelligence feed, certification, procurement score, or claim of field effectiveness.
