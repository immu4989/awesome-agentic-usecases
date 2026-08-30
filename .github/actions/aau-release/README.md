# AAU Agent Release Gate action

Run the change-specific release gate in a checkout, then upload or attest the verified pack in your
own workflow. Pin the action to an immutable commit SHA outside a demonstration.

```yaml
- uses: actions/checkout@<immutable-commit-sha>
  with:
    persist-credentials: false
- uses: immu4989/awesome-agentic-usecases/.github/actions/aau-release@<immutable-commit-sha>
  with:
    baseline-manifest: release/baseline-manifest.json
    candidate-manifest: release/candidate-manifest.json
    policy: release/release-policy.json
    evidence-plan: release/evidence-plan.json
    adapter-command: python app/release_adapter.py
    approval: release/approval.json
    pack: artifacts/aau-release-pack
```

The action runs repository-pinned, standard-library code and verifies the complete pack. It does
not install dependencies, deploy, sign, certify, verify an approver's identity, or convert
`release_ready` into authorization. Treat the adapter command as trusted code and run it with the
least privileges your organization permits.
