# Policy Freshness Radar

Policy-dependent agent tests can look reproducible while the official source beneath them has
quietly changed. This module keeps that risk visible without pretending that software can decide
what a law, standard, or government publication means.

The committed registry binds nine official sources—and their explicitly named revisions—to the
repository artifacts that depend on them. A weekly workflow compares either the exact bytes of
stable documents or a versioned visible-text fingerprint of dynamic HTML pages. Any change,
unreachable source, elapsed review date, or declared implementation/revision mismatch opens one
consolidated maintainer-review issue.

```bash
# Structural and owner-path verification: offline, deterministic
python3 policy-freshness/aau_freshness.py validate policy-freshness/sources.json --root .

# Due-date view only: no network request
python3 policy-freshness/aau_freshness.py offline policy-freshness/sources.json \
  --root . --as-of 2026-08-30

# Explicit network scan: writes a report; never updates a source or a lab
python3 policy-freshness/aau_freshness.py scan policy-freshness/sources.json \
  --root . --out /tmp/aau-policy-freshness.json

# Exact source revision → implementation evidence impact: offline, deterministic
python3 policy-freshness/aau_freshness.py compatibility \
  policy-freshness/compatibility-ledger.json policy-freshness/sources.json \
  --root . --as-of 2026-08-30 --out /tmp/aau-standards-impact.json
```

## Standards Compatibility Ledger

Fresh bytes are not enough. An assurance fixture may still target an older protocol revision after
the watched source is updated. The strict compatibility ledger binds each experimental profile to:

- the exact official source record and revision it was evaluated against;
- the source fingerprint reviewed at that time;
- repository evidence paths that make the declared relationship inspectable;
- a relationship type (`informed_by`, `protocol_tested`, `schema_validated`, or `export_profile`);
- an immutable `experimental_nonconforming_reference` claim boundary.

The report distinguishes four conditions without a score: `source_lock_changed`,
`migration_required`, `review_due`, and `evidence_ready`. The first committed report covers all
nine watched sources across seven profiles. It deliberately exposes one real gap: Portable Agent
Assurance records were evaluated against MCP `2025-06-18`, while the radar now watches the current
`2026-07-28` authorization revision. Eight bindings are revision-aligned and one requires a
human-owned migration. Nothing is silently relabeled current.

This also catches a subtle failure mode: after a maintainer accepts a new source baseline, every
ledger binding still carries the previously reviewed fingerprint. The report changes to
`source_lock_changed` until the evidence owner reviews the source and explicitly updates the
binding. Rebaselining the radar can therefore never rebaseline implementation evidence by
accident.

`refresh` is deliberately manual. After a qualified owner has reviewed the official source and
any affected artifact, copy `registry.seed.json`, capture a new baseline to a new file, inspect the
diff, and replace `sources.json` in a reviewed pull request.

The radar and ledger compare content, revisions, paths, and metadata—not policy meaning or actual
implementation behavior. A changed fingerprint does not prove
that a rule changed, and an unchanged fingerprint does not establish currency, applicability,
compliance, conformance, or legal advice. `evidence_ready` means only that declared revisions,
fingerprints, dates, and evidence paths align. It performs no automatic policy interpretation or
migration and never modifies a lab.
