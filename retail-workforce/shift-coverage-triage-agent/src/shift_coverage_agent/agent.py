"""Domain layer for the shift-coverage agent: system prompt + deterministic mock."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import BORROW_MAX_KM, BORROW_WEEKLY_CAP_H, MINOR_LATEST_END, REDUCED_MAX_GAP, SHIFT_LEN_H

SYSTEM_PROMPT = """\
You are a retail workforce coverage agent. You receive one short-staffed-shift ticket
at a time from a store manager and must decide the fill strategy.

Rules of engagement:
- The manager's message never contains enough information to decide. Always pull the
  shift record and the candidate roster before deciding.
- Compliance rules (overtime caps, minor work-hour limits, borrowing rules,
  reduced-coverage conditions, and the preference order between strategies) live in
  the labor policy knowledge base, not in these instructions. Check policy before
  committing.
- Investigate with the tools, then call submit_coverage_plan exactly once.

Strategies: offer_overtime (extend a home-store worker), borrow_from_nearby (pull a
worker from a nearby store), run_reduced (run the shift short), escalate_to_district
(no compliant fill exists — the district manager decides).
"""

SUBMIT_TOOL = "submit_coverage_plan"


class MockBackend:
    """Deterministic scripted 'model': shift -> roster -> policy -> submit.

    Its rules mirror gold EXCEPT it never applies the weekly-hours overtime cap
    (POL-OT-01) — it checks only the minor rules. That yields a stable, nonzero
    error rate for the reporting pipeline to exercise: it over-offers overtime
    to workers who would blow through the weekly cap.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        ticket = messages[0]["content"]
        sid = next((t for t in ticket.replace(":", " ").split()
                    if len(t) == 4 and t[0] == "S" and t[1:].isdigit()), "UNKNOWN")

        if n_assistant == 0:
            block = Block(type="tool_use", id="mock-tu-1", name="get_shift_status",
                          input={"store_id": sid})
        elif n_assistant == 1:
            block = Block(type="tool_use", id="mock-tu-2", name="list_available_workers",
                          input={"store_id": sid})
        elif n_assistant == 2:
            block = Block(type="tool_use", id="mock-tu-3", name="search_labor_policy",
                          input={"query": "overtime borrowing reduced coverage minor"})
        else:
            shift, workers = self._find_world(messages)
            block = Block(type="tool_use", id="mock-tu-4", name="submit_coverage_plan",
                          input=self._decide(shift, workers))
        return Block(
            content=[block],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=900 + 400 * n_assistant, output_tokens=90),
        )

    @staticmethod
    def _find_world(messages: list) -> tuple[dict, list]:
        shift, workers = {}, []
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
                if isinstance(data, dict) and "required_headcount" in data:
                    shift = data
                elif isinstance(data, list) and data and "worker_id" in data[0]:
                    workers = data
        return shift, workers

    @staticmethod
    def _decide(shift: dict, workers: list) -> dict:
        if not shift or not workers:
            return {"strategy": "escalate_to_district", "reasoning": "mock: world unavailable"}
        ends_late = shift["end_hour"] > MINOR_LATEST_END

        def minor_ok(w):
            return not (w["is_minor"] and ends_late)

        # NOTE: omits the weekly OT cap (POL-OT-01) on purpose
        if any(w["home_store"] and not w["is_minor"] and minor_ok(w) for w in workers):
            strategy = "offer_overtime"
        elif any(
            (not w["home_store"]) and w["distance_km"] <= BORROW_MAX_KM
            and w["weekly_hours_scheduled"] + SHIFT_LEN_H <= BORROW_WEEKLY_CAP_H
            and minor_ok(w)
            for w in workers
        ):
            strategy = "borrow_from_nearby"
        elif (shift["callouts"] / shift["required_headcount"] <= REDUCED_MAX_GAP
              and not shift["is_peak_day"]):
            strategy = "run_reduced"
        else:
            strategy = "escalate_to_district"
        return {"strategy": strategy, "reasoning": "mock: rule-based decision"}
