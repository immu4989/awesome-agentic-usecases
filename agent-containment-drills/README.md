# Agent Containment Drill Runner

An offline, deterministic way to ask a hard operational question: **when an agent must stop, what else keeps moving?**

The runner exercises pause latency, parent revocation, delegated-authority revocation, queued-work cancellation, observability loss, evidence mutation, and accountable human restart. Every event becomes a hash-chained receipt.

```bash
python aau_containment.py evaluate examples/reference-containment-drill.json --out /tmp/containment-receipt.json
python aau_containment.py verify /tmp/containment-receipt.json --drill examples/reference-containment-drill.json
python aau_containment.py pack examples/reference-containment-drill.json /tmp/containment-receipt.json --out /tmp/containment-pack
```

## What is new here

The Agent Boundary Protocol defines authority and existing runtime conformance checks policy decisions. This drill adds explicit clocks for stopping the parent, children, and queued work, plus a recovery gate that requires the named human role and all declared evidence.

## Claim boundary

The committed result is a **synthetic reference execution**, not evidence that a production process, credential, queue, network request, or model was contained. The runner never contacts a target, invokes a tool, or opens the network. Use its event contract in an authorized staging environment and publish a separately labeled reproduction receipt.

The reference scenario is defensive and contains no exploit chain, credential, target, or weaponizable payload.
