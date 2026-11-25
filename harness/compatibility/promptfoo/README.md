# Native Promptfoo export compatibility exercise

This development check executes **Promptfoo 0.126.0**, using two fixed synthetic inputs,
local echo/error providers, and deterministic `equals` assertions. It tests actual SDK JSON
exports against AAU's offline importer. It is not a live-model benchmark. Promptfoo is **not**
an AAU runtime dependency: ordinary `aau promptfoo-eval` imports never execute received
provider code, assertions, or configuration.

## Four exports, twelve checks

| Native export | Required importer behavior |
| --- | --- |
| Complete two-test/two-column evaluation | Import the passing column and, separately, the assertion-failing column with exact scores |
| Second test lacks the named `match` metric | Preserve absence; never replace it with zero |
| Provider error in the unselected column | Reject the complete delivery, even when the selected column passed |
| Two repetitions of each test | Reject against the predeclared two-test inventory; do not count repeated observations as new independent cases |

Those are five projection/rejection checks. Two diagnostic checks retain the rejected provider-error
and repeated exports, account for all rows, and replay without producing an evaluation. Two further
controls reject a wrong mapping pin and a changed derived evaluation. Every successful pack preserves the original export bytes
and replays with its independently supplied mapping hash. The expected inventory and prompt
identities are fixed before reading exports, not reconstructed from whatever rows arrived. Two further
policy-handoff checks select opposite columns from the **same synthetic native export**, retaining
both the met and unmet requested policy outcomes. These are not independent systems or model runs.
One source-index check retains the native provider-error diagnostic while the separately requested
conversion remains missing; verified diagnostic evidence must not satisfy a conversion requirement.
The checker first verifies that the exporter actually produced each intended state: an
unrelated provider failure cannot accidentally satisfy the negative control.

## Reproduce from a reviewed checkout

Use Node **22.22.0 or newer**, npm, and Python 3.12 with the `build` package available.
Dependency installation requires network access. Only the fixed reviewed producer definitions
are executed; do not substitute supplied provider code or private datasets.

From the repository root:

```bash
promptfoo_probe=$(mktemp -d /tmp/aau-promptfoo-probe.XXXXXX)
python3.12 -m build --outdir "$promptfoo_probe/dist" harness
python3.12 -m venv "$promptfoo_probe/venv"
"$promptfoo_probe/venv/bin/python" -m pip --isolated install --no-index --no-deps \
  "$promptfoo_probe"/dist/aau_harness-*.whl
cp harness/compatibility/promptfoo/package.json harness/compatibility/promptfoo/package-lock.json "$promptfoo_probe/"
cp harness/compatibility/promptfoo/produce.mjs harness/compatibility/promptfoo/network-guard.mjs \
  harness/compatibility/promptfoo/network-guard.test.mjs "$promptfoo_probe/"
cp harness/tools/check_promptfoo_exporter.py "$promptfoo_probe/check_promptfoo_exporter.py"
cd "$promptfoo_probe"
node --version
npm --version
npm ci --ignore-scripts --no-audit --no-fund
node --test network-guard.test.mjs
env -i PATH="$PATH" LANG=C.UTF-8 node produce.mjs --out "$promptfoo_probe/exports"
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 "$promptfoo_probe/venv/bin/python" \
  check_promptfoo_exporter.py --source "$promptfoo_probe/exports" --out "$promptfoo_probe/checked"
```

Both output directories must be new. CI uses its already-built wheel and runs the checker
outside the checkout in a fresh Python environment. The SDK uses `writeLatestResults: false`
and native `outputPath` JSON export; no database initialization is needed. npm lifecycle
scripts are disabled. The lock records registry integrity hashes, but the interpreter, OS,
and platform-specific dependency selection are not a hermetic environment attestation.

`exports/producer.json` records the producer/Node versions, platform, code/lock hashes,
source hashes, native outcome counts, and blocked network attempts. `checked/compatibility.json`
records twelve checks and the producer receipt hash. Raw exports remain under both output
trees; deliberately corrupted replay evidence is labeled `tampered-negative-control`.
Timestamps and generated IDs can vary: this checks fixed outcomes and exact preservation
within a run, not byte-identical exports across independent runs.

## Network and disclosure boundaries

The producer runs without inherited environment credentials and sets fresh config/cache/log
directories, a fixed author, and telemetry/update/sharing/remote-generation disable flags
before loading the SDK. JavaScript tripwires throw before dispatch on intercepted fetch,
HTTP(S), TCP/TLS, DNS, and UDP calls. Their unit tests exercise the intercepted paths.

**Observed behavior in the pinned release:** despite the telemetry disable flag, the SDK
attempted one `feature_used` notification with feature `telemetry disabled`. The tripwire
blocked it before dispatch. This is recorded, not described as zero network attempts.
The producer requires exactly that known blocked attempt; any additional or unrecognized
attempt fails the process, including an intercepted late background call. The report retains
only the API, classification, and blocked status, not the notification body or random user ID.

These are development assertions, **not an OS-enforced air gap** or a defense against malicious
native code, subprocesses, or uninstrumented network APIs. Installation is a separate,
network-enabled phase. Do not run untrusted tasks under this guard or treat it as a production
egress policy. Native logs/config files can still include local runtime metadata; keep them
local and review every file before sharing. CI does not upload these outputs.

## Evidence and limitations

Primary sources reviewed November 23, 2026:

- [Promptfoo Node package API](https://www.promptfoo.dev/docs/usage/node-package/),
  [configuration reference](https://www.promptfoo.dev/docs/configuration/reference/), and
  [echo provider](https://www.promptfoo.dev/docs/providers/echo/).
- [Documented telemetry controls](https://www.promptfoo.dev/docs/configuration/telemetry/).
  The blocked opt-out observation above is specific to this pinned execution, not a claim
  about all versions or the behavior of every documented option.
- [Pinned producer source](https://github.com/promptfoo/promptfoo/tree/0.126.0) and
  [published 0.126.0 package](https://www.npmjs.com/package/promptfoo/v/0.126.0).

This adds native producer execution to the separate retained
[upstream 0.118.10 export regression](../../tests/fixtures/promptfoo/README.md).
Synthetic unit fixtures test checker failures; only the SDK exercise establishes the native
observations. Neither proves source authenticity, scoring validity, model quality,
all-version compatibility, independent reproduction, government adoption, or certification.
No latency, cost, API-call count, or evaluation-context fingerprint is inferred by the importer.
