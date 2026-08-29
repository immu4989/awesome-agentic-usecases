# ABP 0.2 conformance guide

ABP conformance is evidence about a named profile, suite, implementation, version, and run. It is
not a permanent property of a product.

## Reference levels

| Level | Required evidence | What it means |
|---|---|---|
| Schema-valid | Profile and runtime suite pass the executable validators | The public artifacts have the required structure and safety boundaries |
| Reference-exact | All 50 reference outcomes, reason codes, and states recompute | The implementation matches the AAU reference policy on the committed synthetic suite |
| Adapter-reproduced | A named recorded-event adapter produces the same normalized events | The reviewed envelope mapping is repeatable for the named example version |
| Independently reproduced | A different organization publishes a same-suite aggregate receipt | Another organization obtained the declared result under its documented conditions |

No level means certification, compliance, production enforcement, an Authority to Operate,
government endorsement, or authorization to connect an agent to consequential systems.

## Required commands

```bash
PYTHONPATH=agentic-cyber-resilience pytest agentic-cyber-resilience/tests -q

python3 agentic-cyber-resilience/aau_runtime.py evaluate \
  agentic-cyber-resilience/examples/synthetic-critical-infrastructure-profile.json \
  agentic-cyber-resilience/evals/runtime-conformance-suite.json \
  --out /tmp/aau-runtime-receipt.json

python3 agentic-cyber-resilience/aau_runtime.py verify \
  /tmp/aau-runtime-receipt.json \
  --profile agentic-cyber-resilience/examples/synthetic-critical-infrastructure-profile.json \
  --suite agentic-cyber-resilience/evals/runtime-conformance-suite.json
```

## Implementation claims

A public implementation report must name:

- ABP profile, runtime suite, and receipt versions.
- Adapter name and the exact framework/specification version reviewed.
- Whether the gateway was advisory, blocking, or connected to a separate executor.
- The identity, time, revocation, log, and enforcement systems outside the ABP reference.
- Counts and denominators for unsafe allows and legitimate-action preservation.
- In-flight, rollback, and external-side-effect limitations.
- The accountable human stop and restart roles.
- A same-suite receipt and its SHA-256 digest.

Claims should use “matched the reference decisions on the named synthetic suite,” not “ABP
certified,” “safe,” “compliant,” or “approved.”
