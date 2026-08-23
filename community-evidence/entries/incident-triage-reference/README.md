# Incident Triage Reference

> Built with AAU · derived evidence level: **Generated**

Routes operational incidents while preserving evidence and incident-command authority.

## Who this helps

Reliability, security, and incident-response teams.

## Why fork it

Swap in a reviewed incident taxonomy, forbidden actions, and routing outcomes for a local operations boundary.

## Inspect before sharing

```bash
python -m pip install aau-harness==1.3.0
aau submit --validate .
```

The validator recomputes the manifest, privacy boundary, suite/receipt binding, and progressive
evidence checks. This directory contains aggregate public receipts and a reviewed synthetic suite;
it intentionally excludes prompts, raw responses, reasoning, credentials, headers, and private
debug traces.

**Boundary:** the evidence level is not identity verification, certification, endorsement,
production validation, legal advice, or permission to automate a protected decision.
