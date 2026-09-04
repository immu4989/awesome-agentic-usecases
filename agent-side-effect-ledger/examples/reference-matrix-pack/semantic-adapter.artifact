"""Public synthetic adapter for the ASEL oracle-free command protocol."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from aau_side_effect import ADAPTER_PROTOCOL_VERSION, evaluate_case  # noqa: E402


def _require_runtime_policy() -> None:
    policy = json.loads(Path(__file__).with_name("reference-runtime-policy.json").read_text())
    if policy != {
        "policy_id": "public-synthetic-side-effect-staging-v1",
        "environment": "public_synthetic",
        "live_targets_allowed": False,
    }:
        raise ValueError("runtime policy does not permit the public-synthetic adapter")


def _contains_oracle(value: object) -> bool:
    if isinstance(value, dict):
        return "expected" in value or any(_contains_oracle(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_oracle(item) for item in value)
    return False


def main() -> int:
    _require_runtime_policy()
    request = json.load(sys.stdin)
    if set(request) != {"protocol_version", "suite_id", "profile", "case"}:
        raise ValueError("adapter request fields changed")
    if request["protocol_version"] != ADAPTER_PROTOCOL_VERSION:
        raise ValueError("unsupported adapter protocol")
    if _contains_oracle(request):
        raise ValueError("adapter request leaked expected evidence")
    case = request["case"]
    results = evaluate_case(request["profile"], case)
    json.dump({"case_id": case["case_id"], "results": results}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
