# Policy Freshness Radar

Policy-dependent agent tests can look reproducible while the official source beneath them has
quietly changed. This module keeps that risk visible without pretending that software can decide
what a law, standard, or government publication means.

The committed registry binds ten official sources—and their explicitly named revisions—to the
repository artifacts that depend on them. A weekly workflow compares either the exact bytes of
stable documents or a versioned visible-text fingerprint of dynamic HTML pages. Any change,
unreachable source, elapsed review date, or declared implementation/revision mismatch opens one
consolidated maintainer-review issue.

The issue now reconciles **changed findings**, rather than stopping when an open issue already
exists. This closes a real monitoring gap: an initial unreachable-source notice could previously
prevent later source changes or revision-migration findings from appearing in the same issue.

Only a marked automated section is replaced. Human text outside that section is preserved, and
an older unmarked notice is retained in full beneath the new section. The updater includes both
source-freshness and standards-compatibility findings; it checks their report hashes, finding
counts, shared registry/date, and rendered issue text before publishing. These checks establish
internal consistency, not authenticity or policy meaning.

Identical findings do not trigger repeated edits merely because the scan date or report hash
changed. The displayed date therefore belongs to the **latest changed finding**, not a heartbeat
claim that every later scan ran. Exact scan reports remain workflow artifacts, including when
issue reconciliation fails. Changes in source content, failure status, affected paths, registry
fingerprint, or compatibility evidence can update the notice.

A later all-clear scan updates an existing notice but **never closes the issue** or marks human
review complete. Owners must inspect earlier findings, retained notes, and scan artifacts before
deciding whether any policy, baseline, implementation, or evidence update is warranted. No source
baseline or compatibility binding is changed by this notifier.

The workflow serializes its own runs. Duplicate review issues, malformed managed markers,
oversized bodies, and a detected intervening edit/closure fail closed without truncating notes or
choosing an arbitrary issue. A final read detects edits made since listing; this is a best-effort
race check, not an atomic lock against simultaneous human/GitHub edits. Keep owner notes outside
the marked section. The updater uses argument arrays and stdin for bodies, never shell-evaluated
issue content, and never posts repetitive comments.

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
`migration_required`, `review_due`, and `evidence_ready`. The ledger first exposed a real gap:
Portable Agent Assurance targeted MCP `2025-06-18` while the radar watched `2026-07-28`. A separate
16-case authorization delta gate then supplied the exact current-revision evidence needed to close
it. The current report covers all ten watched sources across seven profiles with ten aligned
bindings and zero open migrations; Git history preserves the detected gap and its evidence-backed
closure. Nothing was silently relabeled current.

The tenth source is the February 2026 NIST NCCoE Software and AI Agent Identity and Authorization
concept paper. Its exact 406,665-byte PDF is fingerprinted and mapped directly to the revision-locked
portable-agent and A2A-to-MCP relay challenges. MCP and A2A owner paths now point to those current
challenge versions rather than the retained, source-superseded historical artifact.

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
