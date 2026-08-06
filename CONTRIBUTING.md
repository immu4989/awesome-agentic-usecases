# Contributing

Contributions are welcome — the bar is [VERIFICATION.md](VERIFICATION.md), applied
without exceptions. Please open an issue describing the use case before sending a PR.

If you have a real workflow but do not plan to implement it yourself, use the
[use-case request](https://github.com/immu4989/awesome-agentic-usecases/issues/new/choose)
instead. Describe the decision, evidence, and costly failure; no eval-design experience is
required.

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

## Start from the generator, not a blank page

The bar below is high on purpose, and writing a seeded world, a shared gold function, a
deterministic mock and the tests that hold them together is a day of work before you reach
the interesting part. Skip it:

```bash
pip install -e harness
aau-new-use-case --industry healthcare --name prior-auth-triage-agent --seed 41
```

That emits a complete use case and then verifies it: installs it, generates the scenario
file, runs the tests, and runs a mock eval. All four have to pass before it prints the next
steps, so your first command succeeds and every later edit is checked by tests that already
encode the bar. Search the tree for `TODO(domain)` and replace the placeholder domain with
yours; pick a `--seed` no other use case uses.

The [Build Your Own guide](BUILD_YOUR_OWN.md) shows how to choose a nearby use case,
translate a production workflow into programmatic gold, and preserve the invariants that
make the result trustworthy. Use `aau find`, `aau show`, and `aau start` to explore before
you scaffold.

## Development

```bash
pip install -e harness[dev] -e <industry>/<use-case>[dev]
pytest <industry>/<use-case>/tests harness/tests
ruff check .
```

After committing a new use case's `results/`, regenerate the derived assets so the charts
and the cross-use-case matrix never drift from the data:

```bash
python docs/make_assets.py         # per-use-case banner + results chart + decision ladder
python docs/make_leaderboard.py    # the root-README "no best model" matrix + heatmap
python docs/make_terminal_demo.py  # the animated terminal casts (replayed from results)
python docs/make_taxonomy.py       # FAILURE_TAXONOMY.md (fails loudly on a dead citation)
```

The terminal casts replay a real scenario the model passed and one it failed, so they
change when the evals do. They are always dark (a terminal is a dark object, and GitHub
defaults to light), so unlike the other assets there is no light/dark pair — one
`demo.svg` per use case. Add a new solve-the-task use case to the `CASTS` list in
`docs/make_terminal_demo.py`, `docs/use-cases.json`, and to `USE_CASES` in
`docs/make_leaderboard.py`. Run `python docs/make_catalog.py` after changing the catalog;
CI verifies that the catalog, README, runnable packages, and test matrix all agree.
