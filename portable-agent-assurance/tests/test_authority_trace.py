from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("authority_trace", ROOT / "authority_trace.py")
assert SPEC and SPEC.loader
TRACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE)
PROFILE = ROOT / "examples/a2a-mcp-authority-relay-profile.json"
SUITE = ROOT / "examples/a2a-mcp-authority-relay-suite.json"
RECEIPT = ROOT / "examples/a2a-mcp-authority-relay-receipt.json"
EXPORT = ROOT / "examples/a2a-mcp-authority-traces.json"


def sources():
    return tuple(map(TRACE.load_json, (PROFILE, SUITE, RECEIPT)))


def test_trace_export_recomputes_and_blocks_dispatch_after_denial():
    profile, suite, receipt = sources()
    export = TRACE.build_export(profile, suite, receipt)
    assert export == json.loads(EXPORT.read_text())
    assert export["summary"] == {
        "trace_count": 25,
        "span_count": 52,
        "allow_trace_count": 2,
        "block_trace_count": 23,
        "blocked_mcp_dispatch_count": 23,
        "raw_content_attribute_count": 0,
        "tracestate_field_count": 0,
        "baggage_field_count": 0,
    }
    assert all(row["mcp_dispatch_recorded"] is (row["decision"] == "allow") for row in export["traces"])
    TRACE.validate_export(export, profile, suite, receipt)


def test_trace_graph_and_w3c_identifiers_are_well_formed():
    export = TRACE.load_json(EXPORT)
    for trace in export["traces"]:
        span_ids = {span["span_id"] for span in trace["spans"]}
        assert len(trace["trace_id"]) == 32 and len(span_ids) == trace["span_count"]
        for span in trace["spans"]:
            assert span["trace_id"] == trace["trace_id"]
            assert span["traceparent"] == f"00-{trace['trace_id']}-{span['span_id']}-01"
            assert span["parent_span_id"] is None or span["parent_span_id"] in span_ids


def test_export_contains_no_raw_sensitive_profile_values():
    profile, _, _ = sources()
    payload = EXPORT.read_text()
    forbidden_values = [
        profile["delegation"]["subject"],
        profile["delegation"]["actor"],
        profile["delegation"]["task_id"],
        profile["delegation"]["delegation_id"],
        profile["a2a"]["tenant"],
        profile["mcp"]["server_uri"],
    ]
    assert all(value not in payload for value in forbidden_values)
    keys = [attribute["key"].lower() for trace in TRACE.load_json(EXPORT)["traces"] for span in trace["spans"] for attribute in span["attributes"]]
    assert all(not any(fragment in key for fragment in TRACE.FORBIDDEN_FRAGMENTS) for key in keys)


def test_source_and_export_tampering_fail_closed():
    profile, suite, receipt = sources()
    export = TRACE.load_json(EXPORT)
    tampered = copy.deepcopy(export)
    tampered["traces"][0]["spans"][0]["name"] = "tampered"
    with pytest.raises(TRACE.TraceError, match="does not recompute"):
        TRACE.validate_export(tampered, profile, suite, receipt)
    stale = copy.deepcopy(receipt)
    stale["results"][0]["exact"] = False
    with pytest.raises(TRACE.authority_relay.RelayError, match="exactness"):
        TRACE.build_export(profile, suite, stale)


def test_forbidden_and_oversized_attributes_are_rejected():
    with pytest.raises(TRACE.TraceError, match="forbidden attribute"):
        TRACE._attributes({"gen_ai.input.messages": "sensitive"})
    with pytest.raises(TRACE.TraceError, match="oversized"):
        TRACE._attributes({"aau.safe": "x" * 161})
