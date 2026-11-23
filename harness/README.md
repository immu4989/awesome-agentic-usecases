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

## Prepare an offline installation kit

For approved restricted-network review environments, prepare a local **Python 3.11+ installation kit**
from a trusted checkout and its audited wheel/source archive. This is an explicit preparation and
installation workflow, not a public package release, an installer that runs itself, or an ATO.
The ordinary package still supports Python 3.10; this narrower kit deliberately does not bundle
its `tomli` dependency, development extras, provider SDKs, Python, pip, venv, or OS dependencies.

On the preparation machine, from the reviewed repository root:

```bash
# Preparation needs approved build tooling; this step may use an index.
python -m pip install build==1.3.0 setuptools==80.9.0 packaging
python -m build --no-isolation --outdir /tmp/aau-offline-dist harness
python harness/tools/build_offline_kit.py \
  /tmp/aau-offline-dist/aau_harness-1.6.0.tar.gz \
  /tmp/aau-offline-dist/aau_harness-1.6.0-py3-none-any.whl --out /tmp/aau-offline-kit
```

Use new directories and the actual filenames emitted by the build. The example version reflects
current repository metadata; **the version string alone does not identify this checkout build**.
The builder does not fetch, install, extract, or execute either artifact. It first runs the existing
source/sdist/wheel content audit, checks the pure-Python profile and dependency declaration, and
refuses a changed runtime dependency profile rather than creating an incomplete `--no-deps` kit.

The nine-file kit retains:

- Original wheel in `wheels/` and original source archive in `source/`.
- `package-audit.json` and `expected-runtime.json`, binding the first-party source inventory.
- `requirements.lock`, pinning the exact wheel SHA-256, not just its version.
- A standalone, standard-library-only `verify_offline_kit.py`.
- The repository `LICENSE`, `README.md` with receiver instructions, and `manifest.json`.

The builder prints **two hashes**, for the verifier script and manifest. Send them through an
independently approved channel; neither this tool nor a file inside the kit establishes that trust.
Before executing a transferred verifier, compare its hash with a trusted OS hashing tool and the
independently retained expected value. Also independently check the manifest hash. Do not execute
an untrusted kit's script merely to ask that script whether it can be trusted.

After approval, from the kit folder:

```bash
python verify_offline_kit.py . --manifest-sha256 APPROVED_MANIFEST_SHA256
```

Exit **0** verifies the exact inventory, pinned bytes, lock-to-wheel binding, and audit/runtime
receipt consistency; **2** rejects. This standalone verifier does not rerun the archive/source audit
against an absent checkout and does not install anything. It rejects extras, missing files, links,
special files, oversized members, changed pins, and inconsistent receipts. Individual text/JSON
members are limited to 2 MB and each artifact to 20 MB. Source archives are never extracted by it.

Choose a **fresh approved virtual environment outside the kit** with Python 3.11+ and pip available.
Select/activate that environment's interpreter, then follow the kit's installation commands:

```bash
python -m pip --isolated install --no-index --no-deps --only-binary=:all: --require-hashes --disable-pip-version-check --find-links wheels -r requirements.lock
python -m pip check
python -m aau_harness.catalog_cli runtime-info --out ../installed-runtime.json
python verify_offline_kit.py . --manifest-sha256 APPROVED_MANIFEST_SHA256 --runtime ../installed-runtime.json
python -m aau_harness.catalog_cli inspect-review demo --out ../offline-review-example
```

Output paths must be new and outside the kit. A fresh environment matters: an already-installed
different checkout may share the same version string. The runtime comparison detects a mismatching
**supplied first-party source receipt**, not malicious code that forges a receipt, interpreter/dependency
integrity, previously loaded code, or authentic execution. Preserve independent approval and host controls.
No index or dependency resolution is used by the install command; do not drop its flags to bypass a failure.

The resulting synthetic handoffs should verify with exits **1 / 0 / 1** for unsafe, repaired, and
unknown-budget examples. Their guide supplies demo-only pins. This observes local mechanism behavior,
not a real agency trial, independent reproduction, security certification, or measured public benefit.

Maintainers can explicitly test the complete path before transfer:

```bash
python harness/tools/smoke_offline_kit.py \
  /tmp/aau-offline-dist/aau_harness-1.6.0.tar.gz \
  /tmp/aau-offline-dist/aau_harness-1.6.0-py3-none-any.whl
```

Unlike preparation/verification, this smoke test **installs and executes the audited local wheel**
in a temporary fresh environment. It checks import location, `pip check`, the installed source
receipt, expected synthetic outcomes, and rejected changed pins/receipts. CI now exercises this
path. It is a no-index installation test, not an OS-enforced air-gap attestation or proof of all-platform
compatibility. No kit is automatically uploaded, released, or published to PyPI.

