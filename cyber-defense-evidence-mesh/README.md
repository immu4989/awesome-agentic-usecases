# Cyber Defense Evidence Mesh

Organizations often cannot share raw security logs, internal targets, identities, or operational details. This mesh shares something narrower: a hash-bound aggregate statement of **what defensive control shape was tested, at what evidence level, and which bounded measurements resulted**.

It accepts Verified Fix, Agent Containment, Essential-Service Defender, and Frontier Defense Benchmark receipts. Each pack adds a public-safe evidence index, reusable control fingerprints, an experimental OpenTelemetry naming bridge, and a byte-level manifest. Verified Fix packs separately provide OpenVEX-style and SARIF exports.

```bash
python aau_evidence_mesh.py build examples/reference-mesh.json --out /tmp/evidence-mesh
python aau_evidence_mesh.py verify-pack /tmp/evidence-mesh
```

The 0.2 contract refuses absolute paths, parent traversal, symlinks, oversized JSON, unlabeled evidence, and trust-only independent-reproduction labels. `independently_reproduced` now requires a complete, locally verified [Independent Reproduction Exchange](../independent-reproduction-exchange/) pack that recomputes its challenge, oracle, submission, review, receipt, statement, adjudication, and manifest; binds the exact artifact bytes and kind; passes the distinct-role and reviewed-relationship gate; and explicitly states that independence is not cryptographic proof.

This is not a threat-intelligence feed, raw telemetry exchange, vulnerability disclosure channel, organizational score, compliance finding, safety certification, or proof of field effectiveness.
