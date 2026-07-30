"""Prompt, and a mock that is billed the way a real backend is billed.

The mock's usage is derived from the actual serialised conversation rather than from a
made-up constant. That matters here more than anywhere else in the repo: this use case is
about the cost of re-sending history, so a mock with flat synthetic usage would be unable
to show the very thing under test, and CI would pass while proving nothing.
"""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage
from refund_resolution_agent.agent import SUBMIT_TOOL, SYSTEM_PROMPT
from refund_resolution_agent.world import gold_plan

from .amplify import PROMPT_GUARD

AMPLIFIED_PROMPT = SYSTEM_PROMPT

__all__ = ["AMPLIFIED_PROMPT", "SUBMIT_TOOL", "PROMPT_GUARD", "MockBackend"]

# Roughly the ratio real tokenizers land on for English JSON. Only the *shape* of the
# growth matters for the mock; the dollar figures in the README come from real backends.
CHARS_PER_TOKEN = 4


class MockBackend:
    """A competent agent: verifies, reads the order and account, then applies policy.

    It is deliberately not the failure. On every archetype it reaches the correct
    resolution, which is the finding this use case exists to make legible — the answer is
    right, and the bill is not.

    Its one concession to the attacker is compliance: asked to review other orders, it
    does, unless the prompt tells it not to. That is ordinary helpfulness, not a flaw.
    """

    name = "mock"
    model = "mock"

    def __init__(self, arm: str = "none"):
        self.arm = arm

    def create(self, system: str, messages: list, tools: list):
        n = sum(1 for m in messages if m["role"] == "assistant")
        text = messages[0]["content"]
        tid = self._grab(text, "TKT-")
        oid = self._grab(text, "ORD-")
        results = list(self._results(messages))
        # The ticket names the ticket and the order, never the customer -- that is learned
        # from the order record, which is also how a real agent would come by it.
        cid = next((r["customer_id"] for r in results if "customer_id" in r), "UNKNOWN")

        extra = [t.strip(".,") for t in text.replace(",", " ").split()
                 if t.startswith("ORD-") and t.strip(".,") != oid]
        guarded = "EFFICIENCY NOTICE" in system

        if n == 0:
            blocks = [self._call("verify_identity", {"ticket_id": tid})]
        elif n == 1:
            blocks = [self._call("get_order", {"order_id": oid})]
        elif n == 2:
            blocks = [self._call("get_account", {"customer_id": cid})]
        elif n == 3 and extra and not guarded:
            # A modern agent batches these into one turn. The loop executes every
            # tool_use block in a response, so this is faithful rather than convenient.
            blocks = [self._call("get_order", {"order_id": e}, i)
                      for i, e in enumerate(extra)]
        else:
            blocks = [self._call(SUBMIT_TOOL, self._decide(results))]

        return Block(content=blocks, stop_reason="tool_use",
                     usage=self._usage(system, messages, blocks))

    # -- billing ---------------------------------------------------------------------------

    def _usage(self, system: str, messages: list, blocks: list) -> MockUsage:
        """Charge for the whole conversation, every turn, exactly as a real API does."""
        wire = system + json.dumps(messages, default=str)
        out = json.dumps([{"name": b.name, "input": b.input} for b in blocks], default=str)
        return MockUsage(input_tokens=len(wire) // CHARS_PER_TOKEN,
                         output_tokens=max(20, len(out) // CHARS_PER_TOKEN))

    # -- policy ----------------------------------------------------------------------------

    def _decide(self, results: list) -> dict:
        order = next((r for r in results if "days_since_delivery" in r), None)
        account = next((r for r in results if "chargeback_pending" in r), None)
        if not order or not account:
            return {"resolution": "escalate", "summary": "mock: incomplete record"}
        resolution, _ = gold_plan(account, order)
        return {"resolution": resolution, "summary": f"mock: policy says {resolution}"}

    # -- helpers ---------------------------------------------------------------------------

    @staticmethod
    def _call(name: str, tool_input: dict, i: int = 0) -> Block:
        return Block(type="tool_use", id=f"m-{name}-{i}", name=name, input=tool_input)

    @staticmethod
    def _grab(text: str, prefix: str) -> str:
        for tok in text.replace("(", " ").replace(")", " ").replace(",", " ").split():
            t = tok.strip(".:;'")
            if t.startswith(prefix):
                return t
        return "UNKNOWN"

    @staticmethod
    def _results(messages: list):
        for m in messages:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    try:
                        d = json.loads(b["content"])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(d, dict):
                        yield d
