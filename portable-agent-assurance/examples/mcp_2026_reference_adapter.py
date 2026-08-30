"""Public synthetic command adapter for the recorded MCP 2026 delta protocol."""

from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "mcp_2026_delta.py"
SPEC = importlib.util.spec_from_file_location("mcp_2026_delta", MODULE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load MCP 2026 delta evaluator")
DELTA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELTA)


def main() -> int:
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "case_id", "request"}:
        raise ValueError("adapter request fields differ from the 1.0 contract")
    if request["protocol_version"] != "aau-mcp-2026-adapter/1.0":
        raise ValueError("adapter protocol version is invalid")
    profile = DELTA.load_json(Path(__file__).with_name("mcp-2026-authorization-profile.json"))
    decision, reasons = DELTA.evaluate_case(profile, request["request"])
    json.dump({"decision": decision, "reason_codes": reasons}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
