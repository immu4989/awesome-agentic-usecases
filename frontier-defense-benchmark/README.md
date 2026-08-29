# Frontier Defensive Capability Benchmark

Twenty safe, provider-neutral tasks test whether a defensive system can choose a bounded action, cite its evidence, preserve human authority, and avoid disrupting an essential service.

The five families are vulnerability prioritization, secure code review, identity and authorization, containment and recovery, and essential-service continuity.

```bash
python aau_defense_benchmark.py evaluate examples/collective-defense-suite.json examples/reference-protocol-responses.json --out /tmp/defense-receipt.json
python aau_defense_benchmark.py verify /tmp/defense-receipt.json --suite examples/collective-defense-suite.json --responses examples/reference-protocol-responses.json
```

## Bring your own system

Copy `reference-protocol-responses.json`, replace `system_id`, describe the adapter, and populate the twenty response rows. The evaluator never invokes a model or a tool, so the model-facing adapter remains under the participant's control.

The committed “reference protocol” is a hand-authored evaluator fixture. Its 20/20 result is **not a model result, field result, leaderboard entry, vendor comparison, or safety certification**. Public comparisons need a disclosed adapter, immutable artifacts, and independent reproduction.
