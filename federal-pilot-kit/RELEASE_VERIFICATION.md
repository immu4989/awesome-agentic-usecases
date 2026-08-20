# Verify a Federal Pilot Kit release

A release has three independent signals:

1. `SHA256SUMS` checks the downloaded archive and SPDX file byte-for-byte.
2. `verify_release.py` checks archive paths, size and compression limits, the exact manifest,
   every payload digest, external/internal SBOM parity, and non-approval claims.
3. GitHub's artifact attestation binds the artifact digest to this repository's release workflow.

Download the ZIP, SPDX JSON, and `SHA256SUMS` from the same tagged release. Check the downloaded
bytes and their build provenance before extracting anything:

```bash
sha256sum --check SHA256SUMS
gh attestation verify aau-federal-pilot-kit-v0.4.0.zip \
  --repo immu4989/awesome-agentic-usecases
```

On macOS, use `shasum -a 256 --check SHA256SUMS`. Then extract the verified ZIP and run the
included structural verifier against the download directory:

```bash
unzip aau-federal-pilot-kit-v0.4.0.zip
python aau-federal-pilot-kit-v0.4.0/verify_release.py .
```

For a local source build:

```bash
python federal-pilot-kit/tools/build_release.py \
  --version 0.4.0 \
  --source-revision "$(git rev-parse HEAD)" \
  --source-date "$(git show -s --format=%cI HEAD)" \
  --output /tmp/aau-federal-pilot-release

python federal-pilot-kit/verify_release.py /tmp/aau-federal-pilot-release
```

Rebuilding twice with the same source revision, source date, Python version, and builder should
produce the same bytes. The committed test suite checks that property.

These checks establish local byte integrity, payload inventory, and workflow provenance. They do
not establish evidence quality, independent reproduction, security authorization, federal
approval, compliance, or fitness for a mission. Inspect the source revision and the
[threat model](THREAT_MODEL.md) before running the kit.
