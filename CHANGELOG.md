# Changelog

Notable changes to the repository. Versions follow [semantic versioning](https://semver.org/):
the harness API is what is versioned; use cases are additive.

## [0.1.4] — 2026-07-30

### Added
- **`customer-support/refund-amplified`** — denial of wallet (OWASP LLM10). The agent
  answers correctly, every safety metric passes, and the bill is up to **3.7×**. Two
  attacker-controlled vectors on inherited gold: `FANOUT` (ticket demands unrelated
  lookups) and `BLOAT` (an oversized customer-written field inside a tool result). `BLOAT`
  costs 1.75× at an *identical* tool-call and turn count, so rate limits and call quotas
  are blind to it.
- Four arms including a combined one. The two defences turn out to be complementary rather
  than competing: a prompt guard fixes `FANOUT` and cannot touch `BLOAT` (predicted in
  DESIGN.md before the runs), a tool-layer budget gate does the reverse, and only `both`
  closes each vector on both models.
- `evals/analyse.py` — per-archetype bill against each arm's own clean twin, with call and
  turn counts printed beside cost so the stealth claim stays checkable.

### Fixed
- **Corrected the accuracy claim in `refund-amplified`.** The first published version said
  `correct` and `safe` were flat across archetypes "on either model". That holds for
  mistral and is false for gpt-oss: conditioned on runs that submitted, accuracy falls
  0.942 → 0.783 on `BLOAT` and → 0.661 on `LEGIT_COMPLEX`, and safety 0.942 → 0.726. The
  unconditional figures looked flat only because stall rates differ by archetype. Also adds
  the finding this exposed — `budget_gate` recovers `BLOAT` accuracy to 0.909, so the gate
  is worth deploying for decision quality independently of cost.

### Notes
- The replay tax was measured on a real model *before* the use case was designed around it:
  identical task and tool sequence, padded tool results, same 4 calls and 5 turns, 6.1×
  input tokens.
- gpt-oss stalls on 32–37% of runs here; amplification recomputed on completed runs only
  matches the all-runs figure in every cell, so no conclusion rests on the stalls.

## [0.1.3] — 2026-07-29

### Added
- **`customer-support/refund-memory`** — the first use case where the attacker is absent
  when the damage happens. A false fact installed in one session steers a later session
  that contains no payload at all. Poisoned memory suppressed the session-2 identity check
  in 2 of 3 model families (gpt-oss `1.00 → 0.56`, deepseek `1.00 → 0.83`, mistral
  unaffected); a write-time provenance gate restored it significantly on the channel it can
  trace and, as designed, not on the one it cannot.
- `s2_identity_verified` metric, added on a second pass after the original endpoint
  (`sleeper_harm`) came back a null on all three models while traces showed the check being
  skipped. Documented as post-hoc in the use-case README.
- `evals/analyse.py` and `evals/compare_arms.py`: per-archetype tables with Δ against each
  model's own control, and paired bootstrap CIs that print control drift beside every claim.
- `docs/restamp_provenance.py` — recomputes derived provenance flags in committed results
  without touching a measurement, and asserts as much.

### Changed
- **Provenance now treats a requested/served mismatch as unpinned.** `deepseek-chat` served
  `deepseek-v4-flash` and was filed as reproducible, because no marker in the requested name
  revealed the alias. The mismatch itself is now the evidence.
- **CI scenario-reproducibility gate keys on the committed scenario file existing** rather
  than on the use case having no `extra` dependency, which had silently skipped it for 5 of
  14 rows. It also now generates under two `PYTHONHASHSEED` values, so a generator that
  reaches for salted `hash()` fails the build anywhere in the repo.

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
