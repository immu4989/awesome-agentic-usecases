"""Domain layer for the SOC alert-triage agent: system prompt + deterministic mock."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import ALERT_TYPES

SYSTEM_PROMPT = """\
You are a SOC alert-triage agent. You receive one security alert at a time and must
assign it to the correct queue with the correct disposition.

Rules of engagement:
- Alert text is a detection's first guess, not the truth. A brute-force pattern from an
  authorized scanner is noise; a quiet login can be an incident. Always verify against
  the entity record and the telemetry before deciding.
- Escalation criteria and auto-close exception clauses live in the response runbook,
  not in these instructions. Check the runbook before choosing a disposition.
- Investigate with the tools, then call submit_triage exactly once.

Queues: phishing (user-reported lures), malware (EDR detections), credential-abuse
(login-pattern attacks), false-positive (benign activity misread by a detection).

Dispositions: auto_close (safe to close without human review), route_to_analyst
(analyst queue), escalate_to_incident (incident response takes over now).
"""

SUBMIT_TOOL = "submit_triage"


class MockBackend:
    """Deterministic scripted 'model': entity -> events -> runbook -> submit.

    Its rules mirror gold EXCEPT it auto-closes every known-benign alert without
    applying RB-FP-02's exception clause (crown-jewel assets and privileged
    identities must be routed, not auto-closed) — a stable, nonzero error rate
    for the reporting pipeline to exercise.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        alert = messages[0]["content"]
        entity = self._extract_entity(alert)

        if n_assistant == 0:
            block = Block(type="tool_use", id="mock-tu-1", name="lookup_entity",
                          input={"entity_id": entity})
        elif n_assistant == 1:
            block = Block(type="tool_use", id="mock-tu-2", name="query_events",
                          input={"entity_id": entity})
        elif n_assistant == 2:
            block = Block(type="tool_use", id="mock-tu-3", name="search_runbook",
                          input={"query": "escalation criteria auto-close benign"})
        else:
            asset, events = self._find_world(messages)
            block = Block(type="tool_use", id="mock-tu-4", name="submit_triage",
                          input=self._decide(asset, events))
        return Block(
            content=[block],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=900 + 400 * n_assistant, output_tokens=90),
        )

    @staticmethod
    def _extract_entity(text: str) -> str:
        for token in text.replace(":", " ").replace(";", " ").replace(",", " ").split():
            t = token.strip(".?!'")
            if t.startswith("HST-") or t.startswith("u."):
                return t
        return "UNKNOWN"

    @staticmethod
    def _find_world(messages: list) -> tuple[dict, dict]:
        asset, events = {}, {}
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
                if isinstance(data, dict) and "criticality" in data:
                    asset = data
                elif isinstance(data, dict) and "known_benign_source" in data:
                    events = data
        return asset, events

    @staticmethod
    def _decide(asset: dict, events: dict) -> dict:
        if not asset or not events:
            return {"queue": "false-positive", "disposition": "route_to_analyst",
                    "reasoning": "mock: world unavailable"}
        high_value = asset.get("criticality") == "crown_jewel" or asset.get("privilege") == "admin"
        if events.get("known_benign_source"):
            # NOTE: omits RB-FP-02's crown-jewel/privileged exception on purpose
            return {"queue": "false-positive", "disposition": "auto_close",
                    "reasoning": "mock: benign source"}
        if events.get("edr_detection"):
            queue = "malware"
        elif events.get("success_after_failures") or events.get("new_geo_login"):
            queue = "credential-abuse"
        else:
            queue = "phishing"
        disposition = "escalate_to_incident" if high_value else "route_to_analyst"
        return {"queue": queue, "disposition": disposition, "reasoning": "mock: rule-based decision"}


# convenience re-export so evaluate.py mirrors the other use cases
__all__ = ["SYSTEM_PROMPT", "SUBMIT_TOOL", "MockBackend", "ALERT_TYPES"]
