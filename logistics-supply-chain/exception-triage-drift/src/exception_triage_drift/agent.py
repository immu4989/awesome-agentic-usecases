"""Domain layer: the baseline prompt (unchanged) plus a deliberately overconfident mock."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage
from exception_triage_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT

from .drift import PROMPT_GUARD

__all__ = ["SYSTEM_PROMPT", "SUBMIT_TOOL", "PROMPT_GUARD", "MockBackend"]


class MockBackend:
    """The overconfident production agent, scripted.

    It reads the shipment record exactly once, never refreshes it, never cross-checks the
    carrier feed, and commits. It is right whenever the world happens to be truthful and
    wrong on every corruption it was handed the means to catch — a stable, nonzero
    `acted_on_stale` for the reporting pipeline to exercise at $0.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n = sum(1 for m in messages if m["role"] == "assistant")
        tid = self._tid(messages[0]["content"])
        if n == 0:
            b = Block(type="tool_use", id="m1", name="lookup_shipment",
                      input={"tracking_id": tid})
        elif n == 1:
            b = Block(type="tool_use", id="m2", name="search_policy",
                      input={"query": "escalation thresholds queue routing"})
        else:
            b = Block(type="tool_use", id="m3", name="submit_triage",
                      input=self._decide(messages))
        return Block(content=[b], stop_reason="tool_use",
                     usage=MockUsage(input_tokens=850 + 360 * n, output_tokens=80))

    @staticmethod
    def _tid(text: str) -> str:
        for tok in text.replace(".", " ").replace(",", " ").replace("?", " ").split():
            t = tok.strip("'\"")
            if len(t) >= 8 and t[:2].isalpha() and t[2:].isdigit():
                return t
        return "UNKNOWN"

    def _decide(self, messages: list) -> dict:
        from exception_triage_agent.world import (
            ESCALATION_PLATINUM_SLA_H,
            ESCALATION_VALUE_USD,
            EXCEPTIONS,
        )
        ship = {}
        for m in messages:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    try:
                        d = json.loads(b["content"])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(d, dict) and "exception_code" in d:
                        ship = d
        if not ship:
            return {"queue": "customer-notification", "action": "route_to_queue",
                    "reasoning": "mock: no shipment data"}
        code = ship.get("exception_code")
        queue = EXCEPTIONS.get(code, ("customer-notification",))[0]
        value = ship.get("value_usd") or 0            # treats a null value as zero — the
        tier = ship.get("customer_tier")              # overconfident read of a partial row
        sla = ship.get("sla_hours_remaining")
        if value > ESCALATION_VALUE_USD or (
            tier == "platinum" and sla is not None and sla < ESCALATION_PLATINUM_SLA_H
        ):
            action = "escalate_to_human"
        elif code == "ADDRESS_INVALID" and ship.get("has_validated_address_candidate"):
            action = "auto_resolve"
        elif code == "WEATHER_DELAY":
            action = "auto_resolve"
        else:
            action = "route_to_queue"
        return {"queue": queue, "action": action, "reasoning": "mock: rule-based on the "
                                                              "record as served"}
