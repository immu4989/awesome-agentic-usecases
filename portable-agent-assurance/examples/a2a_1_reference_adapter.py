"""Public synthetic command adapter for the recorded A2A 1.0 delta protocol."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "a2a_1_delta.py"
SPEC = importlib.util.spec_from_file_location("a2a_1_delta", MODULE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load A2A 1.0 delta evaluator")
DELTA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELTA)


def main() -> int:
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "request"}:
        raise ValueError("adapter request fields differ from the 1.0 contract")
    if request["protocol_version"] != DELTA.ADAPTER_VERSION:
        raise ValueError("adapter protocol version is invalid")
    profile = DELTA.load_json(Path(__file__).with_name("a2a-1-interface-authorization-profile.json"))
    decision, reasons = DELTA.evaluate_case(profile, request["request"])
    json.dump({"decision": decision, "reason_codes": reasons}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
