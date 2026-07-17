# 🛒 Retail & Workforce

Agentic use cases for retail operations and workforce management. A classic-ML
companion repo with a documented ground-truth workforce simulator lives at
[retail-workforce-analytics](https://github.com/immu4989/retail-workforce-analytics);
the entries here are agentic formulations — an LLM agent that investigates with tools
and commits to a decision, verified per [VERIFICATION.md](../VERIFICATION.md).

| Use case | Capability | The question it answers | Status |
|---|---|---|---|
| [🧑‍🍳 shift-coverage-triage-agent](shift-coverage-triage-agent/) | `investigate` `decide` | When crew call out, what's the compliant fill — overtime, borrow from a nearby store, run short, or escalate — given labor law and policy caps the manager's ticket never mentions? | ✅ Ready |
