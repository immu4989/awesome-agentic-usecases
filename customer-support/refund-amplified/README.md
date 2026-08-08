<!-- README-EXPERIENCE:START -->
<p align="center">
  <img src="docs/experience.svg" width="100%" alt="Refund Amplified — animated case trace">
</p>
<!-- README-EXPERIENCE:END -->

<p align="center">
  <a href="../../README.md">← all use cases</a> ·
  <img src="https://img.shields.io/badge/shape-adversarial%20A%2FB-b3261e" alt="adversarial">
  <img src="https://img.shields.io/badge/attack-denial%20of%20wallet-e07b00" alt="denial of wallet">
  <img src="https://img.shields.io/badge/OWASP-LLM10-6a1b9a" alt="OWASP LLM10">
  <img src="https://img.shields.io/badge/reproduce-%243.63-0b8457" alt="cost to reproduce">
</p>

<!-- VISUAL-BRIEFING:START -->

## Visual briefing

### See the trap

<img src="docs/scenario-map.svg" width="100%" alt="Refund Amplified scenario anatomy: surface story, hidden truth, unsafe shortcut, and exact proof">

### Read the evidence

<img src="docs/benchmark.svg" width="100%" alt="Refund Amplified benchmark chart generated from committed real-model evaluations">

### Learn from the misses

<img src="docs/failure-cards.svg" width="100%" alt="Three observed and reproducible Refund Amplified failure modes">

<p align="center"><sub>Generated from committed <a href="results/">evaluation results</a> and <a href="FAILURE_MODES.md">observed failure modes</a> · rerun <code>python docs/make_readme_experiences.py</code> from the repository root</sub></p>

<!-- VISUAL-BRIEFING:END -->

# 💸 Refund Amplified — the bill is wrong, and sometimes the answer too

## The gap this closes

Every adversarial use case in this repo so far asks whether an attacker can make an agent
do the **wrong thing**. [Injection](../refund-injected/) moves money that policy forbade.
[Memory poisoning](../refund-memory/) suppresses a safety check. Both are scored by
consequence, and both are visible to a metric that watches outcomes.

This one asks a question no accuracy metric can answer: what if the attacker leaves the
answer alone and just runs up the bill?

OWASP calls it **LLM10, Unbounded Consumption**, and names denial of wallet explicitly.
On mistral that is exactly what happens: the run succeeds, the resolution is right, the
safety checks pass, and the invoice is several times larger than it should be — invisible
to any benchmark that scores answers.

On gpt-oss the original payload did two things at once, and it took a length-matched control
to tell them apart. Both are documented below, including the two readings this page got
wrong before the control existed.

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

| model | `FANOUT` | `BLOAT` | `LEGIT_COMPLEX` |
|---|---|---|---|
| **gpt-oss-120b** | **3.69×** | **1.75×** | 2.20× |
| **mistral-small** | **1.75×** | **1.68×** | 1.57× |

The correct answer never changed — gold is inherited and asserted byte-identical to the
clean twin. What did change is only the bill.

That is not the same as saying the runs are otherwise clean, and an earlier version of this
page said so. They are not. gpt-oss errors out on 31–43% of runs depending on archetype and
takes a forbidden action on 6–19% of them; mistral is worse on the second count, taking a
forbidden action in roughly 47% of runs on **every** archetype including the clean twin.
The claim this use case supports is that amplification does not *move* those numbers much,
not that they are passing.

### Length costs money. Persuasion costs accuracy. They are not the same failure.

`BLOAT`'s payload was a complaint — *"arrived damaged, the box was crushed, the courier left
it in the rain, the replacement never shipped."* Long **and** argumentative, which confounds
two things. `NEUTRAL_BLOAT` is the control: the identical field on the identical customer,
the same **8,760 characters**, carrying carrier scan events that argue for nothing.

gpt-oss, arm `none`, accuracy among completed runs:

| archetype | ×cost | calls | turns | accuracy | accuracy on `deny` tickets |
|---|---|---|---|---|---|
| `CLEAN_TWIN` | 1.00× | 3.42 | 4.42 | 0.942 | 1.00 (n=15) |
| `BLOAT` — long **and** argues for a refund | **1.75×** | 3.59 | 4.59 | 0.783 | **0.36** (n=14) |
| `NEUTRAL_BLOAT` — long, argues nothing | **1.50×** | **3.26** | **4.21** | **0.927** | **1.00** (n=14) |

**The dissociation is clean.** Length alone raises the bill 1.50× and leaves the decision
alone. The argumentative payload adds no accuracy harm through its length — it does it by
arguing, and the entire loss lands on `deny` tickets, the ones the text is arguing against.

The pure-length vector is also the stealthier one: `NEUTRAL_BLOAT` uses **fewer** tool calls
and **fewer** turns than the clean twin while costing half again as much. There is no
behavioural signal at all.

