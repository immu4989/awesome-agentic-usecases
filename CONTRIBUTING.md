# Contributing

Contributions are welcome — the bar is [VERIFICATION.md](VERIFICATION.md), applied
without exceptions. Please open an issue describing the use case before sending a PR.

If you have a real workflow but do not plan to implement it yourself, use the
[use-case request](https://github.com/immu4989/awesome-agentic-usecases/issues/new/choose)
instead. Describe the decision, evidence, and costly failure; no eval-design experience is
required.

If you plan to implement it, start with the zero-install
[Boundary Builder](https://immu4989.github.io/awesome-agentic-usecases/#boundary-builder).
It converts one declared semantic boundary into an eight-file, Forge-compatible draft while
keeping source URLs, evidence, and scenario text in your browser. Review the generated ZIP for
sensitive information and complete every `TODO(domain)` before opening an issue or PR.

## What gets merged

A new use case PR needs:

- [ ] Self-contained package under `<industry>/<use-case>/` with `pip install -e .` and a CLI
- [ ] `eval --backend mock` runs green from a clean clone (this is what CI runs)
- [ ] ≥20 scenarios with programmatic ground truth, committed
- [ ] Real-model eval results committed under `results/` — n≥3 repeats, cost per run in dollars
- [ ] `FAILURE_MODES.md` with ≥3 observed failures, each with a reproducing input
- [ ] README following the standard template: Problem → Architecture → Results → Failure modes → Run it
- [ ] A themed entry, four-act story, and scenario anatomy in
  `docs/make_readme_experiences.py`, with all generated visual-case-file assets committed
- [ ] For protective workflows, an exact receipt vocabulary that distinguishes draft,
  attempt, accepted handoff, accountable decision, and completed action
- [ ] For multi-obligation workflows, a versioned graph of every trigger, clock origin,
  deadline semantic, recipient/channel, protected owner, and executed receipt

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

If you began in [AAU Studio](https://immu4989.github.io/awesome-agentic-usecases/#studio),
download its evaluation brief and run `aau forge <brief.json> --name <your-eval>`.
[AAU Forge](AAU_FORGE.md) preserves the matched architecture, generates a runnable lab,
and adds an explicit domain-review checklist and dedicated CI workflow.

## Share an adaptation in the Community Forge Gallery

Useful forks deserve attribution and a route for others to reproduce them. Copy
[`gallery/gallery-entry.example.json`](gallery/gallery-entry.example.json), commit it as
`gallery/entries/<id>.json`, and run `aau gallery validate <id>`. The public level is
derived from evidence; do not add a trust label to the entry.

Community adaptations must use `origin: "forge-adaptation"` and commit Forge provenance
plus the contract blueprint. The included
[Codespaces environment](https://codespaces.new/immu4989/awesome-agentic-usecases?quickstart=1)
installs the contributor tools automatically. Read the
[Gallery standard](gallery/README.md) and use the dedicated Gallery PR template.

## Finish a Reliability Challenge

If a full new lab is too large for a first contribution, choose one of the five bounded
[Reliability Challenge missions](challenge/README.md). The **Reproduce**, **Break**, and
**Adapt** tracks start from existing runnable evidence and state the exact receipt to return.

```bash
aau challenge list
aau challenge show <challenge-id>
aau challenge validate <gallery-id>
```

For Reproduce/Break, add a lightweight `challenge/entries/<id>.json` receipt plus its
Markdown note. For Adapt, add the optional `challenge` object to the Gallery entry. Do not
add achievements or a finish status; CI derives both. Open the PR with
`.github/PULL_REQUEST_TEMPLATE/reliability-challenge.md` so reviewers can inspect the
claim, scenario, result, and safety boundary without reconstructing the contribution.

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
python docs/make_readme_experiences.py  # complete visual case file for every use-case README
```

The terminal casts replay a real scenario the model passed and one it failed, so they
change when the evals do. They are always dark (a terminal is a dark object, and GitHub
defaults to light), so unlike the other assets there is no light/dark pair — one
`demo.svg` per use case. Add a new solve-the-task use case to the `CASTS` list in
`docs/make_terminal_demo.py`, `docs/use-cases.json`, and to `USE_CASES` in
`docs/make_leaderboard.py`. Run `python docs/make_catalog.py` after changing the catalog;
CI verifies that the catalog, README, runnable packages, visual case files, and test matrix
all agree. The README experience generator reads non-mock JSON results and
`FAILURE_MODES.md` directly, so rerun it whenever either evidence source changes.
