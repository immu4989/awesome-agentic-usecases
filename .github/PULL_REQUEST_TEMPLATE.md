<!-- Thanks for contributing. The bar is VERIFICATION.md, applied without exceptions. -->

## What this PR does

<!-- One or two sentences. If it's a new use case, name the industry and the question it answers. -->

## Type

- [ ] New use case
- [ ] Fix / improvement to an existing use case or the harness
- [ ] Docs only
- [ ] Community Forge Gallery adaptation
- [ ] Federal Pilot Kit exchange or readiness improvement

## For a new use case, the verification bar ([VERIFICATION.md](../VERIFICATION.md))

- [ ] Self-contained package under `<industry>/<use-case>/` with `pip install -e .` and a CLI
- [ ] `eval --backend mock` runs green from a clean clone (this is what CI runs)
- [ ] ≥20 scenarios with programmatic ground truth, committed under `evals/`
- [ ] Real-model results committed under `results/` — n≥3 repeats, cost per run in dollars
- [ ] `FAILURE_MODES.md` with ≥3 **observed** failures, each with a reproducing input
- [ ] README follows the template: Problem → How it decides → Results → Failure modes → Run it
- [ ] Added to `docs/use-cases.json` and the CI matrix in `.github/workflows/ci.yml`
- [ ] Ran `python docs/make_catalog.py` and `aau doctor`

## Checks

- [ ] `pytest <industry>/<use-case>/tests harness/tests` passes
- [ ] `ruff check .` is clean
- [ ] I opened an issue describing this use case first (per CONTRIBUTING.md)
- [ ] For a Gallery entry, `aau gallery validate <entry-id>` reports the evidence level claimed by the public card

## For a Federal Pilot Kit change

- [ ] Uses public or synthetic information only
- [ ] Preserves protected human decisions and the non-ranking/non-award boundary
- [ ] Updates the threat model when a parser, workflow, data flow, or trust boundary changes
- [ ] Adds hostile-input or privacy regression tests for a changed attack surface
- [ ] Keeps release manifest, SPDX SBOM, checksums, and attestation workflow reproducible
- [ ] Uses the 30-day launch pack for roles, success/stop gates, and exit evidence

## Notes

<!-- Anything a reviewer should know: a metric that behaves oddly, a deliberate scope limit, an open question. -->
