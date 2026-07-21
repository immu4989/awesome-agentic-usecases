"""Tool schemas and a clock-bearing executor.

The session owns a cursor into the telemetry series. `next_tick` advances it and
returns exactly one sample, so the agent physically cannot see the future: to learn
whether a spike recovers, it must spend a tick waiting. That cost is what makes the
patience tradeoff real rather than rhetorical.
"""

from __future__ import annotations

import json

from .world import SEVERITIES, Scenario, search_runbook

TOOL_SCHEMAS = [
    {
        "name": "get_service_context",
        "description": (
            "Fetch the service's context: tier, SLO thresholds, recent deploys, and "
            "whether an approved maintenance window is currently active. Call this "
            "before interpreting any metric. The same numbers mean different things "
            "with a deploy behind them, or during planned maintenance."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "Service name from the brief"}
            },
            "required": ["service_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "next_tick",
        "description": (
            "Advance the clock by one minute and return that minute's telemetry: error "
            "rate, p99 latency, saturation, and request rate. You see one sample at a "
            "time and cannot look ahead. Call it again to keep watching. Returns "
            "end_of_window once the stream is exhausted."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "Service name from the brief"}
            },
            "required": ["service_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_runbook",
        "description": (
            "Search the on-call runbook. What justifies a page rather than a ticket, "
            "how to treat transients, how deploys change the reading, slow burns, and "
            "maintenance suppression all live here rather than in your instructions."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword query, e.g. 'transient blip page threshold'"}
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "raise_alert",
        "description": (
            "Commit your decision for this window and end the watch. Call exactly once, "
            "when you have seen enough. Waking someone at 3am for a transient has a "
            "real cost; so does missing a live incident."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": SEVERITIES,
                             "description": "page (wake the on-call), ticket (queue it), none (stay silent)"},
                "reasoning": {"type": "string",
                              "description": "One paragraph citing the samples you saw and the runbook clauses you applied"},
            },
            "required": ["severity", "reasoning"],
            "additionalProperties": False,
        },
    },
]


class WatchSession:
    """Per-run executor holding the clock cursor."""

    def __init__(self, scenario: Scenario):
        self.sc = scenario
        self.cursor = -1                 # index of the last tick handed out
        self.saw_context = False
        self.searched_runbook = False
        self.calls: list[str] = []

    @property
    def ticks_seen(self) -> int:
        return self.cursor + 1

    def __call__(self, name: str, tool_input: dict) -> str:
        sc = self.sc
        self.calls.append(name)

        if name == "get_service_context":
            if tool_input.get("service_id") != sc.service_id:
                return json.dumps({"error": f"unknown service {tool_input.get('service_id')!r}"})
            self.saw_context = True
            return json.dumps(sc.context)

        if name == "next_tick":
            if tool_input.get("service_id") != sc.service_id:
                return json.dumps({"error": f"unknown service {tool_input.get('service_id')!r}"})
            if self.cursor >= len(sc.ticks) - 1:
                return json.dumps({
                    "end_of_window": True,
                    "ticks_seen": self.ticks_seen,
                    "note": "no further telemetry; commit a decision now",
                })
            self.cursor += 1
            return json.dumps({**sc.ticks[self.cursor],
                               "ticks_remaining": len(sc.ticks) - 1 - self.cursor})

        if name == "search_runbook":
            self.searched_runbook = True
            return json.dumps(search_runbook(tool_input.get("query", "")))

        return json.dumps({"error": f"unknown tool {name!r}"})
