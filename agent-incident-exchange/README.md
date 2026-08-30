# AAU Agent Incident Exchange

> Turn a public agent-security lesson into a regression another organization can verify.

The Exchange publishes privacy-bounded incident abstractions with exact affected components,
protocols, failure shapes, authority boundaries, source links, clean-twin state, regression artifact
hashes, and post-fix evidence status. It exports four machine-readable views without claiming they
are interchangeable:

- SARIF 2.1.0 findings for developer and security workflows;
- OpenVEX statements for affected/fixed/under-investigation status exchange;
- an experimental CSAF 2.0 bridge for advisory-system exploration; and
- an experimental OCSF 1.4 field bridge for event-pipeline exploration.

The CSAF and OCSF outputs explicitly state that they have not been validated as official schema
extensions or conformant advisories. No export is attribution, an original-incident reproduction,
a CVE, a regulator feed, a production impact determination, certification, or field-effectiveness
evidence.

## Run it

```bash
python agent-incident-exchange/aau_incident_exchange.py validate \
  agent-incident-exchange/examples/reference-exchange.json --root .

python agent-incident-exchange/aau_incident_exchange.py pack \
  agent-incident-exchange/examples/reference-exchange.json \
  --root . --out /tmp/aau-agent-incident-exchange

python agent-incident-exchange/aau_incident_exchange.py verify-pack \
  /tmp/aau-agent-incident-exchange --root .
```

The committed exchange contains three public-synthetic lessons:

| ID | Lesson | Bound artifact | Status |
|---|---|---|---|
| `AAU-AGENT-2026-0001` | Task persistence, undeclared peer communication, egress and monitor loss | Incident Regression Commons | Mitigation available |
| `AAU-AGENT-2026-0002` | Dependency fix without twins, continuity, rollback, or approval evidence | Verified Fix Commons | Fixed in fixture |
| `AAU-AGENT-2026-0003` | Child authority or queued work surviving parent containment | Containment Drill Runner | Mitigation available |

Every entry points to committed public bytes and carries their SHA-256. `validate` fails if the
artifact moves or changes. `make_exchange.py` is the only generator for the derived feed, so CI can
detect metadata or regression drift.

## Export one view

```bash
python agent-incident-exchange/aau_incident_exchange.py export \
  agent-incident-exchange/examples/reference-exchange.json sarif \
  --out /tmp/agent-findings.sarif.json
```

Replace `sarif` with `openvex`, `csaf-bridge`, or `ocsf-bridge`.

## Sharing boundary

Only `TLP:CLEAR` and `TLP:GREEN` abstractions are accepted. Every public record must explicitly
exclude credentials, targets, personal data, raw traces, and exploit instructions. The Exchange is
not an intake for an active incident or vulnerability. Follow the affected organization's security
policy and appropriate government or sector reporting routes for real events.

The strict machine contract is [`exchange.schema.json`](exchange.schema.json). The reference pack
and every export are recomputed during verification instead of trusting stored summaries.
