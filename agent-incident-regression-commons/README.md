# Agent Incident Regression Commons

> A public incident lesson is useful only when another team can rerun the boundary it exposed.

This commons converts public AI-agent incident lessons into small, safe, synthetic regression
packs. Each pack binds named public sources to an abstract timeline, the authority boundary that
failed, paired pre-fix and post-fix outcomes, recovery evidence, open questions, and an exact
SHA-256 receipt.

It is deliberately **not** an incident database, attribution service, offensive cyber range,
production incident-response system, or certification program. Public packs reject live targets,
working credentials, personal data, private telemetry, and exploit instructions.

## Run the reference regression

```bash
python3 agent-incident-regression-commons/aau_incident.py validate \
  agent-incident-regression-commons/examples/public-agent-boundary-incident.json

python3 agent-incident-regression-commons/aau_incident.py evaluate \
  agent-incident-regression-commons/examples/public-agent-boundary-incident.json \
  --out /tmp/aau-incident-receipt.json

python3 agent-incident-regression-commons/aau_incident.py verify \
  /tmp/aau-incident-receipt.json \
  --incident agent-incident-regression-commons/examples/public-agent-boundary-incident.json
```

The reference pack contains six tests: safe stopping on an impossible task, peer-channel denial,
credential non-authority, egress restriction, monitor-loss pause, and preservation of one
legitimate action. Five unsafe pre-fix allows become exact post-fix outcomes while the clean case
remains allowed.

## Contribution contract

Every proposed incident regression must:

1. Name reviewable public sources.
2. Abstract the failure without recreating a live target or exploit path.
3. Declare the human stop and restart authorities.
4. Include at least one legitimate twin so a fix cannot win by blocking everything.
5. Record both pre-fix and post-fix outcomes.
6. State what the synthetic result cannot prove.
7. Pass the label-only sensitive-content scan and deterministic verifier.

Use a private security advisory—not a public pull request—if the contribution concerns an
unfixed vulnerability in this repository.
