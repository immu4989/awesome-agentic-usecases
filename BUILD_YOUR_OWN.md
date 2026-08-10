# Build your own verified use case

Fork this repository when you want a private evaluation lab with the same guarantees—not
when you merely need a folder of prompts. The goal is to preserve the measurement shape
while replacing the synthetic domain with yours.

## Choose the fastest starting point

### Adapt a nearby use case

This is usually the best route. Copy the example whose **decision and consequence** match
yours, even if its industry does not.

| Your agent… | Copy this shape |
|---|---|
| Investigates records and routes work | [Exception Triage](logistics-supply-chain/exception-triage-agent/) |
| Executes an irreversible business action | [Refund Resolution](customer-support/refund-resolution-agent/) |
| Reconciles several records before moving money | [Vendor Payment Review](procurement-finance/vendor-payment-review-agent/) |
| Watches a stream before deciding | [On-Call Watch](it-operations/oncall-watch-agent/) |
| Admits or rejects an artifact/request | [Artifact Admission](security-operations/artifact-admission-agent/) |
| Must produce a faithful regulated record | [DPA Clause Review](legal-compliance/dpa-clause-review-agent/) |
| Compares a defence with a baseline | [Refund Guarded](customer-support/refund-guarded/) |
| Coordinates specialists | [Refund Crew](customer-support/refund-crew/) |
| Mediates access to a consequential service | [Small Business Recovery](public-sector/small-business-recovery-agent/) + [Public Value Contract](PUBLIC_VALUE_CONTRACT.md) |
| Must preserve several parallel filing windows | [Farm Disaster Deadline](agriculture-food-systems/farm-disaster-deadline-agent/) or [Unemployment Claim Navigation](employment-social-insurance/unemployment-claim-navigator/) |
| Must prove which jurisdictional rule it used | [Permit Readiness](housing-construction/permit-readiness-agent/) |
| Must minimize sensitive evidence before human review | [Student Accommodation](education-services/student-accommodation-navigator/) |
| Recovers an account under assurance and takeover risk | [Account Recovery Assurance](identity-access/account-recovery-assurance-agent/) |
| Must distinguish finding, fixing, deploying, and verifying | [Accessibility Remediation](accessibility-digital-services/accessibility-remediation-verifier/) |
| Must cover an exact system set and prove completion | [Privacy Rights Orchestration](privacy-data-governance/privacy-rights-orchestrator/) |
| Must coordinate exact evidence and protect access, clocks, recourse, and human authority | Any lab in the [12-industry Evidence Service Contract wave](USE_CASE_RADAR.md#evidence-service-expansion-wave--shipped) |
| Prepares evidence immediately before a protected high-stakes decision | Any lab in the [six-industry Decision Gate Contract](DECISION_GATE_CONTRACT.md) wave |
| Must prove a source, safety state, or current record before a helpful action | Any lab in the [Proof Before Action report](PROOF_ACTION_REPORT.md) |
| Must prove that a protective action actually reached the right stage and owner | Any lab in the [seven-industry Protection Receipt Contract](PROTECTION_RECEIPT_CONTRACT.md) wave |
| One event fans out into independently clocked duties and recipients | Any lab in the [seven-industry Obligation Graph Contract](OBLIGATION_GRAPH_CONTRACT.md) wave |

Use `aau show <name>` to inspect an entry and `aau start <name>` for its exact local
installation order.

### Generate a new shape

```bash
python -m pip install -e harness
aau-new-use-case \
  --industry insurance \
  --name claim-escalation-agent \
  --seed 67
```

The generator refuses to overwrite an existing directory. It creates and verifies:

- A seeded synthetic world and committed scenario file.
- One shared gold-decision function used by generation and scoring.
- Strict tools and a terminal submission action.
- A deterministic mock with an engineered, nonzero failure.
- Tests for determinism, coverage, hidden facts, tool schemas, and the mock eval.
- README and observed-failure templates.

Search the generated directory for `TODO(domain)`; those are the intended adaptation
points.

## Translate your workflow into an eval

Fill this contract before changing code:

| Question | Your answer |
|---|---|
| What decision or action does the agent own? | |
| Who owns the ground-truth policy? | |
| Which facts must be retrieved rather than prompted? | |
| Which action is irreversible or expensive? | |
| What case reads like one thing but is actually another? | |
| What does a safe refusal or escalation look like? | |
| Which clean case requires the risky capability? | |
| What would make a model result a non-measurement? | |
| What burden, accessibility, deadline, recourse, or rights obligations apply? | |
| Which nearby valid rule must never transfer to this case? | |
| Which gates are conjunctive, and who owns the protected final action? | |
| Which receipt proves each real stage—and which later stage must never be inferred? | |
| Which obligations can one event activate, and what exact fact, clock origin, recipient, and owner belongs to each node? | |

If the first two answers are vague, stop. A precise scorer cannot be built from an
undefined operational decision.

## Preserve these invariants

1. **One source of truth:** the generator and scorer call the same gold function.
2. **Seeded determinism:** the scenario file regenerates byte-for-byte across hash seeds.
3. **Hidden deciding facts:** the case text alone is insufficient.
4. **A real discrimination case:** at least one archetype defeats a plausible shortcut.
5. **Consequence-aware metrics:** score the action path, not just the final label.
6. **Visible non-participation:** always report `submitted` and provider errors.
7. **Repeated runs:** at least three repeats for stochastic models.
8. **Observed failures:** every documented failure links to a scenario and committed run.

## Replace the scaffold in this order

1. Rewrite `world.py`: entities, archetypes, and the gold function.
2. Rewrite tool schemas and their synthetic state transitions.
3. Write the system prompt last; it should describe the task, not contain the answer key.
4. Change the mock so it follows a plausible shortcut and fails at least one archetype.
5. Replace metrics with ones that match the agent's power; use
   [Practical Playbooks](PLAYBOOKS.md#pick-metrics-from-the-agents-power).
6. Regenerate scenarios and run tests.
7. Run at least two real models and inspect scenario-level details.
8. Document failures you observed, including conclusions that contradicted your hypothesis.

## Verify locally

```bash
python -m pip install -e harness[dev] -e insurance/claim-escalation-agent[dev]
claim-escalation-agent generate --n 30 --seed 67
pytest harness/tests insurance/claim-escalation-agent/tests -q
claim-escalation-agent eval --backend mock
ruff check harness insurance/claim-escalation-agent
aau doctor
```

Then run a real provider three or more times and commit both JSON and rendered Markdown
results. The [Verification Bar](VERIFICATION.md) explains why each requirement exists.

## Keep your fork maintainable

- Put domain changes in the use-case package; keep reusable primitives in `harness/`.
- Add the use case to `docs/use-cases.json`, the CI matrix, and any relevant generated
  artifact lists.
- Add a local `visual.json` with its four-stage path, four-act domain story, benchmark
  metric, and scenario anatomy. `docs/make_readme_experiences.py` discovers this brief
  automatically; use the central file only for older labs that predate local briefs.
  Commit the generated `experience.svg`, `story-v2.svg`,
  `scenario-map.svg`, `benchmark.svg`, `contrast.svg`, `result-profile.svg`, and
  `failure-cards.svg`. CI checks that every use case has the full visual case file and that
  it is current with committed evidence.
- Run `python docs/make_catalog.py`; CI will reject drift between the catalog, README,
  packages, and matrix.
- Preserve provider-neutral interfaces so model comparisons change one flag, not agent code.
- State synthetic-world limitations prominently rather than presenting results as production
  prevalence.

## Contribute it upstream

Open a [new use case proposal](https://github.com/immu4989/awesome-agentic-usecases/issues/new/choose)
before the pull request. The high bar is intentional, but the generator means contributors
can spend their time on domain truth and interesting failures rather than repository
boilerplate.

Not ready to build? The [Real-world Use-case Radar](USE_CASE_RADAR.md) lists high-value
problems where a domain review, policy boundary, or set of counterexamples may be more
useful than code.
