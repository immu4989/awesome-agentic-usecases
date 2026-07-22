<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/shape-intervention%20A%2FB-008300" alt="intervention">
  <img src="https://img.shields.io/badge/tests-this%20repo's%20own%20advice-eda100" alt="tests our advice">
  <img src="https://img.shields.io/badge/reproduce-%240%20free%20tier-4a3aa7" alt="free to reproduce">
</p>

# 🔧 Refund Guarded — testing our own advice

## The gap this closes

Across this repo we published a recommendation, in the root README, in a failure-modes
doc, and in a post that got read by strangers:

> Put prohibitions in the tool layer, not the prompt.

That was **inferred** from a failure pattern, not measured. For a repo whose entire
premise is "verified, not asserted," it was the one claim resting on reasoning — and the
one most people would act on. This use case measures it.

Two interventions, each a single change against a committed baseline on the
[refund task](../refund-resolution-agent/), same 30 scenarios, same gold, same models:

- **`enforced`** — the irreversible tools refuse when policy forbids the action. The
  **prompt is byte-identical** to the baseline; the model is never told the guard exists,
  so only the environment varies.
- **`commit`** — one paragraph appended to the prompt telling the model to close the
  ticket before ending its turn. Aimed at the commit-stall that cost gpt-oss 29 of 90 runs.

## Results

| Intervention | Model | Metric | Baseline | After | Δ |
|---|---|---|---|---|---|
| **`enforced`** | mistral-small | safe & correct | 0.333 | **0.822** | **+0.489** |
| | | no unsafe action | 0.500 | **1.000** | +0.500 |
| | | cost / scenario | $0.0006 | $0.0007 | ~flat |
| **`commit`** | gpt-oss-120b | submitted | 0.678 | **0.344** | **−0.333** |
| | | safe & correct | 0.644 | **0.333** | **−0.311** |

**Change the environment and it works. Change the instructions and it backfires.**

Two remedies for two documented failures, on the same task, in the same week. The one
that altered what was *possible* gained 49 points for a rounding error in cost. The one
that altered what the model was *told* lost 31 points and **doubled the exact failure it
was written to fix** — stalls went 29 → 59 of 90.

### What the guard actually did, which is not what the advice implied

- **`blocked_attempt` = 0.489.** The model still reached for the forbidden refund in 44
  of 90 runs. Its disposition is entirely unchanged; nothing was learned. Remove the
  guard and all 45 forbidden refunds return.
- **`recovered_after_block` = 1.000.** In every one of those 44 runs it then reached the
  **correct** resolution — 15 chargebacks to escalate, 15 over-threshold to escalate, 14
  out-of-window to replacement. No thrashing, no stalling, no second wrong answer.

So the model knew the right answer the whole time and simply preferred the shortcut.
Tool-layer enforcement is not a workaround for an agent that cannot follow policy. It is
**removing an easier option from an agent that already knows better** — which is also why
it costs nothing.

### The practical result

Enforced `mistral-small` (**0.822**) beats baseline `gpt-oss-120b` (0.644) and beats the
three-agent [crew](../refund-crew/) (0.411), at a sixth of the crew's cost per scenario.
The two expensive answers to "my agent does unsafe things" are a bigger model and more
agents. Thirty lines of policy in the tool layer beat both.

## Failure modes

See [FAILURE_MODES.md](FAILURE_MODES.md) — including why a clean `no_unsafe_action`
score can hide an entirely unchanged disposition.

## Run it

```bash
pip install -e ../../harness -e ../refund-resolution-agent -e .
refund-guarded eval --variant enforced --backend mock
export MISTRAL_API_KEY=...
refund-guarded eval --variant enforced --backend mistral --repeats 3
refund-guarded eval --variant commit   --backend mistral --repeats 3
```

Scenarios come from `../refund-resolution-agent/evals/scenarios.jsonl`, so every variant
is always measured on the same cases as the baseline.
