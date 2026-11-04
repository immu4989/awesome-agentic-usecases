"""Construct OTLP evidence without a collector, credentials, or model calls."""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from aau_harness.agent_bom import rendered
from aau_harness.eval_otlp import create_otlp_pack, verify_otlp_pack
from aau_harness.eval_retry_demo import demo_inputs


def inputs():
    _, plan, ledger, _, _, _ = demo_inputs()
    plan = deepcopy(plan)
    # The packaged retry fixture's context is not an OTLP instrumentation receipt.
    plan.pop("evaluation_context", None)
    mapping = {"mapping_version": "aau-otlp-retry-import/1.0", "source_format": "otlp_json",
               "span_semantics": "single_attempt_direct_children_same_resource_clock", "accounting_plan": plan,
               "attributes": {"metrics": {"completion": "example.score.completion", "unauthorized": "example.score.unauthorized"},
                              "operating": {"cost_usd": "example.cost.usd", "n_api_calls": "example.api.calls"}},
               "tasks": [], "excluded_spans": []}
    spans = []
    epoch = 1_800_000_000_000_000_001  # Preserve nanoseconds beyond float's exact integer range.
    for task_index, task in enumerate(ledger["tasks"]):
        trace = f"{task_index + 1:032x}"
        root = "0000000000000001"
        spans.append({"traceId": trace, "spanId": root, "name": "synthetic task",
                      "startTimeUnixNano": str(epoch), "endTimeUnixNano": str(epoch + int(task["elapsed_s"] * 1e9))})
        declaration = {"scenario_id": task["scenario_id"], "repeat": task["repeat"], "trace_id": trace,
                       "task_span_id": root, "attempt_span_ids": []}
        for index, attempt in enumerate(task["attempts"]):
            span_id = f"{index + 2:016x}"
            declaration["attempt_span_ids"].append(span_id)
            values = {**{mapping["attributes"]["metrics"][name]: value for name, value in attempt["metrics"].items()},
                      **{mapping["attributes"]["operating"][name]: attempt[name] for name in ("cost_usd", "n_api_calls")}}
            spans.append({"traceId": trace, "spanId": span_id, "parentSpanId": root, "name": "synthetic single attempt",
                          "startTimeUnixNano": str(epoch + index * 1_000_000_000),
                          "endTimeUnixNano": str(epoch + (index + 1) * 1_000_000_000),
                          "attributes": [{"key": name, "value": {"intValue": str(value)} if type(value) is int
                                          else {"doubleValue": value}} for name, value in values.items()]})
        mapping["tasks"].append(declaration)
    # A nested detail span is retained but never counted again as an attempt or cost.
    spans.append({"traceId": "00000000000000000000000000000001", "spanId": "000000000000000f",
                  "parentSpanId": "0000000000000002", "name": "synthetic nested detail",
                  "attributes": [{"key": "example.cost.usd", "value": {"doubleValue": 999}}]})
    mapping["excluded_spans"].append({"trace_id": spans[-1]["traceId"], "span_id": spans[-1]["spanId"],
                                      "reason": "Nested diagnostic detail; not an additional accounting scope"})
    raw = rendered({"resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": [{"spans": list(reversed(spans))}]}]})
    return mapping, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    mapping, raw = inputs()
    create_otlp_pack(mapping, raw, args.out)
    verify_otlp_pack(args.out)
    evaluation = json.loads((args.out / "retry/evaluation.json").read_text())
    assert evaluation["results"][0]["metrics"]["unauthorized"] == 1
    print("Synthetic OTLP example verified: earlier harm and all costs retained; nested cost excluded explicitly.")


if __name__ == "__main__":
    main()
