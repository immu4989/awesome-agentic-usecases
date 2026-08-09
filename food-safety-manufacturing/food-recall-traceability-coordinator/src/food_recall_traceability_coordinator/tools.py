"""Strict domain tools backed by a normalized service-event trace."""

from aau_harness.evidence_service import ServiceToolSession, build_tool_schemas

from .domain import CONFIG

TOOL_SCHEMAS = build_tool_schemas(CONFIG)


class ToolSession(ServiceToolSession):
    def __init__(self, scenario):
        super().__init__(CONFIG, scenario)
