# Policy Freshness Radar

Policy-dependent agent tests can look reproducible while the official source beneath them has
quietly changed. This module keeps that risk visible without pretending that software can decide
what a law, standard, or government publication means.

The committed registry currently binds nine official sources to the repository artifacts that
depend on them. A weekly workflow compares either the exact bytes of stable documents or a
versioned visible-text fingerprint of dynamic HTML pages. Any change, unreachable source, or
elapsed review date opens one consolidated maintainer-review issue.

```bash
# Structural and owner-path verification: offline, deterministic
python3 policy-freshness/aau_freshness.py validate policy-freshness/sources.json --root .

# Due-date view only: no network request
python3 policy-freshness/aau_freshness.py offline policy-freshness/sources.json \
  --root . --as-of 2026-08-30

# Explicit network scan: writes a report; never updates a source or a lab
python3 policy-freshness/aau_freshness.py scan policy-freshness/sources.json \
  --root . --out /tmp/aau-policy-freshness.json
```

`refresh` is deliberately manual. After a qualified owner has reviewed the official source and
any affected artifact, copy `registry.seed.json`, capture a new baseline to a new file, inspect the
diff, and replace `sources.json` in a reviewed pull request.

The radar compares content and metadata—not policy meaning. A changed fingerprint does not prove
that a rule changed, and an unchanged fingerprint does not establish currency, applicability,
compliance, or legal advice. It performs no automatic policy interpretation and never modifies a
lab.
