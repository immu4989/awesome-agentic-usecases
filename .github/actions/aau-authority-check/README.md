# Staging authority check Action

Run an inventory-derived synthetic suite through a trusted local adapter, then recompute the
saved JSON/HTML/JUnit reports. Uses the harness source from the pinned Action checkout without
installing or downloading a harness release. Requires Python 3.10+ and Bash; install your
adapter's dependencies separately. The Action does not upload files or grant authority.

In a job with your repository checked out and Python available:

```yaml
permissions:
  contents: read

steps:
  # Check out your repository and set up Python with reviewed, SHA-pinned Actions first.
  - name: Check staging authority
    uses: immu4989/awesome-agentic-usecases/.github/actions/aau-authority-check@<FULL_COMMIT_SHA>
    with:
      inventory: safety/inventory.json
      adapter-command: python safety/adapter.py
      adapter-artifact: safety/adapter.py
      output: authority-results
      timeout: "10"
```

Replace `<FULL_COMMIT_SHA>` with a reviewed commit containing this Action. This is a job fragment,
not a complete workflow. Use isolated staging runners, public/synthetic inputs, read-only repository
permissions, and no production credentials. The Action is not a sandbox and does not constrain
adapter network or filesystem access. Never put untrusted event text into adapter commands.

## Results and failure handling

- Exit 0: all synthetic cases matched and saved reports verified.
- Exit 1: behavioral failures; verified reports are retained for diagnosis.
- Exit 2: input, adapter, output, or verification error; output may be incomplete.

The `reports` output identifies the configured directory, not proof it exists. The directory
must not already exist. Inventory, adapter, and output paths must be workspace-relative and
remain within the workspace. Spaces are supported. Inputs are passed as environment variables,
not inserted into shell scripts.

An aggregate job summary is added after verification. Add your own **always-run** collection
step for `authority-results/results.xml` or the complete directory. Keep the evaluation's failing
status; do not suppress failures just to retain diagnostics. An absent `completion.json` means
output is incomplete.

**Review before upload:** the bundle includes inventory and test inputs, not just reduced reports.
Retention and access policies belong to the caller. The Action never uploads automatically.
Preserve the original adapter for offline verification:

```bash
aau bom verify-authority-check authority-results \
  --adapter-artifact safety/adapter.py --workspace .
```

Entrypoint hashes do not bind all dependencies, configuration, or remote state. Passing does not
establish live enforcement, production safety, compliance, certification, or an ATO. See the
[staging quickstart](../../../agent-capability-bom/STAGING_QUICKSTART.md).
