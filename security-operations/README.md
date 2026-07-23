<p align="center">
  <a href="../README.md">← all industries</a> ·
  <img src="https://img.shields.io/badge/industry-Security%20Operations-4a3aa7" alt="Security Operations">
  <img src="https://img.shields.io/badge/use%20cases-3-4a3aa7" alt="3 use cases">
  <img src="https://img.shields.io/badge/verified-evals%20%C2%B7%20cost%20%C2%B7%20failure%20modes-008300" alt="verified">
</p>

# 🛡️ Security Operations

The deepest vertical in the repo, and the one that doubles as a thesis: **as agents get
tools, memory, and autonomy, the security question stops being "is the model aligned" and
becomes "what can the environment let it do."** These three use cases trace an incident
end to end — detect the threat, gate what enters the system, and stop what tries to leave —
each with programmatic ground truth, cost, and observed failure modes.

Two of the three are grounded in July 2026 incidents that happened while the repo was being
built: the [Hugging Face dataset-processing breach](artifact-admission-agent/) and the
[MCP tool-poisoning / lethal-trifecta](trifecta-exfil-agent/) research wave.

## The arc

| Stage | Use case | The question | Headline finding |
|---|---|---|---|
| **Detect** | [🚨 alert-triage-agent](alert-triage-agent/) | Which queue does each alert belong in — and can the agent tell a real attack from a scanner that looks like one? | Every model filed an authorized scanner's noise as `credential-abuse` when the alert text read like a brute-force — anchoring on the detector instead of verifying the source. |
| **Gate what enters** | [🛂 artifact-admission-agent](artifact-admission-agent/) | A dataset's manifest declares no code; its config executes anyway. Admit, sandbox, block, or escalate — before any of it runs? | We expected models to repeat the HF mistake (trust the manifest). They didn't — all three scanned the config. But **sandbox-by-default contained the residual unsafe admits, 0.122 → 0.000** on identical decisions. |
| **Stop what leaves** | [🕳️ trifecta-exfil-agent](trifecta-exfil-agent/) | Does an injection make a secret actually leave — and does it matter where the injection hides? | The identical instruction leaks **~0% in fetched content and 100% in a tool's own description**, every model. A prompt guard naming the attack stopped almost none of it; a **tool-layer dataflow gate took it to 0.000**. |

## The through-line

Read across the three and the same lesson recurs: **the fix is in the environment, not the
prompt.** The admission gate contains a fooled agent by sandboxing execution; the taint gate
contains a fooled agent by refusing any secret at every egress; both hold precisely because
they do not depend on the model being right. The adversarial A/B use cases elsewhere in the
repo ([refund-injected](../customer-support/refund-injected/)) reach the same conclusion from
the customer-support side. It is the most load-bearing finding in the project, and the one
teams deploying agents most need to internalize.

## Verify any of it

```bash
pip install -e ../harness -e alert-triage-agent
alert-triage-agent eval --backend mock          # deterministic, $0
export MISTRAL_API_KEY=...
alert-triage-agent eval --backend mistral --repeats 3
```

Each use case's README carries the full model comparison, the exact numbers, and a
`FAILURE_MODES.md` with a reproducing input for every documented failure.
