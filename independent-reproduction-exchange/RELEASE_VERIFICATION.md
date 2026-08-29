# Verify a signed reproduction protocol bundle

The manual **Reproduction protocol bundle** workflow first runs the full pack verifier, creates a
byte-deterministic ZIP, records its SHA-256 checksum, and asks GitHub to attest the ZIP from the
repository workflow identity.

Download the workflow artifact, then verify both layers:

```bash
sha256sum --check SHA256SUMS
gh attestation verify independent-reproduction-protocol-demo.zip \
  --repo immu4989/awesome-agentic-usecases
```

Unzip and recompute the protocol layer:

```bash
unzip independent-reproduction-protocol-demo.zip -d reproduction-pack
python independent-reproduction-exchange/aau_reproduction.py verify-pack reproduction-pack
```

Expected status for the committed walkthrough: `protocol_demonstration`.

The checksum proves downloaded bytes. The GitHub attestation binds those ZIP bytes to a repository
workflow identity. The pack verifier binds the challenge, revealed oracle, submission, review,
receipt, in-toto statement, adjudication, and manifest. None of these layers proves that the
maintainer walkthrough is organizationally independent, safe in production, certified, compliant,
government approved, or effective in the field.
