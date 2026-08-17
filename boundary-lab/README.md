# Boundary Lab

Boundary Lab is an interactive counterfactual test bench for a question ordinary demos hide:
**what is the smallest meaningful fact that should change an agent's action?**

[Open the zero-install lab](https://immu4989.github.io/awesome-agentic-usecases/?boundary=sterility-is-not-chemical-oos#boundary-lab)
or inspect the [generated public data](../docs/boundary-data.json).

## The v1 evidence contract

Each pair is derived from two committed scenarios inside a runnable AAU use case. The pair
declares one semantic boundary, verifies the before and after conditions in source data, and
must change both the committed oracle terminal and the required reviewer action:

| Reviewer action | Meaning in the lab |
|---|---|
| **Trust** | Proceed under the shown contract. |
| **Verify** | Hold and request the missing proof. |
| **Block** | Stop this path and route the exception. |

“One deciding fact” means **one semantic boundary**, not one literal JSON-field diff. Case
identifiers, human-readable prose, evidence requirements, and derived gate states may all
change as consequences of that fact. Every pair declares the exact source selectors used to
prove its boundary in [`pairs.json`](pairs.json).

The v1 set spans pharmaceutical manufacturing, health-insurance appeals, hiring, grid
operations, home safety, Social Security disability, medical-device reporting, and tool
poisoning. Baseline and changed cases alternate sides so screen position is not a shortcut.

## Rebuild and verify

From the repository root:

```bash
python docs/make_boundary_lab_data.py
python docs/check_boundary_lab.py
```

The generator resolves every scenario ID from its committed `evals/scenarios.jsonl`, checks
the declared boundary condition, adapts only the display-safe fields, records source hashes,
and refuses pairs whose oracle or reviewer action does not move. CI regenerates the data and
fails on drift.

## What visitors can take with them

After reviewing both sides, a visitor can download a portable JSON regression fixture, a
pytest assertion, and a 1200×630 visual boundary card. They can also open the runnable lab,
fork in Codespaces, or challenge the oracle through a prefilled evidence issue. Stable
`?boundary=<id>#boundary-lab` routes make each pair directly shareable.

Answers and progress stay in local browser storage. Downloads are constructed in the browser;
the site sends no identity, answer, or telemetry. The scenarios are synthetic and the lab is
for education and evaluation—not legal, medical, safety, employment, benefits, or operational
advice, production certification, or authority to automate a protected decision.
