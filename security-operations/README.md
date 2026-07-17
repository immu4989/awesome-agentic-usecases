# 🛡️ Security Operations

Agentic use cases for the SOC. Alert text is a detection's first guess, not the truth —
these agents verify against asset records, telemetry, and the response runbook before
committing, and every one is verified per [VERIFICATION.md](../VERIFICATION.md).

| Use case | Capability | The question it answers | Status |
|---|---|---|---|
| [🚨 alert-triage-agent](alert-triage-agent/) | `investigate` `decide` | Which queue does each security alert belong in, which alerts can safely auto-close, and which need incident response now — decided against telemetry and runbook clauses, not the alert text's vibes? | ✅ Ready |
