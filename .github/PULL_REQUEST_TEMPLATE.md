<!-- Thanks for contributing. The bar is VERIFICATION.md, applied without exceptions. -->

## What this PR does

<!-- One or two sentences. If it's a new use case, name the industry and the question it answers. -->

## Type

- [ ] New use case
- [ ] Fix / improvement to an existing use case or the harness
- [ ] Docs only

## For a new use case, the verification bar ([VERIFICATION.md](../VERIFICATION.md))

- [ ] Self-contained package under `<industry>/<use-case>/` with `pip install -e .` and a CLI
- [ ] `eval --backend mock` runs green from a clean clone (this is what CI runs)
- [ ] ≥20 scenarios with programmatic ground truth, committed under `evals/`
- [ ] Real-model results committed under `results/` — n≥3 repeats, cost per run in dollars
- [ ] `FAILURE_MODES.md` with ≥3 **observed** failures, each with a reproducing input
- [ ] README follows the template: Problem → How it decides → Results → Failure modes → Run it
- [ ] Added to the root README use-case table and the CI matrix in `.github/workflows/ci.yml`

## Checks

- [ ] `pytest <industry>/<use-case>/tests harness/tests` passes
- [ ] `ruff check .` is clean
- [ ] I opened an issue describing this use case first (per CONTRIBUTING.md)

## Notes

<!-- Anything a reviewer should know: a metric that behaves oddly, a deliberate scope limit, an open question. -->
