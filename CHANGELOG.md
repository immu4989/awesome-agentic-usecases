# Changelog

Notable changes to the repository. Versions follow [semantic versioning](https://semver.org/):
the harness API is what is versioned; use cases are additive.

## [0.1.2] — 2026-07-27

### Added
- **Harness API documentation** (`harness/README.md`): install, a runnable quickstart,
  and reference for every public export, plus the design commitments the library is built
  around.
- Two documentation tests: the README quickstart is **executed** in CI, and every name in
  `__all__` must appear in the README. The second caught three exports that were shipping
  undocumented.
- ORCID on the author record across paper, citation file and Zenodo metadata.

## [0.1.1] — 2026-07-27

Archival release. Adds `.zenodo.json` so the deposited record carries a real title,
abstract, keywords and licence — including the synthetic-world limitation, since a DOI is
permanent and is cited by people who never open the README. No functional changes.

## [0.1.0] — 2026-07-27

First tagged release. Thirteen verified use cases across seven industries, 55 real-model
evaluations, 72 observed failure modes, 208 tests, CI green on every use case.

### Added — verification infrastructure

- **Shared harness** (`aau-harness`): seeded scenario generation, a generic tool-use agent
  loop, cost accounting from measured token usage, and repeated-run evaluation with paired
  bootstrap confidence intervals.
- **Provenance on every result**: timestamp, harness version, interpreter, and the model the
  provider actually served. Results produced against floating aliases (`*-latest`) are
  labelled as point-in-time observations rather than presented as reproducible.
- **Provider-failure guard**: an eval whose runs failed at the transport layer is refused
  rather than saved, so an expired key cannot be published as a model's score.
- **`aau-new-use-case`**: scaffolds a complete use case that already clears the verification
  bar, then installs it, generates its scenarios, runs its tests and a mock eval before
  reporting success.
- **Multi-provider backends**: Mistral, Groq, Gemini, Cerebras, DeepSeek, Together,
  Fireworks, OpenRouter (274 tool-calling models, 15 free) and a native Anthropic backend.

### Added — findings

- **[Failure taxonomy](FAILURE_TAXONOMY.md)**: 72 observed failures cross-cut into 11
  recurring patterns, with measured incidence and a link to the run that produced each. All
  citations are verified to resolve at build time.
- **Cross-use-case model matrix**: every model wins at least one task and loses another.
- Thirteen use cases spanning `investigate`, `decide`, `plan`, `act`, `watch`, `gate`,
  `multi-agent`, and adversarial or reliability A/B shapes.

### Known limitations

- Worlds are synthetic. This buys exact programmatic ground truth and $0 reproducibility;
  it does not support claims about production traffic.
- Sample sizes are 30 scenarios × 3 repeats per model. Confidence intervals are wide and
  are reported rather than omitted.
- 29 of the 55 committed evaluations predate provenance capture and ran against floating
  model aliases; those numbers are point-in-time observations and are not exactly
  reproducible. Later runs record the served model.
