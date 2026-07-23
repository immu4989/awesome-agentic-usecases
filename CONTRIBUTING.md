# Contributing

Contributions are welcome — the bar is [VERIFICATION.md](VERIFICATION.md), applied
without exceptions. Please open an issue describing the use case before sending a PR.

## What gets merged

A new use case PR needs:

- [ ] Self-contained package under `<industry>/<use-case>/` with `pip install -e .` and a CLI
- [ ] `eval --backend mock` runs green from a clean clone (this is what CI runs)
- [ ] ≥20 scenarios with programmatic ground truth, committed
- [ ] Real-model eval results committed under `results/` — n≥3 repeats, cost per run in dollars
- [ ] `FAILURE_MODES.md` with ≥3 observed failures, each with a reproducing input
- [ ] README following the standard template: Problem → Architecture → Results → Failure modes → Run it

## What doesn't

- Link-list additions ("add my project"). This isn't a link list.
- Demos without evals, evals without ground truth, results from a single run.
- Use cases requiring proprietary data or paid services beyond the model API.

## Development

```bash
pip install -e harness[dev] -e <industry>/<use-case>[dev]
pytest <industry>/<use-case>/tests harness/tests
ruff check .
```

After committing a new use case's `results/`, regenerate the derived assets so the charts
and the cross-use-case matrix never drift from the data:

```bash
python docs/make_assets.py        # per-use-case banner + results chart + decision ladder
python docs/make_leaderboard.py   # the root-README "no best model" matrix + heatmap
```
