# Boundary Builder

Boundary Builder turns one real workflow boundary into a portable evaluation draft without
an account, API key, model call, or upload. [Open the zero-install
builder](https://immu4989.github.io/awesome-agentic-usecases/#boundary-builder), describe the
work, make one semantic fact change the required reviewer action, declare evidence and source
routes, and download an eight-file contribution ZIP.

> [!CAUTION]
> The builder checks structure, not domain truth. Every export remains
> `adaptation_required` until qualified review, source verification, synthetic scenario work,
> repeated model runs, and the repository's full evidence standard are complete.

## What the browser checks

Twelve local gates require:

1. An industry and boundary title.
2. A useful workflow description.
3. One repository-backed evaluation shape.
4. An accountable authority and qualified reviewer.
5. The protected action the agent cannot claim.
6. A named boundary with complete before and after states.
7. A real semantic change between those states.
8. Two different Trust, Verify, or Block actions.
9. A causal explanation for the action change.
10. A concrete consequence if the rule transfers incorrectly.
11. Evidence ledgers for both twins.
12. At least one HTTPS source declaration and a clear local sensitive-data screen.

The narrow safety screen blocks likely credentials, US Social Security numbers, email
addresses, telephone numbers, and payment-card numbers. It is not a privacy guarantee. Use
synthetic labels and public source URLs; never paste case records or confidential text.

## Contract templates

| Evaluation shape | Forge path | Inherited example |
|---|---|---|
| Decision Gate | Contract-aware | Batch Disposition Evidence Gate |
| Rights Continuity | Contract-aware | Health Insurance Denial and Appeal Rights Navigator |
| Critical Event Fan-Out | Contract-aware | Pipeline Incident Notification Coordinator |
| Proof Before Action | Generic fallback | Home and Field Service Readiness Coordinator |
| Obligation Graph | Generic fallback | Medical Device Adverse-Event Reporting Gate |
| Taint and Egress Gate | Generic fallback | Trifecta Exfil |

The mode distinction is intentional. Forge has specialized compilers for the first three
contracts. For the other three it creates runnable generic infrastructure while explicitly
refusing to imply specialized contract support. Every path inherits evaluation structure,
never the example lab's domain rules.

## The eight-file handoff

The browser builds a ZIP locally with:

- `README.md` — boundary story, human authority, Mermaid map, and adaptation warning.
- `boundary-pair.json` — the portable `aau-boundary-draft/1.0` contract.
- `evals/scenarios.jsonl` — baseline and changed synthetic scenario shells.
- `tests/test_boundary.py` — structural regression checks for the pair.
- `evidence/PRIMARY_SOURCES.md` — a qualified-review ledger for declared sources.
- `evaluation-brief.json` — an `aau-studio/1.0` brief accepted by Forge.
- `CONTRIBUTION_CHECKLIST.md` — the path from draft to verified evidence.
- `assets/boundary-card.svg` — an original 1200×630 visual handoff card.

No form value is added to analytics or transmitted by the site. The only external action is
an issue link the visitor chooses to open; it includes high-level roles and the declared action
change, but deliberately excludes source URLs, evidence, and scenario text.

## Rebuild and verify

From the repository root:

```bash
python docs/make_boundary_builder_data.py
python docs/check_boundary_builder.py
```

The generator resolves all six source contracts and recommended cases from committed
repository data, hashes the sources, and derives the worked example from Boundary Lab's
verified `one-tag-stops-restoration` pair. CI regenerates the data and artwork and fails if
their evidence, schemas, counts, privacy promises, or browser interaction contract drifts.

After export, run the generated brief through Forge:

```bash
python -m pip install -e harness[dev]
aau forge evaluation-brief.json --name my-boundary
aau forge doctor my-boundary
```

Then complete every `TODO(domain)` and contribution checklist item before treating the
result as anything more than evaluation infrastructure.

The reproducible [launch kit](LAUNCH_KIT.md) contains the social images and animated GIFs
for introducing the builder without overstating what its exports prove.
