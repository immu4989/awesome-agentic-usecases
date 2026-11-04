"""Create source-complete synthetic OTLP pass/fail handoffs; no telemetry collection."""

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

from aau_harness.agent_bom import AgentBomError, rendered
from aau_harness.eval_otlp_review import create_handoff, verify_handoff
from aau_harness.eval_retry_demo import demo_inputs
from aau_harness.evaluation_context import capture_context


def inputs(outcome="repaired"):
    path = Path(__file__).with_name("otlp_retries.py")
    spec = importlib.util.spec_from_file_location("otlp_trace_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mapping, raw = module.inputs()
    # This is a declared synthetic fixture/scoring context, not an execution attestation.
    mapping["accounting_plan"]["evaluation_context"] = capture_context(
        [{"scenario_id": "service", "description": "Fixed synthetic completion/authorization trace fixture"}],
        {"unit": "logical_task", "source": "constructed OTLP spans", "attributes": mapping["attributes"]},
        {"trace_fixture.py": path.read_bytes(), "handoff_fixture.py": Path(__file__).read_bytes()})
    candidate = json.loads(raw)
    spans = candidate["resourceSpans"][0]["scopeSpans"][0]["spans"]
    for span in spans:
        if outcome != "earlier-harm":
            for attribute in span.get("attributes", []):
                if attribute["key"] == "example.score.unauthorized":
                    attribute["value"] = {"intValue": "0"}
        if outcome in ("repaired", "unknown") and span["spanId"] == "0000000000000001" and span["traceId"].endswith("1"):
            span["endTimeUnixNano"] = str(int(span["startTimeUnixNano"]) + 3_000_000_000)
        if outcome == "unknown" and span["spanId"] == "0000000000000002":
            span["attributes"] = [a for a in span["attributes"] if a["key"] != "example.cost.usd"]
    policy, _, _, diagnostics, budget, _ = demo_inputs()
    return [policy, mapping, raw, deepcopy(mapping), rendered(candidate), diagnostics], budget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise AgentBomError("refusing to overwrite example destination")
    for outcome in ("earlier-harm", "slow-completion", "repaired"):
        source, budget = inputs(outcome)
        folder = args.out / outcome
        result = create_handoff(*source, folder, operating_budget=budget)
        assert verify_handoff(folder, require_budget=True) == result
        assert (result["status"] == "constraints_met") == (outcome == "repaired")
    print("Three synthetic OTLP handoffs verified: earlier harm, slow completion, and repaired fixture; 39 files each.")


if __name__ == "__main__":
    main()
