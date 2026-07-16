# 🤖 Awesome Agentic Use Cases

**Agentic AI use cases that are verified, not just runnable — evals, cost numbers, and failure modes included.**

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Verified](https://img.shields.io/badge/every%20agent-evals%20%2B%20cost%20%2B%20failure%20modes-purple)

Most agent demos prove an agent *can run once*. Almost none prove it *works*: how often
it gets the right answer, what a run costs in dollars, and where it breaks. This repo
holds agentic AI use cases for real business problems, each shipped with the harness
that proves it — an eval set with ground truth, cost-per-run measured from token usage,
results reported across repeated runs (agents are stochastic; n=1 proves nothing), and
failure modes that were observed, not hypothesized.

Every use case runs end-to-end on synthetic data with one command. No proprietary data,
no downloads. See [VERIFICATION.md](VERIFICATION.md) for the exact bar every entry must
meet.

## Industries

| # | Industry | Status |
|---|---|---|
| 1 | [🚛 Logistics & Supply Chain](logistics-supply-chain/) | ✅ Shipping |
| 2 | 🛒 Retail & Workforce | 🔜 Wave 2 |
| 3 | 🛡️ Security Operations | 🔜 Wave 2 |
| 4 | 💳 Financial Services & Fraud | 🔜 Wave 2 |
| 5 | 🎧 Customer Support & Success | 📋 Roadmap |
| 6 | 🏥 Healthcare & Life Sciences | 📋 Roadmap |
| 7 | ⚖️ Legal & Compliance | 📋 Roadmap |
| 8 | 🏭 Manufacturing & Industrial | 📋 Roadmap |
| 9 | 🧾 Insurance | 📋 Roadmap |
| 10 | 👥 HR & Recruiting | 📋 Roadmap |
| 11 | 📈 Sales & Marketing | 📋 Roadmap |
| 12 | 🖥️ IT Ops & DevOps | 📋 Roadmap |
| 13 | ⚡ Energy & Utilities | 📋 Roadmap |
| 14 | 🏗️ Real Estate & Construction | 📋 Roadmap |
| 15 | 🎓 Education | 📋 Roadmap |

## Use cases

| Use case | Industry | Capability | The question it answers |
|---|---|---|---|
| [🎫 exception-triage-agent](logistics-supply-chain/exception-triage-agent/) | Logistics | `investigate` `decide` | Which resolution queue should each stuck-shipment ticket go to, which tickets can resolve themselves, and which need a human — decided by an agent that investigates each ticket with tools before committing? |

## Capability tags

Every use case is tagged by what the agent *does*, so you can filter by pattern rather
than industry:

| Tag | Meaning |
|---|---|
| `predict` | Forecasting, anomaly detection, risk scoring |
| `decide` | Quoting, pricing, triage, routing, prioritization |
| `plan` | Multi-step task decomposition, scheduling, optimization |
| `act` | Tool-calling agents that execute — write to systems, send, file |
| `watch` | Always-on monitoring, alerting, drift detection |
| `investigate` | Multi-hop research, RAG, root-cause analysis |

Architecture tags: `single-agent` / `multi-agent` / `human-in-loop`.

## Quick start

```bash
git clone https://github.com/immu4989/awesome-agentic-usecases
cd awesome-agentic-usecases
pip install -e harness -e logistics-supply-chain/exception-triage-agent

# Full eval on the built-in deterministic mock model — no API key, no cost
exception-triage-agent eval --backend mock

# Real-model eval on a free tier — $0 actual spend (also: groq, cerebras, deepseek)
export MISTRAL_API_KEY=...
exception-triage-agent eval --backend mistral --repeats 3

# Or Anthropic (requires ANTHROPIC_API_KEY; prints a cost estimate first)
exception-triage-agent eval --backend anthropic --repeats 3
```

Model access is pluggable: one OpenAI-compatible backend covers Mistral, Groq,
Gemini, Cerebras (hosts GLM), and DeepSeek, so every use case can be verified on
free tiers before anyone spends a dollar. Reports price measured token usage at
list rates either way, so the cost numbers stay meaningful.

## What "verified" means here

1. **Runs from a clean clone with one command.**
2. **Eval set with ≥20 scenarios** and programmatic ground truth.
3. **Cost per run in dollars**, computed from actual token usage, not estimated.
4. **Results from n≥3 repeated runs** with variance — single-run agent numbers are noise.
5. **≥3 documented failure modes**, each with a reproducing input.

Full details and the reasoning behind each rule: [VERIFICATION.md](VERIFICATION.md).

## License

Apache-2.0
