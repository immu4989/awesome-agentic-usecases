# Experiment: equal scores can hide unstable behavior

**A deliberately broken fixture, not an authorization policy.** This experiment checks whether
the campaign workflow detects changing reason codes when aggregate scores and adapter bytes stay
unchanged. It makes no claim about a real model or a deployed service.

## Reproduce

From the repository root with the current harness installed, choose a fresh disposable directory:

```bash
mkdir authority-instability-demo
aau bom repeat-authority agent-capability-bom/examples/candidate.json \
  --command "python agent-capability-bom/examples/unstable_conformance_adapter.py authority-instability-demo/state.sqlite" \
  --adapter-artifact agent-capability-bom/examples/unstable_conformance_adapter.py \
  --workspace . --runs 2 --out authority-instability-demo/campaign
```

Expected exit: **1**, with a completed campaign and diagnostics. The adapter always blocks and
alternates an intentionally incorrect reason code each time it receives the same input. It uses
an explicitly supplied SQLite file to persist input digests and visit counts across fresh
processes. It does not read the expected suite answers or classify the opaque request case ID.

The current synthetic example produces:

| Observation | First run | Second run |
|---|---|---|
| Exact matches | Zero | Zero |
| Adapter entrypoint bytes | Same | Same |
| Per-input reason | `FIXTURE_ODD_VISIT` | `FIXTURE_EVEN_VISIT` |

Every current suite case is classified as unstable despite identical aggregate metrics. This is
covered by an integration test that invokes the real command adapter processes, not mocked receipts.
Changing the suite may change these observations; reproduce instead of treating them as universal.

## Verify without changing the experiment

```bash
aau bom verify-authority-campaign authority-instability-demo/campaign \
  --adapter-artifact agent-capability-bom/examples/unstable_conformance_adapter.py --workspace .
```

Expected exit: **1** again: the failed evidence is internally consistent. Verification does not
execute the fixture or increment its visit counts. The integration test checks that the database
count remains unchanged during verification.

## What this demonstrates—and what it does not

- Aggregate scores can conceal changes in individual outcomes.
- Entry-point hashes do not bind mutable external state, dependencies, or remote service behavior.
- A repeatability assessment must distinguish stable failures from stable passes.
- Fresh processes do not imply fresh external state. The runner intentionally does not reset it.

The deterministic alternation is an engineered failure, not evidence of stochastic behavior or an
estimated production failure rate. Two observations per case do not establish statistical reliability.
The database contains digests, not raw inputs; digests are not a privacy guarantee. Use synthetic
inputs and a disposable database, keep it outside the campaign directory, and review files before
sharing. The fixture writes only to the explicitly named database and needs no network or API key.

Return to [staging onboarding](STAGING_QUICKSTART.md) or the [command guide](README.md).
