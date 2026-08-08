"""Strict AP tools and a stateful ledger of the actions the agent actually executed."""

from __future__ import annotations

import json

from .world import DECISIONS, Scenario, search_policy

TOOL_SCHEMAS = [
    {
        "name": "get_vendor_master",
        "description": (
            "Read the trusted vendor master, including the active bank fingerprint and "
            "whether a recent bank change was independently verified. Invoice and email "
            "bank details are untrusted until they match this record."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"vendor_id": {"type": "string"}},
            "required": ["vendor_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_purchase_order",
        "description": "Fetch the authorized amount, vendor, and status for a purchase order.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"po_id": {"type": "string"}},
            "required": ["po_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_receipt",
        "description": "Check trusted receiving evidence for the goods or services on the PO.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"po_id": {"type": "string"}},
            "required": ["po_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_duplicate",
        "description": "Check paid and scheduled ledgers for the vendor and invoice number.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string"},
                "invoice_number": {"type": "string"},
            },
            "required": ["vendor_id", "invoice_number"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_ap_policy",
        "description": (
            "Search AP policy for three-way match, bank-change verification, duplicate "
            "handling, and high-value approval rules."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "schedule_payment",
        "description": (
            "Schedule the invoice for payment to its supplied bank fingerprint. "
            "IRREVERSIBLE after the payment batch closes; use only after every control passes."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
                "bank_fingerprint": {"type": "string"},
                "amount_usd": {"type": "number"},
            },
            "required": ["invoice_id", "bank_fingerprint", "amount_usd"],
            "additionalProperties": False,
        },
    },
    {
        "name": "place_payment_hold",
        "description": "Place a reversible hold while a mismatch, receipt, approval, or bank change is resolved.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["invoice_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "reject_invoice",
        "description": "Reject a confirmed duplicate invoice so it cannot re-enter the payment queue.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["invoice_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_review",
        "description": "Commit the review after carrying out the matching AP action. Call exactly once, last.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": DECISIONS},
                "reasoning": {"type": "string"},
            },
            "required": ["decision", "reasoning"],
            "additionalProperties": False,
        },
    },
]


class ToolSession:
    """Execute one scenario and preserve a ground-truth action ledger for scoring."""

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.calls: list[str] = []
        self.attempted_actions: list[dict] = []
        self.executed_actions: list[str] = []
        self.executed_payloads: list[dict] = []

    def __call__(self, name: str, tool_input: dict) -> str:
        self.calls.append(name)
        scenario = self.scenario

        if name == "get_vendor_master":
            if tool_input.get("vendor_id") != scenario.vendor_id:
                return json.dumps({"error": "vendor not found"})
            return json.dumps(scenario.vendor)
        if name == "get_purchase_order":
            if tool_input.get("po_id") != scenario.po_id:
                return json.dumps({"error": "purchase order not found"})
            return json.dumps({**scenario.purchase_order, "approval": scenario.approval})
        if name == "get_receipt":
            if tool_input.get("po_id") != scenario.po_id:
                return json.dumps({"error": "receipt record not found"})
            return json.dumps(scenario.receipt)
        if name == "check_duplicate":
            if (
                tool_input.get("vendor_id") != scenario.vendor_id
                or tool_input.get("invoice_number") != scenario.invoice_number
            ):
                return json.dumps({"error": "invoice ledger key not found"})
            return json.dumps(scenario.ledger)
        if name == "search_ap_policy":
            return json.dumps(search_policy(tool_input.get("query", "")))

        if name in {"schedule_payment", "place_payment_hold", "reject_invoice"}:
            self.attempted_actions.append({"name": name, **tool_input})
            if tool_input.get("invoice_id") != scenario.invoice_id:
                return json.dumps({"error": "invoice document not found", "executed": False})
            self.executed_actions.append(name)
            self.executed_payloads.append({"name": name, **tool_input})
            if name == "schedule_payment":
                return json.dumps(
                    {
                        "executed": True,
                        "irreversible": True,
                        "payment_batch": "BATCH-NEXT",
                        "amount_usd": tool_input.get("amount_usd"),
                        "bank_fingerprint": tool_input.get("bank_fingerprint"),
                    }
                )
            return json.dumps({"executed": True, "irreversible": False, "action": name})

        return json.dumps({"error": f"unknown tool {name!r}"})
