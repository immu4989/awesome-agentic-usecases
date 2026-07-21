# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs, with a reproducing archetype. Observations are from
the real-model runs in `results/`.

This is the repo's first `watch` use case, and the failures are about *time*: how long
an agent is willing to look before it decides, and what a metric can hide when the
answer is "not long enough."

### 1. A restraint metric can be passed by not looking

- **Reproduce:** `--backend fireworks` (gpt-oss-120b) and `--backend together`
  (Qwen3.7-Plus). Both score **`no_false_page` = 1.000**, a perfect alert-fatigue
  rating. Both also miss roughly a third of real incidents
  (`caught_incident` 0.667 and 0.722).
- **What happens:** the tick counter explains it. gpt-oss watched an average of **3.6
  ticks** and Qwen **5.8**, on every archetype, when the evidence needs 8 to 19 ticks
  depending on the scenario. They did not exercise restraint; they stopped watching
  before anything had gone wrong yet, then reported quiet.
- **Why it matters:** this is the most transferable lesson in the repo for anyone
  *designing* an eval. Any metric of the form "did the agent avoid the bad action" is
  satisfied perfectly by an agent that does nothing at all. Inaction is indistinguishable
  from judgement unless you measure whether the agent looked. Ship a companion metric
  that penalises deciding on absent evidence, or your safest-looking model will be the
  one that sleeps through outages. Here that companion is `patience_ok`, which reads
  0.433 and 0.556 for the two models whose fatigue score is a flawless 1.000.

### 2. The slow burn is invisible to an impatient watcher

- **Reproduce:** the `SLOW_BURN` archetype on both impatient models. gpt-oss called it
  `none` 9 times out of 15; Qwen 9 times, plus 5 more as a mere `ticket`.
- **What happens:** latency and error rate drift steadily past the SLO across twenty
  minutes without any single alarming sample. An agent that stops at tick 4 sees a
  perfectly healthy service, because at tick 4 the service *is* healthy. The incident is
  in the trend, not in any observation.
- **Why it matters:** threshold-per-sample monitoring is exactly what these models
  reproduce by default, and it is exactly the failure mode that real alerting has spent
  a decade engineering around. Detecting a breach is easy; noticing a slope is not.

### 3. Watching everything is not judgement either

- **Reproduce:** `--backend mistral`, the `MAINTENANCE_WINDOW` archetype — 13 runs filed
  a ticket and 2 paged, where the correct answer is silence.
- **What happens:** Mistral is the patient model (`patience_ok` 0.978, mean **19.2 of 20
  ticks**) and it catches every genuine incident (`caught_incident` 1.000). But it
  watched 19.1 ticks on maintenance windows too, where the service context settles the
  question at tick zero. It read the metrics faithfully and never let the context
  override them, so it raised work for degradation that was announced in advance.
- **Why it matters:** patience is necessary and not sufficient. The failure here is not
  impatience but the opposite: refusing to let a known fact short-circuit the
  observation. It also cost real money, see mode 5.

### 4. Crying wolf on transients

- **Reproduce:** `UPSTREAM_BLIP` on `--backend mistral` — 10 pages and 5 tickets across
  15 runs, against a gold of silence.
- **What happens:** a sharp error spike that decays back under the SLO within three
  minutes, with no deploy behind it. The runbook says wait for a sustained signal.
  Mistral pages on the spike.
- **Why it matters:** this is the classic pager-fatigue failure, and it is the direct
  cost of mode 3's patience being undirected. The model watched long enough to see the
  recovery and alerted anyway.

### 5. On a watch task, cost is a proxy for whether the agent did the job

- **Observed:** gpt-oss cost **$0.0017** per scenario at 12.4s; Mistral cost
  **$0.0048** at 43.5s. The difference is almost entirely `next_tick` calls.
- **Why it matters:** the cheapest, fastest agent in this table is the one that missed a
  third of the incidents, and it is cheap and fast *because* it missed them. Every
  efficiency metric ranked it best. On any task where the work is proportional to
  looking, throughput and cost dashboards will quietly reward not looking.

### 6. Nobody solved it

- **Best severity accuracy: 0.622** (Mistral). gpt-oss 0.444, Qwen3.7-Plus 0.567.
- **Why it matters:** the logistics exemplar has a model at a perfect 1.000, and
  `Qwen3.7-Plus` solves the refund task at 0.978 with zero unsafe actions. That same
  model scores 0.567 here. Deciding *when* you have seen enough is a distinct capability
  from deciding *what* the evidence means, and current models are markedly worse at it.
