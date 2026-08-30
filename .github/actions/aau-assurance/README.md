# AAU Portable Agent Assurance action

This composite action has two layers:

1. It evaluates an `aau-agent-assurance-envelope/0.1`, verifies the deterministic receipt, builds
   a portable evidence pack, and verifies that pack again.
2. When `current_gates: "true"`, it runs project-owned command adapters against the MCP
   `2026-07-28`, A2A `1.0`, and A2A-to-MCP Authority Relay suites. It then emits and re-verifies one
   six-file matrix pack with three gate receipts, an aggregate receipt, a job summary, and a
   SHA-256 manifest.

The action executes dependency-free verifiers from the same repository revision and makes no
package download or remote action call. The current matrix has **58 cases**: six clean twins and
fifty-two isolated violations. Aggregate counts never replace the gate-specific results.

Copy the reference envelope and suite into your repository, replace only synthetic values, and
pin this action to a reviewed full commit SHA:

```yaml
name: Agent assurance

on:
  pull_request:

permissions:
  contents: read

jobs:
  assurance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
        with:
          python-version: "3.12"
      - uses: immu4989/awesome-agentic-usecases/.github/actions/aau-assurance@<FULL_COMMIT_SHA>
        with:
          envelope: assurance/agent-envelope.json
          suite: assurance/mcp-a2a-suite.json
          receipt: assurance-result/receipt.json
          pack: assurance-result/pack
```

## Run the current three-gate matrix

Copy the three profiles and generated suites into your repository, implement one answer-blind
adapter per contract, and enable the matrix:

```yaml
      - uses: immu4989/awesome-agentic-usecases/.github/actions/aau-assurance@<FULL_COMMIT_SHA>
        with:
          envelope: assurance/agent-envelope.json
          suite: assurance/historical-envelope-suite.json
          current_gates: "true"
          current_output: assurance-result/current-matrix
          mcp_profile: assurance/mcp-profile.json
          mcp_suite: assurance/mcp-suite.json
          mcp_adapter_command: python assurance/adapters/mcp.py
          a2a_profile: assurance/a2a-profile.json
          a2a_suite: assurance/a2a-suite.json
          a2a_adapter_command: python assurance/adapters/a2a.py
          relay_profile: assurance/relay-profile.json
          relay_suite: assurance/relay-suite.json
          relay_adapter_command: python assurance/adapters/relay.py

      - name: Archive recomputable assurance evidence
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: current-agent-assurance
          path: assurance-result/current-matrix
          retention-days: 14
```

The matrix output must be a new directory inside `GITHUB_WORKSPACE`; absolute escapes, symbolic
input files, existing outputs, extra pack files, digest drift, receipt drift, and summary drift fail
closed. GitHub's job summary shows exactness and asymmetric failures for every gate. The Action does
not upload evidence itself; the caller controls retention and must pin any upload Action by full
commit SHA.

## Runner and adapter security

Adapter commands intentionally execute repository code. Run the job with `contents: read`, do not
provide secrets, do not use privileged or self-hosted production runners for untrusted pull
requests, and review adapter changes like application code. Inputs reach the shell only through
quoted environment variables; the Action never interpolates event titles, branch names, commit
messages, or other untrusted GitHub context into its script.

This follows GitHub's guidance to use intermediate environment variables to reduce script-injection
risk and to preserve workflow output as explicitly retained artifacts. See [GitHub's secure-use
reference](https://docs.github.com/en/actions/reference/security/secure-use) and [workflow artifact
guidance](https://docs.github.com/en/actions/tutorials/store-and-share-data).

Do not use the committed HS256 secret outside the public test fixture. Passing this action verifies
the experimental fixture contract and evidence bytes; it does not establish production identity,
authorize a live action, certify a system, determine compliance, or grant an Authority to Operate.
See the [full module guide](../../../portable-agent-assurance/README.md).
The [0.1 specification](../../../portable-agent-assurance/SPEC.md) defines the canonical digest,
decision, reason-code, clean-twin, and adapter requirements enforced by this action.
