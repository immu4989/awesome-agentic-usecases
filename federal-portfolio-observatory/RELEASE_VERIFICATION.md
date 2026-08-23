# Verify a Portfolio Observatory release

Download the ZIP, SPDX 2.3 document, and `SHA256SUMS` from the same tagged GitHub release.
Then run from the directory that contains all three files:

```bash
sha256sum --check SHA256SUMS
unzip aau-federal-portfolio-observatory-v0.5.0.zip
python aau-federal-portfolio-observatory-v0.5.0/verify_release.py .
gh attestation verify aau-federal-portfolio-observatory-v0.5.0.zip \
  --repo immu4989/awesome-agentic-usecases
gh attestation verify aau-federal-portfolio-observatory-v0.5.0.spdx.json \
  --repo immu4989/awesome-agentic-usecases
```

On macOS, use `shasum -a 256 -c SHA256SUMS` for the first command. The local verifier rejects
checksum drift, unexpected or duplicate members, traversal paths, symlinks, manifest differences,
and SPDX file/digest differences. GitHub attestation verification independently binds each release
artifact to the repository workflow that built it.

Verification establishes artifact integrity and build provenance. It does not make the artifact an
official government publication, authorize disclosure, certify compliance, validate a portfolio,
or approve any investment, acquisition, award, deployment, savings claim, or protected decision.
