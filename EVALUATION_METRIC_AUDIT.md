# Recorded evaluation metric audit

Browse the [public audit page](https://immu4989.github.io/awesome-agentic-usecases/evaluation-audit.html)
for expandable file-level findings and original-source links, without scripts or external assets.

The current harness recomputed metric summaries for **287 committed evaluation files**:
**264 are internally consistent; 23 contain summary differences**. This audit checks saved
observations, not live model behavior. It does not establish whether old scores or current
scoring conventions are substantively correct.

The [machine-readable audit](evaluation-metric-audit.json) records every source path, exact file
digest, status, and recorded/recomputed mismatch. Historical source files have **not** been
rewritten, and no model calls were made.

## Findings that readers should know

| Lab | Files with differences | Observed limitation |
|---|---:|---|
| Prior Auth Review | 11 | Some stored summaries lack an interval for a recorded diagnostic metric |
| Incident Remediation | 12 | Some stored intervals differ from current recomputation, are missing, or refer to metrics absent from the recorded observations |

Full-precision legacy means are compared at the shared exporter's four-decimal precision;
precision-only differences are not counted as inconsistencies. A first diagnostic pass identified
24 files before this precision normalization; the reproducible count above is the normalized one.

Do not treat affected historical intervals as interchangeable with intervals freshly computed by
the current harness. Review the exact mismatch and the original scorer/revision before using
these results for a comparison. These findings do **not** demonstrate fabricated runs, clinical
performance, operational effectiveness, or a new evaluation. They also do not validate scoring
ground truth, scenario execution, costs, latency, provider availability, or provenance.

## Reproduce without altering observations

From the repository root with the current harness installed:

```bash
python harness/tools/audit_repository_evals.py --check
```

This recomputes the entire corpus and requires the committed audit, including source digests and
known differences, to match exactly. It deliberately preserves historical differences as visible
findings. A successful check means **the audit reproduced**, not that all metric summaries passed.
Source changes, new evaluation files, or changed findings require explicit review and regeneration:

```bash
python harness/tools/audit_repository_evals.py
python harness/tools/render_metric_audit.py
```

Review that diff; do not regenerate merely to silence a new inconsistency. The generator excludes
`output/`, `social-assets/`, and `tmp/`. It writes only the companion audit, never the source
evaluation files. For an individual file, use
[`aau audit-eval`](harness/README.md#audit-a-saved-evaluation-without-rerunning-a-model), whose exit
status distinguishes a consistent summary from mismatches and invalid measurements.

Hashes detect source changes relative to this audit; they are not signatures or independent
execution attestations. A coordinated change to observations and summaries can remain internally
consistent. Bootstrap compatibility is limited to the current shared harness algorithm, not every
historical or external statistical method.
