# AAU Portable Agent Assurance action

This composite action evaluates an `aau-agent-assurance-envelope/0.1` against an
`aau-agent-assurance-suite/0.1`, verifies the deterministic receipt, builds a portable evidence
pack, and verifies the pack again. It executes the dependency-free verifier from the same
repository revision as the action and makes no package download or remote action call.

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

Do not use the committed HS256 secret outside the public test fixture. Passing this action verifies
the experimental fixture contract and evidence bytes; it does not establish production identity,
authorize a live action, certify a system, determine compliance, or grant an Authority to Operate.
See the [full module guide](../../../portable-agent-assurance/README.md).
The [0.1 specification](../../../portable-agent-assurance/SPEC.md) defines the canonical digest,
decision, reason-code, clean-twin, and adapter requirements enforced by this action.
