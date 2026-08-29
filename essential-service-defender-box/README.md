# Essential-Service Defender-in-a-Box

A zero-upload path from a public vulnerability notice and a **synthetic or explicitly authorized** inventory to a continuity-aware decision pack.

It asks four questions for every affected asset:

1. Is applicability confirmed, disproved, or still unknown?
2. Does the declared fix route match the available evidence and patch window?
3. Did a continuity test preserve the essential service and prove rollback readiness?
4. Did the accountable human approve any treatment or not-affected decision?

```bash
python aau_defender_box.py assess examples/community-water-reference-campaign.json --out /tmp/assessment.json
python aau_defender_box.py verify /tmp/assessment.json --campaign examples/community-water-reference-campaign.json
python aau_defender_box.py pack examples/community-water-reference-campaign.json /tmp/assessment.json --out /tmp/defender-pack
```

The committed reference uses fictional asset and vulnerability identifiers. It demonstrates the workflow without exposing an operator, target, version, weakness, credential, or exploit. Source links point to CISA's KEV and VEX guidance so users can replace the training records with current, authorized evidence.

## Hard boundary

This tool performs no discovery, fingerprinting, connection, exploitation, patch, or configuration change. Its output is a planning receipt—not a scan, risk assessment, compliance finding, operational authorization, or proof that a control works in the field.