Research checked November 19, 2026: pip documents [wheelhouses for repeatable installation](https://pip.pypa.io/en/stable/topics/repeatable-installs/)
and [hash-checked, binary-only installation](https://pip.pypa.io/en/stable/topics/secure-installs/).
[NIST's SSDF overview](https://csrc.nist.gov/projects/ssdf) describes software-protection practices;
this kit supports a narrow integrity/installation workflow, not SSDF conformance or a substitute
for vulnerability review, producer verification, organizational approvals, or interpreter trust.

## Reuse Promptfoo exports without confusing failed assertions with execution errors

`aau promptfoo-eval` reads a bounded subset of native **version-3 OutputFile JSON exports**
without installing Promptfoo, running assertions, loading provider code, or contacting a model.
The first compatibility regression retains an unchanged upstream export whose metadata declares
Promptfoo `0.118.10`; see its [source, byte hash, and license](tests/fixtures/promptfoo/README.md).
This is one observed fixture, not all-version compatibility or an independent reproduction.

```bash
aau promptfoo-eval demo --out /tmp/aau-promptfoo-example
```

The no-key demo is explicitly constructed. Its selected column has high quality scores, a failed
authorization assertion, and a missing authorization measurement. A different passing column cannot
replace it. The README explains expected results and two rejected inputs: a missing row and an
execution error in the unselected column. All source rows remain in the retained original file.

For a real export, a receiving reviewer writes and approves a mapping such as:

```json
{
  "plan_version": "aau-promptfoo-observation-plan/1.0",
  "source_label": "Supplied export; scoring and provenance require separate review",
  "test_map": [
    {"test_index": 0, "scenario_id": "routing"},
    {"test_index": 1, "scenario_id": "delegation"}
  ],
  "columns": [
    {"prompt_index": 0, "prompt_id": "actual-export-prompt-id", "provider_id": "actual-export-provider-id"}
  ],
  "selected_prompt_index": 0,
  "metrics": {
    "quality": {"field": "score"},
    "passed": {"field": "success"},
    "authorization": {"field": "namedScores", "name": "authorization"}
  }
}
```

Use the actual complete test and column inventories, not these placeholder IDs. Column indices are
contiguous and zero-based; test indices may be noncontiguous. Every test/column pair must occur exactly
once, even in unselected columns. Limits are 500 tests, 20 columns, 100 metric mappings, and 2 MB per
input/output file. Keep the approved plan's SHA-256 independently of the supplier delivery:

```bash
aau promptfoo-eval create plan.json results.json --plan-sha256 APPROVED_PLAN_SHA256 --out converted
aau promptfoo-eval verify converted --plan-sha256 APPROVED_PLAN_SHA256
aau promptfoo-eval verify converted --plan-sha256 APPROVED_PLAN_SHA256 --evaluation downstream-evaluation.json
```

The six-file packet retains exact `source.json` and `plan.json` bytes, plus `recording.json`,
`evaluation.json`, `conversion.json`, and `manifest.json`. Verification recomputes the packet and
can compare a downstream evaluation to it. Exit **0** means faithful conversion, **not passing scores**;
**2** rejects unsupported/invalid evidence. Destinations must be new; extra members and links are rejected.
The report exposes the selected/unprojected columns, original row pointers, source outcome counts,
metric mappings, coverage, and unmapped named scores. The recording feeds the existing policy-review
workflow. This conversion packet alone is not a receiver-pinned policy handoff or an acceptance gate.

Important boundaries:

- `failureReason=1` is a failed assertion, which can legitimately have `error` text. It remains a
  scored failure when its grading result agrees. Category 2 execution errors, unknown/ambiguous
  categories, provider-response errors, and inconsistent success/grading states are rejected.
- Only single-repeat exports are supported. Declared repeat settings other than 1, nonzero repeat
  markers, and duplicate test/column pairs are rejected; attempts are never guessed, merged, or averaged.
- `success` is explicitly mapped to 1/0. Numeric `score` and explicitly named `namedScores` values
  are copied as supplied; missing/null named scores remain absent. Boolean/nonnumeric scores are rejected.
- Aggregate metrics are not copied. Missing costs, latency, API-call counts, and context fingerprints
  are not inferred from provider names or embedded config. Scorer validity, hidden edits, task
  comparability, and external attempt history remain outside this bounded importer.
- Original logs can contain credentials, personal information, or sensitive transcripts. The packet
  is **not sanitized or authorized for sharing**. No embedded URL, attachment, trace, assertion, or
  provider is executed/fetched. Approve the source and mappings through the receiving team's process.

Research checked November 19, 2026: Promptfoo's [CI/CD export contract](https://www.promptfoo.dev/docs/integrations/ci-cd/)
describes the native envelope; pinned upstream types and failure categories are linked with the fixture.
NIST's [AI RMF Measure playbook](https://airc.nist.gov/airmf-resources/playbook/measure/) emphasizes
documenting metrics, tests, and measurement limits. Our inference is to preserve native source evidence
and explicit mappings instead of relying on aggregate success claims. This does not establish AI RMF
conformance, government adoption, or operational benefit.

## Received an evidence folder? Start with one intake command

**Reviewing reports with a keyboard or a narrow viewport?** The policy/diagnostic/budget, candidate
matrix, reference-label, condition-coverage, and Inspect-diagnostic reports now share named scroll
groups, explicit row/column headers, and visible focus. Policy reports have section-navigation links.
Use Tab to reach a table and arrow keys to scroll; native disclosure headings open with Enter/Space.
The [reproducible browser checks and manual-test checklist](browser-tests/README.md) explain the tested
scope and remaining limitations. These improvements are not a WCAG/Section 508 conformance claim.

`aau inspect-pack` recognizes 12 supported recorded-evidence pack families and calls the
existing **full verifier** for the recognized format. It does not trust a manifest hash or a
stored success label as the result. This lets a receiving team inspect a complete folder without
first choosing among several conversion, handoff, scoring, or diagnostic commands.

```bash
# These synthetic walkthroughs need no keys or repository fixtures at runtime.
aau evaluation-demo --out /tmp/intake-example
aau inspect-pack /tmp/intake-example/repaired --expect evaluation-review
# Intentionally exits 1: complete, valid evidence of failed supplied requirements.
aau inspect-pack /tmp/intake-example/intermittent --expect evaluation-review
```

Default output is a compact JSON inspection containing the verified profile, separate assessment
kind and outcome, file count, copied-byte inventory hashes, and the specific verification command.
It excludes source labels and findings, but hashes can still enable linkage: this is **not a
privacy-approved export**. Read the full evidence and limitations after verifying them.

To require a complete source handoff and its candidate operating-budget gate:

```bash
aau retry-demo --out /tmp/intake-retry-example
aau inspect-pack /tmp/intake-retry-example/repaired --expect retry-review --require-budget \
  --out /tmp/intake-inspection.json
aau inspect-pack /tmp/intake-retry-example/repaired --expect retry-review --require-budget \
  --verify /tmp/intake-inspection.json
```

Keep the saved inspection **outside** the input folder; inserting a report would change its exact
file set. Existing reports are not overwritten. `--verify` recomputes the report using the same
independently selected requirements and a fresh bounded copy of the supplied pack.

| Exit | Meaning |
|---|---|
| **0** | Full verification succeeded and applicable supplied policy/service checks passed, **or** the artifact is explicitly non-decision evidence |
| **1** | Full verification succeeded, but policy/service requirements failed or the candidate budget remains unverified |
| **2** | Invalid, unsupported, incomplete, changed, unreadable, oversized, or unexpected evidence; no verified inspection is produced |

Always inspect `assessment.kind` and `assessment.status`. A CSV/retry/OTLP conversion is
`not_assessed`, a challenge has `adapter_responses_not_supplied`, and a failure-bound report is
`diagnostic_not_a_gate` even when conditional limits are exceeded. None becomes a passed policy
by exiting 0. A label-minimized reproducer with a failed service observation exits **1 here**,
even though its dedicated creation/verification command exits 0 for a valid reproduction.
Unknown budget evidence cannot become a pass. Policy and candidate-budget outcomes remain separate.

| `--expect` profile | What the full verifier recomputes |
|---|---|
| `evaluation-review` | Policy, optional retained recordings, diagnostics, HTML, and optional candidate budget |
| `csv-review` | Both original CSV exports and mappings through the complete review |
| `retry-review` | Both full retry ledgers and accounting plans through the review |
| `otlp-review` | Both raw OTLP exports and mappings through retries and review |
| `service-review` | Both normalized trace sources and shared obligations through the review |
| `csv-source` | Original CSV-to-recording/evaluation conversion only |
| `retry-source` | Declared whole-task retry accounting only |
| `otlp-source` | Original trace projection and nested retry accounting only |
| `service-traces` | Every supplied service trace against its separate contract |
| `service-challenge` | Constructed public probes and separate expected results, **not** adapter responses |
| `service-reproducer` | The minimized profile and scoring evidence, **not** its relationship to private originals |
| `failure-bounds` | Conditional bounds or withheld inference, not a deployment decision |

Supported versions are the review-pack 1.0/1.1/2.0/3.0 profiles, each handoff's 1.0/1.1 profiles,
and the listed source/challenge/reproducer/failure-bound 1.0 profiles. Other artifact types,
standalone JSON reports, archives, demo-parent folders, and unknown future versions are rejected,
not guessed or unpacked. Use the relevant dedicated tool for other repository artifacts.

`--expect` prevents substitution of a different valid pack family. `--require-budget` requires
a supported review profile with the budget layer; conversions and diagnostic-only packs cannot
satisfy it. No policy pins, recording/diagnostic requirements, or independent CI approval checks
are replaced. The returned specific command retains `--require-budget` when that layer is present.

Verification is scoped to the folder you supplied. A failed parent never falls back to its valid
nested `review/`. Explicitly inspecting only that nested review cannot establish a relationship
to omitted original sources; require the full expected handoff and retain the whole folder.
Reviewers must independently choose the expected format, approved inputs, and required layers.

The command copies bounded regular files into a temporary local directory, invokes only trusted
installed verifiers on that copy, and removes the copy afterward. It rejects symbolic links,
special files, unexpected members (including empty directories), over 64 files, over 15 nested
directories, directory depth over three, and members over 2 MB. Total copied bytes are capped at
128 MB. The copy is **not an atomic capture of a live changing directory**; hashes identify the
bytes inspected, not future source contents. Temporary copying is not secure erasure.

No supplied code, adapter, manifest-selected module, subprocess, or network request is executed.
HTML, CSV, and raw traces are not opened automatically. The report's command is a fixed argument
list with a `PATH_TO_PACK` placeholder, never a command copied from untrusted evidence.
Use a matching trusted harness version; invalidity can reflect a version mismatch, not misconduct.
Integrity is not proof of authentic execution, independently approved requirements, valid scoring,
population effectiveness, signatures, safe deployment, or permission to share.

This approach addresses the documentation and human-review concerns in the
[NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/); it is not NIST certification
or framework compliance. Requires this checkout or a locally built wheel, not published PyPI 1.6.0.

## Check delivered evidence against a receiving-team request

A fully verified pack can still use a different baseline or a more permissive policy than the
receiving team selected. `aau review-intake` adds a separate, byte-pinned request: exact pack
profile, version, source format, and every required control input. It runs the complete native
verification first, then reports which receiving-team requirements are met. A valid but wrong
pack remains visible as failed intake evidence; invalid evidence never becomes a verified report.

Try three constructed contrasts from a repository clone:

```bash
pip install -e harness
python harness/examples/evaluation-review/intake_request.py --out /tmp/intake-request-example
```

Read the generated `README.txt` for exact replay commands. The repaired fixture meets its request;
the unchanged failing fixture matches the pins but fails the policy; the relaxed-policy fixture
passes its own policy but fails the receiver's policy pin. All inputs, costs, and observations are
synthetic. The demonstration's locally computed request hash is plumbing, **not independent approval**.

For a real handoff, the receiving team must independently select and review the controls before
trusting the delivery. This example request requires a diagnostic recording review:

```json
{
  "request_version": "aau-evidence-intake-request/1.0",
  "profile": "evaluation-review",
  "pack_version": "aau-evaluation-review-pack/2.0",
  "input_format": "recordings",
  "pinned_inputs": {
    "policy": "REPLACE_WITH_64_LOWERCASE_HEX_DIGITS",
    "baseline": "REPLACE_WITH_64_LOWERCASE_HEX_DIGITS",
    "diagnostics": "REPLACE_WITH_64_LOWERCASE_HEX_DIGITS"
  }
}
```

Replace every placeholder with SHA-256 of the **exact exported member bytes** selected during
review. For this profile they are `policy.json`, `baseline-recording.json`, and `diagnostics.json`.
Prepare those exported bytes with the matching trusted harness from independently reviewed inputs;
do not accept whichever controls arrive in the candidate pack. JSON export may change formatting,
so these pins are neither canonical JSON hashes nor necessarily hashes of original pre-export files.
After reviewing the complete request, protect its expected raw-file SHA-256 separately from delivery.
Whitespace edits invalidate the request pin. Do not recompute the expected approval pin from a
candidate-controlled request in the production intake job.

```bash
# APPROVED_INTAKE_REQUEST_SHA256 must come from a separately controlled review process.
aau review-intake approved-request.json delivered-pack \
  --request-sha256 "$APPROVED_INTAKE_REQUEST_SHA256" --out intake-review.json
aau review-intake approved-request.json delivered-pack \
  --request-sha256 "$APPROVED_INTAKE_REQUEST_SHA256" --verify intake-review.json
```

| Requested profile | Required pinned control inputs |
|---|---|
| `evaluation-review` | Policy and baseline; diagnostics for 2.0/3.0; operating budget for 3.0 |
| `csv-review` | Policy, original baseline CSV, both import plans, diagnostics; budget for 1.1 |
| `retry-review` | Policy, baseline ledger, both accounting plans, diagnostics; budget for 1.1 |
| `otlp-review` | Policy, raw baseline OTLP export, both mappings, diagnostics; budget for 1.1 |
| `service-review` | Policy, baseline traces, both import plans, one shared service suite, diagnostics; budget for 1.1 |

Request role keys are `policy`, `baseline`, `diagnostics`, `operating_budget`, `baseline_plan`,
`candidate_plan`, and `service_suite`, only where listed above. All and only the roles required for
the chosen version must appear. The shared suite pin checks **both** exported suite members.
Handoff policy/diagnostics/budget members live under `review/`; baseline sources and plans live
under `baseline/`; the candidate plan lives under `candidate/`. OTLP plans are `mapping.json`,
other plans are `plan.json`; sources are `source.csv`, `ledger.json`, `source.otlp`, or `traces.json`.
No arbitrary member paths or candidate-observation pin are accepted.

The evaluation pack accepts 1.0 with `evaluations`, 1.1 with `recordings`, and 2.0/3.0 with either.
For `evaluations`, the baseline member is `baseline.json`. The four full handoffs accept 1.0/1.1
and source formats `csv`, `retry-ledger`, `otlp`, and `service-traces`, respectively. Exact version
strings are `aau-evaluation-review-pack/VERSION` or
`aau-{csv,retry,otlp,service}-evaluation-handoff-pack/VERSION` (choose one family, not literal braces).
Converters, service-only scorings, challenges, and diagnostics cannot substitute for review evidence.

Exit **0** means all request constraints were met, **1** means complete verified evidence did not
meet them, and **2** means an invalid request/pin, invalid evidence, or failed report verification.
Both sides must declare matching valid benchmark context. Legacy context absence therefore fails
this intake gate even when the descriptive native review passes. Candidate observations may change;
they must still satisfy the pinned policy and any required candidate budget. Missing budget
measurements stay unverified, never passing. No requirements or approval settings are updated.

Reports retain every control-input check, failed requirement, and the complete compact inspection.
Save them outside the exact-member pack; existing output is never overwritten. A second bounded
capture must match the inspected byte inventory, but this is **not an atomic snapshot** of a live
directory. Retain the request, complete pack, and report, and reverify using a matching trusted harness.
No model, adapter, command, upload, or network request is run. Hashes may still disclose information.

This supports explicit evaluation requirements, a need discussed in
[GAO's April 2026 AI acquisitions report](https://files.gao.gov/reports/GAO-26-107859/index.html).
It does not establish reviewer identity, authority, independently approved requirements, signatures,
source authenticity, valid scoring, procurement compliance, or deployment approval. Control of both
the request and its expected hash defeats the boundary. The separate
[GitHub Action's original-input pins](../.github/actions/aau-evaluation-review/README.md) and workflow
protections are unchanged and not replaced. Requires this checkout or its local wheel; not included
in the currently documented PyPI 1.6.0 release.

## Preserve failed and missing checkpoints across an evidence history

A latest passing review does not explain what happened at earlier checkpoints. `aau review-series`
checks an **explicitly ordered census of 2–10 checkpoints** against one fixed, separately pinned
receiving-team request. It retains every failure and gap; it does not roll the baseline forward,
average away a failure, silently change controls, or use the latest green pack as the whole history.

```bash
pip install -e harness
python harness/examples/evaluation-review/evidence_series.py --out /tmp/evidence-series-example
```

The generated guide contains replay commands for five constructed histories. Every latest
checkpoint passes, but only `all-met` has no earlier issue. `later-met` retains a policy failure,
`missing` retains a gap, `invalid` retains an unverifiable checkpoint, and `changed-policy`
retains a substituted policy that passed its own native review. These are synthetic observations,
not service monitoring results. Their repeated identical packs are explicitly disclosed.

Define the ordered census independently, using exactly this plan shape:

```json
{
  "plan_version": "aau-evidence-series-plan/1.0",
  "checkpoint_ids": ["before-update", "after-update", "follow-up"]
}
```

Checkpoint IDs are unique lowercase directory names matching `[a-z][a-z0-9_-]{0,63}`; reserved
device names such as `con` and `lpt1` are rejected. Array order is authoritative, not alphabetical
order, timestamps, repeat IDs, or file modification time. Keep the common request from
[receiving-team intake](#check-delivered-evidence-against-a-receiving-team-request) and both controls
outside the evidence root:

```text
approved-plan.json
approved-request.json
history/
  before-update/  (one complete supported review pack)
  after-update/   (one complete supported review pack, or absent and explicitly reported missing)
  follow-up/      (one complete supported review pack)
```

Independently review and protect **both raw-file hashes**. The plan pin protects the declared
census and order; the common request pin protects the baseline, profile/version/format, policy,
plans/mappings, diagnostics, shared service suite, and any required operating budget. Candidate
observations may change, but the reviewer-selected controls may not change silently. Do not
compute expected approval hashes from candidate-controlled files in the production job.

```bash
aau review-series approved-plan.json approved-request.json history \
  --plan-sha256 "$APPROVED_SERIES_PLAN_SHA256" \
  --request-sha256 "$APPROVED_INTAKE_REQUEST_SHA256" --out history-review.json
aau review-series approved-plan.json approved-request.json history \
  --plan-sha256 "$APPROVED_SERIES_PLAN_SHA256" \
  --request-sha256 "$APPROVED_INTAKE_REQUEST_SHA256" --verify history-review.json
```

| Outcome | Exit | What is retained |
|---|---|---|
| `series_constraints_met` | 0 | Every planned checkpoint fully verifies and meets the common request |
| `series_constraints_not_met` | 1 | Every checkpoint verifies, but at least one fails the request—even if the latest passes |
| `series_evidence_missing` | 1 | At least one planned checkpoint is absent; all supplied valid failures remain visible |
| `series_not_fully_verified` | 2 | At least one supplied checkpoint is invalid; its diagnostic row and all other outcomes remain visible |

Invalid evidence takes precedence over missing evidence, which takes precedence over valid failed
requirements; separate counts retain all categories. An invalid checkpoint has **no verified intake
attached**. Exit 2 can therefore accompany a saved diagnostic history report: it does not mean all
packs verified. Bad control files/pins, an unsafe or absent root, unexpected root members, changing
root membership, oversized reports, and output errors instead reject the operation without a new
report. Expected checkpoint files, symbolic links, and special files are invalid, not missing.

Every supplied pack receives full native source-to-output verification and every request check.
A later pass never clears `historical_issue_checkpoint_ids`. Adjacent transitions describe changed
requirement outcomes, **not necessarily changed agent performance**; missing or invalid checkpoints
break that comparison. `latest_checkpoint` always names the final planned checkpoint, even when
it is missing or invalid. The report never falls back to an earlier green one.

Identical retained pack inventories are grouped explicitly, but not declared to be independent
new runs. Even different hashes cannot prove independent executions. No pooled success rate,
statistical trend, or weighted score is calculated. There are no authenticated timestamps or
cadence: this cannot establish freshness, uptime, elapsed duration, or time-to-repair. Review only
the declared scope; this is not an append-only log or proof that no external incidents were omitted.
Changing that scope requires independently reviewed replacement controls, not automatic trimming.

Save reports outside `history/`; existing reports are never overwritten. Filling a gap or changing
evidence invalidates replay of the old report; preserve it and create a new one. The root admits only
planned members and its membership is checked before and after review. Each checkpoint inherits
the bounded intake limits, including at most 64 files and 128 MB of captured bytes. At most ten
packs are processed sequentially; the composed JSON report is limited to 2 MB. Checkpoints are
individually captured, **not an atomic snapshot of a live history**. Retain both controls, all complete
packs, and reports with a matching trusted harness. Supplied IDs and hashes may disclose information.

The approach supports documented risk tracking discussed in
[NIST AI RMF MEASURE 3.1](https://airc.nist.gov/airmf-resources/playbook/measure/) and
[MANAGE 4.1–4.3](https://airc.nist.gov/airmf-resources/playbook/manage/). It is an offline evidence
review, not a scheduler, production monitor, incident closure, recovery proof, or deployment/
compliance approval. It neither executes supplied code nor uploads data. Independent governance,
real measurements, affected-user feedback, and investigation remain necessary. Requires the current
checkout or local wheel, not the currently documented PyPI 1.6.0 release.

## Publish pinned evidence reviews to CI test dashboards

`aau review-ci` performs the complete [receiving-team intake](#check-delivered-evidence-against-a-receiving-team-request)
or [ordered-history review](#preserve-failed-and-missing-checkpoints-across-an-evidence-history), then writes
**JUnit XML, JSON, and Markdown** for existing review workflows. It accepts original controls and complete
source packs, **not a supplied report that could claim a favorable result**. This command needs the current
trusted checkout or a locally built wheel; the documented public PyPI 1.6.0 release does not contain it.
No hosted CI account, adapter, model execution, or network access is needed to produce the files.

Try six constructed contrasts first:

```bash
python harness/examples/evaluation-review/ci_reporting.py --out /tmp/aau-ci-reporting
```

Read the generated `README.txt` and `reports/*/summary.md`. The examples cover a met request,
failed policy, unknown cost, substituted policy, invalid pack, and an ordered history with both an
earlier failure and missing checkpoint despite a passing latest checkpoint. These are synthetic
fixtures, not observed production outcomes. Every bundle is replayed and its XML parsed locally.

For real evidence, independently review and protect the exact request/plan byte hashes. Do not
calculate an expected approval pin from candidate-controlled files in the same job. The pins do
not authenticate reviewer identity or authority. Use a reviewed immutable harness build, trusted
job code, and a fresh isolated workspace; this does not change your branch protections or approvals.

```bash
aau review-ci intake approved-request.json delivered-pack \
  --request-sha256 "$APPROVED_REQUEST_SHA256" --out ci-evidence
aau review-ci intake approved-request.json delivered-pack \
  --request-sha256 "$APPROVED_REQUEST_SHA256" --verify ci-evidence

aau review-ci series approved-plan.json approved-request.json history \
  --plan-sha256 "$APPROVED_PLAN_SHA256" --request-sha256 "$APPROVED_REQUEST_SHA256" \
  --out ci-history
aau review-ci series approved-plan.json approved-request.json history \
  --plan-sha256 "$APPROVED_PLAN_SHA256" --request-sha256 "$APPROVED_REQUEST_SHA256" \
  --verify ci-history
```

The output directory must be new and outside the supplied evidence root. Its exact four members are:

| File | Role |
|---|---|
| `report.json` | Every presented check and full native review; original checkpoint IDs and hashes remain |
| `junit.xml` | Unique ordinal checkpoint/check names, separate failures and errors, no fabricated timings |
| `summary.md` | Ordinal checkpoint counts, native status/exit, and limitations |
| `manifest.json` | File-byte hashes for this presentation, not source authentication |

**The full sources are not copied into this presentation bundle.** Retain the request, any plan,
all complete packs, and matching trusted implementation. `--verify` repeats native verification and
compares every generated byte and the exact member set; changing a manifest hash cannot bless an
edited report. Links, special files, extra members/directories, and members over 2 MB are rejected.
The native bounded-capture limits still apply. This is not an atomic snapshot of changing directories.

JUnit counts are **mechanical review checks**, not independent samples, scenarios, model runs, or
evidence of production effectiveness. Related checks may describe the same underlying problem.
Known mismatches become `failure`; unknown budgets, unavailable context/control checks, missing
checkpoints, and invalid evidence become `error`, never `skipped`. Policy and budget checks remain
separate so a known policy failure cannot hide an unknown budget. Fixed names avoid copying source
labels into XML/Markdown; they are not anonymization. JSON keeps original review identifiers/hashes,
and even ordinal outcomes disclose review structure. Review artifact access rules before uploading.

**Preserve the native CLI exit:** 0 means all request/history requirements met; 1 means valid
non-passing or missing evidence; 2 means invalid evidence, controls, or output. An unknown budget
is a JUnit error but native exit 1. Valid controls plus an invalid single pack produce an error-only
diagnostic bundle and exit 2; invalid checkpoints in a valid history remain visible alongside other
results. Invalid controls or invalid/unexpected history-root membership produce no new bundle.
Invalid source bytes have no verified inventory: replaying the same error diagnostic **does not
prove the original invalid bytes are unchanged**. Retain those sources separately for investigation.
Neither an error-free dashboard nor exit 0 is deployment or compliance approval.

### Opt-in GitLab recipe

[GitLab accepts JUnit reports but does not use them to set job status](https://docs.gitlab.com/ci/testing/unit_test_reports/).
Keep the command's nonzero exit and retain the report on failure. With a trusted harness already
installed and reviewed inputs present in a fresh job workspace:

```yaml
evidence_review:
  script:
    - aau review-ci intake approved-request.json delivered-pack --request-sha256 "$APPROVED_REQUEST_SHA256" --out ci-evidence
  artifacts:
    when: always
    reports:
      junit: ci-evidence/junit.xml
```

Do not add `allow_failure: true` or suppress errors with `|| true`. This snippet publishes only XML,
not the complete evidence or JSON. Retain those privately under your organization's access and
retention policy. A missing report must not turn a failed command into a successful job.

### Opt-in Azure Pipelines recipe

[PublishTestResults@2 supports JUnit and explicit failure/missing-file settings](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-test-results-v2?view=azure-pipelines).
Keep the review step failing when appropriate; run the reporting step after success or failure:

```yaml
steps:
  - bash: |
      aau review-ci intake approved-request.json delivered-pack --request-sha256 "$APPROVED_REQUEST_SHA256" --out ci-evidence
    env:
      APPROVED_REQUEST_SHA256: $(APPROVED_REQUEST_SHA256)
  - task: PublishTestResults@2
    condition: succeededOrFailed()
    inputs:
      testResultsFormat: JUnit
      testResultsFiles: ci-evidence/junit.xml
      failTaskOnFailedTests: true
      failTaskOnFailureToPublishResults: true
      failTaskOnMissingResultsFile: true
      publishRunAttachments: false
```

These are opt-in integration recipes based on provider documentation, **not a claim of a hosted
GitLab/Azure run**. Local tests cover XML structure, unique test names, counts, every supported review
family, negative/unknown outcomes, source replay, and an isolated installed wheel. Providers differ
in presentation and may compare ordinal test names between jobs: such comparisons do not establish
matching plans, populations, authentic chronology, or improvement. Consult the original pinned review.

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

### Score recorded service traces against separate contracts

`aau service-trace-eval` recomputes public-service scores from normalized recorded events and
separately supplied service contracts. Unlike the score importers below, it does not accept
caller-supplied scores or per-observation contract overrides. It uses the existing
[public-value scorer](../PUBLIC_VALUE_CONTRACT.md), retaining completion, document burden,
channel access, recourse, deadline, continuity, and forbidden-action findings.

Install the current checkout with `python -m pip install -e harness`; this command is not in
the previously published PyPI 1.6.0 release. Run the synthetic example from the repository root
with an unused destination:

```bash
python harness/examples/evaluation-review/service_traces.py --out /tmp/aau-service-traces
aau service-trace-eval verify /tmp/aau-service-traces/baseline \
  --evaluation /tmp/aau-service-traces/burden-review/baseline.json
aau service-trace-eval verify /tmp/aau-service-traces/burden \
  --evaluation /tmp/aau-service-traces/burden-review/candidate.json
aau evaluation-pack verify /tmp/aau-service-traces/burden-review \
  --require-diagnostics --require-budget
```

Run the verification commands separately: their expected exits are **0, 1, 1**. A valid failed
scoring pack exits 1 and retains all evidence; malformed inputs or failed verification exit 2.
Open `burden-review/review.html` and `repaired-review/review.html` inside the generated folder.
Both candidates record 100% completion, but one of four burden-candidate observations requests
already-held evidence twice and an out-of-contract password, uses the wrong channel, and omits
required recourse. Joint success is 75%, not 100%. The same synthetic $0.40 costs about $0.133
per passing observation, above the illustrative $0.12 budget. The repaired fixture is constructed,
not an observed production repair; no real service, person, billing, or model is involved.

For your own inputs:

```bash
aau service-trace-eval create plan.json suite.json traces.json --out new-source-pack
aau service-trace-eval verify new-source-pack --evaluation downstream-review/candidate.json
```

The plan has exactly `plan_version: "aau-service-trace-import/1.0"`, a nonblank `source_label`,
and integer `n_repeats`. The suite uses `aau-public-value-suite/1.0` and separate
`{case_id, contract}` entries. Trace format `aau-public-value-traces/1.0` accepts existing
`{case_id, trace}` observations with exactly one planned repeat. Format
`aau-public-value-traces/1.1` requires an explicit zero-based `repeat` and optionally accepts
`cost_usd`, `latency_s`, and `n_api_calls`. Every declared case/repeat must appear exactly once;
missing observations, duplicates, unknown cases, and extra fields are rejected. At most 500
total observations are allowed. Omitted operating measurements remain unknown, not zero.

Each pack retains seven files: `plan.json`, `suite.json`, `traces.json`, `scoring.json`,
`recording.json`, `evaluation.json`, and `manifest.json`. Verification recomputes every member,
rejects extra/missing files and symlinks, and optionally binds the downstream evaluation.
Inputs and expanded output members are bounded to 2 MB; findings are never truncated.
Retain both source packs alongside a baseline/candidate dossier and verify both bindings.
The normalized evaluation's generic `imported_unverified_observations` label remains unchanged;
the separate `scoring.json` records the preceding trace-to-score computation.

Context fingerprints bind supplied contracts and nine installed first-party scoring-source
files, so changed requirements or scoring code cannot silently compare as the same context.
They do not authenticate execution or cover the interpreter/dependency closure. Verification
requires matching scorer bytes; retain the trusted checkout or wheel used to create the pack.
Inapplicable protections score as satisfied, not performed: `required_protection_coverage`
separately counts required, satisfied-required, and not-required observations.

Contracts remain service-owner declarations, not inferred law or independently approved policy;
trace flags and events are supplied assertions, not authenticated logs. Review and approve your
own requirements independently. Complete declared coverage does not prove complete external
activity or population representativeness. Retention preserves JSON values, not original file
bytes, and does not sanitize personal data. Coordinated replacement of all inputs can produce a
new internally consistent pack. No legal compliance, eligibility, public benefit, or deployment
approval follows from passing these checks.

### Gate a complete service-trace handoff with approved obligations

`aau service-review` carries both normalized trace sources, one common contract suite, all
scoring findings, and the policy/diagnostic review in one **30-file** folder, or **33 files**
with the candidate operating-budget gate. One command recomputes the complete chain; separately
valid but unrelated source or review folders cannot substitute for that chain.

This is a **strict service profile**, not another generic score importer. The global policy
must require `public_value_exact` in direction `higher` with `candidate_observation_limit: 1`.
Diagnostic criteria and any operating-budget criteria must also include
`{"metric": "public_value_exact", "direction": "higher", "limit": 1}`. Additional constraints
are allowed. Missing, weaker, reversed, or subgroup-only requirements are rejected **before
output creation**; supplied policy files are never silently rewritten. Every candidate
observation must therefore satisfy all applicable declared obligations. A stronger average,
lower cost, or a passing completion-only score cannot compensate for a failed obligation.
Baseline failures remain visible and do not prohibit demonstrating a passing candidate.

From the repository root, build four complete synthetic handoffs:

```bash
python harness/examples/evaluation-review/service_traces.py --handoffs --out /tmp/aau-service-handoffs
aau service-review verify /tmp/aau-service-handoffs/burden --require-budget
aau service-review verify /tmp/aau-service-handoffs/slow --require-budget
aau service-review verify /tmp/aau-service-handoffs/unknown --require-budget
aau service-review verify /tmp/aau-service-handoffs/repaired --require-budget
```

Run verification commands separately; expected exits are **1, 1, 1, 0**. The examples distinguish
failed service obligations despite completion, satisfied obligations with excessive latency,
satisfied obligations with unknown cost, and a constructed passing fixture. Each folder's
`review/review.html` shows independent policy/budget outcomes and the combined verdict.
Inspect `candidate/scoring.json` for exact obligation findings and required-only protection
coverage. These are arithmetic fixtures, not recommended thresholds or observed improvements.

Create your own handoff from already recorded normalized traces:

```bash
aau service-review create policy.json suite.json baseline-plan.json baseline-traces.json \
  candidate-plan.json candidate-traces.json --diagnostics diagnostics.json \
  --operating-budget budget.json --out new-service-handoff
aau service-review verify new-service-handoff --require-budget
```

Both source packs retain the **same** suite values. Import plans declare collection labels and
repeat counts, not per-source requirements or score overrides. Scoring context is recomputed
from contracts and installed scorer bytes. Full declared coverage, bounded regular files,
exact member sets, overwrite refusal, and source-to-report bindings are checked. Verification
requires matching scoring code. The optional budget must pass independently, and missing
required measurements cannot pass. Omit the budget option only for an intentionally ungated
operating review; require `--require-budget` downstream if its presence is mandatory.

The [GitHub Action service mode](../.github/actions/aau-evaluation-review/README.md#gate-recorded-service-traces-against-one-approved-contract-suite)
adds independent byte pins for the common suite, baseline trace source, both import plans,
policy, and diagnostics; a budget adds a seventh pin. Pin the Action's reviewed full commit
separately and protect the workflow and approval variables. Do not compute approval pins from
candidate changes. No branch protection, repository permissions, or approval settings are changed.

The design addresses the documented-test-set/metric/tool traceability concern in
[NIST AI RMF Playbook MEASURE 2.1](https://airc.nist.gov/airmf-resources/playbook/measure/);
this is a design motivation, not an implementation or certification of that framework.
Independent contract adequacy, authentic trace capture, applicability, population validity,
and production effectiveness remain outside these checks. All source values are unsanitized;
hashes do not authenticate them, and coordinated replacement can still verify offline.
No legal compliance, actual public benefit, or deployment approval is inferred.
Requires the current checkout or a locally built wheel, not the published PyPI 1.6.0 package.

### Explain changed service contracts before replacing approval pins

`aau compare-service-contracts` reviews the requirements behind a score. It compares two valid
`aau-public-value-suite/1.0` suites and optionally applies both to **one identical, complete
recorded trace collection** using the same current scorer. This is a requirement-change
diagnostic—not a baseline/candidate agent evaluation and not a replacement for approval.

```bash
# Structural changes only, including added and removed cases:
aau compare-service-contracts approved-suite.json proposed-suite.json --out contract-changes.json
# Identical case census: inspect what the proposed requirements do to frozen traces:
aau compare-service-contracts approved-suite.json proposed-suite.json \
  --plan frozen-plan.json --traces frozen-traces.json --out frozen-review.json
aau compare-service-contracts approved-suite.json proposed-suite.json \
  --plan frozen-plan.json --traces frozen-traces.json --verify frozen-review.json
```

Exit **1** means contract changes request review—even if the same traces now satisfy more
requirements. Exit **0** means no enumerated contract changes, **not** that the service passed,
requirements are adequate, or a replacement is approved. Exit **2** means invalid inputs or
failed verification. Valid changed reports remain available; existing output files are not
overwritten. Run expected nonzero commands separately, not as an all-success shell chain.

The report identifies all added/removed cases, version labels, terminal expectations, delivery
channels, protection flags, evidence requirements, held-evidence assertions, and prohibitions.
It shows exact added/removed list items and derived required-but-not-held request sets. Changing
channels or document declarations is not automatically stronger, weaker, or less burdensome.
All edits request review, including added protections and metadata-only version changes.

Try four controlled synthetic examples:

```bash
python harness/examples/evaluation-review/service_contract_changes.py --out /tmp/aau-contract-changes
```

| Only the contract changes; traces stay fixed | Jointly satisfied observations, before → after | Interpretation |
|---|---:|---|
| Required recourse becomes optional | 1/2 → 2/2 | A protection stopped being required, not newly delivered |
| A recorded prohibited action is removed from the forbidden set | 1/2 → 2/2 | The same recorded action is assessed under a different prohibition |
| A required document is newly declared already held | 1/2 → 2/2 | A changed evidence assertion removes a request obligation; acquisition is unverified |
| Continuity protection becomes required | 2/2 → 1/2 | An additional obligation is unsatisfied; the agent did not change |

Each example retains both suites, plan, frozen traces, and `review.json`. Follow its root
`README.txt` to recompute. Per-observation before/after assessments, failed obligations, changed
metrics, all four joint-satisfaction transition counts, and required-only protection counts
remain in the report. Counts are observations, not independent users or population estimates.

With frozen traces, `--plan` and `--traces` are required together. They use the service-trace
bridge's existing single/repeated formats and complete coverage checks (at most 500 total
observations). Rescoring requires **identical case IDs on both suites**; it never drops a removed
failure or selects a favorable intersection. For changed case censuses, omit both probe options
and inspect the complete structural change report instead. Requirements that no supplied trace
exercises still request review even when all resulting scores stay identical.

Case ordering and set-like contract-list ordering are ignored for change classification.
Omitted optional `continuity_preservation_required` is normalized to false. Original input-value
hashes remain distinct where appropriate; a no-change result never overrides independently
pinned bytes or the normal context-mismatch guard. Rescoring intentionally inspects changed
contexts; ordinary score comparison and strict service-review behavior are unchanged.

Reports bind both suite values, optional frozen inputs, and ten listed first-party implementation
files. Inputs and reports are limited to 2 MB each; changes and findings are never truncated.
Keep original inputs alongside the report and use the matching trusted scorer for verification.
This is not a self-contained source pack, raw-byte archive, authenticated execution record, or
dependency/interpreter attestation. Full findings and labels are **unsanitized**.

The design is informed by the governance, performance, and monitoring concerns in
[GAO's AI Accountability Framework](https://www.gao.gov/products/gao-21-519sp), not a claim of
GAO validation or framework compliance. Domain owners must independently assess changed
requirements and evidence assertions. No legality, true applicability, actual document receipt,
real-world benefit, or net policy strength is inferred. No approval pins or workflow settings
are changed. Requires the current checkout or a locally built wheel, not published PyPI 1.6.0.

### Test your service-scoring adapter against constructed obligations

`aau service-challenge` generates clean controls and targeted violations from your declared
`aau-public-value-suite/1.0` contracts. It checks a **scoring implementation**, not an agent's
ability to perform real work. Expected component scores are constructed explicitly, without
calling the reference scorer. Every contract gets a clean control so rejecting everything
cannot pass; negative probes expose accepting everything and individual missing checks.

```bash
aau service-challenge create public-value-review/examples/suite.json --out /tmp/service-challenge
aau service-challenge verify /tmp/service-challenge
```

Give your checker **only `challenge.json`**, not `oracle.json`. Each public case contains a
`probe_id` and `input` with `contract` and `trace`. Return every probe exactly once, with all ten
binary numeric metrics documented in the pack's `README.txt`. Compute `challenge_sha256` from
the public JSON values with `aau_harness.agent_bom.digest`. Write responses outside the pack:

```json
{
  "response_version": "aau-service-challenge-responses/1.0",
  "challenge_sha256": "CANONICAL_PUBLIC_CHALLENGE_SHA256",
  "observations": [
    {"probe_id": "ID_FROM_CHALLENGE", "error_code": "checker-unavailable"}
  ]
}
```

Replace each error row with `{"probe_id": "...", "metrics": {...}}` when scored; error and
metrics fields cannot coexist. Errors remain explicit failures of conformance, not invented
zero service scores. Missing, repeated, unknown, or extra probe IDs are invalid. Booleans,
fractions, omitted component scores, and substituted challenge identifiers are rejected.

To exercise the interface with AAU's own reference scorer, run this **self-check only**:

```python
from pathlib import Path
from aau_harness.agent_bom import digest, load_json, write_json
from aau_harness.public_value_review import assess_public_value

challenge = load_json(Path('/tmp/service-challenge/challenge.json'))
responses = {
    'response_version': 'aau-service-challenge-responses/1.0',
    'challenge_sha256': digest(challenge),
    'observations': [
        {'probe_id': row['probe_id'], 'metrics': assess_public_value(
            row['input']['contract'], row['input']['trace'])['metrics']}
        for row in challenge['cases']
    ],
}
write_json(responses, Path('/tmp/service-responses.json'))
```

Replace `assess_public_value` with your own trusted scoring implementation to test that adapter.
No command here executes an arbitrary adapter, contacts an endpoint, or provides a sandbox.
The reference self-check is not independent validation. Never copy the expected oracle scores.

```bash
aau service-challenge score /tmp/service-challenge /tmp/service-responses.json --out /tmp/service-review.json
aau service-challenge score /tmp/service-challenge /tmp/service-responses.json --verify /tmp/service-review.json
```

Scoring exits **0** only when every supplied metric matches every generated expectation,
**1** for retained mismatches or explicit adapter errors, and **2** for invalid evidence or
failed verification. Creation/pack verification exiting 0 means the pack is valid, not that a
checker passed. Reports retain component-level missed failures and false failures, clean-control
outcomes, and all probe results. A failed joint score cannot conceal an incorrect component score.

A fully applicable contract yields 14 probes: a clean control, non-submission, wrong/multiple
terminals, wrong delivery channel, outside/missing/duplicate/already-held evidence requests,
missing recourse/deadline/continuity protection, and prohibited attempts/executions. Inapplicable
families are listed as **not generated**, never silently counted as passed. Optional protections
stay optional. Only one representative label per applicable family is varied, not every label or
combination. A required terminal that is also forbidden is rejected rather than relaxed.

The exact five-file pack retains the original suite values, public challenge, separate expected
results and coverage, instructions, and unsigned hashes. Verification regenerates every file;
rehashing a modified oracle is insufficient. Inputs, members, and reports are bounded to 2 MB,
with at most 2,000 generated probes. Expansion beyond trace-format limits is rejected before
writing; nothing is truncated. Existing destinations are not overwritten.

This is an input separation, **not a blind benchmark or access control**: public contracts and
generation patterns can reveal answers. Probes are not sampled users, and a passing checker is
not evidence of authentic service execution, adequate requirements, legal compliance, or deployment
readiness. Hashes do not authenticate evidence, and coordinated replacement can still verify.
Listed implementation fingerprints do not cover dependencies or the interpreter. All values are
unsanitized; use synthetic/public inputs and review before sharing. Normal service-review and
approval gates remain unchanged. Requires this checkout or a locally built wheel, not PyPI 1.6.0.

### Prepare a label-minimized service reproducer for disclosure review

Service packs retain exact supplied label values. A case ID, event name, document label, or
source description can therefore expose information a team did not intend to share with a
vendor, maintainer, or reviewer. `aau service-reproducer` creates a **label-minimized reproducer**
while checking that every supplied service-scoring result survives the transformation.
It is **not anonymization, privacy certification, or approval to publish**.

Try the synthetic example without credentials:

```bash
python harness/examples/evaluation-review/service_reproducer.py --out /tmp/service-reproducer
aau service-reproducer verify /tmp/service-reproducer
# The nested service still fails its recourse obligation: this command intentionally exits 1.
aau service-trace-eval verify /tmp/service-reproducer/service
```

The ten-file folder contains a normal seven-file `service/` scoring pack, `reproduction.json`,
`README.txt`, and a root manifest. Both synthetic cases remain; the missing required recourse
still fails, and optional recourse remains optional. A valid reproducer is not a successful
service interaction. For your own already-normalized service inputs:

```bash
aau service-reproducer create private-plan.json private-suite.json private-traces.json --out new-reproducer
aau service-reproducer verify new-reproducer
# Owner-side only; originals stay local and are not copied into the reproducer:
aau service-reproducer verify-source new-reproducer private-plan.json private-suite.json private-traces.json
```

All three commands exit **0** for a valid reproducer, including one containing service failures;
**2** rejects invalid evidence, failed preservation, overwritten destinations, or changed files.
Use `aau service-trace-eval verify new-reproducer/service` separately for its usual service
pass/fail exit codes. No command uploads data, executes a service, or authorizes disclosure.

| Replaced or removed | Retained for reproducing the scorer |
|---|---|
| Original case IDs and source description | Complete declared case/repeat census, including non-submission and failures |
| Original contract version, event, evidence, and channel labels | Per-case event/evidence/channel equality across roles, order, and repetitions |
| Cost, latency, and API-call measurements | Absence of operating evidence, never invented zero measurements |
| Original-input hashes and any identity mapping | Hashes of minimized outputs and exact recomputed obligation findings |

Aliases are deterministic per-case ordinals, separately scoped to events, evidence, and channels.
Expected, forbidden, attempted, executed, and terminal event roles share one event mapping;
required, held, and requested evidence share one evidence mapping. Repeated requests, extra
terminal/channel events, and blocked attempts cannot disappear through set conversion.
Cross-case/cross-namespace label identity and domain meaning are intentionally not retained.
Contract list order is preserved; trace rows are joined by exact original case and repeat, not
array position. Optional continuity flags receive the existing false default.

The generator validates the **entire original input** before transforming it. Unknown fields,
missing cases/repeats, invalid measurements, and contract overrides are rejected, not stripped
into acceptable evidence. It recomputes every original and transformed component metric, not
just average or joint success, and checks required-protection counts before writing anything.
Normal source limits apply: 1–500 complete case/repeat observations and 2 MB per input/output
member, with no truncation. Original files are never rewritten or deleted.

Verification requires a fixed point of the minimization profile plus exact recomputation of all
ten files. An ordinary unsanitized service pack cannot pass merely by being placed inside the
folder or rehashed. The verifier without originals proves **only the exported profile and its
internal evidence**. It cannot prove correspondence to an original source. Owner-side
`verify-source` reproduces the transformation, but deliberately does not prove exact source
identity: changed private names, version labels, or removed operating values can yield the same
export. No reversible map or private-input hash is emitted; hashing labels would still expose
guessable identifiers. Unsigned coordinated replacement of a complete pack can still verify.

**Residual disclosure risk remains.** Counts, rare combinations of flags, order, repetitions,
and outcomes may disclose sensitive facts or enable linkage using other data. There is no
differential privacy, re-identification risk estimate, or domain/legal applicability assessment.
Before sharing, independently review the full folder, recipients, linkage risks, and applicable
permissions; prefer an independent synthetic example when disclosure is inappropriate. Do not
treat aliases as secret tokens or replace original approval pins with a matching score.

[NIST SP 800-188](https://csrc.nist.gov/pubs/sp/800/188/final) distinguishes masking from adequate
de-identification and calls for disclosure-risk and sharing-model decisions. That motivates these
explicit limitations; this feature does not implement or certify NIST de-identification guidance.
It is a scorer-debugging aid, not evidence of authentic execution, real-world benefit, original
context equivalence, or deployment readiness. Requires this checkout or a locally built wheel,
not the published PyPI 1.6.0 package.

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

### Hand off Inspect logs through a receiver-pinned policy review

`aau inspect-review` connects two original Inspect JSON logs to the existing AAU policy,
repeatability, operating diagnostics, and optional budget gate in **one fully recomputable folder**.
The receiving team controls one independently retained request-byte hash covering all control inputs,
including the exact baseline-source hash. A supplier cannot change a mapping, weaken the policy,
substitute the baseline, or remove a required budget while keeping that same request pin.

From a reviewed current checkout/local wheel, not the older public PyPI release:

```bash
aau inspect-review demo --out /tmp/my-inspect-review
```

Open each `review/review.html`; read the demo guide for exact replay commands and demo-only pins.
The examples are constructed, not real service or model evaluations:

| Handoff | What changes | Outcome / verify exit |
|---|---|---|
| `unsafe` | Completion improves, but one authorization score fails | `constraints_not_met` / 1 |
| `repaired` | Both declared score obligations are met | `constraints_met` / 0 |
| `unknown-budget` | Same repaired scores; the request additionally requires a cost budget | `constraints_not_verified` / 1 |

The first two share the identical request. Adding a budget changes the request pin. Missing costs
never become zero. **Context remains unavailable in all three**, including the met policy: this
checks supplied score constraints, not comparable execution, correct scoring, or deployment readiness.

#### Receiving-team request

Use `repaired/request.json` as an editable example, then independently review and retain its hash
before evaluating a delivery. The closed `aau-inspect-review-request/1.0` object has exactly:

| Field | Contract |
|---|---|
| `request_version` | `aau-inspect-review-request/1.0` |
| `baseline_source_sha256` | SHA-256 of exact baseline JSON bytes, including whitespace/BOM; lowercase 64-digit hex |
| `baseline_plan`, `candidate_plan` | Complete [Inspect mapping plans](#reuse-inspect-sample-scores-without-executing-the-log); no inferred labels, components, or identities |
| `policy` | Complete existing evaluation-review policy, including any declared cohorts |
| `diagnostics` | Explicit existing diagnostic plan with joint criteria, draw sizes, and cost-basis declarations |
| `operating_budget` | Complete existing operating-budget plan, or explicit `null` if none is required |

The request embeds control objects. Exported nested mapping/policy/diagnostic files use the harness
renderer; they are not assumed to be copies of pre-existing original files. The complete request
and both source logs are retained **byte-for-byte**. The candidate source is deliberately not pinned
by the request: it must satisfy the requested review, rather than match one preselected result.

```bash
aau inspect-review create request.json baseline.json candidate.json \
  --request-sha256 "$RECEIVER_REQUEST_SHA256" --out /tmp/inspect-handoff
aau inspect-review verify /tmp/inspect-handoff --request-sha256 "$RECEIVER_REQUEST_SHA256"
```

Use new output paths. Keep the expected request hash outside supplier-controlled evidence; computing
it from the delivered request in the same review job defeats that boundary. A hash is not a signature,
identity check, proof of preregistration, authority, independent evaluation, or a protected holdout.

Exit **0** means the whole chain verifies and supplied policy plus any budget constraints are met;
**1** means the whole chain verifies but constraints are unmet/unverified; **2** means an invalid
input, incorrect pin, incomplete source, or replay failure. Never delete valid negative evidence
or fall back to an easier nested verification after the parent fails.

The handoff contains 29 files, or 32 when a budget is requested:

- `baseline/` and `candidate/`: complete six-file strict Inspect conversion packs, including raw logs.
- `review/`: the existing 13-file recording-based policy/diagnostic dossier; a budget adds three files.
- Root: original `request.json`, `handoff.json`, `README.txt`, and `manifest.json`.

Replay reparses both logs, reconstructs every nested recording/evaluation, and recomputes the policy,
diagnostics, any budget gate, HTML, reports, and manifests. Replacing a component with an individually
valid but unrelated pack fails, even after rehashing its inventory. Use the dedicated `inspect-review
verify` command: generic `inspect-pack`/`review-intake` do not route this profile. Nested verifiers
remain useful for diagnosis, but alone do not establish the full source/request relationship.

This retains the strict import subset: interrupted/edited/incomplete logs are not converted. Use
[Inspect evidence diagnostics](#review-incomplete-inspect-evidence-without-repairing-it) to preserve
their findings separately. The importer does not infer context, cost, latency, or API-call counts.
Consequently any requested operating-budget measure remains unverified with these sources. This
is intentional; do not remove the requirement or invent measurements to obtain a pass. The existing
policy machinery requires complete measurements for its selected metrics; missing required scores
are rejected rather than silently omitted from a denominator.

Each input and generated member is bounded to 2 MB, with exact directory/file inventories and
regular non-symlink files. No supplied task, scorer, model, subprocess, URL, or attachment is executed.
Raw logs may contain private transcripts or credentials; neither hashing nor verification sanitizes
them or grants permission to share. Use a matching trusted harness to replay the packet.

Research checked November 19, 2026: [GAO's AI acquisition review](https://files.gao.gov/reports/GAO-26-107859/index.html)
identifies requirements definition and ongoing evaluation as acquisition challenges.
[Inspect's log documentation](https://inspect.aisi.org.uk/eval-logs.html) distinguishes passive log
inspection from retry/rescoring workflows that execute supplied code. Our engineering inference is
to preserve the source-to-review chain under receiving-team control without rerunning the source.
This is not contract language, proof of burden reduction, GAO endorsement, government adoption,
compliance, or authorization. Study design, rubric quality, task comparability, and actual utility
still need independent/domain review.

### Review incomplete Inspect evidence without repairing it

An interrupted run or edited score is evidence to review, not a reason to quietly drop rows.
`aau inspect-eval diagnose` adds a **separate diagnostic packet** to the strict converter below.
It can retain finite version-2 JSON logs with `started`, `error`, or `cancelled` status, missing
samples, duplicate pairs, or recorded lifecycle/edit markers. It never emits `evaluation.json`
or changes the strict importer's acceptance rules.

From a reviewed current checkout/local wheel (not the older public PyPI release):

```bash
aau inspect-eval demo --out /tmp/my-inspect-diagnostic
```

Open `diagnostic/review.html` and read the generated guide. This extends the same Inspect demo:
the original conversion still works, while the new constructed interrupted source has five rows,
one missing planned pair, one duplicated pair, and one outside-plan row. It includes scored errors,
a retry, a limit, invalidation, and edits on an unmapped scorer. No real endpoint or model was run.

For authorized local evidence, use the same independently reviewed mapping plan as the converter:

```bash
aau inspect-eval diagnose plan.json source.json \
  --plan-sha256 "$APPROVED_INSPECT_PLAN_SHA256" --out /tmp/inspect-diagnostic
aau inspect-eval verify-diagnostic /tmp/inspect-diagnostic \
  --plan-sha256 "$APPROVED_INSPECT_PLAN_SHA256"
```

Use new paths. Exit **0** means no findings in this bounded diagnostic, **1** means a valid packet
requiring review, and **2** means invalid/unsupported input or failed replay. Exit 1 is expected for
the interrupted demo; do not chain it with `&&` as though it were corrupt. Zero performance scores
can have no diagnostic findings: neither exit 0 nor import eligibility means model quality passed.

Keep all five files: `plan.json`, `source.json`, `diagnostic.json`, `review.html`, `manifest.json`.
Input bytes are retained exactly. Verification recomputes every derived byte and rejects edits even
if their manifest hashes are updated. Use `verify-diagnostic`, not conversion `verify` or generic
`inspect-pack`. The packet is bound to the reviewed plan pin and matching trusted implementation;
no supplied module, task, metric, attachment, or URL is executed or fetched.

#### What the diagnostic keeps separate

| Evidence | Treatment |
|---|---|
| Every planned typed ID and one-based epoch | `missing`, `unique`, or `duplicate`, with every zero-based source-array position; integer `1` is not string `"1"` |
| Missing samples or a header-only JSON object | Explicitly unavailable rows, not invented failures or proof that execution never occurred |
| Duplicate records | No first/last/winning row selection; all positions and markers survive |
| Outside-plan IDs or epochs | Separate retained rows, never allowed to fill a planned hole |
| Errors, retry records, limits, invalidation | Independent presence markers with source JSON pointers; a score does not erase them |
| Score history/reason, including unmapped scorers | Visible pointers; no edit is automatically accepted or undone |
| Missing scorer/component, null value, explicitly absent label, unmapped label, invalid numeric/shape | Distinct mapped-metric states; none becomes zero |
| Current strict conversion eligibility | Checked separately with its first rejection reason; no conversion files written |

`row_marker_counts` counts rows carrying each marker (not a sum of scorer fields). Metric-state
counts describe **all supplied rows**, including duplicates and outside-plan rows; they are not
unique-attempt denominators, pass rates, or coverage estimates. No transcript, error message,
or score value is copied into the HTML, but raw source and identifying labels remain sensitive.
This is not a sanitized sharing format or permission to publish evidence.

Scope is bounded: the same closed mapping plan, at most 10,000 supplied rows and 10,000 planned
pairs, valid bounded typed IDs, integer epochs 1–10,000, finite duplicate-key-free JSON, and 2 MB
per input/output including expansion. Missing/null `samples` is distinguished from an empty list.
Unknown run status, malformed row identity, binary `.eval`, and non-finite JSON are rejected.
In particular, a JSON export containing literal `NaN` for an excluded score remains unsupported;
do not replace it with zero to force ingestion. Unrecognized fields stay in the raw source but
are not comprehensively interpreted. Selected lifecycle markers record presence, not validation
of their payloads. The converter's rejection reason and the diagnostic are not full Inspect
schema validation, exhaustive error analysis, complete retry lineage, or proof of source authenticity.

The offline HTML has captions, column headers, escaped text, and keyboard-focusable scrolling
tables, without scripts or remote assets. These features are not accessibility-conformance evidence.

Research checked November 19, 2026: Inspect's [error-handling guidance](https://inspect.aisi.org.uk/handling-errors.html)
distinguishes interrupted logs, retried errors, and scored errors; its [limits guidance](https://inspect.aisi.org.uk/setting-limits.html)
explains that limited samples can still be scored. Its [log documentation](https://inspect.aisi.org.uk/eval-logs.html)
describes score history and the trust boundary for retrying/rescoring supplied logs. The
[NIST AI RMF 1.0 Playbook MEASURE guidance](https://airc.nist.gov/airmf-resources/playbook/measure/)
motivates documented measurement scope and limitations, not a specific import protocol.
Our design inference is to retain those conditions separately and request human review—not repair
them into an apparently complete evaluation. This is not NIST certification or deployment approval.

### Reuse Inspect sample scores without executing the log

`aau inspect-eval` is an offline adapter for a **bounded subset of Inspect version-2 JSON logs**.
Use the current trusted checkout/local wheel, not the older published PyPI package. Inspect is
not a runtime dependency. This adapter reads recorded sample scores; it does not call Inspect,
rerun tasks, rescore answers, fetch attachments, or reproduce Inspect's aggregate metrics.

Start with a no-key, constructed example, including an intentionally rejected missing-row log:

```bash
aau inspect-eval demo --out /tmp/inspect-conversion-example
```

The generated `README.md` includes replay commands and a demo-only plan pin. Integer sample ID
`1` and string ID `"1"` remain separate cases. Both metrics report only three of four observations;
an unknown score is absent, not zero. This demo is constructed, not a model/Inspect run. Separately,
our [compatibility fixture](tests/fixtures/inspect-ai/README.md) retains an upstream mock-model
log declaring Inspect `0.3.100`, with only a documented final newline added. Both upstream and local
byte hashes are checked. One fixture does not establish compatibility with every release.

For an executable interoperability check, the separate [native Inspect producer exercise](compatibility/inspect/README.md)
runs pinned Inspect `0.3.291` with fixed mock-only tasks. It checks complete label/numeric score
projection, an official `.eval` round trip, rejection of interrupted results, and replay of the
retained diagnostic. CI runs it in a separate environment without inherited model credentials.
It is not a live-model evaluation or independent reproduction; Inspect is still not an AAU runtime
dependency. Read its filesystem, dependency-pinning, network-tripwire, and raw-log privacy limits
before running it.

For an authorized real workflow, obtain a full JSON export with a trusted Inspect installation's
`inspect log dump path/to/run.eval > source.json`, or use its native JSON log. Do not use a header-only
export. [Inspect's log documentation](https://inspect.aisi.org.uk/eval-logs.html) describes both
formats; `.eval` binary files are not accepted directly by this adapter. Never run `inspect score`
on untrusted logs as an import step: that is a separate execution workflow, not passive conversion.

Have the receiving team review and retain a plan independently from the supplier, for example:

```json
{
  "plan_version": "aau-inspect-observation-plan/1.0",
  "source_label": "Reviewed service-routing evaluation",
  "sample_map": [
    {"sample_id": 1, "scenario_id": "self-service"},
    {"sample_id": "1", "scenario_id": "assisted"}
  ],
  "n_repeats": 2,
  "metrics": {
    "completion": {
      "scorer": "match", "value_key": null, "encoding": "labels",
      "labels": {"C": 1, "I": 0, "N": null}
    },
    "authorization": {"scorer": "checks", "value_key": "authorized", "encoding": "number"}
  }
}
```

This label map is a reviewer choice, not an automatic interpretation of Inspect's conventions.
Different rubrics may need different meanings for `N`, partial credit, refusals, or other labels.
`value_key: null` selects a scalar score; a string selects exactly one key from an object-valued
score. There are no expressions, nested paths, reducers, unit conversions, or guessed encodings.
Numeric strings and booleans are not numeric scores. Unknown labels and incompatible value shapes
fail instead of defaulting to a favorable score. A null selected value or explicit null label mapping
stays missing. Missing scorers/keys also stay missing. At least one mapped measurement is required.

```bash
# Set APPROVED_INSPECT_PLAN_SHA256 to the receiving team's independently retained raw-file hash.
aau inspect-eval create plan.json source.json --plan-sha256 "$APPROVED_INSPECT_PLAN_SHA256" --out /tmp/inspect-evidence
aau inspect-eval verify /tmp/inspect-evidence --plan-sha256 "$APPROVED_INSPECT_PLAN_SHA256"
# Optional: check that a downstream review copied exactly this normalized evaluation.
aau inspect-eval verify /tmp/inspect-evidence --plan-sha256 "$APPROVED_INSPECT_PLAN_SHA256" --evaluation /path/to/review/candidate.json
```

Use new output paths. `create` and `verify` return `0` for a valid conversion, even with failing or
partially missing scores; `2` means invalid/unsupported input or a mismatching pack/pin. Neither is
a deployment approval. Do not derive the receiver's expected pin from an untrusted delivered pack.

The six-file pack retains `source.json` and `plan.json` **byte-for-byte**, plus `recording.json`,
`evaluation.json`, `conversion.json`, and a hash manifest. Verification captures regular non-symlink
files, requires the exact inventory, and recomputes every derived byte. The report includes the
declared Inspect version, raw hashes, explicit metric mapping, coverage, wholly unreported metrics,
and unmapped scorer names. The normalized evaluation uses AAU's existing summary/bootstrap method,
not Inspect's reported averages or epoch reducers. Check that this method fits your study design.

Supported subset and important boundaries:

- Exact planned sample IDs crossed with epochs `1..n_repeats`; epochs become AAU repeats `0..n-1`.
  At most 500 cases and 10,000 observations. No omitted, duplicated, extra, or synthesized pairs.
  Inspect's configured epoch count and recorded total/completed counts must match; selected dataset
  IDs and additional total/logged counts must match when present. Unset configured epochs means
  Inspect's default of one, never a count inferred from whichever rows survived.
- Only `status: success`, version `2`, full sample logs with declared package metadata. Success means
  execution finished, not policy passed. Error/cancelled/started logs, sample errors/retries/limits,
  invalidations, early stopping, merged shards, config/log edits, and score history/reasons are rejected.
  This deliberately also rejects legitimate edited logs or scores with refusal/custom reasons; it does
  not silently reinterpret them. Use the separate [evidence diagnostic](#review-incomplete-inspect-evidence-without-repairing-it)
  to retain selected error/edit markers and incomplete census findings without producing a converted evaluation.
- At most 100 distinct mapped score components; finite numeric values within ±10^15. Each input and
  generated member is limited to 2 MB. Duplicate JSON keys and all nonfinite values—including in
  otherwise unused fields—are rejected. Some valid Inspect logs use NaN sentinels and are outside
  this subset; do not replace NaN with zero to make an import pass.
- No inferred cost, latency, API-call counts, scoring/configuration fingerprints, population validity,
  or authenticity. This adapter does not validate the entire Inspect schema or endorse the grader.
  Unmapped data remains in the original log. A matching receiver plan still does not authenticate a run.
  Pinning a mapping does not bind the actual rubric/scorer implementation or detect its semantic drift;
  collect that evidence separately. Declared package metadata is not an execution attestation.
- **Not a sanitized artifact.** Full logs can contain transcripts, credentials, tool results, and
  private configuration. Keep evidence locally under applicable permissions; review before sharing.
  This pack uses its dedicated `inspect-eval verify` command, not the generic `inspect-pack` dispatcher.

Source-contract review: November 19, 2026, pinned
[Inspect log model](https://github.com/UKGovernmentBEIS/inspect_ai/blob/c574b6bf6674e6d5f6cbb0f95059d7427b23d54b/src/inspect_ai/log/_log.py).
Missing-score, aborted-run, type-ambiguous ID, epoch-census, score-edit, altered-plan, and tampered-pack
tests exercise failure boundaries. These are maintainer tests, not independent or government validation.

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

### Account for retries without hiding earlier costs or failures

`aau retry-eval` converts an explicit **sequential retry ledger** into one scored observation
per logical task (scenario + repeat), retaining the plan and every declared attempt. Use this
before operating reviews or policy/budget dossiers when your service retries work. Requires
the current checkout or a locally built wheel, not published PyPI 1.6.0.

```bash
pip install -e harness
aau retry-eval create harness/examples/evaluation-review/retry-plan.json \
  harness/examples/evaluation-review/retry-ledger.json --out /tmp/aau-retry-evidence
aau retry-eval verify /tmp/aau-retry-evidence
aau operating-eval /tmp/aau-retry-evidence/evaluation.json \
  --criterion completion higher 1 --criterion unauthorized lower 0 \
  --cost-basis synthetic --out /tmp/aau-retry-operations.json
```

The included fixture has two logical tasks and four underlying attempts. Both final calls
complete, but one task's earlier attempt records an authorization violation. The plan uses
`last` for completion and `max` for unauthorized behavior, so eventual completion cannot erase
that earlier violation. Choose reducers for your own scoring semantics; this is not a universal
prescription for authorization or evidence that retries are safe.

| Same synthetic activity | Final-call-only export | Complete declared retry accounting |
|---|---|---|
| Logical tasks scored | 2 | 2 |
| Tasks meeting both criteria | 2 | 1 |
| Recorded costs included | $0.20 | $0.40 |
| Cost per jointly passing task | $0.10 | $0.40 |
| Whole-task p95 | Misreported as 1 second | 10 seconds supplied by the fixture |

These values demonstrate an accounting error, not measured production performance or savings.
No real agent is run. The operating report's scenario-repeat "attempt" now means **one logical
task**, not a transport call. Do not compare it with call-level observations or incompatible
retry/scoring configurations; declare the task boundary and reducers in your collection context.

**Contract.** The [plan](examples/evaluation-review/retry-plan.json) declares a complete scenario
census, repeat count, source label, `attempt_scope: "sequential_disjoint"`, and 1–100 metric reducers.
An optional `evaluation_context` is preserved, never fabricated. The
[ledger](examples/evaluation-review/retry-ledger.json) declares every task's `attempt_count` and
attempts numbered `0..count-1`, each with a globally unique `attempt_id`, `attempt_index`, `metrics`,
and optional `cost_usd`, `n_api_calls`, `latency_s`. Task-level `elapsed_s` is optional.

- `min` and `max` require the metric on **every** attempt; otherwise the task metric stays absent.
- `last` uses only the highest-index attempt and can hide earlier failures. These metrics are
  explicitly listed in the accounting report. A missing final value stays absent.
- Task cost and API calls sum **all** declared attempts, including failures, only with complete
  field coverage. Partial observed sums remain visible in `accounting.json` but never become
  complete evaluation totals. Omit unknowns; do not write zero, `null`, or an empty string.
- Whole-task latency comes only from `elapsed_s`, which must include the intended end-to-end
  boundary. No last-call substitution, summing of call durations, or invented backoff time.
  Supplied elapsed time shorter than known sequential call durations is rejected (floating-point
  equality tolerance: `1e-12` absolute/relative). Missing elapsed time stays unknown.
- At most 500 scenarios, 10,000 logical tasks, 100 attempts per task, and 10,000 attempts total.
  Complete task API-call totals must also fit the existing observation limit of `10^12`.
  Every input and pack member is bounded to 2 MB. Unknown fields, duplicate identities, missing
  declared rows, malformed numbers, and nonfinite sums are rejected before output creation.

Keep all six files: `plan.json`, `ledger.json`, `recording.json`, `evaluation.json`,
`accounting.json`, `manifest.json`. Verification recomputes the entire source-to-evaluation chain,
not just hashes. Outputs are never overwritten. Exit **0** means accounting verifies, not that
any task passes a policy; exit **2** means invalid input or failed verification.

For a downstream dossier, use `recording.json` with `evaluation-pack from-recordings`, or
`evaluation.json` with `evaluation-pack create`. Retain the retry pack alongside it, then run:

```bash
aau retry-eval verify /tmp/aau-retry-evidence --evaluation /path/to/dossier/candidate.json
aau evaluation-pack verify /path/to/dossier
```

The first command binds only the candidate evaluation; the second verifies the dossier and
returns its policy/gate outcome. Verify a baseline's retry pack separately if it has one.
Approvals for the plan, reducers, scenarios, and operating budgets remain independent reviewer
responsibilities. No new Action input or automated retry execution is introduced.

**Measurement limits.** Do not flatten nested spans, parallel/hedged work, overlapping charge
totals, mixed currencies, or mixed cost bases into this format. It checks declared identities and
coverage, not whether external events were omitted, invoices are accurate, or elapsed time was
measured correctly. Retained JSON preserves values, not original whitespace. Source data is not
sanitized, and coordinated replacement of all files can verify: hashes are not signatures.

**Research basis:** AWS explains that retries can increase load and latency, backoff introduces
waiting, and timeouts do not establish that no side effect occurred.
[Timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/).
The explicit task boundary and conservative aggregation rules above are this repository's design
response, not an AWS standard, endorsement, or proof that a retry is authorized.

### Bring an OpenTelemetry trace export into retry review

`aau otlp-retries` projects an explicitly mapped **OTLP JSON trace object or JSONL trace
file** into the existing retry-accounting contract, entirely offline. It retains the original
bytes and every declared span role. Requires the current checkout or a locally built wheel;
this command is not in published PyPI 1.6.0.

```bash
# A constructed example: two tasks, four attempts, one excluded nested detail span.
python harness/examples/evaluation-review/otlp_retries.py --out /tmp/otlp-example
aau otlp-retries verify /tmp/otlp-example

# Adapt the example mapping to your own already-scored, explicitly bounded export.
aau otlp-retries create reviewed-mapping.json export.json --out otlp-pack
aau otlp-retries verify otlp-pack --ledger handoff/candidate/ledger.json \
  --evaluation handoff/candidate/evaluation.json
```

The last command verifies an **existing** downstream handoff's bindings; it does not create
that handoff. Feed `otlp-pack/retry/plan.json` and `otlp-pack/retry/ledger.json` to
`aau retry-review create` as documented below. Keep the ten-file OTLP pack alongside the
review: the retry handoff alone does **not** retain or verify the original OTLP export.
Verify each projection against its corresponding baseline or candidate handoff paths.
For a single source-complete folder, use [`aau otlp-review`](#hand-off-original-traces-through-the-policy-and-budget-gate) instead.

The example preserves an early authorization violation despite final completion. It also
keeps all four attempt costs, uses the 10-second task span rather than its last 1-second
call, and excludes a fictional nested $999 cost explicitly instead of counting it twice.
These are constructed measurements, not real service performance or provider invoices.

| Mapping field | Required meaning |
|---|---|
| `mapping_version` | `aau-otlp-retry-import/1.0` |
| `source_format` | `otlp_json` for one object; `otlp_jsonl` for newline-delimited trace objects |
| `span_semantics` | `single_attempt_direct_children_same_resource_clock`, an explicit reviewer declaration |
| `accounting_plan` | Complete retry plan: scenario census, repeats, reducers, and optional real context |
| `attributes.metrics` | Each reduced metric maps to a distinct numeric span attribute containing an existing score |
| `attributes.operating` | Optional `cost_usd` and `n_api_calls` map to distinct attributes; no inferred prices or counts |
| `tasks` | Scenario/repeat plus `trace_id`, `task_span_id`, and **ordered** `attempt_span_ids` |
| `excluded_spans` | Every remaining exported span needs its `trace_id`, `span_id`, and a specific `reason` |

This is an explicit sequential profile, **not a general OTLP receiver or automatic GenAI
span classifier**. Selected attempts must be direct children of their task in the same
exported resource entry, in declared non-overlapping time order, inside the task interval.
All direct children must be selected attempts: excluding one to hide a failure is refused.
Nested task scopes, cycles, cross-resource attempts, hedged requests, and parallel attempts
are refused. A task and its attempts split across separate resource entries or JSONL records
are not supported, even if those entries describe an equivalent resource. Export a complete
single-resource task unit; do not relabel distributed clocks to make it pass.

[OpenTelemetry's GenAI guidance](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
allows a logical-operation span to contain automatic retries. Such a span is **not evidence
of one physical attempt**. Use separately instrumented single-attempt spans and review their
accounting scope. No semantic convention, span name, success status, token count, or model
identifier becomes a score, USD charge, or API-call count automatically.

Mapped attributes accept numeric `intValue`/`doubleValue`, not numeric strings stored as
`stringValue`, booleans, or nulls. Missing attributes remain absent. Task and attempt durations
come from integer nanosecond timestamp differences before conversion to seconds; the task
duration is never replaced with a sum of calls. Clock accuracy and disjoint billing scope
remain declarations. Different scopes under the same resource are allowed; co-location does
not authenticate a common clock. See the [research and scope notes](../docs/OTLP_RETRY_IMPORT_RESEARCH_NOTES.md).

The ten-file pack contains `source.otlp`, `mapping.json`, `projection.json`, a root manifest,
and the six-file `retry/` pack. Verification reprojects the source and recomputes every nested
file. Rehashing a substituted ledger or unrelated evaluation is insufficient. Source files
are retained byte-for-byte, including unreviewed attributes and events; JSON mappings retain
values. Each file is capped at 2 MB; at most 10,000 spans, 10,000 tasks, and 100 attempts per
task are supported, subject to the retry contract's 10,000-attempt ceiling. Duplicate JSON
keys and span identities, extra/missing members, symlinks, and overwrites are refused.

Exit **0** means the conversion verifies, even if its scores fail policy. Exit **2** means
invalid inputs or failed verification. Use the separate policy/budget gate for pass/fail.
Only aggregate counts appear in normal CLI output. No network, credentials, collectors,
model execution, or uploads are involved. **The pack is not sanitized:** original traces may
contain prompts, identifiers, secrets, or personal data. Inspect every member before sharing.
Sampling, omitted external events, inappropriate exclusions, false scoring, coordinated source
replacement, and untrustworthy clocks cannot be disproved by these hashes or validators.

### Hand off original traces through the policy and budget gate

`aau otlp-review` carries **both original trace exports all the way through review**, so a
recipient need not assemble and bind separate projection packs. Requires the current checkout
or a locally built wheel, not published PyPI 1.6.0. It uses the same explicit sequential-span
profile described above and does not collect telemetry or execute an agent.

```bash
# Offline constructed examples: earlier harm, slow completion, and repaired fixture.
python harness/examples/evaluation-review/otlp_handoff.py --out /tmp/otlp-handoff-demo
aau otlp-review verify /tmp/otlp-handoff-demo/repaired --require-budget

# Your own independently reviewed maps, scores, policy, diagnostics, and limits.
aau otlp-review create policy.json baseline-mapping.json baseline.otlp \
  candidate-mapping.json candidate.otlp --diagnostics diagnostics.json \
  --operating-budget budget.json --out trace-review
aau otlp-review verify trace-review --require-budget
```

Open `trace-review/review/review.html` for the policy and operating review. The page is
script-free but does not verify itself. The full folder contains **39 files** with a budget
or **36 files** without one:

- `baseline/` and `candidate/`: each complete ten-file OTLP projection, including original
  bytes, mapping, exclusions, and six-file `retry/` accounting pack;
- `review/`: policy, both recordings/evaluations, diagnostic plans/results, HTML, and manifests;
  budgeted mode also retains the candidate budget, its independent verdict, and combined gate;
- root `handoff.json`, `README.txt`, and `manifest.json`: source bindings and verification guide.

Verification reprojects both exports and recomputes the entire chain. It refuses individually
valid but unrelated projection/review substitutions, even if the outer manifest was rehashed.
Verifying only `review/` does **not** establish the original-trace links. The supplied source
bytes are preserved; JSON mapping/plan values are reserialized. Preserve original approved
JSON files separately when auditing independently approved file-byte pins.

Both sides must use **identical score/operating attribute maps, attempt semantics, metric
reducers, and accounting scope**. Matching benchmark-context hashes cannot bypass these checks.
Span IDs, recorded task histories, and JSON versus JSONL serialization may differ. A deliberate
instrumentation/attribute rename requires separate review; this command does not infer semantic
equivalence. Identical names still do not prove valid scoring or disjoint cost attribution.

Exit **0** means the applicable constraints are met and the complete chain verifies. Exit **1**
preserves failed or unverified gate evidence; an unknown required budget cannot pass. Exit **2**
means malformed evidence, an incompatible comparison, missing required budget layer, or failed
verification. A valid conversion cannot compensate for a failed policy or budget. The three
synthetic examples expect exit codes **1, 1, 0**, respectively—not production performance claims.

The [pinned-input Action](../.github/actions/aau-evaluation-review/README.md#gate-original-otlp-exports-with-approved-span-mappings)
accepts `input-format: otlp` and requires independently approved byte hashes for both mappings,
the baseline export, policy, diagnostics, and any budget. It requires matching context inside
both mappings' `accounting_plan`; the CLI instead discloses missing context for separate review.
Approve the complete span census and exclusions as well as the mappings' attribute names.
Do not calculate production approval pins from candidate-controlled files in the same job.

All original trace content remains **unsanitized**, including ignored events, prompts, and
attributes. Inspect every file before sharing. No credentials, installations, network calls,
automatic uploads, scorer execution, or retries are added. Hashes do not authenticate capture,
clocks, measurements, independent approval, compliance, or deployment suitability.

### Hand off retry evidence with its complete policy and budget review

**Read it first:** the [public retry-evidence lab](https://immu4989.github.io/awesome-agentic-usecases/evaluation-review/retry-lab.html)
shows a declared call sequence, compares incomplete and whole-task accounting, and provides all
three source-complete handoffs for download. No installation is required to read the lesson.

`aau retry-review` combines both source-retaining retry packs and their full evaluation review
into **one verifiable folder**. Use it when a reviewer or CI job must check the ledgers, not
just normalized task scores. Requires the current checkout or a locally built wheel, not
published PyPI 1.6.0. The installed package includes a no-key walkthrough; no repository-only
fixture files are needed after installation:

```bash
aau retry-demo --out /tmp/aau-retry-review-demo
aau retry-review verify /tmp/aau-retry-review-demo/earlier-harm --require-budget
# Expected exit 1: earlier authorization failure and candidate budget failure remain visible.
aau retry-review verify /tmp/aau-retry-review-demo/slow-completion --require-budget
# Expected exit 1: policy met, but whole-task p95 exceeds the synthetic budget.
aau retry-review verify /tmp/aau-retry-review-demo/repaired --require-budget
# Expected exit 0: both supplied policy and budget constraints met.
```

The command creates and verifies all three 31-file handoffs plus a readable guide: **94 files**.
It exits 0 when the expected passing and failing examples all verify; individual handoff checks
return the outcomes shown above. Existing destinations are never overwritten, and the guide is
written only after each independent policy, budget, and combined verdict matches its contract.
The repository script `harness/examples/evaluation-review/retry_handoff.py` remains a wrapper
around this same implementation. Source fingerprints now identify the packaged fixture generator.

Open each folder's `review/review.html`. These constructed fixtures demonstrate three distinct
outcomes; they do not measure a real agent repair. No model or service is called. The full
evidence behind each displayed result is retained in the same folder.

For your own inputs:

```bash
aau retry-review create approved-policy.json baseline-plan.json baseline-ledger.json \
  candidate-plan.json candidate-ledger.json --diagnostics approved-diagnostics.json \
  --operating-budget approved-budget.json --out new-retry-handoff
aau retry-review verify new-retry-handoff --require-budget
```

Both plans must use **identical metric reducers and attempt scope**; matching context hashes
alone do not satisfy that check. A candidate cannot switch `unauthorized: max` to `last` and
hide an earlier violation while retaining the same declared context. Equal reducers still do
not prove appropriate scoring: an approved `last` reducer can ignore earlier outcomes on both
sides. Inspect the `last_only_metrics` list and per-attempt coverage in each accounting report.

| Folder | Retained evidence |
|---|---|
| `baseline/` | Six-file baseline retry ledger/accounting pack |
| `candidate/` | Six-file candidate retry ledger/accounting pack |
| `review/` | Thirteen-file recorded-observation dossier, or sixteen files with the candidate budget gate |
| Root | `handoff.json`, readable `README.txt`, and the complete `manifest.json` |

The ungated handoff has **28 files**; supplying an operating budget produces **31 files**.
Diagnostics are always required. Full verification derives recordings from both ledgers and
recomputes the policy, diagnostics, optional combined gate, HTML, and manifests. Substituting an
individually valid but unrelated nested review fails even after rehashing the outer manifest.
Existing destinations, extra/missing members, symlinks, oversized files, and tampering are refused.
The root manifest is written last; partial output is not completed evidence.

Exit **0** means the source chain verifies and all applicable constraints are met; **1** means
it verifies but policy or candidate budget fails, including required budget evidence that is
unknown; **2** means invalid inputs or failed verification. Use `--require-budget` when a budget
is mandatory: an otherwise valid ungated handoff must not be accepted as a replacement.

The [GitHub Action](../.github/actions/aau-evaluation-review/README.md#gate-retry-ledgers-with-approved-accounting-definitions)
supports `input-format: retries`, independent approval pins for both accounting plans, and
matching declared context on both sources. The CLI preserves and discloses missing context;
it does not manufacture it. Keep scenario/scoring context and logical-task boundaries comparable.
No retries are run, authorized, or recommended by a passing review. Both ledgers retain supplied
JSON values rather than exact original file bytes. Review all unsanitized contents before sharing;
hash consistency is not authenticity, policy approval, invoice verification, or deployment approval.

### Compare several candidates without hiding policy failures

`aau candidate-matrix` reviews **2–10 normalized evaluations** against one baseline and one policy.
It retains each full policy review and operating report, plus a script-free comparison page.
Candidates are shown alphabetically, never as a weighted leaderboard. A low recorded cost cannot
compensate for a failed global or cohort constraint.

Requires the current repository harness or a wheel built from it, not published PyPI 1.6.0.
Try the five-candidate synthetic example:

```bash
pip install -e harness
python harness/examples/evaluation-review/matrix.py --out /tmp/aau-matrix-demo
aau candidate-matrix verify /tmp/aau-matrix-demo/matrix
```

Open `/tmp/aau-matrix-demo/matrix/matrix.html`. No agent, model, real payment, or measured service
is involved. The constructed candidates deliberately expose different decision traps:

| Synthetic candidate | What the evidence shows |
|---|---|
| `cheap-unsafe` | Lowest cost/latency, but fails authorization policy; excluded from operating comparisons |
| `balanced` | Meets policy; $0.25 per jointly passing attempt, recorded p95 of 2 seconds |
| `fast` | Meets policy; $0.50 per jointly passing attempt, recorded p95 of 1 second; a trade-off, not an overall winner |
| `dominated` | Meets policy, but another eligible candidate is cheaper and faster on the two recorded axes |
| `unknown-cost` | Meets policy, but one cost is absent; unit cost remains unknown and is not compared |

For your own inputs, create a plan with exactly these fields:

Candidate IDs are distinct nonblank labels of at most 120 characters and cannot contain `=`.

```json
{
  "plan_version": "aau-candidate-matrix/1.0",
  "candidate_ids": ["candidate-a", "candidate-b"],
  "criteria": [
    {"metric": "completion", "direction": "higher", "limit": 1},
    {"metric": "unauthorized", "direction": "lower", "limit": 0}
  ],
  "cost_basis": {"candidate-a": "estimate", "candidate-b": "estimate"}
}
```

```bash
aau candidate-matrix create matrix-plan.json approved-policy.json baseline.json \
  --candidate candidate-a=candidate-a.json --candidate candidate-b=candidate-b.json \
  --out candidate-review
aau candidate-matrix verify candidate-review
```

All sources must have valid matching declared scenario/scorer/configuration context and equal
repeat counts; missing legacy context and mismatches fail before output creation. This deliberately
does not weaken existing comparison gates. Do not edit fingerprints to manufacture comparability
when actual test settings differ. Complete scenario coverage and every global/cohort policy rule
remain enforced. CSV users can first normalize their exports with `csv-eval`; retain those original
conversion packs separately, because the matrix retains normalized evaluations, not original CSV.

The plan's common joint criteria define the unit-cost denominator for **all** candidates. They
may differ from policy criteria; that difference must be reviewed, not hidden. Total recorded cost
includes failed attempts. Missing cost or latency coverage, zero jointly passing attempts, an
unknown cost basis, or failed policy constraints exclude a candidate from operating comparisons.
Policy results and the reason for each exclusion remain visible. Missing API-call counts are
disclosed in the operating report but are not a cost/latency exclusion.

Eligible candidates are compared only **within the same declared cost basis** (`estimate`,
`charge`, or `synthetic`). A candidate is not dominated on the two recorded axes if no other
eligible member of that group has no higher unit cost and no higher p95 latency, with at least
one strictly lower value. Equal points remain tied; a group may contain just one eligible candidate.
Every pair's relationship is recorded in `matrix.json`. No tolerance, statistical inference,
future savings, provider pricing, or confidence-adjusted dominance is inferred. Other important
quality differences are not ranked; inspect each full policy and per-scenario operating report.

This is an implementation of an explicitly scoped descriptive comparison, not a procurement
decision or endorsement. The motivation follows the [FinOps Foundation's unit-economics guidance](https://www.finops.org/framework/capabilities/unit-economics/)
on defining units and documenting measurement assumptions. A scored passing attempt is not a
verified person served, business outcome, fully loaded cost, or ROI.

The portable folder contains **6 + 3 × candidate count** files: plan, policy, baseline, JSON matrix,
HTML matrix, manifest, and each candidate's evaluation/policy/operating reports. Verification
recomputes every byte, including HTML, not just hashes. Each member is limited to 2 MB. Existing
destinations, extra/missing files, symlinks, and oversized evidence are refused. Invalid input is
rejected before creation; the manifest is written last. Labels never become file paths.

Exit **0** means a descriptive matrix was created or verified, **not** that any or all candidates
passed policy. Exit **2** means invalid input or verification failure. Do not use this command's
success as a deployment gate. All supplied evaluation details are retained and **not sanitized**;
review before sharing. Hashes do not authenticate execution, scoring, timestamps, or approval.

### Measure routing trade-offs without assuming human resolution

Many workflows end with “route uncertain cases to a human.” That is a referral, not proof that the
person received timely, correct service. `aau routing-eval` makes the **recorded trade-off** inspectable:
how many supplied observations a declared threshold would automate, which recorded joint failures
remain on that path, and how many observations it would defer. It neither executes routing nor
assumes humans fix the deferred cases. Use a matching trusted checkout/local wheel containing this
unreleased command; do not assume an older published package contains it.

The [selective-classification literature](https://arxiv.org/abs/1705.08500) motivates examining error
together with coverage. This tool implements descriptive counts, **not that paper's learned selector
or statistical guarantees**. [NIST AI RMF MANAGE 1.1–1.2](https://airc.nist.gov/airmf-resources/playbook/manage/)
also discusses risk/benefit trade-offs and resource decisions. Neither source endorses this tool or
makes its example thresholds suitable for a real agency or business.

Try five constructed contrasts:

```bash
python harness/examples/evaluation-review/routing_workload.py --out /tmp/aau-routing-workload
```

In the main synthetic fixture, all ten supplied observations are retained, including four joint
outcome failures. The example's scores are deliberately imperfect rankings:

| Score threshold | Automated observations | Failures on that hypothetical path | Deferred observations | Automated failure fraction |
|---|---:|---:|---:|---:|
| 0 | 6 | 2 | 4 | 1/3 |
| 0.8 | 4 | 2 | 6 | 1/2 |
| 1 | 0 | 0 | 10 | Undefined, not zero |

Raising the score threshold does not necessarily lower the observed error fraction. At threshold 0,
the example's global limits are met, but the declared assisted-channel group has two failures in two
automated observations and fails its own limit. Other contrasts show referral overload, all-deferred
work, and a clean recording. No human outcome or real model execution is supplied in these fixtures.

The plan's exact fields are illustrated below. Limits are **example batch counts and fractions**,
not recommended production values, legal requirements, staffing estimates, or service-level objectives.

```json
{
  "plan_version": "aau-recorded-routing-plan/1.0",
  "scenario_ids": ["case-a", "case-b"],
  "n_repeats": 2,
  "criteria": [
    {"metric": "completion", "direction": "higher", "limit": 1},
    {"metric": "unauthorized", "direction": "lower", "limit": 0}
  ],
  "score_metric": "routing_score",
  "mandatory_review_metric": "human_required",
  "score_basis": "Describe the supplied ranking score and when it is available; not presumed calibrated.",
  "thresholds": [0, 0.8, 1],
  "limits": {
    "minimum_automation_fraction": 0.5,
    "maximum_automated_failure_fraction": 0.1,
    "maximum_review_observations": 2
  },
  "groups": [
    {
      "group_id": "declared-assisted-route",
      "scenario_ids": ["case-b"],
      "limits": {
        "minimum_automation_fraction": 0,
        "maximum_automated_failure_fraction": 0.1,
        "maximum_review_observations": 2
      }
    }
  ]
}
```

Input is a complete saved evaluation, including one produced by `aau import-eval` or `aau csv-eval`.
Every outcome criterion must exist on every scenario/repeat. The routing score, when present, must
be a finite numeric value from 0 through 1; the human-review flag must be numeric 0 or 1, not a
boolean. Omit an unknown routing metric rather than inserting a made-up zero or `null`. Missing
routing metrics remain explicit unknowns; missing outcome measurements invalidate the diagnostic.
The two routing metrics must be distinct from each other and the outcome criteria.

Routing is deterministic and conjunctive: a supplied human-review flag of 0 **and** a present score
at least the threshold are required for the hypothetical automated path. Deferral reasons use the
following precedence so counts do not overlap: required human review, unknown review requirement,
missing score, below threshold. Every input score/flag remains in the report, including when more
than one reason applies. A high score never overrides a required or unknown human-review flag.
The tool does **not** establish that either field is trustworthy, available before action, free of
outcome leakage, or an accurate expression of a person's legal rights or an operator's authority.

Independently select and protect the plan's expected byte hash before evaluating a candidate:

```bash
aau routing-eval approved-routing-plan.json complete-evaluation.json \
  --plan-sha256 "$APPROVED_ROUTING_PLAN_SHA256" --out routing-report.json
aau routing-eval approved-routing-plan.json complete-evaluation.json \
  --plan-sha256 "$APPROVED_ROUTING_PLAN_SHA256" --verify routing-report.json
```

Do not compute an expected approval hash from candidate-controlled input in the same job. Pins
identify bytes, not preregistration or reviewer authority. Plans require 1–500 unique scenarios,
an exact repeat count with at most 10,000 observations, 1–10 joint outcome criteria, 1–20 distinct
thresholds, and up to 19 named nonempty groups. Groups may overlap; they are reviewed separately,
never pooled as disjoint populations. The complete scenario/repeat census must match—no dropped
failures or favorable subset review. Each referral limit is an integer from zero through that scope's
planned observation count. Inputs/reports are bounded to 2 MB; existing outputs are not overwritten.

Each threshold reports every group's coverage, automated and deferred joint failures, referral
count, reason counts, and all three limit checks. Known exceeded limits take status precedence over
unverified checks, but both remain visible. The automated failure fraction is undefined with an
empty denominator, even if the minimum coverage limit is zero. Counts are checked against limits
as exact rational values versus the parsed limits' decimal spelling; displayed fractions are not
rounded before checking. Source summaries are audited and inconsistencies retained, not repaired.

**A valid diagnostic exits 0 even when limits are exceeded or unverified.** Exit 2 rejects invalid
inputs or replay mismatches. This is not a policy gate or a replacement for `review-intake`/`review-ci`.
The report selects no threshold. If a threshold is chosen using these results, assess it separately
on held-out evidence and revalidate any assumptions; there is no confidence bound here.

Every recorded joint failure remains in the report regardless of routing. Deferral cannot undo a
side effect already recorded. `human_resolution` remains `not_measured` for deferred work; no queue
delay, review quality, hours saved, human capacity over time, cost, causal benefit, or future traffic
is inferred. Repeats are not independent people or arrivals, and counts are not population estimates.
Keep the original plan, complete evaluation, and report with a matching trusted harness. Identifiers,
scores, failures, and hashes are retained and require disclosure review. No adapters, model calls,
external actions, uploads, or network requests are performed.

### Replay a finite review queue without inventing human capacity

The routing diagnostic counts referrals; it cannot determine how long those referrals wait.
`aau review-queue` adds an explicit **finite what-if model** using supplied arrival times, positive
service durations, availability windows, and optional completion deadlines. It recomputes the full
routing diagnostic and requires **exactly every deferred scenario/repeat** at one independently
selected threshold. Required or unknown human-review flags cannot be omitted to make capacity look better.
This is an unreleased harness command: use a matching trusted checkout or local wheel.

Finite resources can create queues, as illustrated in the
[SimPy shared-resource documentation](https://simpy.readthedocs.io/en/latest/topical_guides/resources.html). <!-- codespell:ignore simpy -->
This implementation uses its own deterministic bounded interval search, **not SimPy**, and makes <!-- codespell:ignore simpy -->
its particular assumptions explicit. [NIST MANAGE 1.2](https://airc.nist.gov/airmf-resources/playbook/manage/)
discusses resource decisions in risk management; it does not endorse this model or establish that
its assumptions or example times apply to a real organization.

```bash
python harness/examples/evaluation-review/review_queue.py --out /tmp/aau-review-queue
```

All five examples retain the same four hypothetical referrals. Normally each takes three constructed
seconds, arrives at zero, and has a declared finish deadline of six seconds. These deliberately tiny
values make the arithmetic inspectable; they are **not realistic human-review estimates or legal clocks**.

| Constructed model | Scheduled | Unscheduled | Known declared-deadline failures |
|---|---:|---:|---:|
| One slot available through second 12 | 4 | 0 | 2 |
| Two slots available through second 12 | 4 | 0 | 0 |
| One slot with an unavailable interval from 4 to 8 | 2 | 2 | 3 |
| First item needs 20 seconds and cannot fit | 0 | 4 | 4 |
| One short window; no deadlines supplied | 1 | 3 | 0 — all four deadline outcomes remain unknown |

The second row is conditional arithmetic under changed capacity, not advice to hire another reviewer.
The last row is not deadline success. None of these rows measures correct review, resolved cases,
delivered benefits, or recovered harm; the nested routing report retains every original failure.

An independently reviewed queue plan binds the **exact bytes of the routing plan** and one of that
plan's declared thresholds. Its own expected byte hash must be protected separately from candidate
inputs. Computing an expected approval hash from candidate-controlled files in the same job defeats
that separation. The example below uses an intentionally placeholder routing-plan hash; replace it
with the independently reviewed value, not a hash opportunistically accepted from a delivery.

```json
{
  "plan_version": "aau-human-review-queue-plan/1.0",
  "routing_plan_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "threshold": 0,
  "horizon_s": 12,
  "timing_basis": "synthetic",
  "timing_scope": "Constructed arithmetic only; describe real timing assumptions separately.",
  "initial_state": "empty_queue_idle_slots_at_zero",
  "workers": [
    {"worker_id": "review-slot-a", "windows": [{"start_s": 0, "end_s": 12}]}
  ]
}
```

`timing_basis` is `synthetic`, `supplied_measurements`, or `declared_estimates`, always a declaration,
not authentication. All times use integer seconds from the **same supplied relative origin**.
The positive horizon is at most 31,536,000 seconds. Up to 20 interchangeable slots may each have
1–20 ordered, non-overlapping availability windows contained in the horizon. Zero slots is valid
zero capacity, not fabricated availability. Use slot labels rather than employee names: no employee
performance or productivity assessment is performed. Empty initial state and idle slots are explicit
model assumptions; windows must exclude other commitments and cannot prove complete workload coverage.

The separate work-item document supplies one entry per hypothetical referral:

```json
{
  "format_version": "aau-human-review-work-items/1.0",
  "items": [
    {"scenario_id": "case-a", "repeat": 0, "arrival_s": 0, "service_s": 3, "deadline_s": 6}
  ]
}
```

This one-row shape is valid only when that exact observation is the entire deferred census. Arrival
must be nonnegative and before the horizon; service duration must be a positive integer; both are
required, not imputed. Deadlines are nonnegative integer seconds or `null` when unknown. A deadline
can already have passed before arrival; it is not silently reset. Missing/extra/duplicate referrals,
automated observations inserted into the queue, or substituted routing plans are rejected. The
maximum work-item count is 10,000, inherited from the complete routing evaluation.

```bash
aau review-queue approved-queue-plan.json approved-routing-plan.json complete-evaluation.json work-items.json \
  --queue-plan-sha256 "$APPROVED_QUEUE_PLAN_SHA256" --out queue-report.json
aau review-queue approved-queue-plan.json approved-routing-plan.json complete-evaluation.json work-items.json \
  --queue-plan-sha256 "$APPROVED_QUEUE_PLAN_SHA256" --verify queue-report.json
```

The model uses **strict FIFO**: arrival time, then scenario ID and repeat break ties. Jobs start at
the earliest feasible time; equal-start capacity ties use slot ID. Labels are deterministic tie-breakers,
not urgency, fairness, rights, or eligibility priorities. Each job must fit wholly within one window;
completion exactly at its end is allowed. Adjacent windows are not silently merged. No service is
split across breaks, preempted, or extended through overtime. A head reserved for a future slot cannot
be overtaken by a later short job. A head that cannot fit anywhere blocks every later item; this can
leave apparent spare capacity unused. This is a stated FIFO-model limitation, not an optimization.
Skill-specific, urgent, preemptive, abandoning, retrying, or carry-in workloads require a different model.

Every job retains its scheduled start/finish or explicit unscheduled reason. Maximum scheduled wait
and maximum unserved wait at the horizon remain separate, so unfinished work cannot disappear into
an average of completed jobs. The timeline combines all events at the same second before reporting
waiting and in-service counts; immediate starts create no artificial positive wait. Work finishing at
its declared deadline is within it. Unscheduled work with a deadline at/before the horizon fails that
declared deadline; deadlines beyond the horizon remain unresolved. Omitted deadlines remain unknown.

**Valid diagnostic reports exit 0 even when jobs are blocked or deadlines fail; invalid inputs or
replay mismatches exit 2.** No threshold, staffing level, deployment, or human decision is approved.
Replay starts from both original plans, the full evaluation, and all work items, not a supplied report.
Plan pins bind raw bytes; evaluation/work-item hashes bind parsed JSON values. Every input and the
composed report is bounded to 2 MB; no truncation or overwriting is allowed. Keep all original inputs
and use a matching trusted implementation. Data capture is not atomic or source-authenticated.
Review identifiers, times, scores, and hashes before sharing. No model, adapter, human action,
subprocess, upload, or network request is executed by this command.

### Review lifecycle costs without turning unknowns into zero

`aau lifecycle-cost` computes **declared constant-USD scenarios**, including costs outside model
calls. It is a planning diagnostic, not a validated cost estimate or an award recommendation.
Unlike `operating-eval`, which describes recorded attempts, this command uses explicitly supplied
workloads and rates. It never extrapolates a benchmark pass rate into production demand or savings.

Run the synthetic walkthrough from a **trusted current checkout/local wheel** (not the older
published PyPI release):

```bash
pip install -e harness
aau lifecycle-cost-demo --out /tmp/my-lifecycle-review
```

Read the generated `README.md`. Eight files retain one plan, three rate variants, three reports,
and the guide. Four scenarios show fixed and recurring costs, a review-event surge, a combined
case/review surge, and a shorter horizon. The complete expected scenario has $3,000 in model
usage and $368,000 in declared costs. With exit cost unknown, $353,000 is **only a subtotal**.
These values are invented for the walkthrough; they are not current vendor quotes, real agency
workloads, forecasts, salaries, or observed savings.

For an independently reviewed plan and your own rate assumptions:

```bash
aau lifecycle-cost plan.json rates.json --plan-sha256 "$APPROVED_COST_PLAN_SHA256" --out cost-report.json
aau lifecycle-cost plan.json rates.json --plan-sha256 "$APPROVED_COST_PLAN_SHA256" --verify cost-report.json
```

Protect the expected plan hash independently of a supplier's delivery. It binds the cost census,
quantity drivers, scenarios, and assumptions. Rate sources are declared, not fetched or authenticated.
Exact raw input hashes are retained in the report; verification recomputes every rendered report byte.
Existing output files are never overwritten.

#### Cost-plan contract

The plan has exactly these fields:

- `plan_version`: `aau-lifecycle-cost-plan/1.0`.
- `currency`: `USD`; no implicit currency conversion.
- `assumptions`: nonempty description of scope, price basis, exclusions, and workload assumptions.
- `cost_items`: 1–100 rows with exactly `cost_id`, `category`, `driver`, and `description`.
- `scenarios`: 1–20 rows with exactly `scenario_id`, `months`, `cases`, `reviews`, and `assumptions`.

Every plan must include at least one line in each of these cost categories: `implementation`,
`model_usage`, `infrastructure`, `human_review`, `monitoring`, `security_privacy_accessibility`,
and `transition_exit`. Additional lines can use `other`. This is a disclosure prompt, not a
standard work breakdown structure or proof of cost completeness. If a cost does not apply,
use an explicit zero rate and explain why; do not delete the category. Check for omitted and
double-counted obligations with qualified acquisition/cost reviewers.

| Driver | Quantity applied to the supplied unit rate |
|---|---|
| `one_time` | 1 for each scenario; setup/exit do not disappear when the horizon shortens |
| `per_month` | Supplied `months` |
| `per_case` | Supplied `cases` over the entire horizon, **not cases per month** |
| `per_review` | Supplied review events over the entire horizon, not a staff headcount |

Months must be an integer from 1 through 120. Cases and reviews must be integers from 0 through
1,000,000,000; booleans, fractions, negatives, and inferred values are rejected. Multiple reviews
per case are possible, so review counts are not restricted to case counts. IDs are distinct
lowercase slugs, starting with a letter and containing up to 64 letters/digits/underscores/hyphens.
Descriptions allow up to 500 characters; assumptions allow up to 2,000.

#### Rate contract and unknowns

The rate document has exactly `format_version: "aau-lifecycle-cost-rates/1.0"`, `currency: "USD"`,
and `rates`. Each rate row has exactly:

- `cost_id`, matching one planned cost line.
- `unit_cost_usd`: a nonnegative decimal **string**, with up to 12 integer and 6 fractional digits,
  or `null` for unknown. Floats, negatives, scientific notation, and silent rounding are rejected.
- `basis`: `estimate`, `quote`, `synthetic`, or `unknown`. A supplied numeric rate cannot use `unknown`.
- `source_ref`: a nonempty source reference up to 500 characters; never dereferenced by this tool.
- `assumptions`: nonempty scope/limitations, up to 2,000 characters.

Missing rows are permitted and labeled `missing`; explicit null rates are labeled `unknown`.
Duplicate and unplanned rate IDs are invalid. Every planned line remains in every scenario.
An unknown rate with positive quantity makes that category and the scenario total `null`.
Known contributions remain a separately labeled subtotal. With zero quantity, a variable line
has zero extended cost **under the declared linear model**, while its unknown rate stays unknown.
This is not a waiver of minimum commitments: model such commitments separately or use a more
appropriate model. An empty rate list is valid evidence of missing costs, not a free solution.

Reports retain each quantity × unit-rate calculation, source and assumption declarations,
category subtotals, unknown active cost IDs, and scenario totals. Arithmetic uses integer
micro-dollars and fixed six-decimal strings without rounding. Precision is computational, not
evidence of precise source estimates. Comparisons use the first declared scenario as the
baseline and list exactly which quantity drivers changed. If any compared total is unknown,
the difference remains unknown. Several changed quantities are never labeled a one-factor
sensitivity analysis; even one changed quantity is only conditional arithmetic, not a complete
sensitivity/risk study.

All inputs and reports are bounded to 2 MB. Exit **0** means a valid diagnostic, even with
unknown totals. Exit **2** means invalid input/output or a report that does not recompute.
No result asserts affordability, comparative effectiveness, source validity, benefit, savings,
compliance, or authorization. Fixed/linear rates do not model tiered pricing, discounts,
inflation, probabilistic contingency, financing, or taxes unless explicitly represented by
appropriate supplied lines. No network, model, adapter, or subprocess is called. Protect
procurement-sensitive information; these files are not sanitized for public sharing.

See the [agency evaluation path](../GOVERNMENT_EVALUATION_PATH.md) for source-backed motivation
and the separate quality, security, human-review, and pilot decisions this does not replace.

### Find untested conditions before trusting averages

`aau coverage-review` checks **which declared conditions have recorded evidence**, separately from
whether the model performed well. A hundred repeats of one case cannot fill an untested condition.
An unknown classification is not guessed, and an excluded condition cannot silently disappear.

Try the no-key example from a reviewed current checkout/local wheel, not the older public PyPI release:

```bash
aau coverage-review demo --out /tmp/my-coverage-review
```

Open each `review.html` locally and read the generated `README.md` for replay commands. The demo
contains three six-file packets and a guide. All cases, annotations, scores, and fingerprints are
constructed; no model, government service, participant, or live endpoint was evaluated.

| Packet | Recorded evidence | Coverage conclusion |
|---|---|---|
| `gap` | 40 all-one observations from four cases; no assisted/Spanish case | `coverage_not_met` |
| `uncertain` | 50 observations from five cases; the new assisted case has unknown language | `coverage_not_verified` |
| `covered` | The fifth case is classified Spanish; all four cells meet the declared floor | `coverage_met` |

The default example requires one distinct case and two complete-metric repeats per cell. Those
floors are illustrative choices, **not adequate sample sizes for a real evaluation**. Zero scores
can also meet coverage: use separate performance, safety, operational, and domain reviews.

#### Declare scope before reviewing results

Independently review and retain the plan's SHA-256 outside the delivered packet. A self-supplied
hash does not establish preregistration, identity, authority, or an authentic study. Use new paths:

```bash
aau coverage-review create plan.json inventory.json evaluation.json \
  --plan-sha256 "$APPROVED_COVERAGE_PLAN_SHA256" --out /tmp/coverage-packet
aau coverage-review verify /tmp/coverage-packet --plan-sha256 "$APPROVED_COVERAGE_PLAN_SHA256"
```

Both commands return **0** for met declared coverage, **1** for a valid report with unmet or
unverified coverage, and **2** for invalid inputs, a wrong pin, or failed replay. Exit 1 is not
a corrupt packet. The demo command returns 0 after constructing all three valid examples;
do not chain their verification commands with `&&` and expect all three to return 0.

The exact six files are `plan.json`, `inventory.json`, `evaluation.json`, `review.json`,
`review.html`, and `manifest.json`. Original input bytes are retained. Verification reconstructs
every derived byte with the same trusted implementation; editing an HTML/report and updating its
manifest still fails. Use this command's verifier, not the generic `inspect-pack` verifier.
Unexpected members, nested directories, links, and special files are rejected. JSON must be
finite, duplicate-key-free, and bounded to 2 MB per file; expanded outputs are bounded too.

#### Input contracts

Plan and inventory reject unknown fields. The plan has exactly:

```json
{
  "plan_version": "aau-coverage-plan/1.0",
  "purpose": "Constructed service-routing coverage; no actual service evaluation.",
  "dimensions": {
    "channel": ["self-service", "assisted"],
    "language": ["english", "spanish"]
  },
  "minimum_cases": 1,
  "minimum_complete_repeats": 2,
  "required_metrics": ["completion", "authorization"],
  "cell_overrides": []
}
```

- `purpose` is nonblank text up to 2,000 characters. There are 1–5 dimensions, each with 1–10
  unique levels, and at most 200 cells in their **full Cartesian product**. Dimension/level IDs
  match `[A-Za-z0-9][A-Za-z0-9_.-]{0,79}`. Dimensions are sorted; level order is preserved.
- Default `minimum_cases` is an integer 1–500; `minimum_complete_repeats` is an integer 1–10,000.
  Booleans are not integers. `required_metrics` lists 1–100 unique nonblank names of at most 200
  characters. Every named metric must occur **together in an observation**, not on different repeats.
- Each optional `cell_overrides` entry has exactly `coordinates` (every dimension), `minimum_cases`
  (integer 0–500), and nonblank `rationale` (up to 1,000 characters). Coordinates must be unique and
  inside the grid. Zero explicitly excludes that cell, but it remains visible with its rationale;
  at least one cell must remain required. Changing scope changes the required raw plan pin.

Inventory has exactly `inventory_version: "aau-coverage-inventory/1.0"`, nonblank `source_label`
(up to 200 characters), and `items` (1–500). Each item has exactly:

```json
{
  "scenario_id": "example-case",
  "scenario_sha256": "<64 lowercase hexadecimal characters, matching the evaluation context>",
  "attributes": {"channel": "assisted", "language": null}
}
```

Replace the illustrative hash placeholder. IDs are unique nonblank strings up to 200 characters;
declared scenario hashes must also be unique. `attributes` must name every dimension, with a
declared level or explicit `null`. Unknown levels and omitted keys are invalid. Different hashes
do **not** prove semantic diversity, independence, authenticity, or correct annotations.

Use an AAU evaluation with complete scenario/repeat rows, such as `import-eval` output or a saved
runner result. `audit-eval` must find its summaries consistent; no summary is silently repaired.
Every observed scenario must be in the inventory; inventory-only cases are retained as unobserved.
When `evaluation_context` is present, its declared fingerprints must cover exactly the observed
IDs and match the inventory. A mismatch or malformed context is invalid. An entirely absent context
leaves binding unavailable; **do not invent hashes to turn an unbound import into verified coverage**.
The Inspect adapter intentionally does not invent scenario-context fingerprints.

#### How to interpret the report

A case counts once in its cell only when all attributes are known, declared fingerprints match,
and enough recorded repeats contain every required metric. Score magnitudes are not compared to
performance thresholds. An eligible but incompletely classified or unbound case appears as
uncertain in each compatible cell. Insufficient complete observations and unobserved cases cannot
count as supplied coverage, even though future evidence might change that result.

For each required cell: enough counted cases means `coverage_met`; counted plus uncertain below
the floor means `coverage_not_met`; otherwise it is `coverage_not_verified`. Overall, any unmet
cell wins over uncertainty; otherwise any uncertain cell prevents a met conclusion. Excluded
cells are reported separately. **Uncertain cases may appear in several cells: their possibilities
cannot be summed or assumed simultaneously attainable.** This is not a global assignment solver.

The offline HTML exposes all cells and all cases, including flags and fingerprint availability.
Tables have captions, column headers, and keyboard-focusable scrolling regions; no scripts or
remote assets are loaded. This is not accessibility-conformance evidence. Source bytes are not
sanitized: obtain permission and protect sensitive case metadata before sharing a packet.

Research checked November 19, 2026: [NIST AI RMF 1.0's validity discussion](https://airc.nist.gov/airmf-resources/airmf/3-sec-characteristics/)
connects accuracy claims with realistic, representative test sets and documented methodology.
[Apple's evaluation-dataset guidance](https://developer.apple.com/documentation/evaluations/designing-evaluation-datasets)
recommends relevant variation across dimensions and deliberate test-set design. Our inference is
that a declared grid can expose one class of missing evidence. It does **not** establish population
representativeness, fairness, statistical power, protected holdouts, compliance, or deployment
readiness. Resource bounds and user-selected floors are engineering choices, not those sources'
requirements. Domain experts must still justify scope, cases, exclusions, annotations, and studies.

### Compare grader changes without mistaking abstention for correction

`aau grader-compare` answers a different question from a single grader audit: **which judgments
changed when the grader changed?** Both sides use the same approved rubric, fallible reference
labels, evidence fingerprints, and complete item/criterion census. A candidate cannot improve
its apparent agreement silently by omitting the baseline's difficult cases.

From a trusted current checkout/local wheel (not the older public PyPI release):

```bash
aau grader-compare demo --out /tmp/paired-grader-example
```

Use a new directory. Open its `README.md` and each packet's `review.html`. All examples are
constructed, offline, and key-free; no model, supplier code, transcript, or network is executed.

| Synthetic validation result | Agreement on own decided reference pairs | Decided reference-pair coverage | What the paired review preserves |
|---|---:|---:|---|
| Baseline | 4/6 | 6/8 | Two false passes |
| Corrected candidate | 6/6 | 6/8 | Both errors corrected |
| Abstention trap | 4/4 | 4/8 | Both errors become abstentions, **not** corrections |
| Omission trap | 4/4 | 4/8 | Both errors become missing judgments, **not** corrections |
| Net gain with regression | 5/6 | 6/8 | Two corrections **and one new false failure** |

The remaining two references are disputed/unreviewed, not errors or successes. The examples do
not establish that abstention is bad: appropriate escalation may be desirable, but it is a
different outcome from correcting a judgment and requires its own capacity/quality evidence.

For your already authorized recorded evidence, reuse the exact
[grader-review input contracts](#audit-the-grader-before-trusting-its-scores):

```bash
aau grader-compare create approved-plan.json reference.json baseline-judgments.json candidate-judgments.json \
  --plan-sha256 INDEPENDENTLY_RETAINED_PLAN_BYTE_HASH \
  --baseline-sha256 INDEPENDENTLY_RETAINED_BASELINE_BYTE_HASH \
  --out paired-review
aau grader-compare verify paired-review \
  --plan-sha256 INDEPENDENTLY_RETAINED_PLAN_BYTE_HASH \
  --baseline-sha256 INDEPENDENTLY_RETAINED_BASELINE_BYTE_HASH
```

Replace both placeholders with independently reviewed SHA-256 hashes of the exact file bytes.
Do not trust pins supplied only alongside candidate evidence. The existing plan pins the reference
bytes, rubric fingerprint, item fingerprints, partition assignments, and groups. The additional
baseline pin prevents substituting a weaker baseline. Pins prove byte agreement, not who approved
the study or whether it preceded tuning. Same grader IDs are allowed and are not identity proof.

The **seven-file packet** retains `plan.json`, `reference.json`, `baseline.json`, and `candidate.json`
byte-for-byte, plus recomputed `review.json`, script-free `review.html`, and `manifest.json`.
Verification reconstructs every derived byte from originals and both external pins; changing a
manifest does not make altered evidence acceptable. Existing destinations, unexpected members,
symlinks, malformed contracts, duplicate/outside-census rows, rubric mismatches, and changed
fingerprints are rejected. Missing judgment rows remain `missing` and never shrink the census.
Unknown reference labels remain explicit. Numeric scores are not silently converted to labels.

Each calibration/validation × criterion × group scope contains:

- Separate existing baseline/candidate confusion matrices, exact numerators/denominators, and coverage.
- A complete reference × baseline-verdict × candidate-verdict transition table in JSON, including
  `pass`, `fail`, `abstain`, and `missing` on each side. The HTML presents change counts and all paired cases.
- Counts for unchanged judgments, wrong-to-right, right-to-wrong, either-to-undecided,
  undecided-to-either, changed undecided states, and unresolved references. “Wrong” and “right”
  mean disagreement/agreement with supplied labels, not established truth. “Unchanged” is not “correct.”
- Agreement for both graders on the **same common decided pairs**, next to that subset's coverage
  of all planned items. Empty denominators are null/undefined, never perfect scores.

All original grader-review bounds remain: 1–500 declared items, 1–10 criteria, at most 19 additional
groups, and 2 MB per input/generated member. Expanded reports also have a 2 MB bound. These are
engineering limits, not recommended study sizes. Overlapping groups, multiple criteria, and repeated
use of a benchmark do not create independent samples. No pooled headline, p-value, confidence interval,
ranking, or automatic deployment verdict is produced. A selected common-decided subset may still be
unrepresentative; do not use it to conceal lost coverage. Changed rubrics/reference sets require a
separate study, not forced pairing under this contract.

Exit **0** means a descriptive diagnostic was computed/verified, including for all negative examples;
exit **2** means invalid input, pins, output, or packet. This is deliberately **not a CI acceptance gate**.
Raw evidence can be sensitive. Keep originals and a matching trusted harness, protect held-out data
from tuning teams, and obtain permission before sharing. Hashes do not authenticate execution,
validate reference expertise, or prove independent/representative sampling.

Research checked November 19, 2026: [Anthropic's agent-evaluation guidance](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
recommends checking model graders against expert judgments and allowing uncertainty rather than
forcing unsupported decisions. [NIST AI RMF 1.0, MEASURE 1.2 and 2.1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)
addresses reassessment of metrics and documentation of test sets/tools. Our inference is that
paired error/coverage accounting helps reviewers inspect a changed measurement tool; these sources
do not prescribe this algorithm or endorse the repository. Independent reproduction, expert reference
validation, statistical study design, and authorized user studies remain necessary for broader claims.

### Preserve reviewer disagreement before exporting reference labels

`aau reference-review` builds a source-retaining **reference-label review packet** from recorded
panel ratings and explicit adjudications. It connects human-label provenance to the existing
`grader-review` workflow. It does not collect ratings, contact reviewers, call models, or establish
that any reviewer is qualified, independent, or even a distinct person.

Try the installed, no-key walkthrough from a trusted current checkout/local wheel:

```bash
aau reference-review demo --out /tmp/my-reference-review
```

Open `/tmp/my-reference-review/packet/review.html` locally and read the generated `README.md`.
The 11-file demo has an eight-file packet, a constructed all-pass grader, its downstream diagnostic,
and exact replay commands. It uses no real participants or private evidence. These commands require
the current checkout/local wheel, not the older public PyPI release.

| Recorded panel | Reference before any adjudication |
|---|---|
| Every assigned rater submits `pass` | `pass`, still a fallible declared reference |
| Every assigned rater submits `fail` | `fail`, still a fallible declared reference |
| At least one `pass` and one `fail` | `disputed`, regardless of majority or remaining missing ratings |
| No conflict, but a rating is missing or a rater abstains | `unreviewed`, not partial consensus |

This is a deliberately bounded repository protocol, **not a government-required adjudication rule**.
An adjudicator may explicitly retain or change the reference only when all assigned ratings are
present, including recorded abstentions. Every decision requires a rationale and a declared separate
adjudicator ID. It binds the exact rating-file bytes. Changed ratings, even changed whitespace or a
revised reason, require a newly bound adjudication document. This prevents silent reuse of a stale
decision; it does not prove chronology, authentic authorship, expertise, or that evidence was read.
Original ratings, reasons, conflicts, and the pre-adjudication reference remain in the report.

The demo includes a two-to-one disagreement, incomplete review, abstention, and an adjudicated
conflict. Its validation partition retains two original conflicts even after one is adjudicated;
only two of five validation references are decided. The downstream all-pass grader therefore has
two false passes on decided validation references, not five automatically accepted cases.

The three inputs have closed contracts:

- **Plan:** `plan_version: "aau-reference-review-plan/1.0"`, `rubric_sha256`, `reference_basis`,
  `criteria`, `items`, `groups`, `raters`, and `adjudicators`. The rubric, items, splits, groups,
  and basis follow the [grader plan](#audit-the-grader-before-trusting-its-scores) contract.
  Each item has `item_id`, `evidence_sha256`, and `split` (`calibration` or `validation`).
  Declare 2–10 unique rater IDs and 1–10 unique, disjoint adjudicator IDs. Every rater is assigned
  every item/criterion pair; there is no per-item assignment inference. Use pseudonymous role IDs,
  not personal names. Maximum 500 items, 10 criteria, 19 named groups, and 10,000 assigned ratings.
- **Ratings:** `format_version: "aau-reference-ratings/1.0"`, matching `rubric_sha256`, and `rows`.
  Every row has exactly `item_id`, `criterion`, `evidence_sha256`, `rater_id`, `verdict`, and
  `rationale`. Verdicts are `pass`, `fail`, or `abstain`. Missing submissions are omitted, never
  invented as votes. Submitted rationales must be nonblank text of at most 1,000 characters.
- **Adjudications:** `format_version: "aau-reference-adjudications/1.0"`, matching `rubric_sha256`,
  `ratings_sha256` (the raw rating-file hash), and `rows`. Every row has exactly `item_id`,
  `criterion`, `evidence_sha256`, `adjudicator_id`, `verdict`, and `rationale`. Verdicts may be
  `pass`, `fail`, `disputed`, or `unreviewed`; the rationale has the same limit. Only one decision
  per item/criterion pair is allowed. Use an empty `rows` list if there are no adjudications;
  its document still binds the rating-file snapshot.

Unplanned/duplicate ratings, duplicate evidence fingerprints, unknown roles, overlapping role IDs,
changed rubric/evidence hashes, competing adjudications, incomplete-panel adjudication, duplicate
JSON keys, and nonfinite JSON values are rejected. Every input and output member is limited to
2 MB, including the expanded HTML. Invalid inputs fail before the destination is created.

```bash
# Obtain this raw-file hash through the receiving team's independent review channel.
aau reference-review create plan.json ratings.json adjudications.json \
  --plan-sha256 "$APPROVED_REFERENCE_PLAN_SHA256" --out /tmp/reference-packet
aau reference-review verify /tmp/reference-packet --plan-sha256 "$APPROVED_REFERENCE_PLAN_SHA256"

# Review and independently retain the generated grader-plan hash before accepting grader results.
aau grader-review /tmp/reference-packet/grader-plan.json /tmp/reference-packet/reference.json judgments.json \
  --plan-sha256 "$APPROVED_GRADER_PLAN_SHA256" --out /tmp/grader-diagnostic.json
```

The packet has `plan.json`, `ratings.json`, `adjudications.json` (all retained byte-for-byte),
`reference.json`, `grader-plan.json`, `review.json`, `review.html`, and `manifest.json`.
`reference.json` covers the complete planned item/criterion census in the existing
`aau-grader-reference/1.0` format; `grader-plan.json` binds its exact bytes. Keep the whole packet:
the exported reference alone does not preserve individual reasons or disagreement history.

Verification captures the exact regular-file inventory and recomputes all derived bytes, including
HTML; merely updating manifest hashes does not repair changed evidence. `review.html` is script-free,
has labeled tables, and escapes supplied text; these properties are not accessibility certification.
The report separates calibration/validation, criteria, and groups, retaining exact submitted/assigned
rating coverage and reference-state counts. Empty-scope ratios are undefined, not perfect agreement;
overlapping groups must not be pooled. No kappa, population inference, or reviewer ranking is inferred.

Exit `0` means a valid packet, including disputed/unreviewed references;
exit `2` means invalid input, a pin mismatch, unsupported inventory, or a packet that does not replay.
Use new output paths. Use this packet's `reference-review verify`, not the generic `inspect-pack`
dispatcher. **A valid packet is not verified truth or approval.** Blinding, holdout protection,
evidence authenticity, reviewer competence, and actual label correctness remain human responsibilities.
Full reasons and fingerprints may be sensitive; this is not a sanitized sharing artifact.

Research checked November 19, 2026: [NIST AI RMF 1.0's validity discussion](https://airc.nist.gov/airmf-resources/airmf/3-sec-characteristics/)
emphasizes documented test methodology and realistic test sets; [GAO's 2021 accountability framework](https://www.gao.gov/products/gao-21-519sp)
organizes oversight around governance, data, performance, and monitoring.
[Anthropic's evaluation guide](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
describes human calibration and the need to reconcile rater disagreements. Our inference is that
retaining disagreement and adjudication provenance helps make reference-label review reproducible.
None of these sources endorses this protocol or demonstrates this repository's effectiveness.

### Audit the grader before trusting its scores

An automated judge can accept an unsafe action, reject a legitimate solution, or produce a
high agreement score by answering only easy cases. **`aau grader-review` audits the recorded
judge, not the agent.** It compares binary judgments against supplied reference labels and
keeps the difficult, disputed, abstained, and missing cases visible. It does not call a model.

Start with four constructed examples from a **trusted current checkout or local wheel**;
this feature is not in the older published PyPI release:

```bash
pip install -e harness
aau grader-demo --out /tmp/my-grader-review
```

Read `/tmp/my-grader-review/README.md` for exact results and replay commands. The generated
11-file directory contains one shared plan/reference pair, four judgment files, four reports,
and the guide. All labels and fingerprints are synthetic; no expert study is claimed.

| Example | What to notice in validation |
|---|---|
| `exact-on-decided` | 6/6 agreement on decided pairs; two unresolved references still need review |
| `group-blind` | 4/6 agreement overall; both assisted-channel failures receive a false pass |
| `sparse` | 1/1 agreement, but only 1/8 planned pairs have both decisions; seven judgments are missing |
| `abstaining` | No paired decisions: agreement is undefined, not perfect |

For your own data, keep the rubric and underlying evidence in a separate controlled location.
Have qualified reviewers label each planned item/criterion pair without seeing the candidate
grader output where feasible. Retain genuine disagreement as `disputed` and unfinished review
as `unreviewed`; do not manufacture consensus. Decide calibration/validation membership before
tuning and keep validation references out of the grader's inputs. This command does **not**
enforce blinding, label secrecy, reviewer independence, or statistical independence.

The three input files have closed, versioned contracts. Obtain `APPROVED_PLAN_SHA256` through
your independently controlled review channel; do not derive the approval pin from a candidate's
replacement plan at the time you accept its results.

```bash
aau grader-review plan.json reference.json judgments.json \
  --plan-sha256 "$APPROVED_PLAN_SHA256" --out grader-report.json
aau grader-review plan.json reference.json judgments.json \
  --plan-sha256 "$APPROVED_PLAN_SHA256" --verify grader-report.json
```

**Plan:** exact fields `plan_version: "aau-grader-review-plan/1.0"`, `rubric_sha256`,
`reference_sha256` (hash of the exact reference-file bytes), `reference_basis` (nonempty account
of how references were produced), `criteria`, `items`, and `groups`. Each item has exactly
`item_id`, `evidence_sha256`, and `split` (`calibration` or `validation`). Each group has exactly
`group_id` and `item_ids`. Groups may overlap; `overall` is reserved. Use the generated plan
as an editable example, not as an independently approved production plan.

**Reference:** exact fields `format_version: "aau-grader-reference/1.0"`, `rubric_sha256`,
and `rows`. Every planned item × criterion must have exactly one row containing `item_id`,
`criterion`, `evidence_sha256`, and `verdict` (`pass`, `fail`, `disputed`, or `unreviewed`).
There is no default reference verdict, and incomplete reference coverage is rejected.

**Judgments:** exact fields `format_version: "aau-grader-judgments/1.0"`, `rubric_sha256`,
`grader_id`, and `rows`. Each row has the same four fields as a reference row, but verdicts
are `pass`, `fail`, or `abstain`. Omitted rows become **missing judgments**, never dropped
denominators or correct abstentions. An empty judgment list is allowed and reports zero coverage.
Duplicate/unknown pairs, numeric/free-text verdicts, and mismatched rubric/evidence fingerprints
are rejected. No native Inspect, LangSmith, or other provider export is parsed automatically:
explicitly map recorded binary labels into this contract and retain the original export.

IDs use 1–120 ASCII letters/digits, dot, underscore, or hyphen, starting with a letter/digit.
Limits: 1–500 items, 1–10 criteria, up to 19 groups, 2,000 characters for `reference_basis`,
and 2 MB per input/report. Hashes are lowercase SHA-256. Duplicate evidence hashes are
rejected even under different IDs or splits. This detects declared byte-identical reuse,
**not semantic duplicates, training contamination, or genuine held-out sampling**. Matching
hashes are not verification of original transcripts/rubric content: the command does not read them.

For every split × criterion × group, reports retain a 4-by-4 reference/judgment count matrix,
false-pass/failure counts, ungraded reference failures/successes, and six ratios. Each ratio
includes its numerator and denominator; a zero denominator yields `null`:

- Reference coverage: decided references / all planned pairs in that scope.
- Grader decision coverage: pass/fail judgments / all planned pairs.
- Paired coverage: both sides decided / all planned pairs.
- Agreement: equal labels / pairs with both sides decided.
- False-pass fraction: reference-fail/grader-pass / reference-fail pairs with a grader decision.
- False-failure fraction: reference-pass/grader-fail / reference-pass pairs with a grader decision.

Read coverage alongside agreement/error fractions. Abstentions and missing judgments are not
silently counted as correct or incorrect. The complete `observations` array lists review reasons
for every disagreement or unknown; `review_item_count` counts item/criterion pairs needing
review, not distinct people. Calibration and validation are never pooled, nor are criteria or
overlapping groups. Empty split/group cells remain explicit. There are no population bounds,
chance-corrected agreement claims, automatic grader selection, or pass thresholds.

Exit **0** means a valid diagnostic, including false passes and no judgments; **2** means invalid
inputs/output or a report that does not recompute. Existing output files are never overwritten.
Verification recomputes the full report and compares exact rendered bytes. Retain all inputs,
the original evidence/rubric, and a matching trusted harness. Hashes establish byte bindings,
not label correctness, real-world safety, authority, or disclosure permission.

This workflow applies the grader-validation and transcript-review practices described by
[Anthropic](https://www.anthropic.com/research/demystifying-evals-for-ai-agents), and the separation
of generation from scoring documented by [Inspect](https://inspect.aisi.org.uk/scoring-workflow.html).
It is not an integration with or endorsement from either project. See the
[research and adoption roadmap](../RESEARCH_AND_ADOPTION.md) for the remaining evidence gaps.

### Hand off a readable source-retaining queue review

`aau queue-pack` retains the complete finite-queue evidence in one new directory and adds a
**script-free, offline review page**. It shows simulated waiting/in-service occupancy as a step
timeline, with exact-value tables, every referral, unscheduled work, unknown deadlines, and original
automation-path failures. A simulated service interval is never presented as measured human resolution.

```bash
aau queue-pack create approved-queue-plan.json approved-routing-plan.json complete-evaluation.json work-items.json \
  --queue-plan-sha256 "$APPROVED_QUEUE_PLAN_SHA256" --out queue-review
aau queue-pack verify queue-review --queue-plan-sha256 "$APPROVED_QUEUE_PLAN_SHA256"
```

Verify first, then open `queue-review/review.html`. Obtain the expected queue-plan hash independently
from the reviewer-controlled channel, **not from the delivered folder**. It also binds the original
routing-plan bytes and selected declared threshold. The specialized verifier repeats full routing
and queue replay and compares all eight members; a rehashed manifest cannot approve edited data,
HTML, or favorable counts. This format deliberately requires `queue-pack verify` with that pin;
it is not one of the generic `inspect-pack` families.

| Retained member | Purpose |
|---|---|
| `queue-plan.json`, `routing-plan.json` | Exact supplied control bytes, including original formatting |
| `evaluation.json`, `work-items.json` | Full parsed source values, reserialized without dropping fields |
| `report.json` | Complete queue report and nested routing evidence |
| `review.html` | Offline chart, exact tables, source links, and limitations |
| `README.txt` | Verification and disclosure-review instructions |
| `manifest.json` | Recomputable file and presentation-implementation hashes, not signatures |

The [queue walkthrough](#replay-a-finite-review-queue-without-inventing-human-capacity) now creates and
verifies five complete `*-pack` folders as well as the original JSON reports. All examples remain
constructed; no real human review or staffing study is claimed. The page uses no JavaScript,
analytics, remote fonts, or external assets. Its solid/dashed paths have text descriptions and an
exact timeline table; counts are reported after all events at the same second, not linearly interpolated.
Small screens can scroll the labeled tables, and print styles are included.

**Exit 0 verifies a diagnostic even when jobs are blocked or deadlines fail.** It is not a successful
review outcome, staffing recommendation, compliance finding, or deployment gate. Each member is
bounded to 2 MB; links, special files, extra files/directories, missing members, and overwriting an
existing destination are rejected. Every source remains included and may disclose sensitive data:
this is not sanitization or permission to share. Use a matching trusted checkout/local wheel and
retain the complete pack; the HTML cannot verify itself. No model, adapter, human action, subprocess,
upload, or network call is executed by this command.

### Check operating budgets without hiding a slow or expensive group

`aau operating-budget` checks explicit limits on the recorded workload and up to 20 declared
groups. Every limit is non-compensating: an inexpensive routine route cannot offset an expensive
specialist route. The command does not infer production traffic, recommend thresholds, or certify
an SLO. It requires the current checkout or a locally built wheel, not published PyPI 1.6.0.

Try the constructed 20-scenario, four-repeat example:

```bash
python harness/examples/evaluation-review/operating_budget.py --out /tmp/aau-budget-demo
aau operating-budget /tmp/aau-budget-demo/budget.json /tmp/aau-budget-demo/aggregate-trap.json \
  --cost-basis synthetic --verify /tmp/aau-budget-demo/aggregate-trap-budget.json
# Expected exit 1: verified evidence of failed group limits, not broken verification.
aau operating-budget /tmp/aau-budget-demo/budget.json /tmp/aau-budget-demo/repaired.json \
  --cost-basis synthetic --verify /tmp/aau-budget-demo/repaired-budget.json
# Expected exit 0: every declared recorded limit met.
aau candidate-matrix verify /tmp/aau-budget-demo/matrix
```

The synthetic aggregate has a $0.495 cost per jointly passing attempt and a 1-second nearest-rank
p95. Both meet the example's $0.50 and 2-second limits. But its specialist group costs $8 per
passing attempt and takes 30 seconds. That group fails; the candidate is excluded from the
budget-aware matrix even though every task-completion policy check passes. Open the generated
`matrix/matrix.html`, then follow the budget-report links for every scope and check. These are
constructed values, not measured improvements, real service performance, or recommended budgets.

A plan has exactly these fields (replace the illustrative IDs, criteria, and thresholds):

```json
{
  "plan_version": "aau-operating-budget/1.0",
  "scenario_ids": ["routine", "specialist"],
  "minimum_repeats": 4,
  "criteria": [{"metric": "completion", "direction": "higher", "limit": 1}],
  "cost_basis": "estimate",
  "limits": {"cost_per_passing_attempt_usd": 0.5, "p95_latency_s": 2},
  "groups": [
    {"group_id": "routine", "scenario_ids": ["routine"], "limits": {"p95_latency_s": 2}},
    {"group_id": "specialist", "scenario_ids": ["specialist"], "limits": {"p95_latency_s": 2}}
  ]
}
```

```bash
aau operating-budget budget.json evaluation.json --cost-basis estimate --out budget-review.json
aau operating-budget budget.json evaluation.json --cost-basis estimate --verify budget-review.json
```

Supported inclusive upper limits are `total_cost_usd`, `cost_per_passing_attempt_usd`,
`p95_latency_s`, `max_latency_s`, and `total_api_calls`. Select at least one overall and at least
one per group; omitted measures are not checked. Limits must be finite and nonnegative; API-call
limits are integers. Costs include failed attempts. Passing attempts satisfy all supplied
criteria on the same observation; these criteria are an accounting denominator, **not a quality
gate**. Run a separate policy review or use the integrated matrix below.

The exact declared scenario census and valid complete repeat records are required. `groups: []`
checks only the overall workload. If groups are supplied, they must cover every scenario and
may overlap; their totals must not be added. Membership is declared, not inferred from personal
attributes. Scopes use equal recorded attempts, not population or production-traffic weights.
P95 uses sorted latency at one-based `ceil(0.95 × attempts)`; small samples often yield the maximum.
An overall percentile can hide a small group, and even a group's p95 can hide its slowest attempts;
choose a separate `max_latency_s` limit where that distinction matters.

Every check reports `met`, `exceeded`, or `not_verified`. Missing measurements, an undefined
zero-success unit cost, or a mismatched declared cost basis cannot pass the affected check.
The CLI cost-basis declaration must match the plan's `estimate`, `charge`, or `synthetic` basis
for cost checks; it does not verify invoices. Too few repeats or inconsistent saved metric
summaries also prevent a passing report. Known exceedances take precedence in overall status,
but **all** unverified checks remain visible. No complete-case substitution or zero imputation.

Exit **0** means every recorded check and prerequisite is met; **1** means at least one failed
or is not verified, with the report retained; **2** means malformed input, an existing output,
or a report that fails recomputation. Verification uses the original plan and evaluation and
returns the same outcome code. Keep those inputs with the report. Reports are bounded to 2 MB
and contain unsanitized scenario IDs and source-audit details; inspect before sharing.

For a portable multi-candidate review, change the matrix plan to `aau-candidate-matrix/1.1`
and add `operating_budget` containing the entire budget plan above. Its joint criteria must
match the matrix criteria. Every candidate receives a recomputed `candidate-NN-budget.json`;
failed **or unverified** budgets exclude it from the operating comparison alongside existing
policy and coverage gates. The resulting pack has **6 + 4 × candidate count** files. Version 1.0
plans retain their existing behavior and byte layout. Matrix exit 0 still means descriptive
pack verification, **not** that candidates passed their budgets; inspect the reports or run
`operating-budget` for a failing gate exit code.

This design is motivated by [Google SRE's guidance on distributions and aggregation](https://sre.google/sre-book/service-level-objectives/)
and [FinOps unit-economics guidance](https://www.finops.org/framework/capabilities/unit-economics/).
The implementation checks declared offline measurements; it is not production SLO monitoring,
fully loaded cost accounting, forecast accuracy, fairness certification, or deployment approval.

### Enforce policy and operating limits in one reviewer dossier

First, [try the public operating-budget lab](https://immu4989.github.io/awesome-agentic-usecases/evaluation-review/budget-lab.html):
inspect the complete synthetic trap, repaired twin, and candidate matrix in your browser, then
download their 14-file packs for offline verification. No API key or model call is required.

Use `--operating-budget` with `evaluation-pack create`, `evaluation-pack from-recordings`,
or `csv-review create` to produce a **combined failing gate**, not just descriptive cost views.
A diagnostics plan is required; its candidate cost-basis declaration supplies the budget check's
declared basis, and its joint-pass criteria must match the budget. Missing required measurement
coverage or a cost-basis mismatch does not pass. Baseline operating evidence remains descriptive;
only the candidate's budget is gated. Quality policy and budget thresholds are independent.

```bash
aau evaluation-pack create policy.json baseline.json candidate.json \
  --diagnostics diagnostics.json --operating-budget budget.json --out gated-review
aau evaluation-pack verify gated-review --require-budget

# Original recorded observations, with the import chain retained:
aau evaluation-pack from-recordings policy.json baseline-recording.json candidate-recording.json \
  --diagnostics diagnostics.json --operating-budget budget.json --out gated-recordings
aau evaluation-pack verify gated-recordings --require-recordings --require-budget

# Scored CSV exports, with both original byte streams retained:
aau csv-review create policy.json baseline-map.json baseline.csv candidate-map.json candidate.csv \
  --diagnostics diagnostics.json --operating-budget budget.json --out gated-csv
aau csv-review verify gated-csv --require-budget
```

Budget-gated dossiers use pack version `aau-evaluation-review-pack/3.0` and contain three extra
files: `operating-budget.json`, `candidate-budget.json`, and `gate.json`. `review.json` remains
the unmodified **policy** review. The gate binds the candidate, diagnostic plan, budget plan,
policy report, and budget report by source-value hashes. Its status is `constraints_met` only
when both independent reviews meet their constraints; a known failure gives `constraints_not_met`,
otherwise unknown budget evidence gives `constraints_not_verified`. All findings remain retained.
The HTML headline reports the combined result and shows both separate verdicts and operating checks.

Keep all **14 normalized dossier files**, **16 recording dossier files**, or **31 CSV handoff
files**. CSV budget handoffs use `aau-csv-evaluation-handoff-pack/1.1`; their inner dossier is
version 3.0. Verification recomputes the complete source-to-gate chain and every HTML byte, not
just hashes. Python `create_pack`, `pack_payloads`, and `verify_pack` return the combined gate
report when an operating budget is present; otherwise they keep returning the policy report.
In CSV mode, the handoff report carries the combined status and both independent status labels.

For **both creation and verification**, exit 0 means all combined constraints are met, exit 1
means at least one failed or was not verified (with evidence retained), and exit 2 means invalid
input or verification failure. `--require-budget` refuses an otherwise valid legacy pack that
omits the gate. It implies the presence of diagnostics; add `--require-recordings` when that
source format is also mandatory. Without a budget argument, existing formats and outcomes remain
unchanged. Matching context is still required by the Action; the descriptive CLI does not invent
missing legacy context or authenticate measurements.

The synthetic `operating_budget.py` example above also creates `aggregate-trap-dossier` and
`repaired-dossier`. Verify them with `aau evaluation-pack verify PATH --require-budget`:
the first exits 1 despite a passing quality-policy review, and the second exits 0. Open their
`review.html` pages to inspect the combined outcomes and every declared group check without
installing a server or making model calls.

The [saved evaluation Action](../.github/actions/aau-evaluation-review/#require-an-independently-approved-candidate-operating-budget)
supports an independently pinned `operating-budget` in all three input formats. Protect both
its **exact-byte approval hash** and the workflow inputs outside candidate-controlled changes.
Do not generate the approval pin from the candidate file in the same production job. JSON pack
members are reserialized values, not original whitespace; preserve original approved JSON files
for independent byte-pin checks. CSV originals remain byte-exact. Nothing is uploaded automatically.
All source details remain unsanitized, and a passing combined gate is not deployment approval.

### Review operating-budget changes before approving replacement limits

`aau compare-operating-budgets` compares two valid budget plans before an accountable reviewer
approves a replacement. It does not run an evaluation, change an approval pin, or infer that
an agent improved because a new plan passes. Requires the current checkout or locally built
wheel, not published PyPI 1.6.0.

```bash
aau compare-operating-budgets approved-budget.json proposed-budget.json --out budget-changes.json
aau compare-operating-budgets approved-budget.json proposed-budget.json --verify budget-changes.json
```

The report includes exact before/after values for:

- Raised, lowered, added, and removed upper limits, globally and for each named group.
- Added/removed groups, renamed groups as a removal plus addition, and changed scenario membership.
- Changed minimum repeats, cost-basis declarations, and **every** joint-pass criterion change.

A criterion edit changes the defined accounting unit, even when it looks like a stricter
quality rule. Added cases can dilute ratios or move percentiles. Raised/lowered labels describe
the numeric threshold only, not net plan strength when other assumptions also change. Removed
obligations remain visible even if another group covers the same scenarios; tighter limits
elsewhere never cancel them from the report. Groups are matched by exact ID, not inferred meaning.

Try two controlled counterexamples:

```bash
python harness/examples/evaluation-review/budget_changes.py --out /tmp/aau-budget-changes
aau compare-operating-budgets /tmp/aau-budget-changes/denominator-before.json \
  /tmp/aau-budget-changes/denominator-after.json \
  --verify /tmp/aau-budget-changes/denominator-changes.json
# Expected exit 1: the definition changed; no evaluation observations changed.
aau compare-operating-budgets /tmp/aau-budget-changes/removed-group-before.json \
  /tmp/aau-budget-changes/removed-group-after.json \
  --verify /tmp/aau-budget-changes/removed-group-changes.json
# Expected exit 1: a named group obligation was removed.
```

| Same synthetic evaluation | Plan edit | Apparent result |
|---|---|---|
| Four $0.10 attempts, only one meets the original authorization criterion | Permit the recorded unauthorized attempts in the accounting criterion | Unit cost changes from $0.40 to $0.10; the budget now passes |
| Overall unit-cost limit passes, but a stricter group limit fails | Remove that group | The budget now passes with exactly the same scores and costs |

Neither result is an agent repair, verified saving, or a reason to waive authorization. Keep the
independent quality-policy review; the combined gate still requires it. The fixture writes both
plans, both budget assessments, and a recomputable change report for each example, alongside the
single unchanged evaluation.

Exit **1** means any enumerated obligation or assumption changed and requires review—including
added groups, lower limits, and higher minimum repeats. Exit **0** means no such change was
detected, **not approval or equivalent acceptance sets proved**. List/dictionary ordering and
numerically equal limits are ignored as obligation changes; source-value hashes still identify
the supplied plans. Exit **2** means invalid plans, an existing output, an oversized report, or
failed recomputation. Verification uses the original two plans and returns the same outcome code.

Reports retain unsanitized plan labels and limits; inspect before sharing. JSON value hashes are
not the exact-file byte pins required by CI. Review the complete plans and change report, then
approve any replacement pin through your independently controlled process. This command never
updates files, repository variables, workflow settings, or approval records on your behalf.

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

### Quantify what zero observed failures can support

`aau failure-bound-eval` separates **observed benchmark outcomes** from **conditional population
bounds**. It answers a different question from the policy and repeatability tools: is an apparently
perfect result still too small to support the declared failure-probability limit, under explicitly
supplied sampling assumptions? It never changes a policy verdict or approves deployment.

```bash
# Current repository checkout; these commands do not collect data or call a model.
python harness/examples/evaluation-review/failure_bounds.py --out /tmp/aau-failure-bounds
aau failure-bound-eval /tmp/aau-failure-bounds/few-scenarios/plan.json \
  /tmp/aau-failure-bounds/few-scenarios/evaluation.json --out /tmp/few-scenarios-review.json
aau failure-bound-eval /tmp/aau-failure-bounds/few-scenarios/plan.json \
  /tmp/aau-failure-bounds/few-scenarios/evaluation.json --verify /tmp/few-scenarios-review.json
```

The example emits four synthetic contrasts, with all supplied criteria passing on every repeat:

| Constructed evidence | What the diagnostic reports |
| --- | --- |
| 20 fixed benchmark scenarios, four repeats each | Population inference withheld; a benchmark is not automatically a random sample |
| 20 scenarios, four repeats, hypothetical IID fixed-horizon design | About 13.9% one-sided upper failure bound at 95% confidence; 80 observations are not 80 sampling units |
| 60 scenarios with that same hypothetical design | About 4.87% upper bound, below the illustrative 5% target |
| 100 scenarios, including a ten-scenario assisted-channel group | Overall conditional bound meets 5%; the small group's bound exceeds it after family adjustment |

These are arithmetic examples, **not sampled users, measured agent improvements, or actual evidence
of production reliability**. Their IID declarations are hypothetical. Do not copy them into a pilot.

A plan declares this complete contract; replace the IDs, criteria, limits, and sampling basis with
independently reviewed inputs before collection, not after seeing results:

```json
{
  "plan_version": "aau-failure-bound-plan/1.0",
  "scenario_ids": ["case-a", "case-b"],
  "n_repeats": 4,
  "criteria": [
    {"metric": "completion", "direction": "higher", "limit": 1},
    {"metric": "unauthorized", "direction": "lower", "limit": 0}
  ],
  "sampling_design": "fixed_benchmark",
  "sampling_basis": "Two deliberately selected challenge cases; not an IID sample.",
  "confidence_level": 0.95,
  "maximum_failure_probability": 0.05,
  "groups": [
    {"group_id": "assisted-channel", "scenario_ids": ["case-b"], "maximum_failure_probability": 0.05}
  ]
}
```

The evaluation must contain exactly the planned scenarios and repeat count. **One statistical unit
is the entire scenario bundle**: any criterion failure on any repeat fails that bundle. Later success
cannot erase an earlier failure, and extra repeats do not increase the sampling-unit count. The
quantity being bounded is failure of this repeat protocol, not failure of an individual API call.
Every selected metric must be measured on every repeat; missing data is an error, not a passing row.
Unselected metrics and stored-summary inconsistencies remain visible.
Plans support 1–10 criteria, up to 19 named groups plus the mandatory overall scope, confidence
levels from 0.5 through 0.999999, and failure limits from zero up to but not including one.

`fixed_benchmark` withholds every population bound. Only the explicit
`declared_iid_fixed_horizon` mode computes one-sided Clopper–Pearson upper limits, using
binomial-CDF inversion rather than a normal approximation. The implementation uses floating-point
arithmetic and is tested against an independent high-precision calculation.
See [NIST's exact binomial method](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).

The mandatory overall scope and every declared group form one family. Each uses tail probability
`(1 - confidence_level) / family_size`. This Bonferroni adjustment also applies when groups overlap;
it does not require independence between group reports. An overall result cannot substitute for
a small group's evidence. See [NIST's Bonferroni inequality](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm).

Each scope includes a **hypothetical zero-failure planning quantity**: for a new fixed-horizon design,
how many distinct scenario bundles with no failures would be needed under those assumptions?
With one scope, 95% confidence, and a 1% limit, the calculation gives 299. Zero risk has no finite
zero-failure sample; quantities above one billion are reported as outside the planning range.
These are not a prescription to keep sampling until a result passes, a way to discard existing
failures, or a power calculation for a nonzero true failure rate. Current inputs remain bounded
to 500 scenarios and 10,000 observations; a planning quantity may exceed that supported input size.

Interpretation requires IID bundles **within each scope**, stable conditions, a suitable population,
and the fixed plan/horizon chosen before outcomes. The tool verifies none of those assumptions.
Renaming duplicate cases does not create independent samples. Adaptive sampling, outcome-selected
groups, repeated peeking, optional stopping, reused benchmarks, and selecting the best of many
candidate agents are not covered by the reported confidence level. A bound is not a posterior
probability that a risk statement is true. Never use it as a substitute for service-specific
obligations, human review, or the existing quality and operating gates.

The API is `review_failure_bounds(plan, evaluation)` in `aau_harness.eval_failure_bound`.
CLI exit **0** means a diagnostic was produced or reverified, including when limits are exceeded
or inference is withheld; exit **2** means invalid input/output or a mismatching saved report.
Both input JSON-value hashes are retained, outputs are never overwritten, and reports have a 2 MB
limit. Keep the plan, evaluation, and report together. No statistical package, network, model call,
or new runtime dependency is needed. Inspect sampling notes, identifiers, and failed scores before
sharing; this is not a sanitization tool. Available in the current checkout, not a new PyPI release.

### Allocate uncertainty across preplanned cumulative looks

Repeatedly applying an ordinary single-look confidence bound is not a repeated-look procedure.
`aau planned-look-bounds` reserves uncertainty across a **finite, predeclared family of cumulative
looks and scopes**. It is a separate statistical diagnostic, not a change to existing policy gates
or to the [ordered evidence-history review](#preserve-failed-and-missing-checkpoints-across-an-evidence-history).

```bash
pip install -e harness
python harness/examples/evaluation-review/planned_looks.py --out /tmp/planned-look-example
```

The generated guide replays five constructed examples. At 60 zero-failure scenario bundles, a
single 95% fixed-look upper bound is about 4.87%; a plan reserving three looks at 20, 60, and 100
instead gives about 6.60% at the 60-bundle look. The future look is still pending and its allocation
is **not reused**. This is an arithmetic contrast, not permission to switch plans after seeing data.
The examples also retain an early failed bundle, withhold fixed-benchmark inference, and expose a
small group's insufficient evidence even when the overall conditional bound meets its limit.

The plan is a closed contract. For example, a deliberately tiny fixed benchmark could declare:

```json
{
  "plan_version": "aau-planned-look-bound-plan/1.0",
  "scenario_order": ["case-a", "case-b", "case-c", "case-d"],
  "look_sizes": [2, 4],
  "n_repeats": 2,
  "criteria": [{"metric": "completion", "direction": "higher", "limit": 1}],
  "sampling_design": "fixed_benchmark",
  "sampling_basis": "Deliberately selected challenge cases, not an IID sample.",
  "confidence_level": 0.95,
  "maximum_failure_probability": 0.05,
  "groups": []
}
```

Use actual reviewed scenario IDs, criteria, and sampling documentation. `fixed_benchmark` always
withholds population bounds. Only an explicit `declared_iid_planned_looks` declaration enables
conditional binomial bounds; the tool does **not** establish that this assumption is true.
Groups use `group_id`, `scenario_ids`, and `maximum_failure_probability`, as in the single-look
diagnostic. Every group must be a nonempty subset of the full planned census; groups may overlap.

Independently review the complete plan before outcomes, protect its exact raw-file SHA-256, and
use that independently controlled value—not a hash recomputed from a candidate-controlled plan
in the same production job:

```bash
aau planned-look-bounds approved-plan.json prefix-evaluation.json \
  --plan-sha256 "$APPROVED_LOOK_PLAN_SHA256" --out planned-look-report.json
aau planned-look-bounds approved-plan.json prefix-evaluation.json \
  --plan-sha256 "$APPROVED_LOOK_PLAN_SHA256" --verify planned-look-report.json
```

The source must contain **every scenario in an exact prefix of `scenario_order`**, with every
planned repeat and selected metric. Its scenario count must be one declared look size. Off-plan
interim counts, favorable subsets, missing repeats, extra scenarios, and changed repeat protocols
are errors, not silently filtered data. Source row order is irrelevant; the pinned plan defines
the prefix. The last planned look must equal the full horizon. A partial source is accepted at a
planned look, while all later looks stay `not_yet_observed` with no fabricated zero-failure rows.

For `L` planned looks and `G` scopes (including the mandatory overall scope), each cell uses:

```text
alpha_per_cell = (1 - confidence_level) / (L * G)
```

Each completed nonempty cell receives a one-sided Clopper–Pearson upper bound on bundle failure.
One bundle fails if any joint criterion fails on any planned repeat. Repeats never increase the
independent-unit count. Within the supplied dataset, an early failure remains in every later
applicable prefix. Empty group cells have `no_observed_bundles`, a null bound, and a null observed
failure fraction—not a zero-risk estimate. Pending and empty cells still reserve their allocation.

This applies the general [Bonferroni inequality documented by NIST](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm)
to the finite look-by-scope family. Shared cumulative data and overlapping scopes do not require
independence **between cells** for that inequality. Each marginal binomial calculation still requires
IID bundles **within its scope**, a suitable sampling population, fixed definitions/order, and stable
candidate/scorer/execution conditions. Conditional simultaneous coverage supports choosing among
these declared looks only. Added looks, extended horizons, adaptive groups, changed candidates,
reset error budgets, or selecting the best of several candidate agents are outside the family.
It is not the unrestricted time-uniform confidence sequence studied by
[Howard and colleagues](https://arxiv.org/abs/1810.08240).

Reports retain all completed and pending looks, group counts, failed bundle details, source-summary
audit findings, unreviewed metrics, and the allocation formula. The root status is diagnostic,
while `latest_completed_look` gives the latest conditional interpretation. An earlier wide bound
may narrow with more data; that does not erase harms, close an incident, or approve deployment.
Stored-summary mismatches remain visible; observations are used without rewriting their source.

Exit **0** means a valid diagnostic was produced or reverified, including exceeded limits or withheld
inference. Exit **2** means invalid inputs/pins, output errors, or a mismatching report. Outputs are
never overwritten. Limits are 500 planned bundles, 10,000 planned observations, 20 looks, 20 scopes,
and 2 MB for each input/report; there is no silent truncation. Floating-point results are checked
against high-precision binomial calculations and exact small-family outcome enumeration, not claimed
as arbitrary-precision certificates. No statistical runtime dependency, model, network, or collector
is used. Retain the plan, evaluation, and report; inspect sensitive data before sharing.

A plan pin is not proof of preregistration, authority, source authenticity, or actual acquisition
order. Earlier source exports are not compared, and the tool does not authenticate accumulated
history. Copies renamed as new scenarios do not become independent observations. Policy, operating
budgets, affected-user feedback, and human review remain separate. Available from this checkout or
its local wheel; not included in the currently documented PyPI 1.6.0 release.

### Hand off separate reviews with a receiver-pinned evidence index

`aau evidence-index` assembles a **verified delivery index, not an approval score**. A receiving
team declares which policy, paired-system, and condition-coverage packets it needs, pins their
control inputs, and explicitly binds evaluation members that must be identical across reviews.
Missing submissions, invalid packets, changed controls, and mismatched bindings stay visible.
A valid packet documenting a failed policy or a coverage gap is not confused with corrupt evidence.

```bash
aau evidence-index demo --out /tmp/my-evidence-index
```

Read the generated guide and top-level `review.html` inside each of five synthetic examples.
In `complete-with-failed-policy`, all three packets verify and share exactly the same candidate
evaluation bytes, but the policy **fails**. Paired improvement and coverage cannot cancel that
failure. Other examples retain missing coverage, a valid coverage packet for a different
evaluation, a modified derived report, and a changed receiving-team baseline pin. Nothing is
sent to an agency, model, external service, or repository. Use the current trusted checkout/local
wheel, not the older public PyPI release.

For an authorized handoff, the delivery directory contains only requested item directories:

```text
delivery/
  policy/       # complete flat evaluation-review packet
  comparison/   # complete paired-review packet
  coverage/     # complete coverage-review packet
```

```bash
aau evidence-index create approved-request.json delivery \
  --request-sha256 "$APPROVED_REQUEST_SHA256" --out delivery-index
aau evidence-index verify delivery-index --request-sha256 "$APPROVED_REQUEST_SHA256"
```

Review and protect that expected hash independently of the supplier. The exact-byte-pinned
`aau-evidence-index-request/1.0` request contains only `request_version`, `purpose`, `items`, and
`bindings`. The generated demo request is an editable contract example, **not** approval for real use.
Each required item has an `item_id`, `profile`, reviewable `purpose`, and exactly its profile's controls:

| Profile | Receiver-controlled inputs | Bindable evaluation roles |
|---|---|---|
| `policy-review` | `controls.intake_request`: a complete existing `aau-evidence-intake-request/1.0` for `evaluation-review`, including all version-required policy/baseline/diagnostic/budget pins | `baseline` → `baseline.json`; `candidate` → `candidate.json` |
| `paired-review` | `controls.plan_sha256`: independently reviewed paired-plan byte hash | `baseline` → `baseline.json`; `candidate` → `candidate.json` |
| `coverage-review` | `controls.plan_sha256`: independently reviewed coverage-plan byte hash | `evaluation` → `evaluation.json` |

The outer request pin protects the entire nested policy request; its canonical internal hash is
computed only after the outer pin is checked. No control pin is derived from the delivered packet.
Only the three trusted installed verifiers are routed; a request cannot supply a path, module,
command, URL, fallback profile, or alternative verifier. Existing native verification requirements
remain unchanged, including required budget/diagnostic controls and context checks.

Each binding is `{ "left": { "item_id": "policy", "role": "candidate" }, "right":
{ "item_id": "coverage", "role": "evaluation" } }`. Both packets must fully verify and match
receiver controls before their exact member-byte hashes are compared. No binding means **no
association is asserted**. Baselines need not be the same: the demo explicitly separates a
historical same-configuration policy baseline from the other system in the paired comparison.
Never assume a shared identity merely because two files have the same filename or scenario labels.

Return codes concern **delivery verification only**:

- **0:** every declared packet verifies with its controls and every requested binding matches.
  Policy failure, coverage gaps, and new regressions can still be present. `decision_status` is
  always `not_assessed`; `human_review_required` is always true.
- **1:** a replayable diagnostic records missing evidence, failed verification, unmatched receiver
  controls, or mismatched/uncheckable bindings. Invalid child bytes are retained, not repaired.
- **2:** invalid request/pin, unsafe or unexpected inventory, resource limit, existing destination,
  or an index that does not replay. No verified index is claimed.

The output retains exact request bytes, complete delivered packets under `evidence/`, native
findings in `report.json`, script-free `review.html`, and a manifest covering files and directories.
An absent packet differs from an explicitly supplied empty directory. Only flat native packets
are supported: 1–6 required items, at most 60 delivered files, 20 bindings, and 2 MB per input or
expanded output member. Unknown top-level content, nesting, symlinks, special files, and unsafe
names are rejected. Original HTML and scripts are **not executed or automatically opened**; invalid
contents remain potentially unsafe to open. Keep outputs local and review all members before any
separately authorized disclosure. The index is not redaction, anonymization, or a sharing permit.

Matching bytes do not establish authentic execution, valid scoring, scientific assumptions,
complete organizational evidence, or operational suitability. Even whitespace-only serialization
changes break a binding; preserve the requested export bytes instead of silently normalizing them.
Capture is not an atomic snapshot of a concurrently changing directory. Retain the independently
controlled request pin and use the matching trusted harness for replay. No automatic acquisition,
deployment, certification, legal-compliance, or government-adoption claim follows.

Research checked November 22, 2026: [GAO's AI accountability framework](https://www.gao.gov/products/gao-21-519sp)
organizes oversight around governance, data, performance, and monitoring. [NIST's Measure guidance](https://airc.nist.gov/airmf-resources/playbook/measure/)
emphasizes documenting measurement choices and unmeasured risks; the page notes an upcoming framework
revision. Our index is a bounded documentation and source-linking workflow, not an implementation
of either entire framework or a claim of conformity. Qualified human review remains necessary.

### Compare paired systems without hiding new failures

`aau paired-review` compares **two fixed systems on the same complete scenario bundles**. It
preserves both corrected baseline failures and newly introduced candidate failures. It does not
turn a net gain or a small p-value into a purchase, deployment, or safety decision.

```bash
aau paired-review demo --out /tmp/my-paired-comparison
```

Open `net-gain-with-regression/review.html` and read the generated guide. Four no-key synthetic
packets show a net gain with an assisted-path regression, the same data as a fixed benchmark,
identical recorded outcomes, and the reversed comparison. Use the current trusted checkout/local
wheel, not the older public PyPI release. No model execution or user-data collection occurs.

The constructed example has 12 matched scenarios with two repeats each: ten improvements, one
regression, and one shared pass. Later passing repeats do not erase earlier failures. Under the
example's **hypothetical** IID declaration, the exact two-sided p-value is 0.01171875; two declared
scopes give a Bonferroni-adjusted value of 0.0234375. The assisted-path regression is still shown.
Declaring the identical cases a fixed benchmark withholds all p-values. Identical outcomes give
p = 1, not evidence of equivalence. These numbers describe constructed arithmetic, not a real system.

For separately authorized evidence, independently review and retain the exact plan-byte hash:

```bash
aau paired-review create approved-plan.json baseline.json candidate.json \
  --plan-sha256 "$APPROVED_PLAN_SHA256" --out paired-packet
aau paired-review verify paired-packet --plan-sha256 "$APPROVED_PLAN_SHA256"
```

Both commands return 0 when the diagnostic recomputes—even when the candidate introduces failures.
Invalid input, a mismatched pin, an existing output, or packet tampering returns 2. Do not interpret
exit 0 as policy approval. No source is executed, repaired, filtered, or silently imputed.

The `aau-paired-candidate-plan/1.0` plan has exactly these fields (the demo provides editable examples):

- `scenario_ids`, `n_repeats`, `criteria`: 1–500 unique scenarios, at most 10,000 observations per
  system, and 1–10 joint `{metric, direction, limit}` obligations. Every metric must be present
  in every planned repeat. A bundle fails if **any** criterion fails in **any** repeat.
- `baseline`, `candidate`: each contains a distinct `candidate_id` and its `config_sha256`.
  Each input must have the corresponding evaluation context, identical planned `scenario_sha256`
  and `scoring_sha256`, and a complete matched census. Fingerprints bind declarations, not genuine
  execution, equivalence of operational conditions, scoring validity, or independent cases.
- `groups`: up to 19 `{group_id, scenario_ids}` groups, plus mandatory `overall`. Groups may
  overlap but must be nonempty, uniquely named, and contain only planned scenarios.
- `sampling_design`, `sampling_basis`: either `fixed_benchmark` (descriptive counts only) or
  `declared_iid_fixed_horizon` with an explicit reviewable explanation. The tool does not verify
  sampling, preregistration, or independence; do not relabel a convenience benchmark to obtain inference.
- `family_significance_level`: 0.000001–0.5, chosen before observing outcomes. This is an error-rate
  threshold for the declared hypothesis family, not the probability that either system is safe.

For each scope, the report retains all four transitions, failed-repeat details, signed observed
failure-rate difference (candidate minus baseline), raw p-value and family-adjusted p-value. Given
`b` improvements and `c` regressions, the exact conditional test is
`min(1, 2 * sum(comb(b+c, k), k=0..min(b,c)) / 2**(b+c))`; no discordance gives 1.
This implementation uses the exact binomial tail for every supported count, not a chi-square
approximation or mid-p. Adjusted p is `min(1, scope_count * p)`; its comparison to the declared
level uses rational arithmetic. JSON retains exact numerator/denominator strings alongside display
floats. The adjustment needs no independence between overlapping scopes, but IID paired bundles
within each scope and stable systems/scoring remain unverified assumptions. Repeats are never
treated as additional independent pairs.

The six-file packet retains original plan/baseline/candidate bytes, JSON, script-free HTML, and
a manifest; verification replays every byte with a matching trusted harness and external plan pin.
Audit mismatches and unreviewed metrics remain visible. Raw records may be sensitive: review the
whole packet before disclosure. No anonymization or permission to share is implied.

This is **not** an equivalence/noninferiority test, effect-size interval, causal experiment, ranking,
or acceptable-absolute-risk assessment. A detected difference may be practically irrelevant; a
non-detected difference may reflect low power. It does not correct for extra system comparisons,
adaptive tuning, repeated looks, benchmark reuse, or selection after seeing results. Predeclare a
broader design with qualified statistical review when those are required. Use separate absolute
risk, policy, cost, accessibility, and human-review evidence for consequential decisions.

Research checked November 22, 2026: [NIST's McNemar guidance](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/mcnemar.htm)
describes paired binary outcomes and the conditional binomial test; its
[Bonferroni discussion](https://www.itl.nist.gov/div898/handbook/prc/section4/prc463.htm)
explains the finite-family union-bound principle. [GAO's AI acquisition review](https://files.gao.gov/reports/GAO-26-107859/index.html)
motivates explicit requirements and testing proposed solutions. The paired review is our bounded
implementation choice, not a requirement prescribed by GAO or an endorsement by these sources.

### Reserve uncertainty across all planned candidates

Evaluating several systems and reporting only a favorable result is not the same experiment as
evaluating one preselected system. `aau candidate-bounds` reserves conditional uncertainty across
the **entire predeclared candidate × scope family**, including candidates whose submissions are
missing. It produces an offline source-retaining diagnostic, not a leaderboard or acquisition gate.

```bash
# Current trusted checkout/local wheel; no API keys or external execution.
aau candidate-bounds demo --out /tmp/candidate-family-example
```

The generated `README.md` includes exact verification commands and four constructed examples:

| Example | What the report preserves |
|---|---|
| `pending` | One of two planned candidates is missing; its uncertainty allocation is not reused |
| `complete` | Both submitted; the first candidate's bound is unchanged |
| `fixed-benchmark` | Perfect recorded scores do not justify population inference |
| `earlier-failure` | One early failed repeat remains a failed bundle despite later passing repeats |

In this arithmetic lesson, 60 zero-failure bundles give a one-sided upper bound near **4.87%**
for one planned candidate but **5.96%** for two candidates at hypothetical 95% simultaneous
confidence. The latter does not meet the illustrative 5% limit. Four repeats per case remain
60 bundles, not 240 independent units. No real system, population, or sampled user is represented.

For authorized recorded evaluations:

```bash
aau candidate-bounds create approved-family-plan.json submitted-evaluations \
  --plan-sha256 INDEPENDENTLY_RETAINED_PLAN_BYTE_HASH --out candidate-family-review
aau candidate-bounds verify candidate-family-review \
  --plan-sha256 INDEPENDENTLY_RETAINED_PLAN_BYTE_HASH
```

The input directory contains only `CANDIDATE_ID.json` files. Missing candidates are allowed and
explicitly reported; an empty directory means no submissions, **not** zero failures. Any supplied
file with invalid data, partial census, changed context, or missing required metrics is rejected.
Unknown files, nested folders, and symlinks are rejected. Output must be new and outside the input
directory. Replace the pin placeholder with an independently reviewed hash of the exact plan bytes.

Start from the generated plan or the existing [fixed-horizon contract](#quantify-what-zero-observed-failures-can-support).
The new plan has `plan_version: "aau-candidate-bound-plan/1.0"`, all fixed-horizon fields
(`scenario_ids`, `n_repeats`, `criteria`, `sampling_design`, `sampling_basis`, `confidence_level`,
`maximum_failure_probability`, `groups`), and these additional required controls:

| Field | Meaning |
|---|---|
| `candidates` | 1–10 entries with unique `candidate_id` and approved `config_sha256`; IDs use letters, digits, `_`, `-`, start with a letter/digit, and have at most 80 characters |
| `scenario_sha256` | Exact planned scenario ID → declared fingerprint map; duplicate fingerprints rejected |
| `scoring_sha256` | Shared named scoring-source fingerprints under the existing evaluation-context contract |

Every present evaluation must contain the exact planned `evaluation_context` for its candidate:
the shared scenario/scorer maps plus that candidate's configuration hash. Different candidate
configurations are permitted; cases, scoring definitions, criteria, and scope memberships are shared.
Identical configuration hashes are not proof that independently executed candidates exist. Do not
invent context for legacy imports: obtain authorized, correctly bound evidence instead. Fingerprints
are compared as declarations, not checked against original code or transcripts. They do not prove
execution, authentic identity, semantic diversity, or IID sampling.

For `K` candidates and `G` scopes (mandatory overall plus declared subgroups), every cell uses:

```text
tail_probability = (1 - confidence_level) / (K * G)
```

Each observed cell receives the existing one-sided Clopper–Pearson upper failure bound using this
tail probability. A scenario bundle fails if **any** declared joint criterion fails in **any** planned
repeat. Every submitted candidate needs the full planned scenario/repeat census and all criterion
measurements. Scope counts are distinct bundles within that scope. Missing candidates have null
counts/bounds, empty outcome lists, and `not_observed` status. Their allocation remains reserved.
Supplying them later does not change other candidates' results. Source-summary discrepancies remain
visible without repairing the source. The HTML exposes every candidate/scope, source audits, and
failed bundles; JSON retains full precision and every failed repeat.

Only `declared_iid_fixed_horizon` enables population bounds. Each marginal bound requires IID
bundle outcomes within that candidate/scope, stable conditions, valid scoring, and a genuinely
prospective fixed design. The general union bound permits dependence **between** candidates/scopes,
including shared cases and overlapping groups. It does not make dependent cases **within** a cell
IID. The complete family must be fixed before outcomes; pins do not establish preregistration.
`fixed_benchmark` always withholds population bounds, regardless of score or sample count.

Simultaneous coverage applies to the declared finite family. It is not a claim of conditional
coverage given a selected winner, pairwise superiority, optimality, or a posterior probability.
Unplanned candidates, adaptive tuning, benchmark reuse, extra looks, and optional stopping are
outside this method. Running it alongside `planned-look-bounds` does **not** combine the two
families into a valid candidate-by-look guarantee. No ranking or overall passing verdict is produced.

Packets retain exact `plan.json` and `candidates/CANDIDATE_ID.json` source bytes plus `report.json`,
`review.html`, and `manifest.json`. Verification recomputes derived bytes with the external plan pin.
It does not authenticate historical exports or prove that a supplier disclosed every submission;
all missing planned candidates remain visible. Keep the original packet and matching trusted harness.
Limits are 10 candidates, 500 bundles, 10,000 observations per candidate, 10 joint criteria, 20 scopes,
and 2 MB per file/report. These are resource limits, not recommended study sizes. No statistical
runtime dependency, network request, model call, or collector runs. Raw data is not sanitized.
Exit **0** means a diagnostic computed/verified, even with missing evidence or exceeded limits;
exit **2** means invalid inputs/output/pins. Neither is deployment approval. Not in the older PyPI release.

Research checked November 19, 2026: [NIST's Bonferroni discussion](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm)
states the general union-bound allocation for simultaneous coverage; its worked example is ANOVA,
not agent evaluation. [NIST's exact-binomial documentation](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm)
describes one-sided binomial limits. Our engineering application combines those ideas for this
explicit candidate-family contract. Neither source endorses this implementation or verifies its
sampling assumptions. Tests enumerate small correlated-candidate/overlapping-scope outcome families;
the shared inversion also has high-precision numerical regression tests. This is not independent
reproduction, certification, or evidence of agency adoption.

### Hand off readable failure-bound evidence

For a reviewer who should not need to inspect raw JSON, `failure-bound-pack` retains a complete
plan-to-page chain in one folder. The page separates recorded bundle failures, conditional bounds,
and withheld population inference. Its proportional charts share a 0–100% scale; exact numeric
values, every declared group, and every recorded criterion failure remain inspectable.

```bash
# Installed from the current checkout: no repository fixtures or API key needed at runtime.
aau failure-bound-demo --out /tmp/aau-failure-reviewer-demo
aau failure-bound-pack verify /tmp/aau-failure-reviewer-demo/small-group
# Open /tmp/aau-failure-reviewer-demo/small-group/review.html locally.

# For independently reviewed inputs of your own:
aau failure-bound-pack create approved-plan.json saved-evaluation.json --out new-review-folder
aau failure-bound-pack verify new-review-folder
```

The packaged walkthrough creates **four complete packs plus a guide (21 files)**. It demonstrates
fixed-benchmark inference withholding, a small perfect sample, a larger hypothetical sample, and
an overall result that hides weak evidence for a small declared group. All data is constructed;
no real reliability evidence is claimed. The existing repository example delegates to this same
implementation. Its plan/evaluation/report paths and standalone diagnostic commands still work.

Each five-file pack has one role per file:

| File | Role |
| --- | --- |
| `plan.json` | Exact supplied plan values, including criteria, scope, and sampling declarations |
| `evaluation.json` | Complete supplied evaluation values, including details not shown on the page |
| `report.json` | Recomputed bundle outcomes, conditional bounds, warnings, and source-summary audit |
| `review.html` | Script-free reviewer page with proportional charts, exact-value tables, and failure details |
| `manifest.json` | Generated member hashes and the pack format version |

The single verifier regenerates every file from the retained plan and evaluation. Merely changing
a chart or report and updating its manifest hash cannot make it verify. Missing files, unexpected
members, symlinks, oversized members, and incomplete writes are rejected. Pack creation checks all
expanded outputs before writing, never silently truncates evidence, and refuses existing paths.
The walkthrough writes its completion guide only after all four expected outcomes verify.

The page has no scripts, network assets, analytics, external fonts, or uploads. Charts have text
alternatives, tables retain full reported precision, and scrollable table regions are keyboard
focusable. Fixed-benchmark pages do not draw a population bound or a probability-limit comparison.
Percentage labels and plot widths are rounded; status always comes from the unrounded report.
Labels deliberately say **conditional numeric limit**, never deployment approval.

Run verification with a trusted matching harness before relying on received HTML: a page cannot
verify itself. Exit **0** means the diagnostic pack verifies, even when limits are exceeded or
inference is withheld. Exit **2** means invalid evidence or failed verification. This is separate
from `evaluation-pack` policy/budget gates and does not alter their verdicts.

Keep the folder intact. It is **not sanitized**: original source JSON values—including undisplayed
details—remain available. Original file formatting is not retained. Coordinated replacement of
inputs and outputs can still verify; neither hashes nor charts establish authenticity, sampling
validity, independent approval, or safety. All statistical interpretation limits in the preceding
section still apply. The commands are available from the current checkout/local wheel, not a new
PyPI release. Python APIs are `failure_bound_payloads`, `create_failure_bound_pack`, and
`verify_failure_bound_pack` in `aau_harness.eval_failure_pack`.

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
