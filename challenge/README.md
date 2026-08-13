# AAU Reliability Challenge

**30 minutes. One claim. Bring the receipt.**

This is the contribution on-ramp for people who want to do more than star a benchmark.
Choose a bounded mission, run it for $0, and return evidence another person can inspect.
Reproduce and Break use a lightweight Challenge receipt against the starter lab. Adapt
uses a normal [Community Forge Gallery](../gallery/README.md) entry because a new workflow
needs the deeper provenance, contract, review, and evidence ladder.

## Choose a track

| Track | Do this | Minimum finish |
|---|---|---|
| **Reproduce** | Run a published claim again and trace a divergent scenario. | Valid result + note + scenario receipt |
| **Break** | Add a seeded edge case and document a newly observed failure. | Valid result + new scenario receipt |
| **Adapt** | Move a contract to a new workflow and preserve its invariants. | Gallery level `Generated` |

Open the [live mission board](https://immu4989.github.io/awesome-agentic-usecases/#challenge)
to filter the five starter challenges, download a ready-to-edit submission record, see
evidence-derived achievements, and inspect the public scoreboard.

Claim one of the five [`good first issue` missions](https://github.com/immu4989/awesome-agentic-usecases/issues?q=is%3Aissue%20state%3Aopen%20label%3Achallenge),
or introduce yourself in the [Challenge announcement](https://github.com/immu4989/awesome-agentic-usecases/discussions/6).

## The 30-minute path

1. Open the repository in [Codespaces](https://codespaces.new/immu4989/awesome-agentic-usecases?quickstart=1)
   or clone it locally.
2. Run `python -m pip install -e harness`, then `aau challenge list`.
3. Run `aau challenge show <challenge-id>` and copy its zero-cost command.
4. Reproduce/Break: copy [`challenge-entry.example.json`](challenge-entry.example.json) to
   `challenge/entries/<id>.json` and add a short Markdown receipt under `challenge/receipts/`.
   Adapt: create a [Challenge-enabled Gallery entry](../gallery/gallery-entry.example.json).
5. Run `aau challenge validate <entry-id>` and open a PR with the
   [Challenge template](../.github/PULL_REQUEST_TEMPLATE/reliability-challenge.md).

No private records, API key, or paid model are needed for the first run. Synthetic or
public data only. A Challenge finish is evidence of repository checks—not production
certification, regulatory approval, or permission to automate protected authority.

## Machine contract

Challenges live in [`challenges.json`](challenges.json) and are checked against
[`challenge.schema.json`](challenge.schema.json). Reproduce/Break receipts follow
[`challenge-entry.schema.json`](challenge-entry.schema.json) and point to an exact result,
note, and scenario id. An Adapt submission is a Gallery record with:

```json
"challenge": {
  "id": "completion-is-not-correctness",
  "track": "Reproduce",
  "claim": "Reproduced the completion/exactness gap and traced scenario privacy-017."
}
```

The command below chooses the correct receipt type, then validates the mission, declared
track, lab, result, note, scenario trace, or Gallery evidence level:

```bash
aau challenge validate <entry-id>
```

Achievements cannot be requested in JSON. They are calculated from the evidence that the
receipt or Gallery entry actually commits.
