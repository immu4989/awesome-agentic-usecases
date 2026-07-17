"""Tool schemas the agent sees and their execution against one scenario's world."""

from __future__ import annotations

import json

from .world import DISPOSITIONS, QUEUES, Scenario, search_runbook

TOOL_SCHEMAS = [
    {
        "name": "lookup_entity",
        "description": (
            "Fetch the asset/identity record for a hostname or username: criticality "
            "tier (crown_jewel or standard), identity privilege (admin or standard), "
            "and owning department. Call this for every alert — disposition rules "
            "depend on criticality and privilege, not on how scary the alert text reads."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Hostname or username from the alert"}
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "query_events",
        "description": (
            "Pull the last 24h of telemetry for an entity: authentication failures and "
            "successes, geo anomalies, EDR detections, and whether the activity source "
            "matches a known-benign allowlist (authorized scanners, pentest windows). "
            "Alert text frequently misreads benign sources as attacks — verify here."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Hostname or username from the alert"}
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_runbook",
        "description": (
            "Search the SOC response runbook. Escalation criteria and the auto-close "
            "exception clauses live here, not in your instructions — check before "
            "choosing a disposition."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query, e.g. 'auto-close benign scanner exception'"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_triage",
        "description": (
            "Commit the triage decision for this alert. Call exactly once, after "
            "investigating. This ends the task."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": QUEUES, "description": "Alert queue"},
                "disposition": {"type": "string", "enum": DISPOSITIONS, "description": "What happens next"},
                "reasoning": {"type": "string", "description": "One-paragraph justification citing the telemetry and runbook clauses used"},
            },
            "required": ["queue", "disposition", "reasoning"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict, scenario: Scenario) -> str:
    if name == "lookup_entity":
        if tool_input.get("entity_id") != scenario.entity_id:
            return json.dumps({"error": f"no record for entity {tool_input.get('entity_id')!r}"})
        return json.dumps(scenario.asset)
    if name == "query_events":
        if tool_input.get("entity_id") != scenario.entity_id:
            return json.dumps({"error": f"no telemetry for entity {tool_input.get('entity_id')!r}"})
        return json.dumps({"entity_id": scenario.entity_id, **scenario.events})
    if name == "search_runbook":
        return json.dumps(search_runbook(tool_input.get("query", "")))
    return json.dumps({"error": f"unknown tool {name!r}"})
