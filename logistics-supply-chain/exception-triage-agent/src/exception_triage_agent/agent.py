"""The triage agent: a manual tool-use loop over pluggable model backends.

Two backends share one loop:

- AnthropicBackend — the real model via the official SDK (adaptive thinking,
  no sampling params, prompt-cached system prompt).
- MockBackend — a deterministic rule-based stand-in that exercises the whole
  pipeline (tools, loop, scoring, cost plumbing) with zero API cost. Its rules
  deliberately omit one policy (Platinum-tier SLA escalation) so mock evals
  produce realistic, nonzero error rates.

The loop is manual rather than the SDK tool runner so the mock backend can sit
behind the same interface and CI never needs credentials.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from aau_harness import CostTracker

from .tools import TOOL_SCHEMAS, execute_tool
from .world import EXCEPTIONS, Scenario

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

MAX_TURNS = 8


@dataclass
class RunOutcome:
    submitted: bool
    queue: str | None
    action: str | None
    reasoning: str
    n_turns: int
    tool_calls: list = field(default_factory=list)
    refused: bool = False
    error: str | None = None


# ---------------------------------------------------------------- backends


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8"):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model

    def create(self, system: str, messages: list, tools: list):
        return self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=tools,
            messages=messages,
        )


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _MockUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0


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
            block = _Block(type="tool_use", id="mock-tu-1", name="lookup_shipment",
                           input={"tracking_id": tid})
        elif n_assistant == 1:
            block = _Block(type="tool_use", id="mock-tu-2", name="get_carrier_status",
                           input={"tracking_id": tid})
        elif n_assistant == 2:
            block = _Block(type="tool_use", id="mock-tu-3", name="search_policy",
                           input={"query": "escalation value threshold automation"})
        else:
            shipment = self._find_shipment(messages)
            block = _Block(type="tool_use", id="mock-tu-4", name="submit_triage",
                           input=self._decide(shipment))
        return _Block(
            content=[block],
            stop_reason="tool_use",
            usage=_MockUsage(input_tokens=900 + 400 * n_assistant, output_tokens=90),
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


# ---------------------------------------------------------------- agent loop


def run_agent(backend, scenario: Scenario, cost: CostTracker) -> RunOutcome:
    messages: list = [{"role": "user", "content": scenario.ticket_text}]
    tool_calls: list = []

    for turn in range(1, MAX_TURNS + 1):
        response = backend.create(SYSTEM_PROMPT, messages, TOOL_SCHEMAS)
        cost.add_usage(response.usage)

        if getattr(response, "stop_reason", None) == "refusal":
            return RunOutcome(False, None, None, "", turn, tool_calls, refused=True)

        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            return RunOutcome(False, None, None, "", turn, tool_calls,
                              error="ended turn without submitting a decision")

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for tu in tool_uses:
            tool_calls.append({"name": tu.name, "input": tu.input})
            if tu.name == "submit_triage":
                return RunOutcome(
                    submitted=True,
                    queue=tu.input.get("queue"),
                    action=tu.input.get("action"),
                    reasoning=tu.input.get("reasoning", ""),
                    n_turns=turn,
                    tool_calls=tool_calls,
                )
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": execute_tool(tu.name, tu.input, scenario),
            })
        messages.append({"role": "user", "content": results})

    return RunOutcome(False, None, None, "", MAX_TURNS, tool_calls,
                      error=f"no submission within {MAX_TURNS} turns")
