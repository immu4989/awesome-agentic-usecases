"""Tool schemas the agent sees and their execution against one scenario's world."""

from __future__ import annotations

import json

from .world import ACTIONS, QUEUES, Scenario, search_policy

TOOL_SCHEMAS = [
    {
        "name": "lookup_shipment",
        "description": (
            "Fetch the internal shipment record for a tracking id: declared value, "
            "customer tier, SLA hours remaining, the coded exception reason, and whether "
            "the address service has a validated candidate address. Call this first for "
            "every ticket — customer complaints often misstate what actually happened."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "tracking_id": {"type": "string", "description": "Tracking id from the ticket"}
            },
            "required": ["tracking_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_carrier_status",
        "description": (
            "Fetch the carrier's scan history and current disposition for a tracking id. "
            "Use this to confirm what the carrier says happened (needed as evidence for "
            "claims and to disambiguate 'stuck' shipments)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "tracking_id": {"type": "string", "description": "Tracking id from the ticket"}
            },
            "required": ["tracking_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_policy",
        "description": (
            "Search the operations policy knowledge base. Escalation thresholds and "
            "automation eligibility rules live here, not in your instructions — check "
            "policy before deciding the action."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query, e.g. 'escalation value threshold'"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_triage",
        "description": (
            "Commit the final triage decision for this ticket. Call exactly once, after "
            "investigating. This ends the task."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": QUEUES, "description": "Resolution queue"},
                "action": {"type": "string", "enum": ACTIONS, "description": "Disposition"},
                "reasoning": {"type": "string", "description": "One-paragraph justification citing the evidence used"},
            },
            "required": ["queue", "action", "reasoning"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict, scenario: Scenario) -> str:
    """Run a (non-terminal) tool against this scenario's world. Returns a JSON string."""
    if name == "lookup_shipment":
        if tool_input.get("tracking_id") != scenario.tracking_id:
            return json.dumps({"error": f"no shipment found for {tool_input.get('tracking_id')!r}"})
        return json.dumps(scenario.shipment)
    if name == "get_carrier_status":
        if tool_input.get("tracking_id") != scenario.tracking_id:
            return json.dumps({"error": f"no carrier data for {tool_input.get('tracking_id')!r}"})
        return json.dumps({"tracking_id": scenario.tracking_id, "events": scenario.carrier_events})
    if name == "search_policy":
        return json.dumps(search_policy(tool_input.get("query", "")))
    return json.dumps({"error": f"unknown tool {name!r}"})
