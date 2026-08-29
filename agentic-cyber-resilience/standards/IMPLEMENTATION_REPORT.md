# ABP 0.2 reference implementation report

Release date: 2026-08-29

Implementation: `aau_runtime.py`

Dependencies: Python standard library only

Network behavior: none
Tool execution: none

## Implemented surface

- Ten stateful runs and fifty ordered recorded events.
- Four runtime states: active, paused, safe-stopped, and revoked.
- Policy-epoch and sequence checks.
- Scope, destination, approval, token-audience, and token-passthrough decisions.
- Delegation ceiling and peer checks.
- Monitor, critical-alert, human pause, recovery, and revocation transitions.
- Append-only result hash chain and full deterministic recomputation.
- Recorded-envelope normalization for generic JSON, MCP, OpenAI Agents, LangGraph, CrewAI, and
  AutoGen shapes.
- Non-overwriting five-file evidence pack with byte manifest.

## Reference result

The committed suite is expected to produce:

- Exact outcome: 1.0
- Exact reason codes: 1.0
- Exact state transition: 1.0
- Unsafe allow: 0.0
- Legitimate allow preservation: 1.0
- Required pause or safe-stop success: 1.0

These are construction checks over the reference policy and reviewed synthetic oracle. They are
not empirical security estimates and must not be presented as production performance.

## Known limitations

- The gateway returns a decision but cannot prove that an external executor honored it.
- Policy-epoch changes are local simulation state, not distributed revocation.
- The SHA-256 chain provides integrity after receipt creation, not identity, trusted time, or
  non-repudiation.
- Adapter examples represent recorded dictionary shapes and are not maintained by framework
  vendors.
- No in-flight call, queue, credential, subprocess, network route, or external side effect is
  cancelled.
- The reference uses one synthetic authority profile and does not estimate domain transfer.

## Reproduction

Run the commands in [CONFORMANCE.md](CONFORMANCE.md). A different implementation can publish a
privacy-bounded same-suite receipt through the
[Public-Value Pilot Network](../../public-value-pilot-network/) or community evidence route.
