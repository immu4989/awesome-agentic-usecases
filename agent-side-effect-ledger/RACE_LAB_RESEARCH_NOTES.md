# Multi-Process Race Lab research notes

Research checked on 2026-09-03. The lab tests simultaneous-looking fresh-process attempts against a
shared public-synthetic state directory, then separately inspects the durable result. It is a
portable concurrency challenge, not a formal linearizability proof.

## Source-to-test ledger

| Primary source fact | Executable design choice | Explicit non-claim |
|---|---|---|
| AWS Agentic AI Lens AGENTREL06-BP04 recommends deterministic idempotency keys and conditional writes, noting that two parallel retries should not both create a record | Cases launch 2, 4, 8, and 16 processes with an identical key and intent; effect count must remain one | Passing the synthetic races does not prove a distributed exactly-once guarantee |
| The same AWS guidance says a key should be derived from operation inputs and propagated across workflows | Changed-intent cases reuse one key with multiple intent digests and require conflicts rather than cache hits | The lab does not prescribe one universal key derivation or retention policy |
| SQLite documents that separate connections see only committed transactions and that writes are serialized | The reference adapter uses a separate SQLite connection per process and `BEGIN IMMEDIATE` around lookup plus insert | SQLite behavior does not prove another database, queue, API, or multi-region topology is safe |
| PostgreSQL documents that Serializable transactions reject executions that cannot correspond to a serial order | The research contract treats a serializable outcome or explicit conflict as valid, rather than requiring every contender to commit | The lab is not PostgreSQL conformance and does not exercise serialization retry loops |

## Premise checks

1. **Check-then-act must share one atomic boundary.** A query followed by an unguarded external write
   can let every worker observe absence. The reference keeps lookup and insertion inside one write
   transaction and verifies the resulting store after the race.
2. **Responses are not the target.** The runner counts `committed`, `replayed`, `conflict`, and
   `blocked` responses, but also invokes a separate inspection phase. A mismatch remains visible.
3. **Winner identity is intentionally discarded.** Which equivalent worker commits first is a
   scheduler detail. Receipts retain sorted outcome/reason groups so the same valid race is
   byte-deterministic across runs.
4. **Deny-all is not safe conformance.** Distinct valid keys and mixed-authority cases require
   legitimate effects. Missing-effect counts are separate from duplicate-effect counts.
5. **Intent equality and key equality are different.** Two distinct keys for one intent produce two
   effects in this profile; the adapter cannot infer authorization or deduplication scope from the
   digest alone.
6. **A launch barrier is not an overlap proof.** Operating-system scheduling may serialize some or
   all adapter work. More rigorous deployment tests should control workload timing, multiple hosts,
   network partitions, database failover, and the real target's atomic boundary.
7. **The command is trusted code.** Shell-free parsing prevents shell expansion by the runner but
   does not sandbox the adapter or remove inherited credentials and network access.

## Official sources

- [AWS Agentic AI Lens — AGENTREL06-BP04](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel06-bp04.html)
- [SQLite — Isolation Between Database Connections](https://www.sqlite.org/isolation.html)
- [PostgreSQL 18 — Transaction Isolation](https://www.postgresql.org/docs/18/sql-set-transaction.html)
