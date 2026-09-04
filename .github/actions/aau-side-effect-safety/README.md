# AAU side-effect safety matrix action

This dependency-free composite Action runs three answer-blind, staging-only contracts. It refuses
to combine their evidence unless crash and race suites name the same exact `tool_id + operation`
and that pair exists in the semantic suite:

1. exact intent, authority, approval, idempotency, reconciliation, and compensation semantics;
2. recovery in a fresh process after six crash boundaries; and
3. 2-to-16-process races followed by a separate durable-state inspection.

It writes and re-verifies a self-contained nine-file evidence pack before returning the gate result.
A behavioral mismatch returns exit code 1 after preserving a valid diagnostic pack. Structural,
adapter, or tamper failures return exit code 2. The Action never uploads evidence; the caller owns
retention.

```yaml
name: Agent side-effect safety

on:
  pull_request:

permissions:
  contents: read

jobs:
  side-effect-safety:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
        with:
          python-version: "3.12"
      - uses: immu4989/awesome-agentic-usecases/.github/actions/aau-side-effect-safety@<FULL_COMMIT_SHA>
        with:
          semantic_suite: safety/semantic-suite.json
          semantic_adapter_command: python safety/semantic_adapter.py
          crash_suite: safety/crash-suite.json
          crash_adapter_command: python safety/crash_adapter.py
          race_suite: safety/race-suite.json
          race_adapter_command: python safety/race_adapter.py
          output: safety-result/matrix

      - name: Preserve verified diagnostics
        if: ${{ always() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: side-effect-safety
          path: safety-result/matrix
          retention-days: 14
          if-no-files-found: ignore
```

Pin both this Action and every third-party Action to reviewed full commit SHAs. Adapter commands are
trusted executable code: use public-synthetic inputs, no secrets, read-only repository permissions,
GitHub-hosted or appropriately isolated runners, and no production target access. Inputs are passed
through quoted environment variables; event titles, branch names, commit messages, and other
untrusted GitHub context are not interpolated into the script.

The runner groups nondeterministic race winners, keeps each component's metrics separate, records
which one semantic tool-operation pair received all three gates, and does not treat intentionally
unresolved crash states as failures. Other tools in a semantic suite do not inherit crash or race
coverage. Passing is bounded evidence for the exact suites and adapter commands—not atomicity,
linearizability, exactly-once execution, safety, compliance, certification, deployment approval,
government endorsement, or an ATO.

See the [full Side-Effect Ledger guide](../../../agent-side-effect-ledger/README.md) and its
[threat model](../../../agent-side-effect-ledger/THREAT_MODEL.md).
