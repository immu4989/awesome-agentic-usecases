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

Before investigating a changed-source notice, see the
[source snapshot workflow](#retain-source-snapshots-for-offline-review) below. Old fingerprint-only
reports cannot reconstruct historical content; capture new evidence without overwriting an approved baseline.

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

## Retain source snapshots for offline review

A fingerprint tells an owner that content differs, but not what differs. This surfaced in the
[open freshness review](https://github.com/immu4989/awesome-agentic-usecases/issues/12): changed
MCP/NIST pages and an unreachable CISA document require review, while older scans contain hashes
and metadata only. `source_evidence.py` adds **opt-in, one-source capture** and an offline comparison.
It does not interpret those findings, resolve that issue, or relabel existing evidence current.

```bash
# Explicit network request to one source from the existing registry.
python3 policy-freshness/source_evidence.py capture policy-freshness/sources.json \
  nist-tev-v-athlon --out /tmp/tevv-source-before

# Verify locally without another request; keep the complete five-file folder.
python3 policy-freshness/source_evidence.py verify /tmp/tevv-source-before

# At a later collection time, use a fresh destination.
python3 policy-freshness/source_evidence.py capture policy-freshness/sources.json \
  nist-tev-v-athlon --out /tmp/tevv-source-after
python3 policy-freshness/source_evidence.py compare \
  /tmp/tevv-source-before /tmp/tevv-source-after --out /tmp/tevv-source-diff.json
python3 policy-freshness/source_evidence.py compare \
  /tmp/tevv-source-before /tmp/tevv-source-after --verify /tmp/tevv-source-diff.json
```

Every snapshot retains `registry.json`, `capture.json`, `content.bin`, `summary.json`, and
`manifest.json`. The original response body stays byte-for-byte intact. The summary records both
the raw SHA-256 and the registry's fingerprint, plus whether that fingerprint matches the
**previously registered baseline**. Capturing changed content does not make it an approved baseline.
Metadata and raw bodies come from the same response; verification recomputes fingerprints, byte
counts, summaries, and the exact file inventory. The manifest is written last. Existing outputs,
incomplete folders, extra files, symlinks, oversized members, and inconsistent evidence are refused.

Snapshots are portable: verification does not require the original repository owner paths to
exist. The retained registry is structurally checked, not treated as trusted merely because it
was included. Use the same tool implementation and independently review the registry. Source body
limits remain 12 MB; each JSON member is limited to 2 MB. Capture defaults to a 20-second network
timeout. Failed requests do not become empty or apparently current snapshots. HTTPS redirects
are checked against the declared host allowlist **before** following them; rejected targets are
not retried through another hostname or mirror.

Comparisons require the same source ID, configured URL, and fingerprint method. Revisions and
source metadata may change but are disclosed, along with the union of affected owner paths.
Raw-byte differences are reported separately from fingerprint differences:

| Observation | Offline comparison output | Owner action |
|---|---|---|
| Raw bytes changed, extracted text unchanged | `fingerprint_unchanged`, with `raw_bytes_changed: true` | Inspect context; this is not proof of unchanged policy or currency |
| Extracted text changed within limits | `bounded_lexical_diff` with changed word spans | Inspect each span and the complete retained source |
| Text exceeds 200,000 normalized bytes or 5,000 words on either side | `text_diff_omitted_size_limit`; both fingerprints retained | Use appropriate local review tooling; no partial diff is presented as complete |
| Raw-mode PDF, Markdown, or other bytes changed | `raw_content_requires_external_review` | Inspect the original documents safely with a format-appropriate tool |

`visible_text_v1` uses the **existing** extraction method: whitespace is normalized and
script/style/template/SVG/noscript bodies are excluded. It is not browser rendering; CSS visibility,
navigation, titles, and footer changes can affect the result. Diff spans use zero-based half-open
word ranges and are lexical, not semantic or necessarily minimal. Raw mode deliberately performs
no PDF parsing. Compare returns 0 when evidence recomputes, including changed content; this is
**not an all-clear or approval exit code**. Invalid input or verification failure returns 2.

Capture time and response headers are declarations, not authenticated timestamps or retrieval
attestations. Argument order is caller-supplied; the tool does not establish chronology. Hashes are
not signatures, so replacing all sources and derived files consistently can still verify.
**An old hash cannot recreate a missing old document.** Newly captured snapshots must not be
described as the content behind an earlier scan unless their fingerprints actually match.

Raw pages/documents are untrusted and unsanitized. The tool neither opens them as HTML nor executes
their content. Use safe viewing tools, inspect for sensitive or unexpected material, and respect
redistribution rights before sharing a snapshot or textual diff. No snapshots are committed or
uploaded automatically. The weekly scanner still records fingerprints only, and the issue updater,
compatibility ledger, review dates, and approval workflow are unchanged.
