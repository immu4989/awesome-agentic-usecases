// A development tripwire, not an operating-system sandbox or a general egress policy.
import net from 'node:net';
import tls from 'node:tls';
import http from 'node:http';
import https from 'node:https';
import dns from 'node:dns';
import dgram from 'node:dgram';

export function installGuard(onAttempt = () => {}) {
  const attempts = [], restore = [];
  function replace(object, key, name) {
    const original = object[key];
    object[key] = (...args) => {
      let kind = 'unexpected_network_attempt';
      // Recognize but still DENY the pinned producer's opt-out notification. Never retain
      // the body, random user ID, headers, or an unrecognized destination in the report.
      if (name === 'fetch' && args[0] === 'https://r.promptfoo.app/' && args[1]?.method === 'POST') {
        try {
          const body = JSON.parse(args[1].body);
          if (body.event === 'feature_used' && body.meta?.feature === 'telemetry disabled') {
            kind = 'blocked_telemetry_disabled_notification';
          }
        } catch { /* Remains an unexpected attempt. */ }
      }
      attempts.push({api: name, kind, blocked: true});
      onAttempt(attempts.at(-1), attempts.length);
      throw new Error('AAU_PROBE_NETWORK_BLOCKED');
    };
    restore.push(() => { object[key] = original; });
  }
  replace(globalThis, 'fetch', 'fetch');
  replace(net.Socket.prototype, 'connect', 'socket.connect');
  replace(tls, 'connect', 'tls.connect');
  for (const [object, prefix, names] of [
    [http, 'http', ['request', 'get']], [https, 'https', ['request', 'get']],
    [dns, 'dns', ['lookup', 'resolve']], [dns.promises, 'dns.promises', ['lookup', 'resolve']],
    [dgram.Socket.prototype, 'udp', ['send', 'connect']],
  ]) for (const name of names) replace(object, name, `${prefix}.${name}`);
  return {attempts, restore: () => restore.reverse().forEach(fn => fn())};
}
