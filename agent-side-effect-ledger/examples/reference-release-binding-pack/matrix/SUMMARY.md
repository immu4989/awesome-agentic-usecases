## AAU side-effect safety matrix

**EVIDENCE PASSED** · 72/72 exact checked outcomes · 0 unsafe outcomes · 0 availability losses · 3 uncertainties preserved

| Component | Exact | Cases | Unsafe | Availability loss | Unresolved |
|---|---:|---:|---:|---:|---:|
| Intent + approval semantics | 48/48 | 12 | 0 | 0 | 0 |
| Fresh-process crash recovery | 12/12 | 12 | 0 | 0 | 3 |
| Multi-process concurrency | 12/12 | 12 | 0 | 0 | 0 |

Crash and concurrency evidence bind **`notification-service` / `send_synthetic_notice`**. The semantic suite covers 2 tool-operation pairs; only the named pair has all three gates.

Adapter entrypoint artifacts: `semantics:383ba97b9b39` · `crash_recovery:2d8e4e44c260` · `concurrency:c3c35c77fd72`

Captured execution materials: **8** files · **42** unresolved standard-library or installed-package import names remain explicit.

Expected answers were not sent to adapters. Every command is trusted local code and must be restricted to public-synthetic staging state.

A passing matrix is bounded evidence for these exact adapters and suites. It is not proof of production atomicity, linearizability, exactly-once execution, safety, certification, compliance, deployment approval, or an Authority to Operate.
