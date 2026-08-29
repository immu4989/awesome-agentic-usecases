# Public-Value Pilot Network

> A model score is not public value. A field claim needs a baseline, a bounded observation, and
> an independent path to reproduction.

This network provides a strict contribution contract for organizations that want to test whether
an agent reduces burden or improves outcomes without uploading operational or participant data to
this repository.

Evidence levels are derived from artifacts:

1. **Designed** — reviewed suite, agent receipt, measures, boundaries, and stop conditions.
2. **Review ready** — human comparator and institutional determination added.
3. **Observed** — bounded field artifact bound to the same suite.
4. **Independently reproduced** — a different organization supplies a reviewed same-suite artifact.

Missing evidence remains visible. The tool rejects causal claims, false independence, mismatched
suite hashes, incomplete public-data exclusions, and unverified savings claims.

```bash
python3 public-value-pilot-network/aau_pilot_network.py assess \
  public-value-pilot-network/pilots/foia-routing-partner-call.json \
  --out /tmp/foia-pilot-assessment.json
```

The committed FOIA record is intentionally only **Designed**. It does not claim an agency partner,
human baseline, field result, institutional determination, or independent reproduction. Those
gaps require real external organizations; the repository will not fabricate them.

## Partner with the network

Open the dedicated proposal issue with a public or synthetic task description. Do not attach
request records, participant data, personal information, credentials, private telemetry, or
nonpublic agency material. The participating institution retains collection, review, and risk
authority.
