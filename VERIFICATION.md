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

## Federal mission extension: evidence before authority

For a U.S. public-sector AI acquisition or deployment, use the
[Federal Mission Assurance Profile](federal-mission-assurance/) in addition to the lab bar.
The profile must make these states independently inspectable:

- mission outcome, affected groups, baseline, measurable benefit, and high-impact determination;
- accountable owner, protected decisions, intervention point, and prohibited agent actions;
- data classification, provenance, minimization, retention, training use, and rights;
- intended-environment tests, acceptance criteria, independent review, and unresolved failures;
- monitoring signals, reassessment triggers, appeal or remedy, incident path, and cease-use condition;
- acquisition performance terms, lifecycle cost, portability, transition assistance, and exit; and
- dated source versions plus artifacts referenced by stable identifiers and integrity hashes.

A complete profile is not a compliance score. A SHA-256 manifest proves only that exported
bytes have not changed. A control is `evidenced` only when a reviewer links an actual artifact;
browser-created plans remain `planned`. The agent must never turn a complete form or valid
manifest into an ATO, certification, approval, risk acceptance, source selection, obligation,
or award.

For a forked Federal Pilot Kit, also require the
[30-Day Agency Pilot Launch Pack](federal-pilot-kit/pilot-launch/), documented decision rights,
the [kit threat model](federal-pilot-kit/THREAT_MODEL.md), adversarial input and privacy regression
tests, an exact software inventory, and verified release provenance. These are pilot-readiness
receipts, not a security authorization or permission to place protected data in the public kit.

## Human-comparator extension: measure the existing process without ranking people

When a claim says an agent improves accuracy, efficiency, workload, or service quality relative
to the current process, use the [Human Baseline Lab](human-baseline-lab/) and require:

- the same reviewed public or synthetic task contract for the human and agent evidence;
- a blinded participant-visible study separated from its answer key;
- an institutional determination before any human-observed session is collected;
- voluntary participation, withdrawal, accessibility, privacy, labor, and records controls owned
  by the responsible organization;
- exactness with uncertainty, abstention, task-time distribution, confidence calibration, and
  agreement reported independently rather than collapsed into one score;
- participant-level session files kept private, with only an aggregate report published; and
- an explicit prohibition on worker ranking, employment decisions, staffing reductions, causal
  benefit claims, replacement conclusions, certification, or deployment authority.

The five committed Human Baseline reference sessions are generated fixtures. They prove that the
schemas, aggregation, privacy boundary, and browser/CLI parity work; they do not measure people.

## Public-value extension: bind the whole evidence chain

To move beyond a model/process comparison toward public-value evidence, use an
[Impact Capsule](evidence-commons/) and require all five links to remain separately inspectable:

1. a reviewed suite with a byte hash and declared provenance;
2. an aggregate agent receipt bound to that suite—not scenario identifiers alone;
3. a blinded, privacy-bounded aggregate human comparator after the responsible institution's determination;
4. predeclared service, burden, rights, or safety measures plus a method-bounded observation; and
5. an organization-attested independent reproduction with divergences and transfer conditions.

Run `aau evidence validate`, inspect `aau evidence compare`, then build and verify a portable pack
with `aau evidence pack` and `aau evidence verify`. The manifest proves byte integrity only; it
does not verify identity, institutional review, independence, causality, certification,
government endorsement, or deployment authority.

---

## Why this bar exists

Agent demos are cheap to produce and expensive to trust. The gap between "ran once in a
video" and "works at a measured rate for a measured cost" is where every real deployment
decision lives. This repo exists to close that gap in public, per use case, with
receipts.
