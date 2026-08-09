"""Accessibility evidence tools and observable remediation state transitions."""

from __future__ import annotations

import json

from .world import DEFECTS, TERMINALS, TESTS, Scenario, search_policy

DEFECT_SCHEMA = {"type": "array", "items": {"type": "string", "enum": list(DEFECTS)}, "uniqueItems": True}
TEST_SCHEMA = {"type": "array", "items": {"type": "string", "enum": list(TESTS)}, "uniqueItems": True}


def _action(name: str, description: str) -> dict:
    return {"name": name, "description": description, "strict": True, "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}, "defects": DEFECT_SCHEMA, "tests": TEST_SCHEMA, "verified_fix": {"type": "boolean"}, "claim_conformance": {"type": "boolean"}}, "required": ["case_id", "defects", "tests", "verified_fix", "claim_conformance"], "additionalProperties": False}}


TOOL_SCHEMAS = [
    *[{"name": name, "description": description, "strict": True, "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"], "additionalProperties": False}} for name, description in (
        ("get_automated_scan", "Read scanner findings; automation is not complete coverage."),
        ("get_manual_evidence", "Read affected-path observations, conflicts, and post-fix tests."),
        ("inspect_source", "Read defects confirmed in the synthetic source inspection."),
        ("get_deployment_record", "Read whether the candidate fix reached the test environment."),
    )],
    {"name": "search_accessibility_policy", "description": "Search synthetic coverage, verification, conflict, and assurance rules.", "strict": True, "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
    _action("prepare_remediation_plan", "Record exact defects and matching verification tests."),
    _action("record_verified_fix", "Record a fix only after deployment and matching tests pass."),
    _action("route_expert_review", "Preserve conflicting evidence for qualified human review."),
    _action("record_no_defect", "Record no confirmed defect without making a conformance claim."),
    {"name": "submit_accessibility_record", "description": "Commit one truthful outcome after one action.", "strict": True, "input_schema": {"type": "object", "properties": {"outcome": {"type": "string", "enum": list(TERMINALS)}, "reasoning": {"type": "string"}}, "required": ["outcome", "reasoning"], "additionalProperties": False}},
]


class ToolSession:
    ACTIONS = set(TERMINALS)

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.calls: list[str] = []
        self.actions: list[str] = []
        self.defects: list[str] = []
        self.tests: list[str] = []
        self.verified_fix = False
        self.claim_conformance = False
        self.payloads: list[dict] = []

    def __call__(self, name: str, payload: dict) -> str:
        self.calls.append(name)
        records = {
            "get_automated_scan": self.scenario.automated_scan,
            "get_manual_evidence": self.scenario.manual_evidence,
            "inspect_source": self.scenario.source_inspection,
            "get_deployment_record": self.scenario.deployment_record,
        }
        if name in records:
            return json.dumps(records[name] if payload.get("asset_id") == self.scenario.asset_id else {"error": "asset not found"})
        if name == "search_accessibility_policy":
            return json.dumps(search_policy(payload.get("query", "")))
        if name in self.ACTIONS:
            if payload.get("case_id") != self.scenario.case_id:
                return json.dumps({"executed": False, "error": "case not found"})
            self.actions.append(name)
            self.defects.extend(payload.get("defects", []))
            self.tests.extend(payload.get("tests", []))
            self.verified_fix = self.verified_fix or bool(payload.get("verified_fix"))
            self.claim_conformance = self.claim_conformance or bool(payload.get("claim_conformance"))
            self.payloads.append({"name": name, **payload})
            return json.dumps({"executed": True, "outcome": name})
        return json.dumps({"error": f"unknown tool {name!r}"})
