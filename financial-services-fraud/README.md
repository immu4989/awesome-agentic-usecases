# 💳 Financial Services & Fraud

Agentic use cases for banking fraud and transaction monitoring. Fraud alerts deceive in
both directions — a holiday charge looks like a stolen card, and a scam the customer was
tricked into authorizing rides their own trusted device — so these agents verify against
customer records, transaction signals, and fraud policy before committing. Every one is
verified per [VERIFICATION.md](../VERIFICATION.md).

| Use case | Capability | The question it answers | Status |
|---|---|---|---|
| [🚩 fraud-alert-triage-agent](fraud-alert-triage-agent/) | `investigate` `decide` | Which fraud queue does each transaction alert belong in, which can safely release, which to block, and which need the fraud team now — decided against the customer record and transaction signals, not the alert's framing? | ✅ Ready |
