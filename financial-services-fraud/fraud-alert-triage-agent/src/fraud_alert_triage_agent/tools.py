"""Tool schemas the agent sees and their execution against one scenario's world."""

from __future__ import annotations

import json

from .world import DISPOSITIONS, QUEUES, Scenario, search_policy

TOOL_SCHEMAS = [
    {
        "name": "lookup_customer",
        "description": (
            "Fetch the customer record for an account: segment (private_banking or "
            "retail), tenure, prior disputes, and home region. Call this for every "
            "alert — disposition depends on customer segment and the regulatory "
            "threshold, not on how alarming the alert text reads."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Account id from the alert"}
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "query_transaction",
        "description": (
            "Pull the flagged transaction's signals: amount, channel, device/geo "
            "novelty, new-payee and credential-reset flags, beneficiary mule match, "
            "whether the customer authorized it, and whether a benign explanation is "
            "on file (matching travel notice or allowlisted beneficiary). Alert text "
            "frequently misreads both benign and authorized-scam transactions — verify "
            "here."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Account id from the alert"}
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_fraud_policy",
        "description": (
            "Search the fraud-policy knowledge base. Escalation criteria, the "
            "auto-release exception clauses, and the APP-scam guidance live here, not "
            "in your instructions — check before choosing a disposition."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query, e.g. 'auto-release benign private banking exception'"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_triage",
        "description": (
            "Commit the fraud triage decision for this alert. Call exactly once, after "
            "investigating. This ends the task."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {"type": "string", "enum": QUEUES, "description": "Fraud queue"},
                "disposition": {"type": "string", "enum": DISPOSITIONS, "description": "What happens to the transaction"},
                "reasoning": {"type": "string", "description": "One-paragraph justification citing the transaction signals and policy clauses used"},
            },
            "required": ["queue", "disposition", "reasoning"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict, scenario: Scenario) -> str:
    if name == "lookup_customer":
        if tool_input.get("entity_id") != scenario.entity_id:
            return json.dumps({"error": f"no customer record for {tool_input.get('entity_id')!r}"})
        return json.dumps(scenario.customer)
    if name == "query_transaction":
        if tool_input.get("entity_id") != scenario.entity_id:
            return json.dumps({"error": f"no transaction for {tool_input.get('entity_id')!r}"})
        return json.dumps({"entity_id": scenario.entity_id, **scenario.transaction})
    if name == "search_fraud_policy":
        return json.dumps(search_policy(tool_input.get("query", "")))
    return json.dumps({"error": f"unknown tool {name!r}"})
