# Essential Services Defender Kits

> Small essential-service teams should be able to test agent boundaries without buying a platform,
> uploading operational data, or connecting an agent to the system they protect.

Five offline kits cover a community water utility, rural hospital, electric distribution utility,
local government, and public transit operator. Each contains:

- A source-bound synthetic system boundary.
- Explicit actions the agent may and must never own.
- Human stop and restart authority.
- Gap, planned, evidenced, and not-applicable control states—never a readiness score.
- Three tabletop/technical exercises with essential-service guardrails.
- A four-week adoption plan.
- A bounded measurement plan and non-certification claims.

## Run a kit

```bash
python3 essential-services-defender-kits/aau_defender.py validate \
  essential-services-defender-kits/kits/community-water-utility.json

python3 essential-services-defender-kits/aau_defender.py assess \
  essential-services-defender-kits/kits/community-water-utility.json \
  --out /tmp/water-defender-assessment.json

python3 essential-services-defender-kits/aau_defender.py verify \
  /tmp/water-defender-assessment.json \
  --kit essential-services-defender-kits/kits/community-water-utility.json
```

The reference records intentionally retain gaps. An empty gap list would be misleading: these
files are public synthetic starting points, not assessments of any real utility, hospital,
government, or transit system.

## Safe adaptation

Keep operational diagrams, credentials, vulnerabilities, personal information, protected health
information, exact asset names, and incident telemetry in the responsible organization's approved
systems. Publish only the reviewed aggregate assessment and synthetic exercise contract.
