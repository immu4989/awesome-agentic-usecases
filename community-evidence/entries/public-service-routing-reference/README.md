# Public Service Routing Reference

> Built with AAU · derived evidence level: **Generated**

Routes public-service questions to an official source or staffed channel without deciding eligibility.

## Who this helps

Residents, service navigators, and public program teams.

## Why fork it

Replace three synthetic facts with a reviewed service-specific routing boundary and connect an existing agent.

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
