# Failure Modes

Per the [verification bar](../../VERIFICATION.md), every entry documents a failure
**observed** in committed eval runs, with a reproducing archetype or scenario id.
Observations are from the real-model runs in `results/`.

### 1. The legal rule held — universally. The thresholds around it did not.

- **Observed on every model tested:** zero caption waivers across all covered-territory
  caption scenarios. Not one model ever waived a caption defect in a CVAA-covered
  territory, including the models that were wrong about almost everything else nearby.
- **Contrast:** the same models missed the ordinary operational thresholds constantly —
  the release window, in-house repair capability, and vendor SLA account for nearly
  every action error in this use case.
- **Why it matters:** this is the most actionable finding in the repo for anyone
  *writing* agent policy. The accessibility clause (RQ-CVAA-01) is worded as a legal
  obligation with a named statute and consequence, and it was obeyed by models that
  ignored numerically simpler rules sitting beside it in the same knowledge base.
  Framing a constraint as legal appears to be a materially stronger control than
  framing it as a threshold — the same rule, written two ways, is not the same rule.

### 2. Creative intent read as a defect (the "looks broken, is fine" deception)

- **Reproduce:** the `INTENTIONAL_CREATIVE` archetype (`--backend mistral`) — 12 of 15
  runs. The flag reports 22 seconds of digital silence; a director annotation on file
  covers exactly that timecode range and marks it intentional.
- **What happens:** Mistral files it to `audio-eng` as a real defect instead of
  `no-defect`. It retrieves the annotation and still treats the detector's flag as
  authoritative.
- **Split across models:** `gpt-oss-120b` and `Qwen3.7-Plus` pass this deception
  cleanly — zero misses each. So the trap is beatable, and failing it is a model
  property rather than a property of the task.
- **Why it matters:** in production every instance is an unnecessary engineering ticket
  against a correctly delivered asset, and — where it drives a delay — a premiere moved
  for a defect that does not exist.

### 3. Over-escalation: sending resolvable flags to the release board

- **Reproduce:** `--backend mistral` — 9 runs where the vendor should have redelivered
  and 7 where the asset should simply have shipped went to `escalate_to_release_board`
  instead.
- **What happens:** Mistral routes decisions upward whenever the schedule is tight,
  rather than applying the remediation the policy prescribes. Action accuracy 0.433 is
  its worst score across all five industries in this repo, and this pattern is most of it.
- **Why it matters:** the release board is a scarce, expensive forum. An agent that
  escalates everything hard has not automated triage — it has added a step to it.

### 4. Over-fixing: pulling vendor work in-house

- **Reproduce:** `LOUDNESS_SPEC` and `HDR_METADATA` archetypes on **both**
  `gpt-oss-120b` (6 runs) and `Qwen3.7-Plus` (7 runs) — gold says `vendor_redelivery`,
  the model says `expedite_internal_fix`.
- **What happens:** with time on the clock, both models reach for the in-house fix
  rather than sending the package back to the originating vendor. For HDR metadata baked
  into the picture essence, in-house repair is not actually available (RQ-FIX-04) — the
  model asserts a capability the policy denies.
- **Why it matters:** it is the exact mirror of mode 3. Mistral pushes work up to
  humans; gpt-oss and Qwen pull work in to a team that cannot do it. Two opposite
  failure directions, and which one you get depends entirely on the model — so a
  deployment threshold tuned for one is wrong for the other.

### 5. Commit-stall persists across every industry

- **Reproduce:** 2 of 90 `gpt-oss-120b` runs and 3 of 90 `Qwen3.7-Plus` runs submitted
  no decision at all.
- **What happens:** the model investigates, then ends its turn without calling
  `submit_release_decision`.
- **Why it matters:** this same failure now appears in logistics, retail, security,
  fraud, and media — five industries, multiple models, always at a low single-digit
  rate. It is the most portable failure mode in the repo, which is why every use case
  scores `submitted` as a first-class metric rather than assuming a decision exists.
