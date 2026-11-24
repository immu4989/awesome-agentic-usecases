// Executes only these fixed synthetic definitions, never received evaluation files/configs.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {installGuard} from './network-guard.mjs';

assert.equal(process.argv.length, 4, 'usage: node produce.mjs --out NEW_DIRECTORY');
assert.equal(process.argv[2], '--out');
const out = path.resolve(process.argv[3]);
fs.mkdirSync(out, {recursive: false});
Object.assign(process.env, {
  PROMPTFOO_DISABLE_TELEMETRY: '1', PROMPTFOO_DISABLE_UPDATE: '1',
  PROMPTFOO_DISABLE_SHARING: '1', PROMPTFOO_DISABLE_REMOTE_GENERATION: '1',
  PROMPTFOO_CACHE_ENABLED: 'false', PROMPTFOO_CONFIG_DIR: path.join(out, 'config'),
  PROMPTFOO_CACHE_PATH: path.join(out, 'cache'), PROMPTFOO_LOG_DIR: path.join(out, 'logs'),
  PROMPTFOO_AUTHOR: 'AAU synthetic compatibility probe', LOG_LEVEL: 'error',
});
const guard = installGuard((attempt, count) => {
  // Preserve failure even if an SDK background task catches the thrown denial after our last check.
  if (attempt.kind !== 'blocked_telemetry_disabled_notification' || count > 1) process.exitCode = 1;
});
const entry = fileURLToPath(import.meta.resolve('promptfoo'));
const packagePath = path.resolve(path.dirname(entry), '../../package.json');
const metadata = JSON.parse(fs.readFileSync(packagePath));
assert.equal(metadata.version, '0.126.0', 'unsupported producer version');
const {evaluate} = await import('promptfoo');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const summaries = [];
for (const variant of ['complete', 'missing-named-score', 'provider-error', 'repeated']) {
  const tests = ['alpha', 'beta'].map(value => ({
    vars: {value}, assert: [{type: 'equals', value, metric: 'match'}],
  }));
  if (variant === 'missing-named-score') delete tests[1].assert[0].metric;
  const providers = variant === 'provider-error' ? [{
    id: () => 'aau-synthetic-error',
    callApi: async prompt => prompt.startsWith('other:')
      ? {error: 'AAU_SYNTHETIC_PROVIDER_ERROR'} : {output: prompt},
  }] : ['echo'];
  const filename = `${variant}.json`;
  const result = await evaluate({
    prompts: ['{{value}}', 'other: {{value}}'], providers, tests,
    sharing: false, writeLatestResults: false, outputPath: path.join(out, filename),
  }, {maxConcurrency: 1, cache: false, repeat: variant === 'repeated' ? 2 : 1});
  const summary = await result.toEvaluateSummary();
  assert.equal(summary.version, 3);
  assert.equal(summary.results.length, variant === 'repeated' ? 8 : 4);
  const raw = fs.readFileSync(path.join(out, filename));
  const exported = JSON.parse(raw);
  assert.equal(exported.metadata.promptfooVersion, '0.126.0');
  // JSON omits undefined SDK properties; compare JSON representations without changing export bytes.
  assert.deepEqual(exported.results.results, JSON.parse(JSON.stringify(summary.results)),
    'official JSON export differs from the JSON representation of native result rows');
  summaries.push({variant, file: filename, source_sha256: sha(raw), row_count: summary.results.length,
    outcomes: {successes: summary.stats.successes, failures: summary.stats.failures, errors: summary.stats.errors}});
}
// The documented flag still attempts one opt-out notification in this pinned release.
// It was blocked, not silently allowed or erased. Any additional/unrecognized attempt fails.
assert.deepEqual(guard.attempts, [{api: 'fetch', kind: 'blocked_telemetry_disabled_notification', blocked: true}]);
const report = {probe_version: 'aau-promptfoo-native-export/1.0', producer_version: metadata.version,
  node_version: process.version, platform: process.platform, arch: process.arch,
  producer_package_sha256: sha(fs.readFileSync(packagePath)), producer_entrypoint_sha256: sha(fs.readFileSync(entry)),
  source_lock_sha256: sha(fs.readFileSync(new URL('./package-lock.json', import.meta.url))),
  producer_script_sha256: sha(fs.readFileSync(fileURLToPath(import.meta.url))),
  guard_script_sha256: sha(fs.readFileSync(new URL('./network-guard.mjs', import.meta.url))),
  exports: summaries, blocked_network_attempts: guard.attempts,
  boundary: 'Synthetic native SDK exports with deterministic local providers and assertions, not model evaluation. '
    + 'All intercepted network attempts were blocked. JavaScript tripwires do not attest an OS-level air gap, '
    + 'cover native-code bypasses or subprocesses, authenticate sources, or establish agency approval.'};
fs.writeFileSync(path.join(out, 'producer.json'), JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
console.log('Four native Promptfoo exports produced; one opt-out notification attempt blocked; no model services used.');
