<!-- Open this template with: /compare/main...your-branch?expand=1&template=gallery-adaptation.md -->

## Adaptation

- **Gallery id:**
- **Lab path:**
- **Starting AAU contract or use case:**
- **Contributor GitHub handle:**

## What this helps people do

<!-- Name the beneficiary, real decision/action, evidence, and costly failure. -->

## Evidence-derived status

<!-- Paste: aau gallery validate <gallery-id> -->

```text

```

I understand that CI derives the Gallery level from committed artifacts. This PR does not
claim regulator approval, production safety, certification, or permission to automate a
protected decision.

## Safe and reproducible

- [ ] The lab contains only synthetic or public data—no secrets or identifying records.
- [ ] `aau-forge.json` and `contract-blueprint.json` are committed.
- [ ] Every `TODO(domain)` is either replaced or remains visible as an incomplete review item.
- [ ] The source ledger uses dated primary sources and records jurisdiction and scope.
- [ ] `evals/scenarios.jsonl` contains at least 20 seeded scenarios.
- [ ] The mock run passes with no API key.
- [ ] Real-model evidence uses n≥3 repeats and reports cost and latency.
- [ ] `FAILURE_MODES.md` links at least three observed failures to reproducible scenarios.
- [ ] The README states the protected human authority and synthetic-world limitations.
- [ ] `aau gallery validate <gallery-id>` and `pytest harness/tests -q` pass.
