# BagIt evidence-transfer interoperability

This is a **synthetic interoperability exercise**, not Library of Congress endorsement,
independent reproduction, a full conformance suite, or an agency records-transfer qualification.
It tests exported `aau-evidence-bag/1.0` directories against the published
[LibraryOfCongress/bagit-python](https://github.com/LibraryOfCongress/bagit-python) library,
version **1.9.0**, using full checksum validation, not its fast byte/file-count check.

The AAU runtime has no BagIt dependency. `requirements.txt` pins the test dependency's published
source-distribution SHA-256; pip's isolated build tools are not fully hash-locked. Preparing this
test environment requires network access and executes trusted packaging tools. This is not a
hermetic build or an offline dependency installation recipe. The separately documented
[offline installation kit](../../README.md#prepare-an-offline-installation-kit) serves that purpose.

From a reviewed checkout, with an already-built current local harness wheel:

```bash
python3 -m venv /tmp/aau-bagit-check-venv
/tmp/aau-bagit-check-venv/bin/python -m pip --isolated install \
  --require-hashes --no-deps -r harness/compatibility/bagit/requirements.txt
/tmp/aau-bagit-check-venv/bin/python -m pip --no-index --no-deps /path/to/aau_harness-1.6.0-py3-none-any.whl
/tmp/aau-bagit-check-venv/bin/python harness/tools/check_bagit_transfer.py --out /tmp/aau-bagit-results
```

Choose unused output/environment paths. The probe refuses to overwrite its output. CI runs the
copied probe outside the checkout with the locally built wheel and an environment stripped of
model credentials. The probe uses synthetic local files and does not call a model, fetch payloads,
or upload results; it is not an operating-system network sandbox.

| Synthetic change | Library full validation | AAU with original receiver pin |
| --- | --- | --- |
| Unchanged directory, binary data and zero-byte file | Pass | Pass |
| Same-length byte corruption | Reject | Reject |
| Missing zero-byte file | Reject | Reject |
| Extra zero-byte file | Reject | Reject |
| Changed metadata tag | Reject | Reject |
| Removed empty directory | Pass | Reject |
| Different payload with recomputed checksums | Pass | Reject |

The final two rows are intentional boundaries: ordinary BagIt manifests cover files rather than
empty directories, and recomputing all checksums can produce a valid *different* bag. AAU additionally
binds directory presence in a tag file and requires an independently retained tag-manifest pin.
Those controls do not establish sender identity or approval. A pin accepted from the same untrusted
delivery cannot substitute for an independently controlled expected value.

`compatibility.json` records each observed result, the library module hash and version, and the
original transfer receipt. Unit tests separately replay a transported receiver-pinned evidence
index whose policy fails. Transport success leaves that policy failure unchanged.

Research checked November 22, 2026: [RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html)
defines the BagIt 1.0 layout and explains its security boundaries. This project exports a bounded,
canonical subset with SHA-256 and SHA-512; it does **not** accept every valid BagIt representation.
