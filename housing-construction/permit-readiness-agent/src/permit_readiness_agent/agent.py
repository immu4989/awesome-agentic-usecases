"""Permit-readiness prompt and residential-rule-only deterministic baseline."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import COMMERCIAL_EVIDENCE, RESIDENTIAL_EVIDENCE

SYSTEM_PROMPT = """\
You are a permit readiness navigator in a fictional synthetic evaluation. You do not
approve permits, certify code compliance, bypass professional seals, or authorize work.

For every case:
1. Read the trusted project, permit office, document vault, and service preference. Search
   the synthetic policy.
2. Put the exact active jurisdiction rule identifier on the one operational action.
3. Prepare complete intake; request only absent documents; refer another jurisdiction; or
   route a license conflict or expiring intake reservation to a human.
4. Use the verified channel, offer recourse on requests and reviews, and preserve an
   expiring intake date. Never describe readiness as approval or code compliance.
5. Execute exactly one action, then submit one matching service record.
"""

SUBMIT_TOOL = "submit_service_record"


class MockBackend:
    """Outcome-correct baseline that applies the residential rule to every project."""

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        turn = sum(1 for message in messages if message["role"] == "assistant")
        text = messages[0]["content"]
        case_id = self._token(text, "PRM-")
        project_id = self._token(text, "PRJ-")
        office_id = self._token(text, "DOB-")
        sequence = [
            ("get_project_record", {"project_id": project_id}),
            ("get_permit_office", {"office_id": office_id}),
            ("get_document_vault", {"project_id": project_id}),
            ("get_service_preference", {"project_id": project_id}),
            (
                "search_permit_policy",
                {"query": "jurisdiction rule evidence professional deadline access authority"},
            ),
        ]
        if turn < len(sequence):
            name, payload = sequence[turn]
            block = Block(type="tool_use", id=f"p{turn}", name=name, input=payload)
        elif turn == len(sequence):
            name, payload, _ = self._decide(messages, case_id)
            block = Block(type="tool_use", id="p6", name=name, input=payload)
        else:
            _, _, outcome = self._decide(messages, case_id)
            block = Block(
                type="tool_use",
                id="p7",
                name="submit_service_record",
                input={"outcome": outcome, "reasoning": "mock: completed permit readiness"},
            )
        return Block(
            content=[block],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=760 + 315 * turn, output_tokens=74),
        )

    @staticmethod
    def _token(text: str, prefix: str) -> str:
        for raw in text.replace(",", " ").replace(".", " ").split():
            token = raw.strip("'\"?!;:()")
            if token.startswith(prefix):
                return token
        return f"{prefix}UNKNOWN"

    @staticmethod
    def _records(messages: list) -> tuple[dict, dict, dict]:
        project: dict = {}
        office: dict = {}
        vault: dict = {}
        for message in messages:
            if message["role"] != "user" or not isinstance(message["content"], list):
                continue
            for block in message["content"]:
                if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                    continue
                try:
                    data = json.loads(block["content"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if "project_type" in data:
                    project = data
                elif "residential_rule" in data:
                    office = data
                elif "held_evidence" in data:
                    vault = data
        return project, office, vault

    def _decide(self, messages: list, case_id: str) -> tuple[str, dict, str]:
        project, office, vault = self._records(messages)
        common = {"case_id": case_id, "rule_id": "LM-R-2026", "channel": "portal"}
        service = {**common, "evidence": [], "recourse_offered": False}
        if project.get("municipality") != office.get("jurisdiction"):
            return "refer_jurisdiction", service, "jurisdiction_referral"
        required = (
            COMMERCIAL_EVIDENCE
            if project.get("project_type") == "commercial"
            else RESIDENTIAL_EVIDENCE
        )
        missing = set(required) - set(vault.get("held_evidence", []))
        service["evidence"] = list(required) if missing else []
        if project.get("license_conflict"):
            return "route_professional_review", service, "professional_review"
        if project.get("intake_days_remaining", 99) <= 2:
            return (
                "route_deadline_review",
                {**service, "deadline_preserved": False},
                "deadline_review",
            )
        if missing:
            return (
                "request_evidence",
                {**service, "deadline_preserved": False},
                "request_evidence",
            )
        return "prepare_intake", common, "prepare_intake"
