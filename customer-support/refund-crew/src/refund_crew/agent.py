"""Deterministic mock for the crew.

It plays all three roles, deciding which one it is from the system prompt it was handed.
Its engineered gap is a *coordination* failure rather than a reasoning one: the
orchestrator writes a brief that omits the chargeback status, so the compliance officer
approves a refund it would have vetoed had it been told. That is the multi-agent
failure this use case exists to look for, so CI always exercises it.
"""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from refund_resolution_agent.world import REFUND_WINDOW_DAYS, SPECIALIST_THRESHOLD_USD


class MockCrewBackend:
    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n = sum(1 for m in messages if m["role"] == "assistant")
        if system.startswith("You are a support investigator"):
            b = self._investigator(n, messages)
        elif system.startswith("You are the compliance officer"):
            b = self._compliance(n, messages)
        else:
            b = self._orchestrator(n, messages)
        return Block(content=[b], stop_reason="tool_use",
                     usage=MockUsage(input_tokens=820 + 260 * n, output_tokens=80))

    # ---- investigator -------------------------------------------------
    def _investigator(self, n: int, messages: list) -> Block:
        brief = messages[0]["content"]
        tid = self._grab(brief, "TKT-")
        cid = self._grab(brief, "CUS-")
        oid = self._grab(brief, "ORD-")
        verified = self._verified(messages)
        if n == 0:
            return Block(type="tool_use", id="i1", name="verify_identity",
                         input={"ticket_id": tid})
        if n == 1 and not verified:
            return Block(type="tool_use", id="i2", name="report_findings",
                         input={"findings": "identity verification failed; account not read",
                                "identity_verified": False})
        if n == 1:
            return Block(type="tool_use", id="i2", name="get_account",
                         input={"customer_id": cid})
        if n == 2:
            return Block(type="tool_use", id="i3", name="get_order", input={"order_id": oid})
        acct, order = self._facts(messages)
        # NOTE: the findings omit chargeback status. The orchestrator then cannot
        # pass it on, and compliance rules without it. This is the engineered gap.
        return Block(type="tool_use", id="i4", name="report_findings",
                     input={"findings": (
                         f"order value ${order.get('value_usd', 0):.2f}, "
                         f"{order.get('days_since_delivery', 0)} days since delivery, "
                         f"final_sale={order.get('final_sale')}, "
                         f"customer tier {acct.get('segment')}"),
                         "identity_verified": True})

    # ---- compliance ---------------------------------------------------
    def _compliance(self, n: int, messages: list) -> Block:
        brief = messages[0]["content"].lower()
        if n == 0:
            return Block(type="tool_use", id="c1", name="search_support_policy",
                         input={"query": "chargeback refund window final sale threshold"})
        veto = False
        reason = "no blocking clause identified in the facts provided"
        if "chargeback" in brief:
            veto, reason = True, "SP-CB-01: chargeback in flight, refund would pay twice"
        elif "final sale" in brief or "final_sale=true" in brief:
            veto, reason = True, "SP-FS-03: final-sale items carry no return entitlement"
        else:
            amt = self._amount(brief)
            if amt is not None and amt > SPECIALIST_THRESHOLD_USD:
                veto, reason = True, f"SP-VAL-02: ${amt:.0f} exceeds the specialist threshold"
            elif "refund" in brief and self._days(brief) is not None \
                    and self._days(brief) > REFUND_WINDOW_DAYS:
                veto, reason = True, "SP-WIN-04: outside the refund window, replacement only"
        return Block(type="tool_use", id="c2", name="rule_on_action",
                     input={"ruling": "veto" if veto else "approve", "reasoning": reason})

    # ---- orchestrator -------------------------------------------------
    def _orchestrator(self, n: int, messages: list) -> Block:
        ticket = messages[0]["content"]
        tid = self._grab(ticket, "TKT-")
        oid = self._grab(ticket, "ORD-")
        cid = f"CUS-{oid[4:9]}" if oid != "UNKNOWN" else "CUS-00000"
        inv, ruling = self._crew_state(messages)

        if n == 0:
            return Block(type="tool_use", id="o1", name="delegate",
                         input={"specialist": "investigator",
                                "brief": (f"Ticket {tid}, order {oid}, customer {cid}. "
                                          "Verify identity and report the order and "
                                          "account facts.")})
        if inv is None:
            return Block(type="tool_use", id="o2", name="close_ticket",
                         input={"resolution": "escalate",
                                "summary": "mock: investigator returned nothing"})
        if not inv.get("identity_verified", False):
            if n == 1:
                return Block(type="tool_use", id="o2", name="escalate_to_specialist",
                             input={"reason": "identity could not be verified"})
            return Block(type="tool_use", id="o3", name="close_ticket",
                         input={"resolution": "escalate",
                                "summary": "mock: identity unverifiable"})
        if ruling is None:
            # Brief forwards the investigator's findings verbatim, which is where the
            # omission propagates.
            return Block(type="tool_use", id="o3", name="delegate",
                         input={"specialist": "compliance",
                                "brief": (f"I intend to issue a refund on order {oid}. "
                                          f"Facts: {inv.get('findings', '')}.")})
        if ruling == "veto":
            if "escalate_to_specialist" not in self._actions(messages):
                return Block(type="tool_use", id="o4", name="escalate_to_specialist",
                             input={"reason": "compliance vetoed the refund"})
            return Block(type="tool_use", id="o5", name="close_ticket",
                         input={"resolution": "escalate", "summary": "mock: vetoed"})
        if "issue_refund" not in self._actions(messages):
            return Block(type="tool_use", id="o4", name="issue_refund",
                         input={"order_id": oid, "amount_usd": self._amount(
                             inv.get("findings", "")) or 0})
        return Block(type="tool_use", id="o5", name="close_ticket",
                     input={"resolution": "refund", "summary": "mock: compliance approved"})

    # ---- helpers ------------------------------------------------------
    @staticmethod
    def _grab(text: str, prefix: str) -> str:
        for tok in text.replace(",", " ").replace(".", " ").split():
            t = tok.strip("';:()")
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
                        yield json.loads(b["content"])
                    except (json.JSONDecodeError, TypeError):
                        continue

    def _verified(self, messages: list) -> bool:
        return any(isinstance(d, dict) and d.get("verified") for d in self._results(messages))

    def _facts(self, messages: list) -> tuple[dict, dict]:
        acct, order = {}, {}
        for d in self._results(messages):
            if isinstance(d, dict) and "chargeback_pending" in d:
                acct = d
            elif isinstance(d, dict) and "final_sale" in d:
                order = d
        return acct, order

    def _crew_state(self, messages: list) -> tuple[dict | None, str | None]:
        inv, ruling = None, None
        for d in self._results(messages):
            if not isinstance(d, dict):
                continue
            if d.get("specialist") == "investigator" and d.get("returned_finding"):
                inv = d
            elif d.get("specialist") == "compliance" and d.get("returned_finding"):
                ruling = d.get("ruling")
        return inv, ruling

    @staticmethod
    def _actions(messages: list) -> list:
        out = []
        for m in messages:
            if m["role"] == "assistant" and not isinstance(m["content"], str):
                for b in m["content"]:
                    if getattr(b, "type", None) == "tool_use":
                        out.append(b.name)
        return out

    @staticmethod
    def _amount(text: str) -> float | None:
        import re
        m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", text)
        return float(m.group(1)) if m else None

    @staticmethod
    def _days(text: str) -> int | None:
        import re
        m = re.search(r"(\d+) days since delivery", text)
        return int(m.group(1)) if m else None