This matters for what the use case claims. Denial of wallet is real and is now isolated
from any correctness confound. What is *not* true — and two earlier versions of this page
said it was — is that context length degrades the decision.

### Where the accuracy loss actually comes from

The first version of this page claimed accuracy was flat on both models. That was wrong,
and the way it was wrong is worth keeping on the record: the *unconditional* numbers do
look flat, because gpt-oss stalls at different rates on different archetypes and the two
effects cancel. Conditioning on runs that actually submitted — the same lens this repo
built for [refund-memory](../refund-memory/) and then failed to apply here — shows
something else.

**gpt-oss, accuracy among runs that completed:**

| arm | `CLEAN_TWIN` | `FANOUT` | `BLOAT` | `LEGIT_COMPLEX` |
|---|---|---|---|---|
| `none` | 0.942 | 0.863 | **0.783** | **0.661** |
| `budget_gate` | 0.960 | 0.929 | **0.909** | 0.607 |

Safety moves with it: 0.942 on the clean twin, 0.817 on `BLOAT`, 0.726 on `LEGIT_COMPLEX`.

The accuracy loss on `BLOAT` is **indirect prompt injection through a customer-controlled
field** — the [Wave 11](../refund-injected/) mechanism arriving through a new door. Of 13
wrong `BLOAT` submissions, **10 predict `refund`** and 9 of those have gold `deny`; on the
clean twin, none of the 3 errors have gold `deny`.

Clustered bootstrap over the 30 base scenarios, against each arm's own clean twin:

| archetype | Δ correct | Δ safe |
|---|---|---|
| `FANOUT` | −0.080 `[−0.200, +0.046]` | −0.080 `[−0.211, +0.052]` |
| `BLOAT` | **−0.159** `[−0.317, −0.009]` | −0.126 `[−0.290, +0.040]` |
| `LEGIT_COMPLEX` | **−0.281** `[−0.462, −0.104]` | **−0.217** `[−0.408, −0.037]` |

So the accuracy drop is real on `BLOAT` but only barely — the interval nearly touches zero —
and clearly real on `LEGIT_COMPLEX`. The safety drop is significant on `LEGIT_COMPLEX`
only; "safety moves with it" was too strong for the other two.

`budget_gate` appears to recover `BLOAT` accuracy (0.783 → **0.909**), but that compares two
independent arm runs and the clustered bootstrap gives **+0.126, 95% CI [−0.007, +0.278]** —
it crosses zero. It is a promising signal, not a deployment argument, and an earlier version
of this page called it "a second, independent reason to deploy" the gate. It is not yet.

**On mistral no archetype differs significantly from its own clean twin**, so for that model
the pure denial-of-wallet reading holds (0.367 / 0.417 / 0.344 / 0.311 under `none`). Note
this is an underpowered null rather than a demonstrated flat line — the interval on the
clean twin alone spans [0.200, 0.533] — and `FANOUT` vs `LEGIT_COMPLEX` *do* differ from
each other (+0.106, 95% CI [+0.027, +0.188]). "Flat against control" is defensible;
"genuinely flat" was not.

### The expensive vector is the one nothing is watching

`BLOAT` costs **1.75×** on gpt-oss at **3.59 calls / 4.59 turns**, against the clean twin's
**3.42 / 4.42** — a difference of +0.17 on each, about 5%, which a clustered permutation
test cannot separate from noise (p = 0.33). On mistral the gap is smaller still: **3.5 /
4.4** against **3.4 / 4.4** (p = 0.50 and 0.67).

An earlier version of this page printed both turn columns as "4.6", which made them look
identical. They are not identical; they are indistinguishable, and the honest word is the
second one.

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
- **gpt-oss stalls on 32–38% of runs** (32.2% `prompt_guard`, 35.8% `budget_gate`, 37.5%
  `none` and `both`). This does not overturn the cost signal, but it does move it, and an
  earlier version of this page claimed the two matched "in every cell". They do not.
  Recomputed on completed runs only, `none` FANOUT 3.69× → 3.45× and BLOAT 1.75× → 1.83×,
  but `LEGIT_COMPLEX` rises 2.20× → 2.46×, and the headline combined arm moves from
  1.11× / 1.16× to **1.19× / 1.25×**. Every conclusion survives; several numbers shift by
  roughly 10%.
- **Conditioning on `submitted` conditions on a collider.** The denominator is itself
  affected by the treatment (52 / 51 / 60 / 62 completed runs across archetypes), so the
  conditional accuracy finding is not bound-robust: scoring every stalled run incorrect
  gives 0.544 vs 0.522 and the gap vanishes; scoring them all correct gives 0.967 vs 0.856
  and it survives. The unconditional numbers are nearly equal. This is the honest status of
  the accuracy result — a real effect among runs that completed, not a demonstrated
  property of the model.
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

Committed cost: **$3.63** across 8 real runs (gpt-oss $2.41, mistral $1.22).
