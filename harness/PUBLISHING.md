# Publishing `aau-harness`

The package is built, checked, attested, and published without a long-lived PyPI token.
The release workflow uses PyPI Trusted Publishing and an immutable commit of the official
PyPA publishing action.

The identity is live: [`aau-harness` on PyPI](https://pypi.org/project/aau-harness/) is
published from the `pypi` GitHub environment, and the first provenance-backed distributions
were attached to the [1.1.0 GitHub release](https://github.com/immu4989/awesome-agentic-usecases/releases/tag/harness-v1.1.0).
The [latest release](https://github.com/immu4989/awesome-agentic-usecases/releases/tag/harness-v1.3.0)
adds privacy-bounded Community Evidence bundles, deterministic progressive evidence levels,
fail-closed validation, share cards, and the zero-upload Contribution Desk.

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
the wheel and source distribution, checks metadata, creates build-provenance attestations,
publishes through the trusted PyPI identity, and attaches both distributions to a GitHub
release.

Do not push a release tag until the trusted publisher and GitHub environment exist; package
publication is intentionally fail-closed.
