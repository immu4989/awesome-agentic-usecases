# Publishing `aau-harness`

The package is built, checked, attested, and published without a long-lived PyPI token.
The release workflow uses PyPI Trusted Publishing and an immutable commit of the official
PyPA publishing action.

The identity is live: [`aau-harness` on PyPI](https://pypi.org/project/aau-harness/) is
published from the `pypi` GitHub environment, and the first provenance-backed distributions
were attached to the [1.1.0 GitHub release](https://github.com/immu4989/awesome-agentic-usecases/releases/tag/harness-v1.1.0).
The [latest release](https://github.com/immu4989/awesome-agentic-usecases/releases/tag/harness-v1.6.0)
adds change-specific Agent Release Gate commands, fail-closed impact coverage, protected approval
records, deterministic packs, and an experimental non-certifying OSCAL Assessment Results export.

## Trusted identity (completed)

The PyPI project trusts exactly one repository workflow identity:

1. PyPI project: `aau-harness`
2. GitHub publisher:
   - owner: `immu4989`
   - repository: `awesome-agentic-usecases`
   - workflow: `harness-release.yml`
   - environment: `pypi`
3. GitHub deployment environment: `pypi`

No API token is stored in GitHub. The workflow receives a short-lived OpenID Connect token
only in the publishing job.

## Release

Update the version in `harness/pyproject.toml`, update `CHANGELOG.md`, replace `X.Y.Z` below,
and run:

```bash
python harness/tools/check_release_version.py harness-vX.Y.Z
git tag -s harness-vX.Y.Z -m "AAU Harness X.Y.Z"
git push origin harness-vX.Y.Z
```

The tag must exactly match the package version. GitHub Actions runs all harness tests, builds
the wheel and source distribution, checks metadata, audits contents against the checkout,
tests the installed wheel outside the checkout,
creates build-provenance attestations,
publishes through the trusted PyPI identity, and attaches both distributions to a GitHub
release.

Do not push a release tag until the trusted publisher and GitHub environment exist; package
publication is intentionally fail-closed.

## Read-only package content audit

Before the installed-wheel smoke test, upload, or attestation, the release workflow now runs
[`tools/audit_package_contents.py`](tools/audit_package_contents.py). It helps maintainers and
downstream reviewers check whether the artifacts contain the first-party code and install-time
declarations they reviewed. This repository tool requires Python 3.11+ and `packaging`, which is
already a dependency of the release build tools; it adds no harness runtime dependency.

The existing `python -m build harness` command already builds a source distribution and then
builds the wheel **from that source distribution**. The new audit compares those artifacts with
the supplied checkout; it does not add a second build or claim a reproducible build.
See [PyPA's default build strategy](https://build.pypa.io/en/stable/explanation/how-it-works.html#default-build-strategy).

```bash
python -m build harness
python harness/tools/audit_package_contents.py \
  harness/dist/aau_harness-*.tar.gz harness/dist/aau_harness-*.whl \
  --out /tmp/aau-package-audit.json
python harness/tools/audit_package_contents.py \
  harness/dist/aau_harness-*.tar.gz harness/dist/aau_harness-*.whl \
  --verify /tmp/aau-package-audit.json
```

Use a new output path; existing reports are never overwritten. `--project` selects a different
trusted harness checkout. Without `--out` or `--verify`, the report is printed to standard output
(as it is in release CI). Keep audit reports **outside `harness/dist/`**, which is uploaded as
package distributions. Verification recomputes the report byte-for-byte, including raw archive
digests; repacking identical members changes those artifact digests and invalidates an old report.

| Check | What fails |
| --- | --- |
| Every checkout Python source against wheel and source archive | Missing, altered, or extra package files |
| Exact wheel payload allowlist | Additional `.pth`, `.data`, foreign-package, or unsupported metadata files, even with a valid `RECORD` |
| Source-archive packaging inputs | Changed or missing `pyproject.toml` and `README.md` |
| Package identity, Python constraints, dependencies, extras | Missing or unexpected declarations, including dependency environment markers |
| Console commands and top-level package | Missing, extra, or redirected entry points |
| Wheel `RECORD` | Incomplete coverage, duplicate entries, changed hashes or sizes |
| Bounded archive parsing | Links, special files, unsafe paths, duplicate members, malformed or oversized archives |

Exit **0** means `contents_match`; **1** retains a `contents_differ` report; **2** means invalid
or unsupported input, a mismatching saved report, or output failure. A verified difference report
still exits 1. Tests include altered modules with a freshly recomputed `RECORD`, injected
dependencies and startup files, redirected commands, archive traversal and links, and repacking.

The audit reads archives in memory; it does not extract, install, import, or execute them.
Its strict AAU profile accepts only the current pure-Python payload and five metadata members,
with SHA-256 `RECORD` entries. Other valid wheel layouts require a reviewed profile change; this
is not a generic wheel-conformance checker. The checks build on the
[PyPA wheel format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/).

Boundaries: the supplied checkout and auditor must be trusted. Matching code is not necessarily
safe code. Remaining source-archive members are hashed in the report but **not approved as build
inputs**; this is not a sandbox for arbitrary source distributions. Build and install commands
execute code separately. The report does not authenticate Git history or signatures, verify
interpreter/dependency bytes, compare independent builds, or approve publication. It records
member names and hashes, not source contents, local absolute paths, or environment values.
Signed tags, trusted publishing, provenance, tests, and installed-artifact checks remain separate.

## Installed-artifact adoption check

The release workflow must pass `tools/smoke_installed_wheel.py` before distributions are uploaded,
attested, or made available to publishing jobs. It creates a temporary Python 3.11+ virtual
environment, installs only the locally built wheel with `--no-index --no-deps`, clears inherited
Python source-path overrides, and runs from a temporary directory outside the repository.
It also checks that the imported module resolves inside that new environment.

```bash
python -m build harness
python harness/tools/audit_package_contents.py harness/dist/aau_harness-*.tar.gz harness/dist/aau_harness-*.whl
python harness/tools/smoke_installed_wheel.py harness/dist/aau_harness-*.whl
```

The check captures and re-verifies a path-free `runtime-info` source receipt from the installed
wheel. The checks cover the packaged `evaluation-demo`, fixed-benchmark inference withholding,
conditional failure-bound diagnostics, source-bound reviewer packs and all four packaged
failure-bound walkthrough contrasts, a multi-candidate matrix that excludes failed policy,
finite planned-look diagnostics with pending-look allocation, fixed-benchmark withholding, and byte-pin rejection,
contract-to-service-trace scoring with retained failures, unknown operating measurements,
downstream evaluation binding, and altered-score rejection,
complete service handoffs with strict obligation criteria, failed/unknown budget outcomes,
completion-only policy refusal, and budget-downgrade rejection,
contract-change diagnostics with identical-trace rescoring, changed-census rejection, and tamper checks,
scorer challenges with accept-all/reject-all negative controls and complete response coverage,
label-minimized service reproducers with preserved failures, removed labels, private-source checks, and tamper rejection,
unified pack intake with preserved negative outcomes, explicit expected-profile/budget requirements, and replayed inspection reports,
receiving-team intake requests with separate request-byte pins, substituted-control failures, and replayed reports,
ordered evidence histories with preserved earlier failures, missing checkpoints, invalid evidence, and latest-result separation,
CI presentation bundles with native pass/fail/invalid exits, retained historical errors, full-source replay, and tamper rejection,
recorded routing diagnostics with required/unknown human deferral, retained failures, undefined empty automation, and plan-pin rejection,
finite review-queue replay with exact referral census, waiting time, retained deadline failures, and no inferred human resolution,
source-retaining queue reviewer packs with independent control pins, offline readable HTML, and altered-presentation rejection,
packaged grader-review examples with explicit coverage gaps, separate validation results, independent reference/plan pins, and tamper rejection,
packaged lifecycle-cost scenarios with exact arithmetic, retained unknown exit costs, independent plan pins, and report tamper rejection,
standalone operating-budget pass/fail reports, a budget-aware matrix,
combined policy/budget dossier and CSV gates, and downgrade rejection with `--require-budget`,
operating-budget change review with both changed and unchanged outcomes,
retry-ledger accounting with earlier-failure retention and downstream evaluation binding,
complete retry handoffs with independent policy/budget outcomes and budget-downgrade rejection,
the complete 94-file installed `retry-demo` with all three expected handoff outcomes,
source-retaining OTLP projection and complete OTLP policy/budget handoffs with original-byte binding,
both policy outcomes, complete recorded
diagnostic-pack verification, operating-measurement and CSV import, a complete CSV review handoff,
context comparison, overwrite refusal,
and rejection of a modified operating report. It adds no package-index fallback, credentials,
model calls, or external Action dependency. Temporary test files are cleaned up on completion.
Use it only on a locally built wheel you trust: installation and CLI smoke testing execute code.

This check targets the release workflow's Python 3.12 runner; it is not a complete operating-system
or minimum-Python-version compatibility matrix. Python 3.10's separately declared `tomli` dependency
still applies. Source tests and metadata checks remain separate requirements. A local smoke pass
does not publish a package; the signed-tag and trusted-publisher process above is still required.
