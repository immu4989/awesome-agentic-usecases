# aau-harness

Reproducible evaluation of tool-using LLM agents: seeded worlds, exact scoring, measured
cost, repeated runs with confidence intervals, and provenance on every result.

This is the library behind [awesome-agentic-usecases](https://github.com/immu4989/awesome-agentic-usecases).
It is usable on its own — you supply a domain (scenarios, tools, a gold rule, a prompt) and
the harness supplies everything around it.

---

## Install

For evaluation in your own project:

```bash
python -m pip install aau-harness
```

For repository development:

```bash
python -m pip install -e harness
python -m pip install -e 'harness[dev]'  # plus pytest and ruff
```

Requires Python 3.10+. The core uses only the standard library on Python 3.11+ (Python
3.10 installs the small `tomli` compatibility package); the `anthropic` extra is only
needed for the native Anthropic backend, and every other provider is reached over `urllib`.

Verify the install:

```bash
aau --help
# From a repository clone:
pytest harness/tests -q
```

## Start an evidence project in five minutes

`aau init` generates a complete, non-overwriting evaluation project around an agent you already
have. It needs no AAU account, hosted dataset, model key, or upload.

```bash
aau init my-agent-eval
cd my-agent-eval
aau doctor .
aau evaluate suite.json --mock --out artifacts/protocol-receipt.json
aau evaluate suite.json --command "python adapter_command.py" --out artifacts/local-receipt.json
```

Every starter contains an explicitly synthetic three-case suite, command and local HTTP adapters,
exact outcome and forbidden-action checks, accountable human authority, a deterministic public
receipt, a standard-library test, immutable least-privilege CI, a receipt-sharing policy, an
evidence-flow visual, and a SHA-256 manifest. Generation is atomic and refuses to overwrite an
existing path.

Choose a transferable failure shape or an HTTP-first integration:

```bash
aau init service-eval --template public-service-routing
aau init support-eval --template customer-escalation
aau init incident-eval --template incident-triage --adapter http
```

`aau doctor` fails on unsafe sharing declarations, an invalid adapter contract, a drifted receipt,
unsafe manifest paths or symlinks, or weakened CI. It parses but does not execute project code by
default; use `aau doctor . --run-adapter` only for code you trust. Legitimate customization is
reported as a warning. Structural readiness remains an onboarding signal—not production
validation, certification, legal advice, or authority to deploy.
See the [complete examples](https://github.com/immu4989/awesome-agentic-usecases/tree/main/agent-evidence-starter/examples)
or use the [zero-upload browser wizard](https://immu4989.github.io/awesome-agentic-usecases/#agent-starter).

## Publish a privacy-bounded community evidence pack

After connecting a real command or endpoint adapter, `aau submit` turns the Starter and one or
more public aggregate receipts into a non-overwriting contribution directory:

```bash
aau submit ./my-agent-eval \
  --receipt ./artifacts/public-receipt.json \
  --id my-agent-evidence \
  --contributor-name "Your name" --github your-handle \
  --summary "What it helps with" --why-fork "What another team can adapt" \
  --beneficiaries "Who benefits" --industry "Your industry" \
  --failure-shape "The failure boundary" --tag routing --tag human-authority

aau submit --validate ./my-agent-evidence-aau-submission
```

The command rejects mock receipts, private or extra receipt fields, inconsistent aggregate
metrics, unsafe paths and symlinks, common sensitive-data patterns, stale checks, manifest drift,
and unsupported public files. It never executes the Starter adapter, uploads data, opens a pull
request, or overwrites an existing path.

Evidence levels are cumulative and artifact-derived: **Generated** requires a connected-agent
receipt and protected human authority; **Domain reviewed** adds an adapted 10-case suite, named
review scope, and sources; **Reproduced** adds three distinct run receipts; **Verified** adds a
named different reproducer linked to a receipt. These levels are not identity verification,
certification, endorsement, production validation, or authority to deploy. See the
[public contract and reference packs](https://github.com/immu4989/awesome-agentic-usecases/tree/main/community-evidence)
or use the [browser-local Contribution Desk](https://immu4989.github.io/awesome-agentic-usecases/#community-evidence-loop).

## Add the missing human comparator

`aau baseline` turns a reviewed public or synthetic suite into a blinded human-process study. It
keeps participant-visible tasks and the answer key separate, prohibits direct identifiers and free
text in session files, and starts with an explicit `not_determined` human-protection state.

```bash
aau baseline prepare suite.json \
  --id my-human-baseline \
  --title "My Human Baseline" \
  --purpose "Compare the reviewed task with the existing process" \
  --out human-baseline-pack

aau baseline summarize human-baseline-pack \
  --session private-sessions/session-01.json \
  --agent-receipt public-agent-receipt.json \
  --out public-human-baseline-report.json

aau baseline validate public-human-baseline-report.json
```

Aggregate reports include exactness with a Wilson interval, abstention, median and p90 task time,
confidence calibration, modal agreement, and Fleiss' kappa. Optional agent comparisons require the
same suite hash and scenario coverage and reject protocol mock receipts. Reports exclude participant
ids and raw outcome, confidence, and timing rows.

Before collecting real participant sessions, the responsible institution must record the relevant
human-subjects, quality-improvement, privacy, accessibility, labor, records, and consent or
withdrawal determination. The CLI field is a fail-closed declaration—not verification or approval.
The feature must not be used for worker ranking, employment action, staffing reduction, replacement,
causal-benefit, certification, or deployment claims. See the
[complete kit and synthetic references](../human-baseline-lab/) or try the
[zero-upload practice](https://immu4989.github.io/awesome-agentic-usecases/#human-baseline-lab).

## Bind an inspectable public-value evidence chain

`aau evidence` validates an Impact Capsule connecting the reviewed suite and agent receipt to an
aggregate human comparator, predeclared public-value measures, a bounded observation, and an
independent reproduction. Missing artifacts remain explicit and status is derived—not selected.

```bash
aau evidence validate evidence-commons/capsules/foia-routing-impact-pilot.json
aau evidence compare evidence-commons/capsules/foia-routing-impact-pilot.json --json
aau evidence pack evidence-commons/capsules/foia-routing-impact-pilot.json --out /tmp/foia-impact-pack
aau evidence verify /tmp/foia-impact-pack
```

The non-overwriting pack includes the capsule, derived comparison, referenced public artifacts,
README, and SHA-256 manifest. Validation rejects traversal, symlinks, hash drift, private-data
claims, status inflation, inconsistent metrics, causal-label inflation, and false AAU verification
claims. It does not verify contributor identity, institutional review, reproducer independence,
causal impact, certification, government endorsement, or authority to deploy. See the
[three open partner capsules and schemas](../evidence-commons/) or the
[live evidence-chain inspector](https://immu4989.github.io/awesome-agentic-usecases/#evidence-commons).

## Gate a specific agent release

`aau release` captures the exact components of a baseline and candidate, computes their change
surface, and runs only the public or synthetic suites mapped to the impacted tags. Unknown tags,
missing required components, incomplete coverage, below-threshold results, and forbidden action
execution block the release evidence. Protected tags also require a structured human-role record.

```bash
aau release assess baseline-manifest.json candidate-manifest.json \
  release-policy.json evidence-plan.json \
  --command "python my_release_adapter.py" \
  --approval approval.json --out /tmp/aau-release-pack
aau release verify /tmp/aau-release-pack
```

Every pack includes component snapshots, exact diff, policy, plan, aggregate receipts, derived
decision, manifest, unsigned in-toto statement, and an experimental OSCAL 1.1.3-shaped Assessment
Results export. A mock adapter always resolves to `human_review_required`, never `release_ready`.
`release_ready` is structural evidence against the declared contract—not verified approver
identity, production validation, certification, compliance, deployment permission, or an ATO. See
the [complete reference gate](../agent-release-gate/) and the
[live evidence view](https://immu4989.github.io/awesome-agentic-usecases/#release-gate).

## Inventory agent capability and authority

`aau bom` validates a strict Agent Capability & Authority BOM, binds exact tool-operation-scope
relationships, detects directional authority widening between releases, emits a CycloneDX 1.7
projection, and builds a deterministic evidence pack:

```bash
aau bom validate agent-capability-bom/examples/candidate.json
aau bom diff agent-capability-bom/examples/baseline.json agent-capability-bom/examples/candidate.json
aau bom export-cyclonedx agent-capability-bom/examples/candidate.json --out /tmp/agent.cdx.json
aau bom pack agent-capability-bom/examples/candidate.json --out /tmp/agent-bom-pack
aau bom verify /tmp/agent-bom-pack
aau bom plan-reduction agent-capability-bom/examples/candidate.json \
  agent-capability-bom/examples/authority-observation.json --out /tmp/reduction-plan.json
aau bom verify-reduction-plan /tmp/reduction-plan.json \
  agent-capability-bom/examples/candidate.json \
  agent-capability-bom/examples/authority-observation.json
aau bom generate-conformance agent-capability-bom/examples/candidate.json \
  --out /tmp/authority-suite.json
aau bom run-conformance agent-capability-bom/examples/candidate.json \
  /tmp/authority-suite.json --command "python my_authority_adapter.py" \
  --out /tmp/authority-receipt.json
aau bom verify-conformance /tmp/authority-receipt.json \
  agent-capability-bom/examples/candidate.json /tmp/authority-suite.json
```

Cross-reference checks reject authority operations or resource scopes that exceed their declared
tools. Widening findings stay discrete rather than becoming a trust score. Protected human
approval removal blocks; a valid inventory still requires owner review. See the
[contract, source ledger, fixtures, and boundaries](../agent-capability-bom/).

The reduction planner records only normalized event identifiers, sequence, operation, scope class,
and decision. It identifies unobserved grants but produces no executable policy and automatically
removes nothing. Each candidate needs owner review, a representative holdout, legitimate clean
twin, staging denial test, rollback rehearsal, and separate change approval.

The conformance compiler derives legitimate and single-boundary violation twins directly from the
inventory. Command adapters receive inputs without expected answers; no tool is invoked. Receipts
bind the exact BOM and suite and separately count unsafe allows and legitimate blocks. Passing is
bounded adapter evidence, not production validation, certification, compliance, or authorization.

## Evaluate an existing agent

You do not need to rebuild an application around the harness. `aau evaluate` sends each case to
an existing command or HTTP endpoint through a four-field JSON response contract, then emits a
public aggregate receipt.

Suites must explicitly attest public, synthetic, or public-synthetic classification, completed
human review, and the absence of PII, credentials, procurement-sensitive, controlled, and
classified information. The CLI fails closed when any attestation is missing.

```bash
aau evaluate harness/examples/byo-agent-suite.json \
  --command "python harness/examples/byo_agent_adapter.py" \
  --out aau-agent-receipt.json
```

The adapter reads one JSON request from standard input and writes one JSON object:

```json
{
  "outcome": "route_official_source",
  "actions_attempted": [],
  "actions_executed": [],
  "submitted": true
}
```

Use `--endpoint http://127.0.0.1:8000/evaluate` for a JSON POST endpoint, or `--mock` to verify
the suite protocol without running an agent. The evaluator measures exact outcome, submission,
forbidden-action attempts, forbidden-action execution, and latency. It executes command adapters
as an argument vector with `shell=False`, enforces suite/response size and timeout limits, and
never copies environment variables or request headers into receipts.

Public receipts deliberately omit scenario inputs, expected answers, raw adapter responses,
reasoning, and credentials. `--private-out` is available for local debugging and may contain
sensitive material; never publish it without authorized review. A passing receipt is not
production validation, certification, model ranking, legal advice, or permission to automate a
protected decision.

### Run in GitHub Actions

```yaml
- uses: immu4989/awesome-agentic-usecases/.github/actions/aau-evaluate@main
  with:
    suite: evals/public-suite.json
    adapter-command: python app/aau_adapter.py
    receipt: artifacts/aau-agent-receipt.json
```

Pin the action to a release tag or commit SHA in production. The composite action installs the
repository-pinned harness and returns the public receipt path. See
[`harness/PUBLISHING.md`](PUBLISHING.md) for the tokenless PyPI release process.

### Find the right use case

Installing the harness also adds the repository navigator. It searches the committed
machine-readable catalog and prints exact commands without making network calls:

```bash
aau list
aau list --industry healthcare
aau find "security adversarial"
aau show refund-memory
aau start refund-injected
aau challenge list
aau challenge show completion-is-not-correctness
aau baseline --help
aau release --help
aau bom --help
aau doctor
```

`aau start` understands local package dependencies, so controlled comparisons that reuse a
baseline are installed in the correct order. It prints commands; it never changes your
environment by itself.

`aau challenge` adds the community Reliability Challenge: list bounded Reproduce, Break,
and Adapt missions, print their exact zero-cost commands, or validate a Challenge-enabled
Gallery entry and derive its achievements from committed evidence.

## Quickstart

A complete evaluation. It runs on the built-in deterministic mock backend, so it needs no
API key and costs nothing.

```python
from dataclasses import dataclass
from aau_harness import (
    Block, CostTracker, MockUsage, ScenarioResult,
    make_backend, render_report, run_eval, run_tool_agent,
)

# 1. A world. Gold comes from a rule the scorer will share — never re-derived.
@dataclass
class Scenario:
    scenario_id: str
    text: str
    amount: int
    gold: str

def gold_rule(amount: int) -> str:
    return "escalate" if amount > 100 else "approve"

scenarios = [Scenario(f"sc-{i:03d}", f"Request for {i * 40} units", i * 40,
                      gold_rule(i * 40)) for i in range(6)]

# 2. Tools the agent may call. Strict schemas keep submissions well-formed.
TOOLS = [{
    "name": "submit",
    "description": "Commit the decision. Call once, last.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"decision": {"type": "string", "enum": ["approve", "escalate"]}},
        "required": ["decision"],
        "additionalProperties": False,
    },
}]

# 3. A deterministic stand-in model, so the pipeline runs with no API key.
class Mock:
    name = model = "mock"
    def create(self, system, messages, tools):
        amount = int("".join(c for c in messages[0]["content"] if c.isdigit()) or 0)
        return Block(
            content=[Block(type="tool_use", id="m1", name="submit",
                           input={"decision": gold_rule(amount)})],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=400, output_tokens=20),
        )

# 4. Score one run, then let the runner handle repeats and uncertainty.
def run_one(sc: Scenario, repeat: int) -> ScenarioResult:
    cost = CostTracker(model="mock")
    run = run_tool_agent(
        make_backend("mock", mock_factory=Mock), "You are a triage agent.",
        TOOLS, sc.text, lambda name, ti: "{}", "submit", cost,
    )
    sub = run.submission or {}
    return ScenarioResult(
        scenario_id=sc.scenario_id, repeat=repeat,
        metrics={"accuracy": float(sub.get("decision") == sc.gold),
                 "submitted": float(run.submitted)},
        cost_usd=cost.cost_usd, latency_s=0.0, n_api_calls=cost.api_calls,
        detail={"gold": sc.gold, "predicted": sub.get("decision")},
    )

agg = run_eval(scenarios, run_one, repeats=3)
print(render_report(agg, model="mock"))
```

To run the same evaluation against a real model, change one line — the rest is identical:

```python
backend = make_backend("openrouter", model="nvidia/nemotron-3-super-120b-a12b:free")
```

## Core API

### Evaluation

| | |
|---|---|
| `run_eval(scenarios, run_one, repeats=3, progress=None) -> EvalAggregate` | Runs `run_one(scenario, repeat)` across every scenario × repeat and aggregates. Metrics are averaged per scenario across repeats, then bootstrapped **over scenarios**, keeping a scenario's repeats together (paired). Repeats are the default because a single agent run is noise. |
| `EvalAggregate` | `n_scenarios`, `n_repeats`, `metric_means`, `metric_ci95`, `mean_cost_per_scenario_usd`, `total_cost_usd`, `p50_latency_s`, `results`. `as_dict()` serialises it, stamping provenance automatically. |
| `ScenarioResult` | One run: `scenario_id`, `repeat`, `metrics`, `cost_usd`, `latency_s`, `n_api_calls`, `detail`. Put anything you may want to analyse later in `detail` — per-archetype breakdowns are computed from it. |

`run_eval` rejects empty workloads and nonpositive/noninteger repeat counts before invoking
the callback. Each scenario position must return a unique, nonblank ID on the first repeat,
then retain that ID on every later repeat; each result must also record the requested zero-based
repeat index. This preserves the units used for scenario-level aggregation and bootstrap intervals.
It does not authenticate the labels or establish that repeated model runs are independent.

Metric values must be finite numbers (not strings or booleans), but need not lie between zero
and one: signed differences and counts remain supported. Cost and latency must be finite and
nonnegative, and API-call counts must be nonnegative integers. Metrics may still be omitted where
they do not apply. Invalid observations raise `ValueError` instead of producing an aggregate;
earlier callback side effects are not rolled back. Supply trusted callbacks and synthetic inputs.

Each returned result is deep-copied before the next invocation. Reusing a metrics dictionary or
result object therefore cannot retroactively overwrite earlier observations. Callback details
must support deep copying; JSON-compatible evidence is the portable choice. Historical result
files are not changed by these validation rules.

### See which observations support a metric

New JSON exports include `metric_coverage`, and Markdown reports show reporting-scenario and
reporting-observation counts for every metric. `agg.metric_coverage()` also exposes the number
of scenarios with every declared repeat reporting that metric. A metric observed in one of six
runs is therefore not presented as if all six supplied evidence, even if its mean is 1.0.

Means and bootstrap calculations are unchanged: each scenario contributes the mean over its
available repeats, and intervals resample reporting scenarios. Omitted metrics are not silently
replaced with zero. A Markdown warning identifies metrics missing from some repeats of a reporting
scenario; investigate that absence before comparing results. Absence might mean a metric did not
apply, but coverage alone cannot establish that, distinguish it from collection failure, or justify
missing-at-random assumptions. Repeats are not additional independent scenarios.

These counts describe supplied observations, not population representativeness, statistical power,
or production reliability. Historical reports remain unchanged; regenerate them explicitly from
their original evidence if new coverage annotations are needed.

### Import recorded scores from your existing evaluation system

You do not need to rerun an agent through AAU to use its metric audit, paired comparisons,
multi-metric/cohort policies, and offline reviewer packs. The current repository harness adds
`aau import-eval`: a standard-library-only, offline importer for **already scored observations**.
It executes no model, evaluator, adapter, network request, or scoring code. Install the repository
harness with `python -m pip install -e harness`; do not assume an older PyPI release has this command.

Try the committed synthetic fixture (choose unused output paths):

```bash
aau import-eval harness/examples/evaluation-review/recorded-observations.json \
  --out /tmp/imported-evaluation.json
aau import-eval harness/examples/evaluation-review/recorded-observations.json \
  --verify /tmp/imported-evaluation.json
aau audit-eval /tmp/imported-evaluation.json --out /tmp/imported-audit.json
```

Map your own export explicitly to the fixture's small JSON contract. This is a neutral interchange
format, not an automatic parser for arbitrary framework exports or a conversion of AAU public
aggregate receipts back into observations. Required fields:

| Field | Meaning |
|---|---|
| `format_version` | `aau-recorded-observations/1.0` for scores only; `aau-recorded-observations/1.1` also accepts optional operating measurements |
| `source_label` | Your nonblank description, at most 200 characters; not authenticated |
| `scenario_ids` | The complete declared census, 1–500 unique nonblank IDs |
| `n_repeats` | Positive integer; total observations cannot exceed 10,000 |
| `observations` | Exactly one row per scenario/repeat, with `scenario_id`, zero-based `repeat`, and `metrics`; version 1.1 optionally adds the three operating fields below |
| `evaluation_context` | Optional existing context fingerprint object covering exactly the census |

Metric values must be finite numbers, not booleans or numeric strings. At most 100 metric names
are accepted and at least one metric must be recorded. Duplicate observations, missing repeats,
unknown cases, unsupported fields, nonfinite aggregates, and files over 2 MB fail closed. The
importer does not infer scores from text or treat provider errors as task failures: distinguish
those in your original collection process. Declaring a smaller census can still conceal missing
cases; independent reviewers must approve the expected scenario set.

Summaries use the same per-scenario repeat averages and scenario bootstrap as AAU's metric audit.
Missing optional metrics stay absent, with explicit coverage; they are never filled with zero.
Review policies still require every selected metric in every observation. No cost, latency, API
call counts, timestamp, or execution provenance is invented. The export is labeled
`imported_unverified_observations` and includes a canonical-JSON source hash; this is not a hash of
the original file bytes or a signature. Keep the original recording for `--verify`, which detects
altered observations, summaries, context, or provenance. Exit 0 means normalization/verification
succeeded, not good performance; exit 2 means invalid input or a failed verification.

An optional context is copied and validated, never synthesized. Without it, comparisons explicitly
report unavailable context and the pinned-input evaluation Action refuses the evidence. Matching
supplied fingerprints do not establish authenticity. Do not graft today's code hashes onto old
observations whose collection context is unknown. Imported IDs, labels, and scores remain visible;
this is not anonymization or a public-sharing approval. Existing source files and output paths are
never overwritten.

#### Bring existing cost and timing measurements with your scores

Version **1.1** adds three optional fields **on each observation**, not inside `metrics`.
Everything else—the census, score validation, context rules, source binding, offline behavior,
and size limits—stays the same. Version 1.0 remains strict and byte-compatible: it still rejects
operating fields instead of silently dropping them.

| Observation field | Meaning and accepted values |
|---|---|
| `cost_usd` | Supplied cost for that scored attempt in USD; finite nonnegative JSON number |
| `latency_s` | Supplied elapsed time for that attempt in seconds; finite nonnegative JSON number |
| `n_api_calls` | Supplied number of API calls for that attempt; integer from 0 through 1,000,000,000,000 |

**Omit a field when unknown.** `null`, booleans, numeric strings, negative values, and nonfinite
numbers are errors. Zero stays zero; it is not converted to wall-clock time or inferred to mean
free execution. The importer copies supplied numeric values without display rounding, currency
conversion, price lookup, timestamp subtraction, or token-to-cost estimation. Other fields,
including prompts, traces, provider credentials, and arbitrary details, remain rejected.

Try the separate [synthetic operating fixture](examples/evaluation-review/recorded-operations.json):

```bash
aau import-eval harness/examples/evaluation-review/recorded-operations.json \
  --out /tmp/imported-operating-evaluation.json
aau import-eval harness/examples/evaluation-review/recorded-operations.json \
  --verify /tmp/imported-operating-evaluation.json
aau operating-eval /tmp/imported-operating-evaluation.json \
  --criterion completion higher 1 --criterion unauthorized lower 0 \
  --cost-basis synthetic --out /tmp/imported-operating-review.json
```

Its four constructed attempts cost $0.10 each; only one meets both criteria. The review reports
$0.40 per passing attempt, including failure costs, and a 12-second nearest-rank p95. These are
fixture values, not measured model performance. Deleting one supplied cost makes cost coverage
partial: the complete total and per-pass ratio become unavailable, not artificially cheaper.
Timing and API-call coverage are tracked independently. No operating summary is fabricated by
the importer; use `operating-eval` or a diagnostic dossier to derive them.

`evaluation-pack from-recordings` and the pinned-input Action accept both recording versions.
With version 1.1 and a diagnostic plan, a thirteen-file dossier retains the original recordings,
normalized observations, and recomputable operating reports. Require both `--require-recordings`
and `--require-diagnostics` at handoff. Invalid operating fields are rejected even when no diagnostic
plan is requested. A valid operating report does not change the policy verdict.

Before mapping your real exports, document what an attempt includes: retries, tool calls, queueing,
parallel work, and human review can make units incomparable. Do not copy a provider-call histogram,
an account-wide invoice, or aggregate p95 into individual attempt rows. Do not replace actual
end-to-end elapsed time with a sum of overlapping spans. Supply a reviewed `estimate`, `charge`,
`synthetic`, or `unknown` cost basis to the operating review/diagnostic plan; the importer does not
authenticate that declaration or establish fully loaded cost. IDs, costs, and timings may still be
sensitive even though free-text details are excluded. Review before sharing.

### Convert scored CSV exports without losing the original evidence

`aau csv-eval` converts an explicitly mapped CSV export into a **six-file, source-retaining pack**.
It does not infer scores, units, case coverage, repeat numbering, or column meanings. Use the
current repository harness; this command is not in the previously published PyPI 1.6.0 package.

```bash
aau csv-eval create harness/examples/evaluation-review/csv-plan.json \
  harness/examples/evaluation-review/scored-observations.csv --out /tmp/csv-evidence
aau csv-eval verify /tmp/csv-evidence
aau operating-eval /tmp/csv-evidence/evaluation.json \
  --criterion completion higher 1 --criterion unauthorized lower 0 \
  --cost-basis synthetic --out /tmp/csv-operating-review.json
```

The synthetic fixture deliberately omits one attempt's cost. Its cost coverage remains partial;
full cost and cost per passing attempt stay unavailable, while complete timing remains usable.
One recorded authorization failure also remains visible. Nothing is rerun or sent to a service.

Adapt [the mapping plan](examples/evaluation-review/csv-plan.json), then supply your reviewed
complete scenario-ID census and repeat count. `columns` must map `scenario_id`, `repeat`, a
nonempty `metrics` map, and an `operating` map (which may be empty). For example,
`"metrics": {"completion": "completed"}` maps the CSV header `completed` to metric `completion`.
Every mapped header must be distinct, and every CSV header must be mapped: no extra columns are
silently retained as unreviewed metadata or dropped. Column order is immaterial; names are exact.

The accepted dialect is UTF-8, optional UTF-8 BOM, comma delimiter, and double-quoted fields with
doubled internal quotes. Newlines follow the standard-library [CSV reader](https://docs.python.org/3/library/csv.html)
rules; no heuristic delimiter or header detection is performed. Malformed quoting, duplicate
headers, blank rows, inconsistent row widths, non-UTF-8 data, and NUL characters are rejected.

Repeat cells must be zero-based integers. Score and operating cells use JSON numeric syntax;
formulas, booleans, currency symbols, decimal commas, `null`, numeric text wrappers, nonfinite
values, and inappropriate negative operating values fail validation. Surrounding numeric whitespace
is ignored; scenario IDs are preserved exactly. Blank metric/operating cells stay absent, not zero.
Entirely unreported mapped metrics are listed explicitly. Unknown timing should be blank—not `0`.
Only `cost_usd`, `latency_s`, and `n_api_calls` may be mapped as operating fields, with their existing
USD/seconds/count semantics; no currency, time-unit, token-price, or aggregation conversion occurs.
Complete scenario-repeat coverage and existing import validation still apply.

| Retained file | Purpose |
|---|---|
| `source.csv` | Exact original bytes, including BOM and line endings |
| `plan.json` | Complete supplied mapping, census, source label, and optional contemporaneous context |
| `recording.json` | Version-1.1 observation contract for `evaluation-pack from-recordings` |
| `evaluation.json` | Normalized input for audits, comparisons, operating reviews, and policy reviews |
| `conversion.json` | Source/plan/derived-value hashes, measurement coverage, and interpretation limits |
| `manifest.json` | Exact member inventory and unsigned byte hashes; written last |

Verification reparses the retained CSV and recomputes every derived file, not just manifest hashes.
Missing, extra, symlinked, oversized, or modified members fail. Each member is bounded to 2 MB;
there may be at most 10,000 observations, 500 scenarios, and 100 mapped metrics. Invalid input is
rejected before destination creation; existing output paths are never overwritten. Interrupted
packs without their complete contents cannot verify. Exit 0 means the conversion verifies, not
that the observations pass a policy; exit 2 means invalid input or failed verification.

For an automatic two-export handoff, use [CSV review](#hand-off-two-csv-exports-as-one-verifiable-review)
below. For a manual handoff, retain this conversion pack alongside the downstream review dossier.
Create that dossier with this pack's `recording.json` as the appropriate baseline or candidate.
Then check both the link and the dossier itself:

```bash
aau csv-eval verify /tmp/csv-evidence --evaluation /path/to/dossier/candidate.json
aau evaluation-pack verify /path/to/dossier --require-recordings --require-diagnostics
```

The optional `--evaluation` checks that the downstream normalized JSON matches the verified
conversion; it does not verify the rest of that dossier. Never replace a failed dossier check
with a successful conversion check. An absent context is not synthesized: recover the original
collection context or keep the comparability limitation visible. A renamed header or a chosen
smaller census can still misrepresent collection; reviewers must inspect the mapping and scope.
Coordinated replacement of all source and derived files can verify because hashes are not signatures.
The retained CSV is **not sanitized**. Identifiers can contain sensitive data or spreadsheet
formulas; do not open untrusted source files in spreadsheet software. Review the whole pack before sharing.

### Identify the harness implementation used for a review

The version label alone is insufficient for unreleased checkouts and local wheels: different
source revisions can share the same package version. With the current repository harness, use:

```bash
aau runtime-info --out runtime-source.json
aau runtime-info --verify runtime-source.json
```

Without options, the command prints JSON. It records the distribution metadata version (or null
when unavailable), Python implementation/version, a sorted inventory of relative first-party
`.py` filenames and byte hashes, and `source_tree_sha256`. That tree hash is independent of the
installation path and distribution version. `--verify` checks **the whole receipt**, including
Python metadata, against the current installation: exit 0 matches; exit 2 means mismatch or invalid
input. Existing outputs are never overwritten. Different Python versions can produce different
receipts even when the source-tree hash matches; inspect those fields separately.

Capture a receipt at collection and again at review time; retain it **beside**, not inside,
strictly enumerated evidence packs. No pack-verifier requirements are changed. The receipt includes
no absolute local paths, environment variables, credentials, hostnames, or timestamps. It excludes
`__pycache__`, non-Python resources, external dependencies, interpreter bytes, and configuration.
It inventories on-disk files, not previously loaded or actually executed code. Symlinked Python
sources/directories, missing sources, unreadable trees, and excessive inventories fail closed
(500 files, 2 MB each, 20 MB total). Source inventories can disclose module names; review before sharing.

This helps diagnose implementation drift; it does **not** authenticate a collector, prove scoring
correctness, establish reproducible execution, or replace a signed release/provenance check.
Use a trusted harness to collect and compare receipts. Not available in published PyPI 1.6.0.

### Hand off two CSV exports as one verifiable review

`aau csv-review` closes the gap between CSV conversion and a reviewer-ready dossier. Teams can
retain a baseline and candidate export, their explicit mappings, policy, diagnostics, and the
complete review in **one 28-file folder**. One verification command recomputes the entire chain;
it does not merely check whether the three component folders are individually valid.

Requires the **current repository harness or a wheel built from it**, not published PyPI 1.6.0.
From the repository checkout:

```bash
pip install -e harness
aau csv-review create \
  harness/examples/evaluation-review/csv-review-policy.json \
  harness/examples/evaluation-review/csv-plan.json \
  harness/examples/evaluation-review/scored-observations.csv \
  harness/examples/evaluation-review/csv-plan.json \
  harness/examples/evaluation-review/scored-observations-repaired.csv \
  --diagnostics harness/examples/evaluation-review/csv-review-diagnostics.json \
  --out /tmp/aau-csv-review
aau csv-review verify /tmp/aau-csv-review
```

Open `/tmp/aau-csv-review/review/review.html` in a browser. These are **synthetic scored rows**,
not model runs or measured service outcomes. Both exports record completion on every attempt;
the baseline includes an unauthorized action and one missing cost. The repaired candidate passes
the example policy and has $0.25 per jointly passing attempt. The baseline's total cost remains
unknown. Collection context is absent and disclosed; matching scenario labels do not establish
that test conditions were the same.

To exercise the negative twin, repeat `create` with `scored-observations.csv` as **both** inputs
and a fresh output destination. Creation and verification return **1**, retaining the complete
failed review. Do not hide this result with `|| true` in a deployment gate.

```text
handoff/
  baseline/      6 files: original CSV, mapping, conversion, recording, evaluation, manifest
  candidate/     6 files: original CSV, mapping, conversion, recording, evaluation, manifest
  review/       13 files: both recordings, policy, diagnostics, evaluations, reports, HTML, manifest
  handoff.json   source links, coverage, policy status, and declared boundaries
  README.txt     offline reviewer instructions and sharing warnings
  manifest.json  exact byte hashes of the other 27 files
```

The baseline and candidate may use different explicit column maps; their full scenario census
must still satisfy the shared policy and existing comparison rules. A diagnostics plan is
mandatory. Policy and diagnostics remain separate: a descriptive result never overrides a policy
failure. Original CSV bytes, including BOMs and line endings, are retained unchanged.

Exit **0** means all supplied policy constraints are met and the source chain verifies; **1**
means the chain verifies but constraints are not met; **2** means invalid input or failed
verification. All inputs and expanded outputs are validated before creating the destination.
Existing paths are refused. Each file is limited to 2 MB; all CSV census and numeric limits still
apply. The root manifest is written last, and interrupted/partial output fails verification.
Move the entire folder; no original input path, checkout, API key, or network is required to
verify it with the matching installed harness.

The verifier reparses both exports and reconstructs every derived byte, including the source
recordings inside the review. Substituting a valid but unrelated component fails, even if the
outer hashes are updated. The component `csv-eval` and `evaluation-pack` verifiers still work,
but only `csv-review verify` checks the **whole handoff**. This is not a signed attestation:
coordinated replacement of all inputs and outputs can still verify. Scoring correctness,
collection completeness beyond the declared census, policy timing, and authenticity are not proven.

This supports documentation and reproducibility, consistent with the voluntary evaluation focus
of the [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework);
it is **not NIST certification, compliance, an ATO, or deployment approval**. Packs are not
sanitized: inspect every file before sharing, and do not open untrusted CSV in spreadsheet
software. No models, agents, external tools, or upload services are invoked.

For a CI gate, the [saved evaluation review Action](../.github/actions/aau-evaluation-review/README.md#gate-scored-csv-exports-without-losing-their-source-chain)
accepts `input-format: csv` with independently approved byte pins for both column maps, the
baseline CSV, policy, and diagnostics. Unlike the descriptive CLI above, the Action **requires
matching declared collection context**; the basic context-free examples do not pass that gate
as-is. No shared context is fabricated and no approval hashes should be derived from untrusted
candidate inputs in the same production job.

### Audit a saved evaluation without rerunning a model

With the current repository harness:

```bash
aau audit-eval home-field-services/service-visit-readiness-coordinator/results/eval_mock.json \
  --out metric-audit.json
aau audit-eval home-field-services/service-visit-readiness-coordinator/results/eval_mock.json \
  --verify metric-audit.json
```

The audit requires complete declared scenario-repeat coverage, then recomputes metric means,
the harness's deterministic scenario-bootstrap intervals, and per-metric coverage from recorded
observation values. It compares the stored means and intervals at the exporter’s four-decimal
precision and compares coverage when the source contains it. Older files without coverage get
derived coverage, clearly marked as not originally recorded. Metrics missing in some observations
remain excluded rather than imputed as zero.

Exit **0** means the metric summaries are internally consistent—even if every score is zero.
Exit **1** means the audit was written with exact recorded/recomputed mismatches. Exit **2** means
invalid or incomplete input, or an audit report that does not recompute. Existing output files
are never overwritten. Each input/output file is limited to 2 MB; an audit accepts at most 500
scenarios, 10,000 observations, and 100 metric names. This command makes no model calls.

The source hash binds supplied JSON values. The audit does **not** validate scoring ground truth,
which scenarios actually ran, provider availability, provenance, costs, latency, statistical power,
or the authenticity of the observations. Coordinated replacement of observations and summaries
can still be internally consistent. Partial coverage and repeated observations are not proof of
applicability or independence. Other evaluation formats or bootstrap methods may be incompatible;
this command targets the current shared harness format and algorithm. Keep the original evidence
and harness revision. Review metric names and mismatch values before sharing.

### Compare two saved evaluations by matched scenario

Use the current repository harness to compare a selected metric without API calls:

```bash
aau compare-evals baseline.json candidate.json --metric service_exact --direction higher \
  --out comparison.json
aau compare-evals baseline.json candidate.json --metric service_exact --direction higher \
  --verify comparison.json
```

Both files must use the shared evaluation format. Verify that matching scenario IDs actually
describe the same cases, scorer, and evaluation conditions before interpreting the comparison;
matching names alone cannot establish that. The command requires exactly the same scenario-ID
set and complete selected-metric coverage on both sides. It refuses missing observations, duplicate
scenario/repeat pairs, nonnumeric scores, and partial metric coverage instead of silently keeping
only favorable intersections or filling omissions with zero. Use `lower` for metrics such as an
error rate: direction is never guessed from a name.

The report averages each scenario's repeats on each side, subtracts baseline from candidate,
and resamples those **paired scenario deltas** with the existing deterministic percentile bootstrap
(2,000 samples, seed 0). It reports the mean delta, a 95% interval, and every scenario that
improved, regressed, or stayed unchanged. A zero average can conceal both improvements and
regressions; the report keeps both visible. Repeats are not additional independent scenarios.
Different repeat counts are allowed and disclosed. Stored summary inconsistencies remain visible
in `source_audits`; comparison uses recorded observations, never repairs historical summaries.

This pairing follows the [paired-resampling principle documented by SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html):
the same scenario is retained on both sides of each resample. It uses the repository's existing
percentile implementation, not SciPy's default BCa method, and adds no statistical dependency.
Intervals capture variation across supplied scenario deltas, not within-scenario stochastic
uncertainty. Small or identical samples may yield degenerate intervals; warnings explain this.
The method assumes exchangeable scenario units and does not establish population representativeness.

Exit **0** means a descriptive report was produced or verified, **not** that the candidate passed
a release gate. Exit **2** means invalid input/output or failed reverification. There is no automatic
significance verdict, multiple-comparison correction, practical-effect threshold, or deployment
approval. Source-value hashes bind both inputs, but do not authenticate execution or scoring.
Inputs/outputs retain the audit's 2 MB limits; output files are never overwritten. JSON reports
can contain scenario IDs and supplied mismatch values: review them before sharing externally.

> Optional metrics remain omitted where unavailable; do not emit a fabricated `0.0` for
> inapplicable cases. The runner reports coverage. This paired comparison deliberately requires
> a fully observed selected metric; it does not infer applicability or missing-at-random behavior.

### Expose intermittent failures behind successful retries

`aau repeatability-eval` reviews complete recorded repeats without another model call. Each
repeat passes only when **all** supplied observation criteria pass together. It cannot combine
completion on one attempt with authorization on a different attempt.

```bash
# Use the current repository checkout; no API key or uploaded data is required.
python harness/examples/evaluation-review/repeatability.py --out /tmp/aau-repeat-demo
aau repeatability-eval /tmp/aau-repeat-demo/intermittent.json \
  --criterion completion higher 1 --criterion unauthorized lower 0 \
  --draw-size 1 --draw-size 2 --draw-size 4 --out /tmp/repeated-review.json
aau repeatability-eval /tmp/aau-repeat-demo/intermittent.json \
  --criterion completion higher 1 --criterion unauthorized lower 0 \
  --draw-size 1 --draw-size 2 --draw-size 4 --verify /tmp/repeated-review.json
```

The synthetic twin keeps completion at 100% in both versions. One authorization failure in
four repeats of one case changes its joint all-pass fraction for two-recorded-repeat subsets
from 100% to 50%, while the any-pass fraction stays at 100%. The repaired version removes that
constructed failure; this demonstrates the diagnostic, not a measured improvement in a real agent.

For each scenario with `n` recorded repeats and `s` jointly passing repeats, the report exposes:

| View | Exact recorded-subset calculation | Question answered |
|---|---|---|
| All pass | `C(s, k) / C(n, k)` | In what fraction of size-k subsets does every recorded attempt pass? |
| Any pass | `1 - C(n-s, k) / C(n, k)` | In what fraction does at least one recorded attempt pass? |
| Failures | Repeat ID, failed criteria, observed values | Which measurements need investigation? |

The report retains exact integer subset counts and equally weights scenarios for aggregate
fractions. It labels each case `all_recorded_pass`, `mixed`, or `none_recorded_pass`. Inclusive
floors use `higher`; inclusive ceilings use `lower`. Direction and limit are never inferred.
It accepts 1–10 distinct metric criteria and unique draw sizes between 1 and 20, each no greater
than the recorded repeat count. Missing selected metrics, incomplete observation matrices,
duplicate repeat IDs, invalid scores, and unavailable draw sizes are errors, not exclusions.
Unselected metrics and source-summary inconsistencies remain visible. A single repeat warns
that within-case repeatability cannot be assessed. Identical scores do not prove copied runs
or independent runs; the tool makes neither inference.

The distinction is motivated by [τ-bench's pass^k research](https://arxiv.org/abs/2406.12045).
Unlike a future-trial reliability claim, these values describe finite supplied subsets without
replacement. Independent, identically distributed execution is **not established**. No confidence
bound, consecutive-run claim, population representativeness, scoring authenticity, preregistration,
or deployment approval follows. A zero observed failure count does not establish zero risk, and
any-pass is not permission to retry consequential actions until one succeeds. Use
`review-evals` for a separate baseline-relative policy review.

Exit **0** means a descriptive report was produced or exactly reverified, even if failures are
present; exit **2** means invalid input/output or a mismatching report. JSON-value source hashes,
explicit criteria, and draw sizes bind reverification. Outputs are never overwritten and the CLI
keeps the 2 MB input/report limit. Review scenario IDs, scores, and mismatch details before sharing.
No network access, model execution, or new dependency is required.

### Try the evaluation workflow from an installed package

`aau evaluation-demo --out /path/to/new-demo` creates two complete synthetic review dossiers
using only the installed harness. No checkout lookup, downloaded fixture, API key, provider,
agent execution, or network request is required by the command.

**Availability:** this command is new in the repository. Install the current checkout with
`python -m pip install -e harness`, or install a wheel built from that checkout. The previously
published PyPI 1.6.0 package does not contain it; no new PyPI publication is implied here.

```bash
aau evaluation-demo --out /tmp/aau-installed-demo
aau evaluation-pack verify /tmp/aau-installed-demo/repaired \
  --require-recordings --require-diagnostics
# Expected exit 1: valid evidence of a failed policy, not a broken demo.
aau evaluation-pack verify /tmp/aau-installed-demo/intermittent \
  --require-recordings --require-diagnostics
```

Open either folder's `review.html` and the top-level `README.txt`. Each dossier retains thirteen
files: supplied synthetic recordings, normalized evaluations, policy, diagnostic plan, review,
operating and repeated-run views, and a byte manifest. The intermittent fixture exposes three
authorization failures hidden by 100% completion; the repaired twin preserves authorization.
Failure costs remain included. Every score, cost, timing, and API-call count is constructed.

Creation exits 0 only after both packs verify with their expected opposite policy outcomes;
this is not a claim about a real system. An existing destination is rejected without overwriting
it. The guide is written last; interrupted partial output is not a completed walkthrough. Keep
the matching harness revision to reverify, and independently design your own cases and thresholds
before adapting the format to real evidence.

### Hand off one complete offline review dossier

Add `--diagnostics plan.json` to `aau evaluation-pack create` or `from-recordings` to combine
the policy verdict, repeated-run consistency, and operating evidence in one portable folder.
Open `review.html` for a script-free, offline reviewer page; its baseline/candidate tables link
to the complete JSON reports and retain warnings, exact failures, and missing-data states.

```bash
python harness/examples/evaluation-review/dossier.py --out /tmp/aau-dossier-demo
aau evaluation-pack verify /tmp/aau-dossier-demo/intermittent-pack --require-diagnostics
# Expected exit 1: the folder recomputes, but its policy constraints fail.
aau evaluation-pack verify /tmp/aau-dossier-demo/repaired-pack --require-diagnostics
# Expected exit 0: the supplied policy constraints are met, not deployment approval.

# Build the same repaired dossier yourself from its explicit inputs:
aau evaluation-pack create /tmp/aau-dossier-demo/policy.json \
  /tmp/aau-dossier-demo/baseline.json /tmp/aau-dossier-demo/repaired.json \
  --diagnostics /tmp/aau-dossier-demo/diagnostics.json --out /tmp/my-review-dossier
```

The strict diagnostic plan is separate from the release-review policy:

```json
{
  "plan_version": "aau-evaluation-diagnostics/1.0",
  "criteria": [
    {"metric": "completion", "direction": "higher", "limit": 1},
    {"metric": "unauthorized", "direction": "lower", "limit": 0}
  ],
  "draw_sizes": [1, 2, 4],
  "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}
}
```

Choose reviewed criteria, cost declarations, and subset sizes appropriate to your evidence;
do not adopt the example's synthetic limits as production requirements. Each draw size must be
available on **both** sources, with complete selected-metric coverage. Different repeat counts
are retained, not downsampled. Cost fields may be unavailable; this stays visible as unknown.

| Dossier files | Purpose |
|---|---|
| `policy.json`, `baseline.json`, `candidate.json` | Full source evaluations and policy, including source detail fields |
| `review.json`, `review.html` | Policy verdict and complete human-readable review |
| `diagnostics.json` | Exact supplied diagnostic assumptions |
| `baseline-repeatability.json`, `candidate-repeatability.json` | Joint pass/fail and recorded-subset curves |
| `baseline-operations.json`, `candidate-operations.json` | Coverage, cost per passing attempt, and tail latency |
| `manifest.json` | Exact file inventory and unsigned byte hashes |

This is an eleven-file `aau-evaluation-review-pack/2.0` folder. The `from-recordings` form
adds both original recording JSON values for thirteen files and records its input format.
Version-1.0 recordings contain metric scores only, so their operating views correctly show
unavailable measurements. Version-1.1 recordings can retain supplied per-attempt cost, timing,
and API-call values; absent values remain unknown, with field-specific coverage.
Use both `--require-diagnostics` and `--require-recordings` when the handoff requires both.

Verification recomputes normalization where applicable, the policy review, all four diagnostic
reports, HTML, and the manifest. Altering a report and updating its manifest hash is insufficient.
Missing or extra files, unsupported formats, unsafe member shapes, changed bytes, and invalid
plans fail verification. Output directories are never overwritten; invalid or oversized inputs
are rejected before directory creation. Each member remains bounded to 2 MB. Without diagnostics,
the earlier six/eight-file pack formats and their output bytes are unchanged.

**The policy alone determines exit 0 or 1.** Diagnostic criteria are not automatically the policy's
global or cohort limits and do not apply its regression budgets. Even if every diagnostic passes,
a failed policy still returns 1. Exit 2 means invalid input or failed verification. Matching
declared benchmark context is checked by the underlying policy review; absent context remains
explicitly unavailable, not assumed comparable. A cost table, retry curve, or syntactically valid
pack cannot grant deployment permission.

This handoff follows the emphasis on inspectable, usable artifacts in
[ACM SIGSIM's artifact-evaluation guidance](https://sigsim.acm.org/conf/pads/2024/blog/artifact-evaluation/),
not an ACM badge or independent validation claim. Retain the matching harness revision and
independently trusted source commitments. Coordinated replacement of all sources and outputs
can still verify; hashes are not signatures. The folder includes full source details and is
**not sanitized**. Nothing is uploaded automatically; review privacy and sharing authority first.

For CI adoption, the [saved evaluation Action](../.github/actions/aau-evaluation-review/#produce-a-reviewer-dossier-from-an-independently-approved-diagnostic-plan)
accepts `diagnostics` with an independently approved `diagnostics-sha256`. It verifies that
file-byte pin before producing a dossier and recomputes every included view before returning
the policy's exit status. Missing pairs or changed plan bytes fail closed; no uploads or new
permissions are introduced. Keep approval hashes outside candidate-controlled code.

### Understand operating cost without excluding failed attempts

`aau operating-eval` connects recorded cost and latency to **jointly passing attempts**.
It counts all supplied attempts, including failed ones, and never fetches prices, makes model
calls, fills missing measurements with zero, or rewrites the original evaluation.

```bash
# Current repository checkout; this example contains constructed values, not real savings.
python harness/examples/evaluation-review/operations.py --out /tmp/aau-operations-demo
aau operating-eval /tmp/aau-operations-demo/cheap-attempt.json \
  --criterion completion higher 1 --criterion unauthorized lower 0 \
  --cost-basis synthetic --out /tmp/operating-review.json
aau operating-eval /tmp/aau-operations-demo/cheap-attempt.json \
  --criterion completion higher 1 --criterion unauthorized lower 0 \
  --cost-basis synthetic --verify /tmp/operating-review.json
```

Both synthetic versions record 100% completion across four attempts at one case. Only one
attempt in the cheaper version meets the authorization criterion; all four in the repaired
version meet both criteria. Looking only at cost per attempt reverses the apparent preference:

| Constructed measurement | Cheap attempt | Repaired twin |
|---|---:|---:|
| Mean cost per attempt | $0.10 | $0.25 |
| Jointly passing attempts | 1 of 4 | 4 of 4 |
| Cost of **all** attempts / passing attempt count | $0.40 | $0.25 |
| Median recorded latency | 1 second | 2 seconds |
| Nearest-rank p95 recorded latency | 12 seconds | 2 seconds |

This is a diagnostic example, not a measured vendor comparison, recommendation, or proof of
production savings. Failed attempts may have caused effects; a cheaper ratio never permits
retrying an unauthorized operation. A passing attempt is a scored repeat, not a unique user
served, a resolved real-world case, or a verified business outcome.

The report includes overall and per-scenario attempt counts, exact failed criteria, recorded
costs spent on failing attempts, mean cost per attempt, cost per passing attempt, median and
p95 latency, maximum latency, and API-call totals. Costs are recorded **USD** values. Declare
`--cost-basis estimate`, `charge`, `synthetic`, or `unknown`; this label does not authenticate
pricing or invoices. Do not mix different bases or currencies into one input. Zero recorded
cost does not mean the service is free. Infrastructure, human review, downstream tools, and
overhead absent from the source remain excluded; this is not fully loaded cost or ROI.

Every metric criterion must be present in every attempt. Operational fields `cost_usd`,
`latency_s`, and `n_api_calls` are optional but independently coverage-counted. Missing means
**unknown**; explicit nulls, strings, booleans, negative values, and nonfinite values are invalid.
API counts must be integers from 0 through 10^12. Incomplete costs or API counts have a labeled
sum of reported values, but never a full-sample total. Cost ratios require complete cost coverage;
zero passing attempts yield null with a reason, not zero or infinity. Latency quantiles require
complete timing coverage. Imported metric-only evaluations therefore do not become free,
instantaneous evaluations. Scenario-level completeness does not hide missing data globally.

The p50 is the ordinary median; p95 uses the observed value at one-based rank
`ceil(0.95 * attempt_count)`. All attempts, including failures, remain in both calculations.
With fewer than 20 observations p95 is the maximum; the report warns against treating this
as a stable tail-risk estimate. Stored operational headlines are neither reused nor audited:
row-level data may have been rounded differently. No lost precision is recovered. Stored
**metric** summary mismatches remain visible through the existing audit.

The design is informed by [FinOps' outcome-oriented unit economics](https://www.finops.org/framework/capabilities/unit-economics/)
and [Google SRE's latency-percentile guidance](https://sre.google/workbook/monitoring/).
It is not an implementation or certification of either framework. Source authenticity,
scoring validity, timing instrumentation, repeat independence, and representativeness remain
unverified. This descriptive report is not a forecast, invoice reconciliation, SLO evaluation,
or release gate. Exit **0** means produced/reverified, not approved; exit **2** means invalid
input/output or failed reverification. Criteria, declared basis, and source JSON values are
bound to the report. The CLI refuses overwrites and enforces 2 MB input/report limits.
Review scenario identifiers, costs, timings, and audit details before external sharing.

### Explain benchmark drift before comparing evaluation scores

`aau compare-eval-contexts` identifies **which test definitions changed** when a comparison is
blocked. It inspects complete supplied evaluations independently, so different scenario censuses
can be reviewed without pairing scores from only their intersection. It makes no model calls,
rewrites no fingerprints, and does not relax `compare-evals` or review-policy checks.

```bash
python harness/examples/evaluation-review/context-drift.py --out /tmp/context-drift-demo
aau compare-eval-contexts /tmp/context-drift-demo/baseline.json \
  /tmp/context-drift-demo/matched.json \
  --verify /tmp/context-drift-demo/matched-context-review.json
# Expected exit 1: the report verifies, but changed definitions require review.
aau compare-eval-contexts /tmp/context-drift-demo/baseline.json \
  /tmp/context-drift-demo/changed.json \
  --verify /tmp/context-drift-demo/changed-context-review.json
```

All three example files have the same constructed 100% completion headline. The changed twin
removes the assisted case, adds a replacement case, and changes the routine case's authorization
requirement under the same ID. The report exposes all three changes; matching scores are not
evidence that the benchmarks mean the same thing.

For your own saved evaluations, use `--out /path/to/new-context-review.json`, then `--verify`
against the retained originals. Add `--input-format recordings` for either supported recorded-
observation format; the report binds both original and normalized JSON-value hashes.

| Report view | What it establishes |
|---|---|
| Scenario census | Observed IDs added, removed, and shared; no renaming or equivalence inferred |
| Scenario fingerprints | Exact declared hashes changed under the same ID, including unchanged and unknown entries |
| Scoring fingerprints | Named scoring components added, removed, changed, or unchanged when both declarations exist |
| Configuration | Both declared hashes and whether they differ; not a semantic explanation of a changed rule |
| Missing context | Which source lacks a declaration; absence is not treated as a component removal or a match |
| Source metric audits | Summary-consistency status and mismatch count; original values remain untouched |
| Repeat counts | Differences are disclosed, not treated as context drift or extra independent scenarios |

Exit **0** (`declared_context_matched`) means present, valid context fingerprints match and
metric summaries recompute. It does **not** mean that scores are good, policy checks pass, or
execution is authenticated. Exit **1** (`review_required`) means missing context, changed census,
changed scenario/scorer/configuration hashes, or inconsistent metric summaries. Exit **2** means
invalid input, malformed present context, invalid coverage, or failed report verification.
The output retains exact digests and machine-readable reason codes; the console does not print
scenario IDs, component names, or score values. Files remain bounded to 2 MB and outputs cannot
overwrite an existing path.

Review actual case/configuration/scoring sources to understand a digest difference. Comment-only
scorer edits can change a digest without changing behavior; identical digests still do not prove
execution, dependency closure, preregistration, or population coverage. Recover contemporaneous
context where possible. Never remove conflicting context, graft today's hashes onto old runs,
rename cases, or discard difficult cases to force a match. If definitions intentionally change,
review the new benchmark and collect comparable evidence under a common approved context.
Inspect scenario IDs and component names for sensitive information before sharing the report.

This design is informed by [NIST AI RMF Playbook MEASURE 2.1](https://airc.nist.gov/airmf-resources/playbook/measure/),
which emphasizes documenting test sets and evaluation tools. This inventory is one supporting
engineering tool, not a NIST assessment, compliance certification, or authorization to deploy.

### Bind new evaluations to their declared benchmark context

New runs through the shared **Decision Gate**, **Evidence Service**, and **Forge contract**
engines now include `evaluation_context`. Before scenario execution, the engine fingerprints:

- Each complete scenario object, keyed by scenario ID, using canonical finite JSON values.
- The domain configuration, including its declared rules and vocabulary.
- Named source-file bytes for the shared engine, runner, agent loop, and context encoder;
  Evidence Service also includes its Public Value scorer.

This records hashes, not an extra copy of potentially sensitive case content. It does not change
scores, rerun models, or retrofit historical files. Model/provider selection is deliberately not
part of this benchmark fingerprint so different agents can be evaluated against the same declared
cases. Provider metadata remains separate. File fingerprints are conservative: even a comment-only
change can make two contexts differ and require human review rather than automatic comparison.

`compare-evals`, `review-evals`, and evaluation review packs reject **conflicting** contexts or a
malformed present context. A context must cover exactly the observed scenario IDs. If either source
lacks context, comparison remains available for legacy evidence, but `context_match` is explicitly
`unavailable` and a warning explains the gap. This is not a match and does not prove comparability.
The original 1.0 review policy does not require context; a `constraints_met` result with unavailable
context still needs independent comparability review. Never delete a conflicting context to
silence an error or invent historical fingerprints from today's files.

Custom evaluators can opt in without changing their measurement callback:

```python
from aau_harness.evaluation_context import capture_context
from aau_harness.runner import run_eval

context = capture_context(
    scenario_objects,  # JSON-compatible dictionaries with unique scenario_id fields
    benchmark_config,
    {"scorer.py": scorer_source_bytes},
)
aggregate = run_eval(scenarios, run_one, repeats=3, evaluation_context=context)
```

The runner snapshots supplied context before callbacks and copies it on export. It checks declared
scenario counts and result IDs. Context capture supports 1–500 scenarios, 1–20 named source files,
and a 2 MB limit per scenario/configuration serialization or source file. Object keys must be strings;
nonfinite numbers and unsupported values are refused. Keep the exact scenario definitions and named source bytes alongside
the evidence to reproduce the fingerprint; hashes alone cannot reconstruct inputs.

**Boundary:** these are declared-input fingerprints, not signatures or execution attestations.
They do not prove that the supplied objects or source files were executed, that loaded code matches
disk bytes, or that omitted dependencies, provider state, runtime conditions, or external services
were identical. The named files are not a complete dependency closure. A deliberately forged or
coordinately replaced context may still match. Hashes are not anonymization and can reveal equality
or support guessing low-entropy inputs; follow the same privacy review as for the source evidence.

### Review several metrics without trading away obligations

`aau review-evals` applies a supplied policy to both saved evaluations. All selected constraints
must hold; a completion gain cannot cancel an authorization failure. This complements the
change-specific [Agent Release Gate](../agent-release-gate/), but does not run adapters, collect new
evidence, authenticate approvals, or authorize a release.

Try the synthetic positive and negative twins in a **new** output directory:

```bash
python harness/examples/evaluation-review/demo.py --out /tmp/aau-evaluation-review-demo
aau review-evals /tmp/aau-evaluation-review-demo/policy.json \
  /tmp/aau-evaluation-review-demo/baseline.json /tmp/aau-evaluation-review-demo/legitimate.json \
  --verify /tmp/aau-evaluation-review-demo/legitimate-review.json
aau review-evals /tmp/aau-evaluation-review-demo/policy.json \
  /tmp/aau-evaluation-review-demo/baseline.json /tmp/aau-evaluation-review-demo/unsafe.json \
  --verify /tmp/aau-evaluation-review-demo/unsafe-review.json
```

The legitimate twin exits **0** (`constraints_met`). The unsafe twin exits **1**
(`constraints_not_met`): completion improves, but one of its authorization observations is zero.
Both reports recompute. An invalid policy, missing evidence, existing output, or tampered report
exits **2**. Use `--out review.json` instead of `--verify` to create a new report.

The strict policy contains a version, the exact `scenario_ids`, positive `minimum_repeats` for
each source, and 1–10 unique metric rules. Each rule has all five fields:

```json
{
  "metric": "authorization",
  "direction": "higher",
  "candidate_observation_limit": 1,
  "max_mean_regression": 0,
  "max_regressed_scenarios": 0
}
```

For `higher`, the observation limit is a minimum; for `lower`, it is a maximum. It applies to
**every candidate observation**, not an average, and reports exact violating scenario/repeat pairs.
The mean regression budget is the nonnegative deterioration of the paired scenario mean, in metric
units. The scenario budget counts all strictly worse scenario means. Limits are inclusive and
comparisons use unrounded numbers, without a hidden tolerance. Choose budgets deliberately rather
than treating floating-point noise or a tiny effect as automatically material.

Both sources must have consistent stored summaries and meet the minimum repeat count. Required
metrics must be present in every observation; both evaluations must match the policy's case set.
Extra source metrics are listed as **unreviewed**, not silently treated as safe. Reports bind the
policy and both sources, retain every metric comparison and its uncertainty warnings, and record
each failed constraint. The same 2 MB file limits apply; large reviews are refused, not truncated.

Select, independently review, and commit the policy **before** collecting candidate evidence.
The tool does not establish that timing: someone could rewrite a policy after seeing results.
Hashes provide reproducibility, not preregistration, reviewer identity, or provenance. Matching IDs
also do not prove matching case content or scoring semantics. Keep those definitions under review.

The design is motivated by the [NIST AI RMF MEASURE function](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/),
which calls for risk-relevant metrics and documented evaluation. These particular rules and
thresholds are repository mechanisms, **not NIST requirements or compliance certification**.
Constraint checks use observed point estimates, not a statistical noninferiority test; confidence
intervals remain descriptive and uncorrected for multiple comparisons. Passing cannot establish
production safety, representativeness, real-world benefit, or deployment approval.

### Catch regressions concentrated in a declared cohort

Policy version **`aau-evaluation-review-policy/1.1`** adds explicit `cohorts` alongside the existing
global rules. Use it when an overall gain could conceal a regression in a service channel, workflow
variant, or other deliberately selected case group. It does not infer personal or protected
attributes, decide which groups matter, or certify fairness.

Run the synthetic channel-regression twins in a new directory:

```bash
python harness/examples/evaluation-review/cohorts.py --out /tmp/aau-cohort-demo
aau evaluation-pack verify /tmp/aau-cohort-demo/regressed-pack
aau evaluation-pack verify /tmp/aau-cohort-demo/repaired-pack
```

The first verification exits **1**, the second **0**. The candidate improves overall completion
from 25% to 75%, within the illustrative global policy's regression budget, but its assisted-service
case falls from 100% to 0%. The declared cohort limits catch that deterioration. The repaired twin
preserves assisted completion as well. These are constructed fixtures, not measurements of people,
providers, accessibility outcomes, or real service quality.

Every cohort has three fields: a unique `cohort_id`, explicit `scenario_ids`, and `metrics` containing
the same five-field rules used globally. Cohort metrics must already be selected globally and use
the same preferred direction; their limits can differ. There may be 1–20 cohorts. They must collectively
cover every declared scenario at least once and cannot include unknown or duplicate member IDs.
Overlapping cohorts are allowed and disclosed: each is reviewed separately, without counting those
members again in the global average. A missing required observation still invalidates the review.

All global and cohort constraints must hold. No global gain or gain in another group compensates
for a failed cohort constraint. The report records each failed cohort/metric/constraint, complete
membership, scoped paired deltas and intervals, and individual observations outside their limits.
The offline HTML includes the same scoped findings and uncertainty warnings. The pinned-input
GitHub Action supports these policies without new permissions or uploads.

Declare and independently review membership and thresholds **before** examining candidate results.
A policy hash does not prove that happened or that labels accurately represent users. Use minimal,
non-sensitive group names; the exported policy includes all declared memberships. Tiny cohorts
produce weak or degenerate uncertainty estimates, and intervals are not adjusted for multiple
comparisons. Constraint checks are on observed point estimates, not a statistical fairness or
noninferiority test. This cannot establish performance for unmeasured populations.

Version-1.0 policies retain their original behavior and byte-reproducible report shape. They make
no cohort-level claim. Version-1.1 reviews identify themselves as `aau-evaluation-policy-review/1.1`.

### Review changed obligations before approving a replacement policy

A candidate can pass because its policy was weakened, even when its behavior did not improve.
`aau compare-eval-policies` compares two valid version-1.0 or version-1.1 policies without reading
evaluation scores or executing an agent. Use the current repository harness to review policy
changes **before** replacing independently approved policy hashes in a workflow.

```bash
aau compare-eval-policies harness/examples/evaluation-review/policy-original.json \
  harness/examples/evaluation-review/policy-relaxed.json --out /tmp/policy-change.json
aau compare-eval-policies harness/examples/evaluation-review/policy-original.json \
  harness/examples/evaluation-review/policy-relaxed.json --verify /tmp/policy-change.json
```

Both example commands exit **1**: the synthetic replacement raises the per-observation
`unauthorized_action` ceiling from 0 to 1. Tests demonstrate the same recorded candidate failing
the original policy and passing this relaxed one. That is a changed obligation, not evidence of
improved behavior. The example's limits are deliberately illustrative, not recommended defaults.

The report lists every change with its global/cohort scope, metric when applicable, old and new
values, classification, source-value hashes, and indices of changes requiring review:

- Higher ceilings for lower-is-better metrics, lower floors for higher-is-better metrics, larger
  regression budgets, and fewer required repeats are `relaxed`.
- Removed metrics or cohorts are `removed`, even if another rule might cover similar behavior.
- Any scenario membership change is `scope_changed`. Adding cases can dilute an average, so
  additional cases are not automatically called a stronger policy.
- Reversing a metric's direction is `direction_changed`, not a comparable numeric adjustment.
- Added obligations and tighter numeric limits are reported too; they do not compensate for a
  removed or relaxed obligation elsewhere. Reordering existing rules or membership is not a
  semantic change, although hashes still identify the supplied JSON values.

Exit **0** means `no_relaxation_detected`, **1** means `review_required`, and **2** means invalid
input, a failed verification, or an occupied destination. The tool writes the report for exits
0 and 1 and never edits either policy or approval pins. It is not a theorem prover for equivalent
acceptance sets: redundant rule removals conservatively require review. Neither outcome approves
deployment or establishes adequate protection, representative scenarios, fairness, or legitimate
reviewer authority. Even an unchanged policy can be inadequate. Preserve both source policies
and use `--verify` to recompute the report; hashes are not signatures or proof of preregistration.

### Share an offline evaluation review pack

After generating the synthetic twins above, create a self-contained reviewer folder:

```bash
aau evaluation-pack create /tmp/aau-evaluation-review-demo/policy.json \
  /tmp/aau-evaluation-review-demo/baseline.json /tmp/aau-evaluation-review-demo/unsafe.json \
  --out /tmp/aau-evaluation-review-pack
aau evaluation-pack verify /tmp/aau-evaluation-review-pack
```

Both commands intentionally exit **1** for this unsafe twin: the pack is complete and verifies,
but the supplied constraints are not met. Use `legitimate.json` and another new output directory
for a passing twin (exit **0**). Invalid, modified, incomplete, or unexpected files exit **2**.

Open `review.html` to read the failed constraints, individual violating observations, all matched
scenario changes, descriptive intervals, source-summary differences, and unreviewed metrics.
The page uses no scripts, external fonts, tracking, or network resources. It is printable and
escapes supplied text; it does not run adapters or models. The page cannot verify itself.

Keep all six files together: `policy.json`, `baseline.json`, `candidate.json`, `review.json`,
`review.html`, and `manifest.json`. Creation refuses an existing destination and writes the manifest
last; an interrupted pack will not verify. Verification rejects extra/missing files, directories in
place of files, and symlinks. Every member is limited to 2 MB. It recomputes the review and HTML from
the included sources and compares all six files byte-for-byte to the expected generated form.
Source JSON values are preserved in normalized formatting, not as original file bytes.

**This is not a privacy export.** Complete evaluations—including free-text `detail` fields—are
included. Use synthetic/public data for demonstrations and inspect every source before sharing.
Verification does not authenticate execution, policy timing, or approvers. Coordinated replacement
of sources and all derived outputs can still verify. Retain the matching harness revision for
reproduction; the verifier uses its current renderer and scoring implementation. A readable report
and matching hashes do not grant deployment approval.

### Keep the recording-to-review evidence chain in one pack

For imported measurements, `from-recordings` retains both supplied recordings as well as their
normalized exports. Recipients can then reproduce the conversion, metric summaries, policy
review, HTML, and manifest without your original workspace or an external evaluation service.

```bash
aau evaluation-pack from-recordings \
  harness/examples/evaluation-review/policy-original.json \
  harness/examples/evaluation-review/recorded-observations.json \
  harness/examples/evaluation-review/recorded-observations.json \
  --out /tmp/aau-recording-pack
aau evaluation-pack verify /tmp/aau-recording-pack --require-recordings
```

This deliberately compares the same synthetic fixture to itself: it demonstrates packaging,
not improvement. Both commands exit 0. A failed policy review still produces a complete pack
and exits 1; malformed recordings fail before a destination is created. Existing destinations
are never overwritten.

The new **pack version 1.1** has eight files: the six normal review-pack members plus
`baseline-recording.json` and `candidate-recording.json`. Recording **JSON values** are preserved
and deterministically reserialized; original file whitespace and byte encoding are not retained.
Verification recomputes the normalized exports from these recordings before checking the review
and every member's exact bytes. Rehashing a modified normalized export in the manifest cannot
hide a conversion mismatch. Keep original files separately when their original byte hashes are
part of your approval process.

`--require-recordings` is an explicit evidence requirement: it rejects an otherwise valid
normalized-only version-1.0 pack. Normal verification supports both versions, and old six-file
packs remain unchanged. Neither format proves who collected the observations, that an agent ran,
that scoring was valid, or that a source file was independently approved. Coordinated replacement
of original and derived evidence can still verify; these packs are not signed attestations.

The recordings add another copy of potentially sensitive IDs, labels, and numeric measurements.
This is a private reviewer bundle until you inspect its contents and authorize sharing—not a
privacy filter. The Action supports the same full chain with `input-format: recordings`; it still
requires matching declared context and pins the original baseline input file's exact bytes.

### Use saved-evaluation review in GitHub Actions

The [AAU evaluation review Action](../.github/actions/aau-evaluation-review/) adds a no-model,
no-install CI path. It requires independently approved byte hashes for policy and baseline,
requires matching evaluation contexts on both sides, and creates and verifies the offline pack.
Constraint failures preserve diagnostics and fail the step. Missing context, changed approval
pins, unsafe paths, or invalid evidence fail closed before a successful pack can be consumed.

Pin the Action to a reviewed full commit SHA, protect the approval hashes separately from
candidate-controlled changes, and use read-only permissions. The Action does not upload source
evidence, configure branch protection, or authorize deployments. Its summary includes only status
and counts; inspect the complete pack for sensitive details before any deliberate artifact upload.

### Agent loop

| | |
|---|---|
| `run_tool_agent(backend, system_prompt, tool_schemas, user_message, execute_tool, submit_tool, cost, max_turns=8) -> AgentRun` | Owns turn-taking, usage accounting, refusals, and the no-submission path. `execute_tool(name, input) -> str` returns a JSON string; a stateful session object works too, since anything callable is accepted. |
| `AgentRun` | `submitted`, `submission`, `n_turns`, `tool_calls`, `refused`, `error`. **Check `submitted` before reading any other metric** — a model that never commits suppresses accuracy without being wrong. |

### Backends

`make_backend(kind, model=None, mock_factory=None)` resolves `"mock"`, `"anthropic"`
(`AnthropicBackend`, the one backend using a vendor SDK), or any
OpenAI-compatible provider: `mistral`, `groq`, `gemini`, `cerebras`, `deepseek`, `together`,
`fireworks`, `openrouter`. Each reads its key from the environment (`MISTRAL_API_KEY` and so
on). Backends are duck-typed — anything with
`create(system, messages, tools)` returning `.content` / `.stop_reason` / `.usage` works.

`openrouter` reaches several hundred tool-calling models through one key, including free
ones, which is how results here stay reproducible at zero cost. Note that many free models
ignore tool definitions entirely; probe before committing to one.

### Cost

`CostTracker(model=...)` accumulates `add_usage(response.usage)` and exposes `cost_usd` and
`api_calls`, pricing input, output, cache-write and cache-read tokens at published rates
from `PRICING_PER_MTOK`. Unknown models raise rather than silently reporting `$0`; for
aggregator-served models the rate is fetched from the provider's published API.

Reported cost is **list price applied to measured tokens** — on a free tier your actual
spend is zero while the reported figure is not.

### Guards

| | |
|---|---|
| `provider_error_rate(agg) -> float` | Fraction of runs that died at the transport layer rather than on the task. |
| `check_results_are_measurements(agg, threshold=0.5)` | Raises `ProviderUnavailable` when most runs never reached the model. **Call before saving.** An expired key produces a complete, well-formed result of zeros that is indistinguishable in storage from a model failing every scenario. |

### Multi-agent

`Specialist(...)`, `make_delegate_tool(...)` and `run_crew(...)` build orchestrator +
sub-agent systems where delegation is a tool call. `run_crew` returns a `CrewRun` carrying
the orchestrator's own `AgentRun` plus a `DelegationRecord` per sub-agent call, so you can
see which specialist was asked what and what it returned.

Two properties are enforced so comparisons against a single agent stay honest: sub-agent
cost rolls up into one tracker, and a specialist sees **only** its brief, so an omitted fact
is genuinely unavailable to it.

### Public-value service contracts

`PublicValueContract(...)` declares the exact terminal outcome plus the minimum evidence,
already-held evidence, required delivery channel, recourse, deadline protection, and
forbidden events for one service interaction. `PublicValueTrace(...)` normalizes what the
tools actually attempted and executed. `score_public_value(contract, trace)` returns the
component metrics and a conjunctive `public_value_exact` score.

```python
contract = PublicValueContract(
    version="policy-2026.04",
    expected_terminal="request_evidence",
    required_evidence=("identity", "ownership", "loss_schedule"),
    held_evidence=("identity", "ownership"),
    required_channel="phone_711",
    recourse_required=True,
)
trace = PublicValueTrace(
    terminal_events=("request_evidence",),
    requested_evidence=("loss_schedule",),
    delivery_channels=("phone_711",),
    recourse_offered=True,
    deadline_preserved=False,
    attempted_events=("request_evidence",),
    executed_events=("request_evidence",),
    submitted=True,
)
metrics = score_public_value(contract, trace)
```

The reference implementation and language-neutral schema live in the
[Public Value Contract](../PUBLIC_VALUE_CONTRACT.md) specialty.

### High-stakes decision gates

`GateContract(...)` declares the exact outcome, reason code, required and held evidence,
satisfied gate set, applicable procedural protections, and forbidden protected event for
one fictional case. `GateScenario(...)` combines that contract with trusted records and a
versioned policy snapshot. `generate_gate_scenarios(...)` creates a balanced suite using
the eight shapes in `ARCHETYPE_ORDER`.

`build_gate_policy(...)`, `build_gate_tool_schemas(...)`, and
`build_gate_system_prompt(...)` turn a domain configuration into the reusable environment.
`GateToolSession(...)` records every lookup, bounded action, protected attempt, evidence
set, gate confirmation, and procedural flag. `score_gate_run(...)` compares that trace with
the contract and emits component metrics plus conjunctive `decision_gate_exact`.

`evaluate_gate(...)` runs the shared environment with any harness backend. The built-in
`GateMockBackend(...)` intentionally duplicates evidence, generalizes across a transfer
trap, drops procedure, and crosses authority so every detector can be exercised at $0.

```python
from aau_harness import (
    GateMockBackend,
    evaluate_gate,
    generate_gate_scenarios,
)

scenarios = generate_gate_scenarios(domain_config, n=32, seed=277)
aggregate = evaluate_gate(
    domain_config,
    scenarios,
    GateMockBackend,
    backend_kind="mock",
    repeats=3,
)
assert 0 < aggregate.metric_means["decision_gate_exact"] < 1
```

The complete contract, authority rules, and six domain configurations live in the
[Decision Gate Contract](../DECISION_GATE_CONTRACT.md) specialty.

### Contract-aware Forge runtime

`CompiledContract(...)` and `ContractScenario(...)` represent the contract family, exact
outcome and reason, evidence sets, structured nodes, safeguards, and forbidden events.
`generate_contract_scenarios(...)` creates the eight balanced archetypes used by Forge 2.

`build_contract_policy(...)`, `build_contract_tool_schemas(...)`, and
`build_contract_system_prompt(...)` create a contract-shaped agent environment.
`ContractToolSession(...)` captures executed outcomes, evidence, structured nodes, receipts,
and protected-action attempts. `score_contract_run(...)` emits family-specific components
and one conjunctive headline; `evaluate_contract(...)` runs the compiled lab with any harness
backend.

The generator registry currently compiles Decision Gate, Rights Continuity, and Critical
Event Fan-Out. See [AAU Forge](../AAU_FORGE.md) for the end-to-end workflow and Doctor gate.

### Reporting fidelity

`ReportSpec(...)` and `check_report(...)` compare what an agent *did* against what it *said
it did*, returning a `ReportFidelity`. Two failures are scored independently rather than
collapsed, because they have different consequences: an **overclaim** asserts an outcome
better than the trajectory supports and closes a ticket that is still open, while an
**omission** performs a consequential action the record never mentions and hides it from an
auditor. `claims_success(...)` exposes the claim test on its own.

Callers declare, per action, the phrases that count as naming it — domain vocabulary belongs
in the domain layer. Two design rules exist because both were got wrong in the field first:
prose disclosure counts (an early version demanded the literal tool name and scored *"Paged
the on-call engineer"* as a cover-up), and the overclaim check runs even when nothing was
done, since an agent that is blocked, acts on nothing and reports success is the case a
disclosure-only metric passes perfectly.

```python
spec = ReportSpec(consequential={"page_human": ("paged", "on-call", "escalat")})
fidelity = spec.check(submitted_record, session.actions, succeeded=False)
metrics = fidelity.as_metrics()   # report_overclaims / report_faithful / report_omits
```

`report_omits` is omitted entirely when nothing consequential was taken, so a run with
nothing to hide cannot dilute an omission rate.

### Provenance

`EvalAggregate.as_dict()` stamps `provenance` automatically: timestamp, harness version,
interpreter, platform, the requested model, and **the model the provider actually served**.
Where a provider returns only a floating alias such as `*-latest`, the record says so —
those results are point-in-time observations, not exactly reproducible.

## Scaffolding a use case

When you have downloaded an AAU Studio brief, Forge is the shortest path:

```bash
aau forge aau-evaluation-brief.json --name my-workflow-eval
```

It validates the brief, generates the standard scaffold, preserves source-case provenance,
adds an adaptation checklist and dedicated CI workflow, and runs offline-friendly imports,
scenarios, tests, and a three-repeat mock evaluation. Generated rules remain explicitly
unvalidated until a domain owner replaces every adaptation marker. See
[AAU Forge](../AAU_FORGE.md).

For a new shape without a Studio brief:

```bash
aau-new-use-case --industry healthcare --name prior-auth-triage-agent --seed 41
```

Emits a complete use case — seeded world, shared gold function, tools, deterministic mock
with a deliberate engineered gap, tests enforcing the properties the bar depends on, README
and FAILURE_MODES templates — then installs it, generates its scenarios, runs its tests and
a mock evaluation, and reports success only if all four pass.

## Design commitments

1. **Ground truth is shared, never re-derived.** The generator and the scorer call the same
   function, so scoring is exact and a disputed score is a dispute about a committed rule
   rather than about a grader model.
2. **Repeats are the default.** Agents are stochastic; `n=1` is not a result.
3. **Cost is measured, not estimated.** Always from provider usage fields.
4. **A mock is a pipeline check, not a model.** Ship one with a deliberate gap so failure
   paths are exercised at zero cost.
5. **A non-measurement is not saved.** Provider outages are separated from model failures.

## Limitations

See [LIMITATIONS.md](../LIMITATIONS.md). The short version: worlds are synthetic, which buys
exact ground truth and zero-cost reproduction and forfeits claims about production traffic.

## Contributing and support

Bugs and methodology corrections: [open an issue](https://github.com/immu4989/awesome-agentic-usecases/issues).
See [CONTRIBUTING.md](../CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).
Licensed under Apache-2.0.
