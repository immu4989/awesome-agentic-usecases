# Two-Process Crash Lab research notes

Research checked on 2026-09-03. The lab tests whether a fresh adapter process can choose a bounded
next action from synthetic persisted state after a declared process crash. It does not simulate or
claim physical-storage durability.

## Source-to-test ledger

| Primary source fact | Executable design choice | Explicit non-claim |
|---|---|---|
| AWS Agentic AI Lens AGENTREL06-BP04 says retries without idempotency can duplicate side effects; it recommends deterministic keys, checking prior results, and propagating keys across multi-step workflows | Every crash case preserves one intent-bound key and scores any unsafe resume separately | Following the pattern does not establish exactly-once behavior |
| The AWS Builders' Library describes the ambiguous state after a timeout and the need to reconcile before blindly recreating a singleton resource | Crashes after dispatch enter target lookup; committed and absent results have different recovery paths | The synthetic target is not an AWS service or external-system test |
| PostgreSQL documents write-ahead logging as recording and flushing recovery information before related data changes | The reference adapter persists a journal state before advancing to later phases | JSON files are not a database WAL and do not inherit PostgreSQL guarantees |
| SQLite documents explicit flush, commit, and hot-journal recovery steps, while also identifying filesystem and storage assumptions | The lab names six boundaries and restarts a new process against only the files that survived the injected point | `fsync` plus exit code 86 is not a power-loss, torn-write, or device-cache test |

## Premise checks

1. **A process crash is not a power failure.** `os._exit(86)` bypasses normal Python shutdown and
   forces fresh-process recovery, but the operating system, filesystem, and device remain alive.
2. **A flush call is not a universal durability proof.** The reference adapter flushes and calls
   `fsync`, yet hardware caches, mount options, container volumes, replication, and database commit
   settings remain outside the experiment.
3. **Two durable stores are still two stores.** A local journal and an external target can diverge
   between operations. The correct response to that window is reconciliation or an explicit hold,
   not a local hash claiming distributed atomicity.
4. **Unknown is a valid safety result.** Three reference cases deliberately keep the effect count
   unknown when the binding journal, target lookup, or retention guarantee is unavailable. Treating
   those holds as test failures would reward fabricated certainty.
5. **Recovery authority can expire.** A target-confirmed absence does not revive an expired human
   approval or agent authority. The isolated cases require a new approval or authorization before
   another dispatch.
6. **The oracle is withheld, not secret.** The suite is intentionally public for review. Each adapter
   request removes `expected`, so accidental answer echoing fails, but deliberate overfitting remains
   possible.
7. **The adapter is trusted executable code.** The runner parses its command without a shell and
   gives it a temporary state directory. That does not sandbox the program or remove inherited
   operating-system authority.

## Official sources

- [AWS Agentic AI Lens — AGENTREL06-BP04](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel06-bp04.html)
- [AWS Builders' Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- [PostgreSQL 18 — Write-Ahead Logging](https://www.postgresql.org/docs/current/wal-intro.html)
- [SQLite — Atomic Commit](https://sqlite.org/atomiccommit.html)
