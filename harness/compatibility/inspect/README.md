# Native Inspect producer interoperability exercise

This maintainer check runs **Inspect 0.3.291 itself**, using only two fixed synthetic samples,
two epochs, its `mockllm/model` provider, and label/numeric scorers. No real model or user dataset
is involved. The importer remains passive: this separate development tool executes trusted
fixed tasks, never a supplied log, task module, provider configuration, or external dataset.

## What must pass

1. The native JSON export projects to all four expected sample/epoch observations, with both
   scores equal to one for the correct sample and zero for the incorrect sample.
2. Inspect's official `write_eval_log` / `read_eval_log` APIs perform JSON → `.eval` → JSON
   conversion; the second JSON export must project to the same scores and complete census.
3. A deliberately interrupted solver produces evidence the strict importer **rejects**.
4. A separate diagnostic retains that interrupted evidence and verifies without repairing it
   or upgrading its conversion eligibility.

Both successful conversion packs preserve their own raw JSON bytes and replay with the mapping
plan's SHA-256. The probe also rejects an invented evaluation-context fingerprint. The native
`.eval` file is retained, but AAU does not implement a second binary-log parser. Inspect documents
multiple binary/storage variants and recommends its official APIs: see
[evaluation logs](https://inspect.aisi.org.uk/eval-logs.html) and the upstream
[format round-trip tests](https://github.com/UKGovernmentBEIS/inspect_ai/blob/c574b6bf6674e6d5f6cbb0f95059d7427b23d54b/tests/log/test_log_formats.py).

## Run from a reviewed checkout

Use Python 3.12 and a disposable environment. Installing Inspect requires network access to a
package index; running these fixed tasks needs no model credentials. Inspect is **not** added
to AAU's runtime requirements. From the repository root, prepare a current wheel first:

```bash
probe_dir=$(mktemp -d /tmp/aau-inspect-probe.XXXXXX)
python3.12 -m venv "$probe_dir/venv"
"$probe_dir/venv/bin/python" -m pip --isolated install --only-binary=:all: inspect-ai==0.3.291 build==1.3.0
"$probe_dir/venv/bin/python" -m build --outdir "$probe_dir/dist" harness
"$probe_dir/venv/bin/python" -m pip --isolated install --no-index --no-deps "$probe_dir"/dist/aau_harness-*.whl
cp harness/tools/check_inspect_exporter.py "$probe_dir/check_inspect_exporter.py"
cd "$probe_dir"
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$probe_dir/venv/bin/python" \
  "$probe_dir/check_inspect_exporter.py" --out "$probe_dir/results"
```

The tool refuses to overwrite an existing output. CI follows this path with its already-built
local wheel and a separate producer environment; no native logs are uploaded as artifacts.
`results/compatibility.json` records producer/Python/dependency versions, raw-log hashes, four
check outcomes, and the limitations below. Inspect timestamps and UUIDs vary: this asserts the
fixed projection, census, and rejection behavior, **not** byte-identical independent runs.

## Permission, privacy, and claim boundaries

- Inspect may use its normal per-user sample-buffer/cache directories outside `--out`. A
  restricted filesystem can block those writes; obtain approval or use an approved disposable
  runner. Do not bypass an organization's filesystem policy. Trace files are directed under
  the output using the pinned version's private logger initialization API; this is test-only
  setup, not an additional supported AAU runtime API.
- The process runs without inherited environment credentials. Python socket tripwires reject
  attempted IPv4/IPv6 `connect`, `connect_ex`, and `sendto` calls. They are test assertions, not
  an OS-enforced network sandbox, a DNS-blocking guarantee, or protection against native code
  or subprocess networking. Only the fixed reviewed tasks are authorized by this recipe.
- Mock token usage is explicitly constructed as zero, avoiding the mock provider's default
  tokenizer download. It is not measured usage; AAU imports none of those token/cost/latency
  fields. No efficiency, live-model quality, or performance claim follows.
- Raw logs can include local paths/runtime metadata even with synthetic samples. Keep them
  local; review every file before disclosure. This check neither collects private agency data
  nor publishes results automatically.
- Only the top-level producer is version-pinned; dependency versions are recorded, not fully
  hash-locked. This is not a hermetic dependency/environment attestation or all-platform test.
- Observed locally on November 20, 2026 with Python 3.12 and Inspect 0.3.291. The retained
  upstream [0.3.100 fixture](../../tests/fixtures/inspect-ai/README.md) provides a separate
  historical-format regression. Neither establishes all-version compatibility, independent
  reproduction, scoring validity, government adoption, certification, or legal compliance.
