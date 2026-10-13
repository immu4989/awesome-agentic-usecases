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
the wheel and source distribution, checks metadata, tests the installed wheel outside the checkout,
creates build-provenance attestations,
publishes through the trusted PyPI identity, and attaches both distributions to a GitHub
release.

Do not push a release tag until the trusted publisher and GitHub environment exist; package
publication is intentionally fail-closed.

## Installed-artifact adoption check

The release workflow must pass `tools/smoke_installed_wheel.py` before distributions are uploaded,
attested, or made available to publishing jobs. It creates a temporary Python 3.11+ virtual
environment, installs only the locally built wheel with `--no-index --no-deps`, clears inherited
Python source-path overrides, and runs from a temporary directory outside the repository.
It also checks that the imported module resolves inside that new environment.

```bash
python -m build harness
python harness/tools/smoke_installed_wheel.py harness/dist/aau_harness-*.whl
```

The check captures and re-verifies a path-free `runtime-info` source receipt from the installed
wheel. It also exercises the packaged `evaluation-demo`, a multi-candidate matrix that excludes
failed policy, standalone operating-budget pass/fail reports, a budget-aware matrix,
combined policy/budget dossier and CSV gates, and downgrade rejection with `--require-budget`,
operating-budget change review with both changed and unchanged outcomes,
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
