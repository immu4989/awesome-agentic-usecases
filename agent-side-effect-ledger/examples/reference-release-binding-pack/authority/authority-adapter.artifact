"""Public-synthetic authority adapter for the release-binding reference."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aau_harness.agent_bom import evaluate_authority_case


def main() -> int:
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "input"}:
        raise ValueError("authority adapter request fields changed")
    if request["protocol_version"] != "aau-agent-authority-adapter/1.1":
        raise ValueError("unsupported authority adapter protocol")
    bom = json.loads(
        Path(__file__).with_name("agent-capability-bom.json").read_text()
    )
    decision, reasons = evaluate_authority_case(bom, request["input"])
    json.dump({"decision": decision, "reason_codes": reasons}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
