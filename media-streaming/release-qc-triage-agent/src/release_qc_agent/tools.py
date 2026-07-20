"""Tool schemas the agent sees and their execution against one scenario's world."""

from __future__ import annotations

import json

from .world import ACTIONS, QUEUES, Scenario, search_policy

TOOL_SCHEMAS = [
    {
        "name": "get_release_context",
        "description": (
            "Fetch the title's release context: tier, days remaining to premiere, "
            "release territories, whether those territories carry US accessibility "
            "(CVAA) obligations, and whether marketing is locked. Call this for every "
            "flag — the remediation that is permitted depends on the schedule and the "
            "territories, which the QC flag never mentions."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "title_id": {"type": "string", "description": "Title id from the flag, e.g. TTL-48213"}
            },
            "required": ["title_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_qc_flag",
        "description": (
            "Fetch the full QC flag record for an asset: which component failed "
            "(video, audio, timed_text), severity, the flagged timecode, which "
            "inspection stage raised it, and whether it is a caption defect."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset id from the flag, e.g. AST-90371"}
            },
            "required": ["asset_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_creative_annotations",
        "description": (
            "Fetch production annotations filed against an asset — director and post "
            "supervisor notes marking intentional creative choices such as silent "
            "scenes or stylised grain. Each annotation states whether it covers the "
            "flagged timecode range. An annotation that does not cover the flagged "
            "range does not explain the flag."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset id from the flag"}
            },
            "required": ["asset_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_release_policy",
        "description": (
            "Search the release-policy knowledge base. Remediation preference order, "
            "the accessibility hard block, creative-intent handling, the release "
            "window, in-house repair capability, and board-escalation criteria all "
            "live here, not in your instructions."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query, e.g. 'caption defect waiver accessibility'"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_release_decision",
        "description": (
            "Commit the triage decision for this QC flag. Call exactly once, after "
            "investigating. This ends the task."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": QUEUES, "description": "Owning engineering queue, or no-defect"},
                "action": {"type": "string", "enum": ACTIONS, "description": "What happens to the release"},
                "reasoning": {"type": "string", "description": "One-paragraph justification citing the release context and policy clauses used"},
            },
            "required": ["queue", "action", "reasoning"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict, scenario: Scenario) -> str:
    if name == "get_release_context":
        if tool_input.get("title_id") != scenario.title_id:
            return json.dumps({"error": f"no title record for {tool_input.get('title_id')!r}"})
        return json.dumps(scenario.title)
    if name == "get_qc_flag":
        if tool_input.get("asset_id") != scenario.asset_id:
            return json.dumps({"error": f"no QC flag for asset {tool_input.get('asset_id')!r}"})
        # creative_intent_match is the generator's own bookkeeping — the agent must
        # reach it through check_creative_annotations, not read it off the flag.
        return json.dumps({k: v for k, v in scenario.flag.items()
                           if k != "creative_intent_match"})
    if name == "check_creative_annotations":
        if tool_input.get("asset_id") != scenario.asset_id:
            return json.dumps({"error": f"no annotations for asset {tool_input.get('asset_id')!r}"})
        return json.dumps({"asset_id": scenario.asset_id, "annotations": scenario.annotations})
    if name == "search_release_policy":
        return json.dumps(search_policy(tool_input.get("query", "")))
    return json.dumps({"error": f"unknown tool {name!r}"})
