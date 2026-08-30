"""Public synthetic command adapter for the AABOM conformance protocol."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aau_harness.agent_bom import evaluate_authority_case


def main() -> int:
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "input"}:
        raise ValueError("adapter request fields changed or leaked expected evidence")
    if request["protocol_version"] != "aau-agent-authority-adapter/1.0":
        raise ValueError("unsupported protocol")
    bom = json.loads((Path(__file__).with_name("candidate.json")).read_text())
    decision, reasons = evaluate_authority_case(bom, request["input"])
    json.dump({"decision": decision, "reason_codes": reasons}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
