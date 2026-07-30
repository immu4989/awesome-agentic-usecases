"""The baseline tool set, with the customer's other orders made reachable — and a gate.

Two changes to the baseline executor, both required for the amplification to be honest:

* The orders a `FANOUT` ticket names actually exist. If they returned "no such order" the
  agent would pay for a handful of short error strings and the vector would be measuring
  nothing. A customer really does have other orders, and looking them up really does
  return records.
* The in-scope order can carry a large customer-written field. Nothing about it changes
  the answer — `gold_plan` reads value, age, final-sale and the account, and never this.

`budget_gate` lives here rather than in the prompt because this is the only place the
replay tax can still be stopped. Once an oversized result has been appended to the
conversation the tokens are bought, and they are bought again on every later turn.
"""

from __future__ import annotations

import json

from refund_resolution_agent.tools import TOOL_SCHEMAS, ToolSession

from .amplify import (
    MAX_ORDER_LOOKUPS,
    MAX_RESULT_CHARS,
    TRUNCATION_MARKER,
    gates_tools,
)

__all__ = ["TOOL_SCHEMAS", "AmplifiedSession"]


class AmplifiedSession(ToolSession):
    """Baseline behaviour, plus reachable sibling orders and an optional budget gate."""

    def __init__(self, scenario, arm: str):
        super().__init__(scenario)
        self.arm = arm
        self.order_lookups: list[str] = []
        self.refused_lookups: list[str] = []
        self.truncated: list[str] = []
        self.result_chars = 0

    # -- the customer's other orders -----------------------------------------------------

    def _sibling_order(self, order_id: str) -> dict:
        """A plausible record for another order on the same account.

        Deliberately unremarkable: nothing here is in scope for the ticket, which is the
        point. The agent spends real money reading records that cannot change its answer.
        """
        seed = int(order_id.split("-")[1])
        return {
            "order_id": order_id,
            "customer_id": self.sc.customer_id,
            "value_usd": round(20 + (seed % 380) + (seed % 97) / 100, 2),
            "days_since_delivery": seed % 90 + 1,
            "final_sale": seed % 5 == 0,
            "defect_reported": seed % 3 == 0,
            "status": "delivered",
        }

    def _known_ids(self) -> set[str]:
        d = self.sc.detail or {}
        return set(d.get("fanout_ids", [])) | set(d.get("related_ids", []))

    # -- execution ------------------------------------------------------------------------

    def __call__(self, name: str, tool_input: dict) -> str:
        if name == "get_order":
            oid = tool_input.get("order_id")
            if oid != self.sc.order_id and oid in self._known_ids():
                self.actions.append(name)
                if self._lookup_refused(oid):
                    return json.dumps({
                        "error": "lookup budget exhausted for this ticket",
                        "policy": "SP-BUDGET-01",
                        "hint": "resolve the order this ticket is about",
                    })
                self.order_lookups.append(oid)
                return self._finish(json.dumps(self._sibling_order(oid)))
            if oid == self.sc.order_id and self._lookup_refused(oid):
                self.actions.append(name)
                return json.dumps({"error": "lookup budget exhausted for this ticket",
                                   "policy": "SP-BUDGET-01"})
            if oid == self.sc.order_id:
                self.order_lookups.append(oid)

        return self._finish(super().__call__(name, tool_input))

    def _lookup_refused(self, order_id: str) -> bool:
        if not gates_tools(self.arm):
            return False
        # The in-scope order is always affordable; the cap bites on everything else.
        if order_id == self.sc.order_id:
            return False
        if len(self.order_lookups) < MAX_ORDER_LOOKUPS:
            return False
        self.refused_lookups.append(order_id)
        return True

    def _finish(self, payload: str) -> str:
        """Last point before the result enters the conversation and starts being replayed.

        Truncation is field-aware on purpose. Slicing the serialised bytes is the obvious
        implementation and it is wrong: it cuts a JSON document mid-string, the agent can
        no longer parse its own tool result, and the gate buys a smaller bill by losing the
        answer. Shortening the offending value and re-serialising keeps the record valid.
        """
        if not gates_tools(self.arm) or len(payload) <= MAX_RESULT_CHARS:
            self.result_chars += len(payload)
            return payload

        try:
            doc = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            doc = None

        if isinstance(doc, dict):
            longest = max((k for k, v in doc.items() if isinstance(v, str)),
                          key=lambda k: len(doc[k]), default=None)
            if longest is not None:
                budget = max(0, MAX_RESULT_CHARS - (len(payload) - len(doc[longest])))
                self.truncated.append(longest)
                doc[longest] = doc[longest][:budget] + TRUNCATION_MARKER
                payload = json.dumps(doc)
        else:
            self.truncated.append(payload[:40])
            payload = payload[:MAX_RESULT_CHARS] + TRUNCATION_MARKER

        self.result_chars += len(payload)
        return payload
