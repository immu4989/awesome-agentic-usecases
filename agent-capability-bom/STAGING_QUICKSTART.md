# From an unfinished adapter to reviewable evidence

**For teams connecting a staging policy engine—not deploying a production agent.**
No model API key is required for the supplied unfinished adapter. Your own integration may
need dependencies or a staging service; keep production credentials and targets out of this exercise.

## 1. Install the current repository harness

From your checkout of this repository, using Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e harness
```

These commands target the current checkout, not a promise that the latest PyPI release has
every reporting command. Record `git rev-parse HEAD` with your review so others can use the
same implementation. The activation command above is for POSIX shells.

## 2. Create an intentionally unfinished adapter

```bash
aau bom init-adapter agent-capability-bom/examples/candidate.json --out authority-demo
```

This copies a **synthetic example inventory** and creates `authority-demo/adapter.py`.
The adapter blocks every request with `ADAPTER_NOT_IMPLEMENTED`. It is deliberately not a
policy engine. The output directory must not already exist; choose a new name if necessary.

## 3. Run the first check and preserve its failure

From the repository root:

```bash
aau bom check-authority authority-demo/inventory.json \
  --command "python authority-demo/adapter.py" \
  --adapter-artifact authority-demo/adapter.py --workspace . \
  --out authority-run-001
```

**Expected: exit 1**, with diagnostic files saved. A failing stub is a successful setup test,
not passing authority evidence. In CI, keep this exit status; collect reports in a separate
always-run step instead of appending `|| true` to the evaluation.

| File | What the reviewer gets |
|---|---|
| `inventory.json`, `suite.json` | Exact source inventory and generated synthetic tests |
| `receipt.json` | Recorded outcomes and adapter entrypoint binding |
| `report.json` | Unsafe allows, legitimate blocks, and reason differences |
| `review.html` | Offline, script-free human-readable findings |
| `results.xml` | Every test result in JUnit-style XML for a CI test viewer |
| `completion.json` | Marker written only after the other outputs finish |

Open `review.html` locally. Do not interpret it or the completion marker as a signature or
independent verification. The saved inventory and suite contain inputs; review all files before sharing.

## 4. Verify without executing the adapter again

```bash
aau bom verify-authority-check authority-run-001 \
  --adapter-artifact authority-demo/adapter.py --workspace .
```

**Expected: exit 1 again.** This means the failed evidence is internally consistent—not that
verification could not run. The command checks adapter bytes and recomputes every report.

| Exit | Meaning | Next action |
|---|---|---|
| `0` | All synthetic cases match and evidence verifies | Review scope and production gaps with the responsible humans |
| `1` | Valid behavioral failures | Read the case-level report; repair the staging integration |
| `2` | Invalid inputs, protocol, output, or verification error | Read stderr; do not treat an absent report as a passing test |

If `completion.json` is absent, output is incomplete. Do not reuse that directory as a new
output target. The verifier also rejects extra files, so keep reviewer notes outside the bundle.

## 5. Connect your staging policy and compare a fix

Implement `decide()` in a **new adapter file** using only the supplied input facts and your
reviewed staging policy. Do not read expected answers from the generated suite, decode case
IDs, or import the reference decision function to claim integration evidence. The public
reference example is useful for protocol learning, not independent validation.

Keep the original adapter bytes at their original path. For example, if your next adapter is
`authority-demo/candidate.py`, run:

```bash
aau bom check-authority authority-demo/inventory.json \
  --command "python authority-demo/candidate.py" \
  --adapter-artifact authority-demo/candidate.py --workspace . \
  --out authority-run-002

aau bom compare-conformance authority-run-001/receipt.json authority-run-002/receipt.json \
  authority-run-001/inventory.json authority-run-001/suite.json \
  --before-artifact authority-demo/adapter.py --after-artifact authority-demo/candidate.py \
  --workspace . --format html --out authority-comparison.html
```

The comparison requires identical inventory and suite inputs and detects introduced failures
even when the aggregate score is unchanged. Editing the inventory starts a different evaluation;
do not force a like-for-like comparison across changed contracts.

## Before presenting this to an organization or agency

- Name the exact policy boundary tested and the staging integration actually exercised.
- Keep the repository revision, both adapter entrypoints, source inputs, and recorded outputs.
- Disclose that entrypoint hashes do not bind all dependencies, configuration, or remote services.
- List untested identities, permissions, data, failure modes, and production enforcement paths.
- Review identifiers and reason codes for sensitive information before publishing results.
- Do not claim compliance, certification, an authorization to operate, or production safety.

The runner executes local code and is **not a sandbox**. Tests are public, synthetic, and finite.
Passing them supports only the recorded observations. Human domain and security review remains
necessary before any consequential use.

Continue with the [complete command reference and boundaries](README.md).
