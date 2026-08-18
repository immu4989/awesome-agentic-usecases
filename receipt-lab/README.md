# Receipt Lab

Receipt Lab answers one narrow question: **what does this evaluation artifact actually
support?** It opens an AAU-style `eval_*.json` entirely in the browser, recomputes its
structural evidence, keeps limitations visible, and exports an aggregate-only receipt.

**[Open Receipt Lab](https://immu4989.github.io/awesome-agentic-usecases/#receipt-lab)**

No file is uploaded, no model is called, no account is required, and no input is saved to
browser storage. Use synthetic, public, or safely redacted artifacts anyway: a local-first
tool cannot make unsafe source data appropriate to handle.

## The evidence ladder

Receipt Lab deliberately does not collapse unlike claims into a verified/not-verified badge.

1. **Unreadable** — the input is not one valid JSON object.
2. **Integrity gaps** — at least one hard structural check fails.
3. **Structurally coherent** — counts and aggregates reconcile locally. This is not domain
   validation, source verification, regulator approval, production certification, or proof
   that the metric is the right metric.
4. **Source-bound example** — a teaching artifact is also bound to a known committed path and
   SHA-256. Source binding is not independent reproduction.
5. **Independently reproduced** — requires a separate run, environment, and returned receipt.
   The browser inspector never grants this level by itself.

There is no composite score. Exact task success, completion, safety, cost, latency, and
uncertainty answer different questions and remain visibly separate.

## Ten hard checks

The hard gate requires all of the following:

| Check | What is recomputed |
|---|---|
| Parse | The JSON root is one object |
| Envelope | Required AAU result fields and core types are present |
| Coverage | Scenario and repeat counts are positive integers |
| Trial count | Rows equal `n_scenarios × n_repeats` |
| Scenario grid | The declared number of scenario identities is present |
| Repeat grid | Every scenario has exactly repeats `0..n_repeats-1` |
| Row shape | Identity, metrics, cost, latency, and call count are exposed |
| Finite values | Operational and metric values are finite numbers |
| Metric aggregation | Every published mean recomputes from trial rows |
| Cost aggregation | Published total cost reconciles with trial costs |

Tolerances cover declared rounding, not unexplained movement: metric means use `0.00015`;
total cost uses the greater of `$0.001` or 1% of the published total.

## Seven disclosure checks

These findings do not rewrite an otherwise inspectable historical artifact. They keep open
questions explicit:

- metric coverage across non-error trials;
- confidence-interval keys versus published metric keys;
- finite, ordered confidence intervals that contain their mean;
- mean cost reconciliation within declared precision;
- median latency reconciliation within declared precision;
- visible provider-error trial counts; and
- requested model, served model, and model-pinning provenance.

A provider error is not silently converted into success or deleted. A floating model alias is
not called reproducible. Older artifacts without provenance remain inspectable but carry an
open disclosure.

## Source-bound teaching receipts

[`samples.json`](samples.json) selects three intentionally different committed artifacts:

- a current, structurally coherent pharmaceutical decision-gate result with a disclosed
  floating model alias;
- an older security result that predates provenance stamps and retains provider errors; and
- an incident-remediation result with confidence-interval declaration drift.

[`make_receipt_lab_data.py`](../docs/make_receipt_lab_data.py) verifies each source path,
hashes the original file, copies only the fields needed by the public inspector, and produces
[`receipt-lab-data.json`](../docs/receipt-lab-data.json). It does not copy scenario text,
reasoning, summaries, messages, or tool payloads.

## Aggregate-only exports

The JSON receipt and SVG card may include:

- input file name and SHA-256;
- source binding for committed teaching artifacts;
- backend, model, provenance, coverage, and provider-error count;
- published and recomputed aggregates;
- selected metric dimensions and explicit inverted-risk labels;
- hard-check and disclosure findings; and
- privacy-warning category names.

They exclude scenario text, tool arguments and outputs, reasoning, free-text trial detail,
and per-trial records. The JSON schema identifier is `aau-reproduction-receipt/1.0`, but the
receipt is an inspection record—not a claim that a run was independently reproduced.
If the local scan detects a likely credential or common personal identifier, inspection stays
available but every aggregate export remains locked until the source artifact is redacted.

## Rebuild and verify

From the repository root:

```bash
python docs/make_receipt_lab_data.py
python docs/check_receipt_lab.py
node --check docs/receipt-lab.js
git diff --exit-code docs/receipt-lab-data.json docs/assets/receipt-lab.svg
```

CI reruns those checks. Any source edit, manifest change, stale hash, missing privacy boundary,
or generated-data drift fails the repository build.

## Limits

Receipt Lab understands this repository's current result envelope. It does not judge whether
a scenario is realistic, an oracle is correct, a source controls, a confidence-interval
method is appropriate, or a system is safe to deploy. Those claims still need qualified
domain review, threat modeling, independent runs, and the decision owner's approval.
