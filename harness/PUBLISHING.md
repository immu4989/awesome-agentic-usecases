# Publishing `aau-harness`

The package is built, checked, attested, and published without a long-lived PyPI token.
The release workflow uses PyPI Trusted Publishing and an immutable commit of the official
PyPA publishing action.

## One-time maintainer setup

1. Create or claim the `aau-harness` project on PyPI.
2. In the PyPI project, add a GitHub trusted publisher with:
   - owner: `immu4989`
   - repository: `awesome-agentic-usecases`
   - workflow: `harness-release.yml`
   - environment: `pypi`
3. In GitHub, create the `pypi` deployment environment. Add required reviewers if desired.

No API token is stored in GitHub. The workflow receives a short-lived OpenID Connect token
only in the publishing job.

## Release

Update the version in `harness/pyproject.toml`, update `CHANGELOG.md`, and run:

```bash
python harness/tools/check_release_version.py harness-v1.1.0
git tag -s harness-v1.1.0 -m "AAU Harness 1.1.0"
git push origin harness-v1.1.0
```

The tag must exactly match the package version. GitHub Actions runs all harness tests, builds
the wheel and source distribution, checks metadata, creates build-provenance attestations,
publishes through the trusted PyPI identity, and attaches both distributions to a GitHub
release.

Do not push a release tag until the trusted publisher and GitHub environment exist; package
publication is intentionally fail-closed.
