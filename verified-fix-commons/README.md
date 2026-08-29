# Verified Fix Commons

> Turn “we applied the fix” into a portable, replayable, non-certifying evidence claim.

The Verified Fix Commons evaluates public or synthetic before/after fixtures for a named patch,
upgrade, configuration change, or compensating control. Every contract must test the vulnerable
condition, the closest legitimate twin, service continuity, and rollback. Temporary compensating
controls need their own evidence case.

The evaluator never scans a host, opens a socket, runs an exploit, executes a patch, changes a
system, or claims an organization is secure. Reference results prove only that the deterministic
runner matched the reviewed synthetic oracle.

## Run a reference fix

```bash
python3 verified-fix-commons/aau_fix.py evaluate \
  verified-fix-commons/examples/ai-generated-dependency-upgrade.json \
  --out /tmp/aau-fix-receipt.json

python3 verified-fix-commons/aau_fix.py verify \
  /tmp/aau-fix-receipt.json \
  --contract verified-fix-commons/examples/ai-generated-dependency-upgrade.json

python3 verified-fix-commons/aau_fix.py pack \
  verified-fix-commons/examples/ai-generated-dependency-upgrade.json \
  /tmp/aau-fix-receipt.json \
  --out /tmp/aau-fix-pack
```

The non-overwriting pack includes the exact contract and receipt, an OpenVEX-style statement,
SARIF results, a human-readable boundary, and a SHA-256 byte manifest. The three committed examples
cover an AI-generated dependency upgrade, a least-privilege configuration change, and an
essential-service compensating control.

## Publication boundary

Use only authorized public or synthetic fixtures in this repository. Do not contribute exploit
payloads, live targets, production inventories, credentials, private advisories, customer records,
or operational telemetry. A Fix Receipt is not a VEX issuer's production determination, security
assessment, certification, compliance finding, endorsement, or authorization to deploy.
