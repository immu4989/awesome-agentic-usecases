"""Domain layer for the release-QC agent: system prompt + deterministic mock."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import INHOUSE_FIX_DAYS, RELEASE_WINDOW_DAYS, VENDOR_SLA_DAYS

SYSTEM_PROMPT = """\
You are a content release operations agent at a streaming service. Automated quality
control has flagged an issue on a delivered asset ahead of release. You do not detect
defects — the QC system already did that. You decide who owns the flag and what happens
to the release.

Rules of engagement:
- A QC flag is a detector's opinion, not a verdict. Some flags describe intentional
  creative choices; some cosmetic-looking flags are legally blocking. Always check the
  release context and the production annotations before deciding.
- Remediation rules, the accessibility hard block, the release window, in-house repair
  capability, and board-escalation criteria live in the release-policy knowledge base,
  not in these instructions. Check policy before committing.
- Investigate with the tools, then call submit_release_decision exactly once.

Queues: video-eng (picture essence), audio-eng (sound), timed-text (captions and
subtitles), no-defect (the flag does not describe a real defect).

Actions: waive_and_release (ship as delivered), vendor_redelivery (originating vendor
supplies a corrected package), expedite_internal_fix (repair in house before premiere),
delay_release (move the premiere), escalate_to_release_board (a commercial call above
this desk).
"""

SUBMIT_TOOL = "submit_release_decision"


class MockBackend:
    """Deterministic scripted 'model': release context -> QC flag -> annotations ->
    policy -> submit.

    Its rules mirror gold EXCEPT the accessibility precedence (RQ-CVAA-01): it treats
    caption defects as ordinary defects of their severity, so it waives close-in
    caption defects that policy says can never be waived. That yields a stable,
    nonzero error rate for the reporting pipeline to exercise.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        flag_text = messages[0]["content"]
        tid = self._extract(flag_text, "TTL-")
        aid = self._extract(flag_text, "AST-")

        if n_assistant == 0:
            block = Block(type="tool_use", id="mock-tu-1", name="get_release_context",
                          input={"title_id": tid})
        elif n_assistant == 1:
            block = Block(type="tool_use", id="mock-tu-2", name="get_qc_flag",
                          input={"asset_id": aid})
        elif n_assistant == 2:
            block = Block(type="tool_use", id="mock-tu-3", name="check_creative_annotations",
                          input={"asset_id": aid})
        elif n_assistant == 3:
            block = Block(type="tool_use", id="mock-tu-4", name="search_release_policy",
                          input={"query": "remediation preference release window in-house fix board"})
        else:
            title, flag, annotations = self._find_world(messages)
            block = Block(type="tool_use", id="mock-tu-5", name="submit_release_decision",
                          input=self._decide(title, flag, annotations))
        return Block(
            content=[block],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=900 + 400 * n_assistant, output_tokens=90),
        )

    @staticmethod
    def _extract(text: str, prefix: str) -> str:
        for token in text.replace("(", " ").replace(")", " ").replace(",", " ").split():
            t = token.strip(".:;/'")
            if t.startswith(prefix):
                return t
        return "UNKNOWN"

    @staticmethod
    def _find_world(messages: list) -> tuple[dict, dict, list]:
        title, flag, annotations = {}, {}, []
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
                if isinstance(data, dict) and "days_to_premiere" in data:
                    title = data
                elif isinstance(data, dict) and "severity" in data:
                    flag = data
                elif isinstance(data, dict) and "annotations" in data:
                    annotations = data["annotations"]
        return title, flag, annotations

    @staticmethod
    def _decide(title: dict, flag: dict, annotations: list) -> dict:
        if not title or not flag:
            return {"queue": "no-defect", "action": "delay_release",
                    "reasoning": "mock: world unavailable"}
        if any(a.get("covers_flagged_range") for a in annotations):
            return {"queue": "no-defect", "action": "waive_and_release",
                    "reasoning": "mock: creative intent covers the flagged range"}

        queue = {"video": "video-eng", "audio": "audio-eng",
                 "timed_text": "timed-text"}[flag["component"]]
        days = title["days_to_premiere"]
        # NOTE: no caption-precedence check — the engineered gap.
        if flag["severity"] == "minor":
            action = ("waive_and_release" if days <= RELEASE_WINDOW_DAYS
                      else "vendor_redelivery")
        elif flag["component"] in ("timed_text", "audio") and days >= INHOUSE_FIX_DAYS:
            action = "expedite_internal_fix"
        elif days > VENDOR_SLA_DAYS:
            action = "vendor_redelivery"
        elif title["tier"] == "tentpole":
            action = "escalate_to_release_board"
        else:
            action = "delay_release"
        return {"queue": queue, "action": action, "reasoning": "mock: rule-based decision"}
