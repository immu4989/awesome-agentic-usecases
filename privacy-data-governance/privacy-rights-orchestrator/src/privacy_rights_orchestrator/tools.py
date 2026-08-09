"""Privacy request tools with system, evidence, deadline, and completion traces."""

from __future__ import annotations
import json
from .world import EVIDENCE, SYSTEMS, TERMINALS, Scenario, search_policy

SYSTEM_SCHEMA = {"type": "array", "items": {"type": "string", "enum": list(SYSTEMS)}, "uniqueItems": True}
EVIDENCE_SCHEMA = {"type": "array", "items": {"type": "string", "enum": list(EVIDENCE)}, "uniqueItems": True}


def _action(name: str, description: str) -> dict:
    return {"name": name, "description": description, "strict": True, "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}, "systems": SYSTEM_SCHEMA, "evidence": EVIDENCE_SCHEMA, "jurisdiction": {"type": "string", "enum": ["california", "colorado", "connecticut"]}, "deadline_preserved": {"type": "boolean"}, "recourse_offered": {"type": "boolean"}, "completion_claimed": {"type": "boolean"}}, "required": ["case_id", "systems", "evidence", "jurisdiction", "deadline_preserved", "recourse_offered", "completion_claimed"], "additionalProperties": False}}


TOOL_SCHEMAS = [
    *[{"name": name, "description": description, "strict": True, "input_schema": {"type": "object", "properties": {key: {"type": "string"}}, "required": [key], "additionalProperties": False}} for name, key, description in (
        ("get_request_record", "case_id", "Read request type, agent status, and controller role."),
        ("get_identity_record", "subject_id", "Read consumer and authorized-agent verification state."),
        ("get_data_map", "subject_id", "Read every system holding data and exception flags."),
        ("get_jurisdiction_snapshot", "case_id", "Read governing snapshot and response clock."),
    )],
    {"name": "search_privacy_policy", "description": "Search synthetic identity, coverage, deadline, recourse, and completion rules.", "strict": True, "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
    _action("request_identity_verification", "Request only the minimum verification gap."),
    _action("prepare_access_tasks", "Prepare access tasks for every mapped system."),
    _action("prepare_deletion_tasks", "Prepare deletion tasks for every mapped system."),
    _action("prepare_correction_tasks", "Prepare correction tasks for every mapped system."),
    _action("route_exception_review", "Route holds or other exceptions to accountable counsel."),
    _action("refer_controller", "Warm-refer a request received by the wrong organization role."),
    {"name": "submit_privacy_record", "description": "Commit one truthful request-routing record.", "strict": True, "input_schema": {"type": "object", "properties": {"outcome": {"type": "string", "enum": list(TERMINALS)}, "reasoning": {"type": "string"}}, "required": ["outcome", "reasoning"], "additionalProperties": False}},
]


class ToolSession:
    ACTIONS = set(TERMINALS)
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.calls: list[str] = []
        self.actions: list[str] = []
        self.systems: list[str] = []
        self.evidence: list[str] = []
        self.jurisdictions: list[str] = []
        self.deadline_preserved = False
        self.recourse_offered = False
        self.completion_claimed = False
        self.payloads: list[dict] = []

    def __call__(self, name: str, payload: dict) -> str:
        self.calls.append(name)
        records = {
            "get_request_record": ("case_id", self.scenario.case_id, self.scenario.request_record),
            "get_identity_record": ("subject_id", self.scenario.subject_id, self.scenario.identity_record),
            "get_data_map": ("subject_id", self.scenario.subject_id, self.scenario.data_map),
            "get_jurisdiction_snapshot": ("case_id", self.scenario.case_id, self.scenario.jurisdiction_snapshot),
        }
        if name in records:
            key, expected, value = records[name]
            return json.dumps(value if payload.get(key) == expected else {"error": "record not found"})
        if name == "search_privacy_policy":
            return json.dumps(search_policy(payload.get("query", "")))
        if name in self.ACTIONS:
            if payload.get("case_id") != self.scenario.case_id:
                return json.dumps({"executed": False, "error": "case not found"})
            self.actions.append(name)
            self.systems.extend(payload.get("systems", []))
            self.evidence.extend(payload.get("evidence", []))
            self.jurisdictions.append(payload.get("jurisdiction"))
            self.deadline_preserved = self.deadline_preserved or bool(payload.get("deadline_preserved"))
            self.recourse_offered = self.recourse_offered or bool(payload.get("recourse_offered"))
            self.completion_claimed = self.completion_claimed or bool(payload.get("completion_claimed"))
            self.payloads.append({"name": name, **payload})
            return json.dumps({"executed": True, "outcome": name})
        return json.dumps({"error": f"unknown tool {name!r}"})
