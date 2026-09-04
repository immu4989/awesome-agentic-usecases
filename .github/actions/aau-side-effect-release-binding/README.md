# AAU side-effect release binding action

This dependency-free local composite Action joins a verified Side-Effect Safety Matrix to an exact
Agent Capability and Authority BOM release plus byte snapshots of the semantic, crash, and race
adapters. It fails closed when the matrix boundary, AABOM consequential operations, binding plan,
authority approval requirement, or evidence digest does not agree.

Run the matrix Action first, then bind its pack:

```yaml
- uses: immu4989/awesome-agentic-usecases/.github/actions/aau-side-effect-safety@<FULL_COMMIT_SHA>
  with:
    semantic_suite: safety/semantic-suite.json
    semantic_adapter_command: python safety/semantic_adapter.py
    semantic_adapter_artifact: safety/semantic_adapter.py
    crash_suite: safety/crash-suite.json
    crash_adapter_command: python safety/crash_adapter.py
    crash_adapter_artifact: safety/crash_adapter.py
    race_suite: safety/race-suite.json
    race_adapter_command: python safety/race_adapter.py
    race_adapter_artifact: safety/race_adapter.py
    output: safety-result/matrix

- uses: immu4989/awesome-agentic-usecases/.github/actions/aau-side-effect-release-binding@<FULL_COMMIT_SHA>
  with:
    bom: safety/agent-capability-bom.json
    matrix: safety-result/matrix
    plan: safety/release-binding-plan.json
    output: safety-result/release-binding
```

Exit code 0 means all consequential operations are bound. Exit code 1 means a structurally valid,
reverifiable hold pack was produced. Exit code 2 means malformed input, tampering, unsafe paths, or
another structural failure. The Action uploads nothing; preserve the output in a later step if your
records policy allows it.

Adapter paths are workspace-relative declarations. Their exact copied bytes are hashed, but the
release pack is accepted only when each path and digest agrees with the artifact captured by the
matrix. The pack has no signature or builder identity and does not establish interpreter or
dependency closure, live workload identity, production
provenance, authority, safety, compliance, certification, deployment approval, or an ATO. Pin this
Action and every third-party Action to a reviewed full commit SHA, use synthetic staging adapters,
and do not expose production credentials to the runner.

See the [full release-binding guide](../../../agent-side-effect-ledger/README.md#bind-the-test-evidence-to-an-exact-release)
and [research notes](../../../agent-side-effect-ledger/RELEASE_BINDING_RESEARCH_NOTES.md).
