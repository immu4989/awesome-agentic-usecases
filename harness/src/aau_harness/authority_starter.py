"""Create an offline authority-adapter workspace without implementing its policy."""

from pathlib import Path

from .agent_bom import AgentBomError, generate_conformance_suite, rendered


ADAPTER = '''"""Replace decide() with your staging policy integration before evaluating."""
import json
import sys


def decide(authority_input):
    # Evaluate only these input facts against your reviewed staging policy.
    # Do not load suite.json or classify the random request case_id.
    # Return ("allow" or "block", sorted unique reason codes).
    return "block", ["ADAPTER_NOT_IMPLEMENTED"]


def main():
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "input"}:
        raise ValueError("unexpected request fields")
    if request["protocol_version"] != "aau-agent-authority-adapter/1.1":
        raise ValueError("unsupported protocol")
    decision, reasons = decide(request["input"])
    json.dump({"decision": decision, "reason_codes": reasons}, sys.stdout)


if __name__ == "__main__":
    main()
'''

GUIDE = '''# Your authority adapter workspace

This starter contains a copy of your public or synthetic inventory (`inventory.json`),
its generated contract (`suite.json`), and an unfinished `adapter.py`.

The stub blocks every case with `ADAPTER_NOT_IMPLEMENTED`. Its first evaluation is
expected to fail. Implement `decide()` using your staging policy engine before
accepting results. Never implement decisions by reading the expected suite answers
or decoding case IDs. The test suite is public, not a hidden benchmark.

From this directory, with the current repository harness installed:

```bash
aau bom run-conformance inventory.json suite.json \\
  --command "python3 adapter.py" --adapter-artifact adapter.py --workspace . \\
  --out receipt.json
aau bom verify-conformance receipt.json inventory.json suite.json \\
  --adapter-artifact adapter.py --workspace .
```

Exit 0 means passing evidence, 1 means valid failed evidence, and 2 means invalid
input. Output files are never overwritten: use a new receipt filename after edits.
Keep stdout for the JSON response and stderr for diagnostics. Return the decision
and sorted unique reason codes only; do not emit credentials, payloads, or reasoning.

When the inventory changes, generate a new suite with `aau bom generate-conformance`.
Run only a trusted adapter in a suitable staging sandbox. The runner executes local
code and cannot prevent it from contacting systems. Synthetic success does not prove
live identity, authorization, enforcement, compliance, or deployment approval.
'''


def create_starter(bom: dict, out: Path) -> None:
    suite = generate_conformance_suite(bom)
    if out.exists() or out.is_symlink():
        raise AgentBomError(f"refusing to overwrite: {out}")
    out.mkdir(parents=True, exist_ok=False)
    (out / "inventory.json").write_bytes(rendered(bom))
    (out / "suite.json").write_bytes(rendered(suite))
    (out / "adapter.py").write_text(ADAPTER)
    (out / "README.md").write_text(GUIDE)
