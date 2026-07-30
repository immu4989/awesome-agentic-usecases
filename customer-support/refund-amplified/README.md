<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/shape-adversarial%20A%2FB-b3261e" alt="adversarial">
  <img src="https://img.shields.io/badge/attack-denial%20of%20wallet-e07b00" alt="denial of wallet">
  <img src="https://img.shields.io/badge/OWASP-LLM10-6a1b9a" alt="OWASP LLM10">
  <img src="https://img.shields.io/badge/reproduce-%243.76-0b8457" alt="cost to reproduce">
</p>

# 💸 Refund Amplified — the answer is right, the bill is not

## The gap this closes

Every adversarial use case in this repo so far asks whether an attacker can make an agent
do the **wrong thing**. [Injection](../refund-injected/) moves money that policy forbade.
[Memory poisoning](../refund-memory/) suppresses a safety check. Both are scored by
consequence, and both are visible to a metric that watches outcomes.

This one asks a question no accuracy metric can answer: what if the attacker leaves the
answer alone and just runs up the bill?

OWASP calls it **LLM10, Unbounded Consumption**, and names denial of wallet explicitly. It
is the failure that every correctness benchmark is structurally blind to — the run
succeeds, the resolution is right, the safety checks pass, and the invoice is several times
larger than it should be.

## The mechanism, measured before it was designed around

`run_tool_agent` re-sends the whole message history every turn. A tool result that arrives
on turn 2 is part of the *input* on turns 3…N, so cost is superlinear in tool-output
volume: the attacker pays for their payload once, the victim pays for it repeatedly.

Probed on gpt-oss **before** any of this was built — identical task, identical tool
sequence, the only change being a padded field inside each tool result:

| | tool calls | turns | input tokens | cost |
|---|---|---|---|---|
| small tool results | 4 | 5 | 1,530 | $0.00038 |
| **large tool results** | **4** | **5** | **9,400** | **$0.00160** |

Same calls, same turns, **6.1× the input tokens**. That single fact shapes everything
below: the expensive vector is invisible to any monitor that counts calls or turns.

## The design

Scenarios are the committed [refund-resolution-agent](../refund-resolution-agent/) set,
amplified at run time. **Gold comes from the baseline's `gold_plan` and is never
recomputed**, so an amplification cannot change what the correct answer was — every
amplified scenario has an exact clean twin already measured next door. That is what makes
"the answer was right and the bill was wrong" a statement about cost alone.

The attacker controls two things a real support system genuinely exposes: the ticket text,
and customer-supplied fields on their own records.

| Archetype | Vector | Extra calls? | Visible to call-counting? |
|---|---|---|---|
| `CLEAN_TWIN` | baseline ticket, unchanged | — | control |
| `FANOUT` | ticket asks the agent to review 8 other orders | yes | yes |
| `BLOAT` | a customer-written field on the order is enormous | **no** | **no** |
| `LEGIT_COMPLEX` | genuinely needs several lookups | yes, legitimately | over-blocking control |

**Arms.** `none` · `prompt_guard` (resolve only the order in scope) · `budget_gate` (tool
layer caps repeated lookups and truncates oversized results) · `both`.

## Results

2 model families × 4 arms × 30 base scenarios × 4 archetypes × 3 repeats = **360 runs per
arm**. Cost is reported relative to each arm's own `CLEAN_TWIN`, never absolutely, because
providers differ by an order of magnitude in price.

### The bill, undefended

| model | `FANOUT` | `BLOAT` | `LEGIT_COMPLEX` | accuracy |
|---|---|---|---|---|
| **gpt-oss-120b** | **3.69×** | **1.75×** | 2.20× | flat |
| **mistral-small** | **1.75×** | **1.68×** | 1.57× | flat |

`correct` and `safe` do not move with archetype on either model. There is no error, no
refusal and no policy violation — just an invoice up to 3.7× larger for a ticket whose
right answer never changed.

### The expensive vector is the one nothing is watching

`BLOAT` costs **1.75×** on gpt-oss at **3.6 calls / 4.6 turns**, against the clean twin's
**3.4 / 4.6**. On mistral, **1.68×** at **3.5 / 4.4** against **3.4 / 4.4**.

Rate limits and tool-call quotas are the defences teams actually deploy. Both are blind
here. The cost is not in how many times the agent acted; it is in how much text each action
dragged into a conversation that gets re-sent on every subsequent turn.

### Neither defence covers both vectors

Cost relative to each arm's own clean twin:

| arm | gpt-oss `FANOUT` | gpt-oss `BLOAT` | mistral `FANOUT` | mistral `BLOAT` |
|---|---|---|---|---|
| `none` | 3.69× | 1.75× | 1.75× | 1.68× |
| `prompt_guard` | **1.11×** | 1.66× | **1.01×** | 1.62× |
| `budget_gate` | 2.32× | **1.18×** | 1.51× | **1.10×** |
| `both` | **1.11×** | **1.16×** | **1.03×** | **1.00×** |

Two structural results, both reproduced on both models:

**A prompt guard cannot fix `BLOAT`.** This was written into [DESIGN.md](DESIGN.md) as a
falsifiable prediction before the runs, and it held: 1.75× → 1.66× on gpt-oss, 1.68× →
1.62× on mistral. It is not a wording problem. By the time an oversized result is in the
context window the tokens are bought, and bought again every later turn. An instruction can
change what an agent *asks for*, never what it is *charged for* on work already done.

**A budget gate cannot fix `FANOUT`.** 3.69× → 2.32× on gpt-oss. A refusal is not free: the
request and the refusal both enter the conversation and are replayed, and the extra round
trip costs a turn of its own.

They are not competing defences to be benchmarked against each other. They address
different halves of the problem, and deploying either alone leaves a vector fully open.
Combined, they close both on both models — gpt-oss to 1.11× / 1.16×, mistral to
1.03× / 1.00× — which is the practical recommendation this use case exists to support.

## Honest limits

- **`LEGIT_COMPLEX` cannot detect over-blocking through accuracy.** Gold is inherited from
  the baseline and depends only on the in-scope order, so an agent that refuses every
  sibling lookup still answers correctly. Fixing that would mean giving up the property
  that makes the cost claim clean. Over-blocking is reported instead through suppressed
  legitimate work — mistral's `LEGIT_COMPLEX` cost falls 1.57× → 1.24× under `prompt_guard`
  because the agent stops checking duplicates the customer legitimately raised.
- **gpt-oss stalls on 32–37% of runs.** This does not explain the cost signal:
  amplification recomputed on completed runs only matches the all-runs figure in every cell
  (`none` FANOUT 3.69× → 3.45×, BLOAT 1.75× → 1.83×).
- **`mistral-small-latest` is a floating alias** and is recorded unpinned; re-running may
  exercise different weights.
- The dollar figures are provider list prices at time of run, not a claim about what any
  particular deployment pays.

## Failure modes

See [FAILURE_MODES.md](FAILURE_MODES.md) — including the truncation bug that bought a
smaller bill by destroying the agent's own tool results.

## Run it

```bash
pip install -e ../../harness -e ../refund-resolution-agent -e .
refund-amplified eval --arm none --backend mock          # free, no API key

export FIREWORKS_API_KEY=...
for arm in none prompt_guard budget_gate both; do
  refund-amplified eval --arm $arm --backend fireworks \
    --model accounts/fireworks/models/gpt-oss-120b --repeats 3
done

python evals/analyse.py    # per-archetype bill, x vs clean twin, calls and turns beside it
```

Committed cost: **$3.76** across 8 real runs (gpt-oss $2.54, mistral $1.22).
