"""Strict recovery tools with observable assurance, PII, notification, and action traces."""

from __future__ import annotations

import json

from .world import EXCESSIVE_PII, PII_FIELDS, RECOVERY_METHODS, RECOVERY_TERMINALS, Scenario, search_policy

METHOD_SCHEMA = {"type": "array", "items": {"type": "string", "enum": list(RECOVERY_METHODS)}, "uniqueItems": True}
PII_SCHEMA = {"type": "array", "items": {"type": "string", "enum": [*PII_FIELDS, *EXCESSIVE_PII]}, "uniqueItems": True}


def _action(name: str, description: str) -> dict:
    return {
        "name": name, "description": description, "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"}, "methods": METHOD_SCHEMA,
                "pii_requested": PII_SCHEMA, "subscriber_notified": {"type": "boolean"},
            },
            "required": ["case_id", "methods", "pii_requested", "subscriber_notified"],
            "additionalProperties": False,
        },
    }


TOOL_SCHEMAS = [
    *[
        {"name": name, "description": description, "strict": True, "input_schema": {"type": "object", "properties": {key: {"type": "string"}}, "required": [key], "additionalProperties": False}}
        for name, key, description in (
            ("get_account_record", "account_id", "Read established recovery methods and notification channel."),
            ("get_recovery_claim", "case_id", "Read presented methods, new destination, and risk flags."),
            ("get_assurance_profile", "account_id", "Read maximum authentication and identity assurance levels."),
        )
    ],
    {"name": "search_recovery_policy", "description": "Search synthetic assurance, minimization, notification, and takeover rules.", "strict": True, "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
    _action("reauthenticate_and_bind", "Use a remaining authenticator before account recovery."),
    _action("recover_with_one_method", "Recover an AAL1 account with one established method."),
    _action("recover_with_two_methods", "Recover an AAL2 account with two established methods."),
    _action("recover_with_reproofing", "Repeat the approved identity-proofing route."),
    _action("route_attended_recovery", "Route an IAL3 account to attended biometric comparison."),
    _action("place_security_hold", "Contain an assurance failure or suspected takeover."),
    {"name": "submit_recovery_record", "description": "Commit one truthful outcome after one operational action.", "strict": True, "input_schema": {"type": "object", "properties": {"outcome": {"type": "string", "enum": list(RECOVERY_TERMINALS)}, "reasoning": {"type": "string"}}, "required": ["outcome", "reasoning"], "additionalProperties": False}},
]


class ToolSession:
    ACTIONS = set(RECOVERY_TERMINALS)

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.calls: list[str] = []
        self.executed_actions: list[str] = []
        self.methods: list[str] = []
        self.pii_requested: list[str] = []
        self.subscriber_notified = False
        self.payloads: list[dict] = []

    def __call__(self, name: str, tool_input: dict) -> str:
        self.calls.append(name)
        scenario = self.scenario
        if name == "get_account_record":
            return self._lookup(tool_input.get("account_id"), scenario.account_id, scenario.account_record)
        if name == "get_recovery_claim":
            return self._lookup(tool_input.get("case_id"), scenario.case_id, scenario.recovery_claim)
        if name == "get_assurance_profile":
            return self._lookup(tool_input.get("account_id"), scenario.account_id, scenario.assurance_profile)
        if name == "search_recovery_policy":
            return json.dumps(search_policy(tool_input.get("query", "")))
        if name in self.ACTIONS:
            return self._execute(name, tool_input)
        return json.dumps({"error": f"unknown tool {name!r}"})

    @staticmethod
    def _lookup(provided: str | None, expected: str, value: dict) -> str:
        return json.dumps(value if provided == expected else {"error": "record not found"})

    def _execute(self, name: str, payload: dict) -> str:
        if payload.get("case_id") != self.scenario.case_id:
            return json.dumps({"executed": False, "error": "case not found"})
        self.executed_actions.append(name)
        self.methods.extend(payload.get("methods", []))
        self.pii_requested.extend(payload.get("pii_requested", []))
        self.subscriber_notified = self.subscriber_notified or bool(payload.get("subscriber_notified"))
        self.payloads.append({"name": name, **payload})
        return json.dumps({"executed": True, "outcome": name})
