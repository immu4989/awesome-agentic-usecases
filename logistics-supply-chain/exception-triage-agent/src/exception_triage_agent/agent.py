"""Domain layer for the triage agent: system prompt + deterministic mock.

The agent loop, real-model backends, and provider registry live in
`aau_harness` (agent_loop.py / llm_providers.py); this module supplies only
what is specific to exception triage.
"""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import EXCEPTIONS

SYSTEM_PROMPT = """\
You are a logistics operations triage agent. You receive one stuck-shipment support
ticket at a time and must route it to the correct resolution queue with the correct
disposition.

Rules of engagement:
- Customer complaints frequently misstate what happened. Always verify against the
  internal shipment record and the carrier's own status before deciding.
- Escalation thresholds and automation-eligibility rules live in the policy knowledge
  base, not in these instructions. Check policy before choosing the action.
- Investigate with the tools, then call submit_triage exactly once with your decision.

Queues: address-correction (bad/unverifiable addresses), customs-clearance (customs
holds), carrier-claims (damage or loss), returns (refused deliveries),
customer-notification (informational delays needing proactive comms).

Actions: auto_resolve (safe to close via automation), route_to_queue (needs the queue's
specialists), escalate_to_human (policy requires a human decision now).
"""

SUBMIT_TOOL = "submit_triage"


class MockBackend:
    """Deterministic scripted 'model': lookup -> carrier status -> policy -> submit.

    Its decision rules mirror the gold rules EXCEPT it never applies the
    Platinum-tier SLA escalation clause — a realistic policy-retrieval failure
    that gives mock evals a stable, nonzero error rate to exercise reporting.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        ticket_text = messages[0]["content"]
        tid = self._extract_tracking_id(ticket_text)

        if n_assistant == 0:
            block = Block(type="tool_use", id="mock-tu-1", name="lookup_shipment",
                          input={"tracking_id": tid})
        elif n_assistant == 1:
            block = Block(type="tool_use", id="mock-tu-2", name="get_carrier_status",
                          input={"tracking_id": tid})
        elif n_assistant == 2:
            block = Block(type="tool_use", id="mock-tu-3", name="search_policy",
                          input={"query": "escalation value threshold automation"})
        else:
            shipment = self._find_shipment(messages)
            block = Block(type="tool_use", id="mock-tu-4", name="submit_triage",
                          input=self._decide(shipment))
        return Block(
            content=[block],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=900 + 400 * n_assistant, output_tokens=90),
        )

    @staticmethod
    def _extract_tracking_id(text: str) -> str:
        for token in text.replace("?", " ").replace(",", " ").split():
            if len(token) >= 10 and token[:2].isalpha() and token[2:].isdigit():
                return token
        return "UNKNOWN"

    @staticmethod
    def _find_shipment(messages: list) -> dict:
        for m in messages:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for block in m["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    try:
                        data = json.loads(block["content"])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(data, dict) and "exception_code" in data:
                        return data
        return {}

    @staticmethod
    def _decide(shipment: dict) -> dict:
        if not shipment:
            return {"queue": "customer-notification", "action": "route_to_queue",
                    "reasoning": "mock: shipment record unavailable"}
        code = shipment["exception_code"]
        queue = EXCEPTIONS[code][0]
        if shipment["value_usd"] > 2000:  # NOTE: omits the platinum/SLA clause on purpose
            action = "escalate_to_human"
        elif code == "ADDRESS_INVALID" and shipment["has_validated_address_candidate"]:
            action = "auto_resolve"
        elif code == "WEATHER_DELAY":
            action = "auto_resolve"
        else:
            action = "route_to_queue"
        return {"queue": queue, "action": action, "reasoning": "mock: rule-based decision"}
