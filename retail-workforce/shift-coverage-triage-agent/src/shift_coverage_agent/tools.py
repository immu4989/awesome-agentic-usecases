"""Tool schemas the agent sees and their execution against one scenario's world."""

from __future__ import annotations

import json

from .world import STRATEGIES, Scenario, search_policy

TOOL_SCHEMAS = [
    {
        "name": "get_shift_status",
        "description": (
            "Fetch tomorrow's shift record for a store: window and hours, required vs "
            "confirmed headcount, call-outs, role needed, and whether the day is "
            "flagged as a peak day. Call this first — the manager's message rarely "
            "includes the details that decide the answer."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "store_id": {"type": "string", "description": "Store id from the ticket, e.g. S042"}
            },
            "required": ["store_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_available_workers",
        "description": (
            "List workers who could plausibly cover the shift: home-store staff and "
            "nearby-store staff, with scheduled weekly hours, minor status, and "
            "distance. Eligibility rules live in the labor policy KB — check them."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "store_id": {"type": "string", "description": "Store id from the ticket"}
            },
            "required": ["store_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_labor_policy",
        "description": (
            "Search the labor policy knowledge base. Overtime caps, minor work-hour "
            "limits, borrowing rules, and reduced-coverage conditions live here, not "
            "in your instructions."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query, e.g. 'overtime weekly cap minor'"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_coverage_plan",
        "description": (
            "Commit the coverage decision for this shift. Call exactly once, after "
            "investigating. This ends the task."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy": {"type": "string", "enum": STRATEGIES, "description": "Fill strategy"},
                "reasoning": {"type": "string", "description": "One-paragraph justification citing the roster facts and policy clauses used"},
            },
            "required": ["strategy", "reasoning"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict, scenario: Scenario) -> str:
    if name == "get_shift_status":
        if tool_input.get("store_id") != scenario.store_id:
            return json.dumps({"error": f"no shift data for store {tool_input.get('store_id')!r}"})
        return json.dumps({"store_id": scenario.store_id, **scenario.shift})
    if name == "list_available_workers":
        if tool_input.get("store_id") != scenario.store_id:
            return json.dumps({"error": f"no roster for store {tool_input.get('store_id')!r}"})
        return json.dumps(scenario.workers)
    if name == "search_labor_policy":
        return json.dumps(search_policy(tool_input.get("query", "")))
    return json.dumps({"error": f"unknown tool {name!r}"})
