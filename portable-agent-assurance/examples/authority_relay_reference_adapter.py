"""Public synthetic command adapter for the authority relay protocol."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "authority_relay.py"
SPEC = importlib.util.spec_from_file_location("authority_relay", MODULE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load authority relay evaluator")
RELAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELAY)


def main() -> int:
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "request"}:
        raise ValueError("adapter request fields differ from the 1.0 contract")
    if request["protocol_version"] != RELAY.ADAPTER_VERSION:
        raise ValueError("adapter protocol version is invalid")
    profile = RELAY.load_json(Path(__file__).with_name("a2a-mcp-authority-relay-profile.json"))
    decision, reasons = RELAY.evaluate_case(profile, request["request"])
    json.dump({"decision": decision, "reason_codes": reasons}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
