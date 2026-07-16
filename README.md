<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
  <img alt="Awesome Agentic Use Cases — agentic AI use cases that are verified, not just runnable" src="docs/assets/banner-light.svg" width="100%">
</picture>

<p align="center">
  <a href="https://github.com/immu4989/awesome-agentic-usecases/actions/workflows/ci.yml"><img src="https://github.com/immu4989/awesome-agentic-usecases/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-2a78d6" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-Apache--2.0-008300" alt="Apache-2.0 license">
  <img src="https://img.shields.io/badge/reproduce%20for-%240%20(free%20tiers)-4a3aa7" alt="Reproduce for $0 on free tiers">
</p>

<p align="center">
  <a href="#the-64-cent-comparison">Results</a> ·
  <a href="#use-cases">Use cases</a> ·
  <a href="#industries">Industries</a> ·
  <a href="#what-verified-means-here">The verification bar</a> ·
  <a href="#quick-start">Quickstart</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

Most agent demos prove an agent *can run once*. Almost none prove it *works*: how often
it gets the right answer, what a run costs in dollars, and where it breaks. Every use
case here ships with the harness that proves it — an eval set with programmatic ground
truth, cost measured from token usage, results across repeated runs (agents are
stochastic; n=1 proves nothing), and failure modes that were **observed, not
hypothesized**. All of it runs end-to-end on synthetic data with one command, and the
model backends include free tiers, so reproducing any result costs nothing.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/stats-dark.svg">
  <img alt="4 models compared, $0.64 total eval spend, 8 failure modes observed, 90 runs per model, $0 to reproduce on free tiers" src="docs/assets/stats-light.svg" width="100%">
</picture>

## The 64-cent comparison

Same agent, same 30 scenarios, 3 repeats per model. Total spend for everything below:
**$0.64**.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/results-dark.svg">
  <img alt="Action accuracy by model: kimi-k2p6 1.000, gpt-oss-120b 0.778, mistral-small 0.700, Llama-3.3-70B 0.167" src="docs/assets/results-light.svg" width="100%">
</picture>

The ranking is the least interesting part. **The four models fail in four different
ways**, and only the failure breakdown tells you what you'd actually be deploying:

- 🥇 `kimi-k2p6` solved it — 90/90 — and the transcripts show *how*: it searched the
  policy KB twice per ticket, the exact retrieval step every other model fumbled. It
  buys that reliability at 13× the cost and 3× the latency of `gpt-oss-120b`.
- 🕳️ `gpt-oss-120b` investigates everything, then occasionally **never commits a
  decision** — all the evidence, no output, 6 runs out of 90.
- 📜 `mistral-small` investigates correctly, then misjudges policy — in one scenario it
  **cites the $2,000 escalation policy in its own reasoning, then violates it**, three
  repeats out of three.
- 🧩 `Llama-3.3-70B` fails on mechanics: 66/90 submissions were **missing the required
  `action` field**, and 17/90 skipped investigation entirely.

Every failure has a reproducing scenario id in
[FAILURE_MODES.md](logistics-supply-chain/exception-triage-agent/FAILURE_MODES.md).

## Use cases

| Use case | Industry | Capability | The question it answers |
|---|---|---|---|
| [🎫 exception-triage-agent](logistics-supply-chain/exception-triage-agent/) | Logistics | `investigate` `decide` | Which resolution queue should each stuck-shipment ticket go to, which tickets can resolve themselves, and which need a human — decided by an agent that investigates with tools before committing? |

Every use case is tagged by what the agent *does*: `predict` · `decide` · `plan` ·
`act` · `watch` · `investigate`, plus architecture (`single-agent` / `multi-agent` /
`human-in-loop`).

## Industries

| Shipping now | Next waves |
|---|---|
| 🚛 [Logistics & Supply Chain](logistics-supply-chain/) | 🛒 Retail & Workforce · 🛡️ Security Operations · 💳 Financial Services & Fraud |

<details>
<summary><b>Full 15-industry roadmap</b></summary>
<br>

| # | Industry | Status |
|---|---|---|
| 1 | 🚛 Logistics & Supply Chain | ✅ Shipping |
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

</details>

## What "verified" means here

Five rules, no exceptions — the full reasoning lives in [VERIFICATION.md](VERIFICATION.md):

|  | Rule |
|---|---|
| 1️⃣ | **Runs from a clean clone with one command** — no API key needed for the mock backend |
| 2️⃣ | **≥20 scenarios with programmatic ground truth**, committed and reproducible by seed |
| 3️⃣ | **Cost per run in dollars**, computed from actual token usage, never estimated |
| 4️⃣ | **n≥3 repeated runs with bootstrap CIs** — single-run agent numbers are noise |
| 5️⃣ | **≥3 observed failure modes**, each with a reproducing input |

## Quick start

```bash
git clone https://github.com/immu4989/awesome-agentic-usecases
cd awesome-agentic-usecases
pip install -e harness -e logistics-supply-chain/exception-triage-agent

# Full eval on the built-in deterministic mock model — no API key, no cost
exception-triage-agent eval --backend mock

# Real-model eval on a free tier — $0 actual spend
export MISTRAL_API_KEY=...
exception-triage-agent eval --backend mistral --repeats 3
```

One OpenAI-compatible backend covers **Mistral · Groq · Gemini · Cerebras (GLM) ·
DeepSeek · Together · Fireworks**, plus a native `anthropic` backend — so every use
case can be verified on free tiers before anyone spends a dollar, and adding a new
model to the comparison is one flag.

## Contributing

New use cases are welcome if they clear the [verification bar](VERIFICATION.md) —
see [CONTRIBUTING.md](CONTRIBUTING.md). Link-list additions aren't a fit; this isn't
a link list.

If this repo saved you an eval harness, a ⭐ helps others find it.

---

<p align="center">Apache-2.0 · built by <a href="https://github.com/immu4989">@immu4989</a> · classic-ML companions: <a href="https://github.com/immu4989/Logistics_UseCases">Logistics_UseCases</a> · <a href="https://github.com/immu4989/retail-workforce-analytics">retail-workforce-analytics</a></p>
