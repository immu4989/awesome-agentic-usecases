"""Strict domain tools backed by a normalized decision-gate trace."""

from aau_harness.decision_gate import GateToolSession, build_gate_tool_schemas

from .domain import CONFIG

TOOL_SCHEMAS = build_gate_tool_schemas(CONFIG)


class ToolSession(GateToolSession):
    def __init__(self, scenario):
        super().__init__(CONFIG, scenario)
