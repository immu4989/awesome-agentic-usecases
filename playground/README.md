# Can You Trust This Agent?

The [interactive playground](https://immu4989.github.io/awesome-agentic-usecases/?case=grid-restoration-ready#playground)
turns committed evaluation traces into a five-case review exercise. Visitors inspect the
same scenario facts, model action, evidence ledger, and result artifact used by the repository,
then choose one reviewer action:

- **Trust** — accept the output because its full evidence contract is exact.
- **Verify** — hold the workflow and request the specifically missing artifact.
- **Block** — reject an unsafe, unfaithful, or authority-crossing output.

No model call, API key, account, or backend is required. Answers and progress stay in the
visitor's browser. Every case has a stable share URL and opens its exact scenario, result,
lab, and related Reliability Challenge mission.

## Evidence contract

[`scenarios.json`](scenarios.json) contains only the editorial selection and learning layer.
[`docs/make_playground_data.py`](../docs/make_playground_data.py) loads the referenced JSONL
scenario and real-model result, derives the observable and expected decisions, redacts synthetic
secret values, stamps source hashes, and writes `docs/playground-data.json`.

CI regenerates the public data and runs [`docs/check_playground.py`](../docs/check_playground.py).
It fails if a source file, scenario, model repeat, verdict rule, Challenge link, or landing-page
interaction drifts.

```bash
python docs/make_playground_data.py
python docs/check_playground.py
git diff --exit-code docs/playground-data.json
```

The playground is an educational review surface built from synthetic scenarios and committed
evaluation evidence. It is not production certification, legal advice, regulatory approval, or
permission to automate protected authority.
