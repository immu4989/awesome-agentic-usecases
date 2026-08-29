# Agent Control Effectiveness Observatory

> Measure the control—not the marketing claim.

The observatory runs matched, deterministic policy arms over the same synthetic agent-boundary
cases. It keeps unsafe allows, exact outcomes, legitimate-action preservation, and control
coverage separate. It never turns them into a universal score or vendor ranking.

The reference experiment compares:

1. Capability without declared boundary controls.
2. Identity and token checks alone.
3. The complete ABP 0.2 reference control set.

```bash
python3 agent-control-observatory/aau_observatory.py evaluate \
  agent-control-observatory/experiments/authority-control-ladder.json \
  --out /tmp/aau-control-report.json

python3 agent-control-observatory/aau_observatory.py verify \
  /tmp/aau-control-report.json \
  --experiment agent-control-observatory/experiments/authority-control-ladder.json
```

The twelve matched cases include three legitimate actions and nine boundary failures spanning
scope, identity, token audience, delegation, safe stopping, monitor loss, revocation, and evidence
tampering. The policy arms are transparent synthetic models—not measurements of a commercial
product, model, identity provider, or enforcement stack.

## Add a real control arm

Run the same case identifiers through your authorized staging control, publish only reviewed
aggregate outcomes and reason codes, preserve the implementation and environment limitations, and
bind the result through the repository's Evidence Commons. Do not submit credentials, private
telemetry, exploit paths, live targets, or product claims that the evidence cannot support.
