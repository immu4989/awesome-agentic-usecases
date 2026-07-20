"""Domain layer for the fraud-triage agent: system prompt + deterministic mock."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import REG_REVIEW_THRESHOLD_USD

SYSTEM_PROMPT = """\
You are a transaction-fraud triage agent at a bank. You receive one fraud alert at a
time and must assign it to the correct queue with the correct disposition.

Rules of engagement:
- Alert text is a rule's first guess, not the truth. A foreign charge can be a customer
  on holiday who filed a travel notice; a payment from the customer's own trusted device
  can still be a scam they were tricked into authorizing. Always verify against the
  customer record and the transaction signals before deciding.
- Escalation criteria, auto-release exceptions, and the APP-scam guidance live in the
  fraud-policy knowledge base, not in these instructions. Check policy before choosing a
  disposition.
- Investigate with the tools, then call submit_triage exactly once.

Queues: card-fraud (stolen-card charges), account-takeover (credential compromise),
app-scam (authorized push-payment scams), false-positive (legitimate activity a rule
misread).

Dispositions: allow (release the transaction), hold_for_review (manual review queue),
block_and_notify (stop it and tell the customer), escalate_to_fraud_ops (the fraud team
takes over now).
"""

SUBMIT_TOOL = "submit_triage"


class MockBackend:
    """Deterministic scripted 'model': customer -> transaction -> policy -> submit.

    Its rules mirror gold EXCEPT it treats every customer-authorized payment as
    benign (allow) — it never applies the APP-scam guidance (FP-APP-05) that a
    trusted device does not clear a new-mule-beneficiary payment. That yields a
    stable, nonzero error rate for the reporting pipeline to exercise.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        alert = messages[0]["content"]
        entity = self._extract_entity(alert)

        if n_assistant == 0:
            block = Block(type="tool_use", id="mock-tu-1", name="lookup_customer",
                          input={"entity_id": entity})
        elif n_assistant == 1:
            block = Block(type="tool_use", id="mock-tu-2", name="query_transaction",
                          input={"entity_id": entity})
        elif n_assistant == 2:
            block = Block(type="tool_use", id="mock-tu-3", name="search_fraud_policy",
                          input={"query": "escalation auto-release benign private banking app scam"})
        else:
            customer, txn = self._find_world(messages)
            block = Block(type="tool_use", id="mock-tu-4", name="submit_triage",
                          input=self._decide(customer, txn))
        return Block(
            content=[block],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=900 + 400 * n_assistant, output_tokens=90),
        )

    @staticmethod
    def _extract_entity(text: str) -> str:
        for token in text.replace(",", " ").replace(".", " ").split():
            t = token.strip("';:")
            if t.startswith("acct-"):
                return t
        return "UNKNOWN"

    @staticmethod
    def _find_world(messages: list) -> tuple[dict, dict]:
        customer, txn = {}, {}
        for m in messages:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for block in m["content"]:
                if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                    continue
                try:
                    data = json.loads(block["content"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(data, dict) and "segment" in data:
                    customer = data
                elif isinstance(data, dict) and "known_benign_source" in data:
                    txn = data
        return customer, txn

    @staticmethod
    def _decide(customer: dict, txn: dict) -> dict:
        if not customer or not txn:
            return {"queue": "false-positive", "disposition": "hold_for_review",
                    "reasoning": "mock: world unavailable"}
        high_value = (customer.get("segment") == "private_banking"
                      or txn.get("amount_usd", 0) > REG_REVIEW_THRESHOLD_USD)
        # NOTE: treats customer_authorized as benign — misses the APP-scam clause on purpose
        if txn.get("known_benign_source") or txn.get("customer_authorized"):
            return {"queue": "false-positive",
                    "disposition": "hold_for_review" if high_value else "allow",
                    "reasoning": "mock: benign / customer-authorized"}
        if txn.get("credential_reset") or (txn.get("new_device") and txn.get("new_payee")):
            queue = "account-takeover"
        else:
            queue = "card-fraud"
        disposition = "escalate_to_fraud_ops" if high_value else "block_and_notify"
        return {"queue": queue, "disposition": disposition, "reasoning": "mock: rule-based decision"}
