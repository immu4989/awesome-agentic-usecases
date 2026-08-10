# The Verification Bar

Every use case in this repo must satisfy all five claims below before it ships. This is
the difference between a demo and a use case: a demo shows the agent running; a use case
shows whether you should trust it.

## 1. Runs from a clean clone with one command

```bash
pip install -e harness -e <industry>/<use-case>
<use-case-cli> eval --backend mock
```

No API key, no downloads, no proprietary data. The mock backend is a deterministic
stand-in model that exercises the entire pipeline — tools, agent loop, scoring,
reporting — so the harness itself is testable in CI for free. Real-model runs are one
flag away.

## 2. Eval set with ≥20 scenarios and programmatic ground truth

Scenarios are generated synthetically with a seeded RNG, and the ground truth comes from
the generator's own rules — so scoring is exact, reproducible, and auditable. The
scenario file is committed. If you change the generator, the diff shows exactly which
scenarios changed.

## 3. Cost per run in dollars

Computed from the `usage` block of every API response — input, output, cache-write, and
cache-read tokens, priced at current published rates. Not estimated, not extrapolated.
The README reports mean cost per scenario and per full eval run, so an adopter can
project their monthly bill before writing a line of code.

## 4. Results from n≥3 repeated runs with variance

Agents are stochastic. A single run can swing accuracy by several points, and a
conclusion drawn from n=1 is noise. Every reported metric is the mean across ≥3 repeats
with a bootstrap confidence interval. If the CI straddles the decision boundary, the
README says so.

## 5. At least 3 observed failure modes

Each entry in `FAILURE_MODES.md` documents a failure that actually occurred during eval
runs — the input that triggers it, what the agent did, and what it should have done.
Hypothetical failure modes don't count. A use case whose evals never fail has an eval
set that's too easy, and that's a finding too.

## High-stakes extension: prove the gate, not just the answer

For a workflow immediately upstream of a regulated, safety-critical, financial, employment,
or other protected decision, the five repository rules are necessary but not sufficient.
Use the [Decision Gate Contract](DECISION_GATE_CONTRACT.md) and require:

- a dated policy snapshot and rule-specific reason vocabulary;
- exact held, relied-on, and requested evidence sets;
- exact conjunctive-gate state with no urgency waiver;
- explicit notice, deadline, and confidentiality fields where applicable;
- a separately observable protected action that the agent cannot execute; and
- reconciliation of the closeout record with the actual tool trace.

The benchmark must also include a clean twin and a nearby transfer trap. A model that knows
one valid rule has not demonstrated that it knows where that rule stops.

The [Proof Before Action report](PROOF_ACTION_REPORT.md) provides three lower-authority but
still consequential examples: claim publication, home-service routing, and nonprofit grant
evidence. They use the same extension because “helpful” is not a waiver for exact proof.

---

## Why this bar exists

Agent demos are cheap to produce and expensive to trust. The gap between "ran once in a
video" and "works at a measured rate for a measured cost" is where every real deployment
decision lives. This repo exists to close that gap in public, per use case, with
receipts.
