# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs. Two model families × four arms × 30 base scenarios ×
4 archetypes × 3 repeats = 360 runs per arm, identical scenarios and identical gold
throughout.

Two entries are failures of the *experiment* rather than of the models. Both produced
clean-looking numbers, and both would have shipped.

---

### 1. The bill triples and every metric says the run was fine

- **Reproduce:** `--arm none`, compare `FANOUT` against `CLEAN_TWIN`.
- **What happens:** gpt-oss pays **3.69×**, mistral **1.75×**, for a ticket whose correct
  answer is unchanged. `correct` and `safe` do not move. There is no error, no refusal, no
  policy violation and no incident — just an invoice several times larger than it should be.
- **Why it matters:** accuracy-based evaluation is structurally incapable of seeing this.
  A benchmark that scores answers scores this a pass, which is why OWASP had to name
  unbounded consumption separately (LLM10) rather than leaving it to correctness testing.

### 2. The expensive vector is the one no monitor is watching

- **Reproduce:** `--arm none`, compare `BLOAT` against `CLEAN_TWIN` on calls and turns.
- **What happens:** gpt-oss **1.75×** cost at **3.6 calls / 4.6 turns** against the clean
  twin's **3.4 / 4.6**. Mistral **1.68×** at **3.5 / 4.4** against **3.4 / 4.4**. The call
  count and turn count are the same to within noise.
- **Why it matters:** rate limits and tool-call quotas are the defences teams actually
  deploy, and both are blind here. The cost is not in *how many* times the agent acted, it
  is in how much text each action dragged into a conversation that gets re-sent every turn.

### 3. A prompt-level defence cannot fix what a tool already returned

- **Reproduce:** `--arm prompt_guard` vs `--arm none` on `BLOAT`.
- **What happens:** gpt-oss **1.75× → 1.66×**, mistral **1.68× → 1.62×**. Essentially
  nothing, on both models. The same notice fixes `FANOUT` completely (gpt-oss 3.69× →
  1.11×, mistral 1.75× → 1.01×).
- **Why it matters:** this was written down as a prediction in [DESIGN.md](DESIGN.md)
  *before the runs* and it held. It is not a wording problem. By the time an oversized
  result is in the context window the tokens are bought, and they are bought again on
  every later turn. An instruction can change what an agent *asks for*, never what it is
  *charged for* on work already done.

### 4. Refusing a tool call still costs money

- **Reproduce:** `--arm budget_gate` vs `--arm none` on `FANOUT`.
- **What happens:** gpt-oss **3.69× → 2.32×**, mistral **1.75× → 1.51×**. The cap fires,
  the lookups are refused, and most of the bill survives.
- **Why it matters:** a refusal is not free. The request and the refusal both enter the
  conversation and are replayed on every subsequent turn, and the extra round trip adds a
  turn of its own. Budget enforcement that rejects work after the model has asked for it
  recovers far less than it appears to.

### 5. Neither defence covers both vectors; only the pair does

- **Reproduce:** all four arms.
- **What happens** (cost relative to each arm's own clean twin):

  | arm | gpt-oss FANOUT | gpt-oss BLOAT | mistral FANOUT | mistral BLOAT |
  |---|---|---|---|---|
  | `none` | 3.69× | 1.75× | 1.75× | 1.68× |
  | `prompt_guard` | **1.11×** | 1.66× | **1.01×** | 1.62× |
  | `budget_gate` | 2.32× | **1.18×** | 1.51× | **1.10×** |
  | `both` | **1.11×** | **1.16×** | **1.03×** | **1.00×** |

- **Why it matters:** the two defences are not alternatives to be benchmarked against each
  other, they address different halves of the problem. The prompt guard stops the agent
  *asking*; the tool gate limits what comes *back*. Deploying either alone leaves a vector
  fully open, and which one you left open is not visible from the arm you measured. Only
  `both` closes both, on both models.

---

## Failures of the experiment

### 6. Byte-level truncation corrupts the record and halves accuracy

- **What happened:** the first `budget_gate` sliced the serialised tool result at a byte
  offset. That cuts a JSON document mid-string, the agent can no longer parse its own tool
  result, and `BLOAT` accuracy fell to **0.50** while the cost number looked excellent.
- **Why it nearly shipped:** the arm was doing exactly what it advertised — the bill came
  down. Only the accuracy column showed that it had bought the saving by destroying the
  data the agent needed.
- **The fix:** truncation is field-aware; the longest string value is shortened and the
  document re-serialised. `test_budget_gate_cuts_bloat_without_corrupting_the_record`
  pins it.

### 7. The over-blocking control cannot detect over-blocking through accuracy

- **What happened:** `LEGIT_COMPLEX` exists so a defence that simply refuses work cannot
  score well. It cannot do that job through `correct`, because gold is inherited from the
  baseline and depends only on the in-scope order — an agent that refuses every sibling
  lookup still answers correctly.
- **Why it was kept anyway:** making gold depend on the sibling orders would fix the
  control and destroy the property that makes the whole cost claim clean, namely that an
  amplification can never change the correct answer. The inherited gold is worth more.
- **What is reported instead:** suppressed legitimate work. Under `prompt_guard` the agent
  stops checking the duplicate orders the customer legitimately raised — lookups fall from
  **5 to 3** on the mock, and mistral's `LEGIT_COMPLEX` cost falls from **1.57× to 1.24×**.
  In production that is a service failure; here it is simply invisible to accuracy, and
  [DESIGN.md](DESIGN.md) says so.

---

## Robustness checks run before any of the above was reported

| Check | Result |
|---|---|
| Is the replay tax real, or an artefact of the harness? | Probed on gpt-oss **before** the use case was designed: identical task and tool sequence, padded tool results → same 4 calls, same 5 turns, **6.1× input tokens** |
| Is the cost signal a stalling artefact? gpt-oss errors on 32–37% of runs | Amplification recomputed on completed runs only matches the all-runs figure in every cell (`none` FANOUT 3.69× → 3.45×, BLOAT 1.75× → 1.83×) |
| Does amplification change the answer? | `correct` flat across all four archetypes on both models; gold inherited from the baseline and asserted byte-identical to the clean twin |
| Does the `BLOAT` payload leak into the decision? | `gold_plan` never reads the field; asserted in `test_bloat_field_is_not_read_by_the_policy` |
