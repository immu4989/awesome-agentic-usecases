import assert from 'node:assert/strict';
import test from 'node:test';
import net from 'node:net';
import tls from 'node:tls';
import http from 'node:http';
import https from 'node:https';
import dns from 'node:dns';
import dgram from 'node:dgram';
import {installGuard} from './network-guard.mjs';

test('every intercepted path throws before dispatch, including the opt-out notification', () => {
  const original = globalThis.fetch;
  const guard = installGuard();
  try {
    const calls = [
      () => fetch('https://example.invalid/'),
      () => net.Socket.prototype.connect.call({}, 443, 'example.invalid'),
      () => tls.connect(443, 'example.invalid'),
      () => http.request('http://example.invalid/'), () => http.get('http://example.invalid/'),
      () => https.request('https://example.invalid/'), () => https.get('https://example.invalid/'),
      () => dns.lookup('example.invalid'), () => dns.resolve('example.invalid'),
      () => dns.promises.lookup('example.invalid'), () => dns.promises.resolve('example.invalid'),
      () => dgram.Socket.prototype.send.call({}, Buffer.from('not sent'), 123, 'example.invalid'),
      () => dgram.Socket.prototype.connect.call({}, 123, 'example.invalid'),
    ];
    for (const call of calls) assert.throws(call, /AAU_PROBE_NETWORK_BLOCKED/);
    assert.equal(guard.attempts.length, 13);
    assert.ok(guard.attempts.every(a => a.kind === 'unexpected_network_attempt' && a.blocked));
    assert.throws(() => fetch('https://r.promptfoo.app/', {method: 'POST', body: JSON.stringify({
      event: 'feature_used', meta: {feature: 'telemetry disabled', user_id: 'not-retained'},
    })}), /AAU_PROBE_NETWORK_BLOCKED/);
    assert.deepEqual(guard.attempts.at(-1), {api: 'fetch', kind: 'blocked_telemetry_disabled_notification', blocked: true});
    assert.ok(!JSON.stringify(guard.attempts).includes('not-retained'));
  } finally { guard.restore(); }
  assert.equal(globalThis.fetch, original);
});

test('unexpected endpoint, malformed body, or different event cannot be classified as opt-out', () => {
  const observed = [];
  const guard = installGuard((attempt, count) => observed.push({kind: attempt.kind, count}));
  try {
    for (const [url, options] of [
      ['https://r.promptfoo.app/', {method: 'POST', body: '{'}],
      ['https://r.promptfoo.app/', {method: 'POST', body: '{"event":"eval_ran"}'}],
      ['https://example.invalid/', {method: 'POST', body: '{"event":"feature_used","meta":{"feature":"telemetry disabled"}}'}],
    ]) assert.throws(() => fetch(url, options), /AAU_PROBE_NETWORK_BLOCKED/);
    assert.ok(guard.attempts.every(a => a.kind === 'unexpected_network_attempt'));
    assert.deepEqual(observed.map(a => a.count), [1, 2, 3]);
  } finally { guard.restore(); }
});
