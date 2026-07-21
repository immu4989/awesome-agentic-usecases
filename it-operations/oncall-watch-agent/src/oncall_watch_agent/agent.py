"""Domain layer for the on-call watch agent: system prompt + deterministic mock."""

from __future__ import annotations

import json

from aau_harness import Block, MockUsage

from .world import SATURATION_WARN, SLO_ERROR_RATE, SLO_P99_MS

SYSTEM_PROMPT = f"""\
You are an on-call watch agent. Telemetry for one service streams to you a minute at a
time, and you decide whether this window needs a page, a ticket, or nothing at all.

Rules of engagement:
- You cannot see the future. Each call to next_tick buys you exactly one more minute.
  Deciding early means deciding on less evidence; waiting costs time you may not have.
- One bad sample is not an incident, and not every incident announces itself with a
  spike. The same numbers can mean different things depending on what else is true
  about the service.
- What justifies a page rather than a ticket, how to treat transients and slow drifts,
  and when degraded metrics are expected all live in the on-call runbook, not in these
  instructions.
- SLOs for reference: {int(SLO_ERROR_RATE * 100)}% error rate, {SLO_P99_MS}ms p99,
  saturation warning at {SATURATION_WARN}.
- Watch as long as you need, then call raise_alert exactly once.

Severities: page (wake the on-call engineer now), ticket (queue it for working hours),
none (no action warranted).
"""

SUBMIT_TOOL = "raise_alert"


class MockBackend:
    """Deterministic scripted 'model': context, runbook, then watch until it has an
    opinion.

    Its gap is impatience: it commits as soon as any single sample breaches an SLO,
    without waiting to see whether the signal is sustained. That makes it page the
    upstream blips, which is exactly the alert-fatigue failure the metrics are built to
    measure, so the reporting path stays exercised in CI.
    """

    name = "mock"
    model = "mock"

    def create(self, system: str, messages: list, tools: list):
        n = sum(1 for m in messages if m["role"] == "assistant")
        service = self._service(messages[0]["content"])
        ctx, samples, ended = self._state(messages)

        if n == 0:
            b = Block(type="tool_use", id="m0", name="get_service_context",
                      input={"service_id": service})
        elif n == 1:
            b = Block(type="tool_use", id="m1", name="search_runbook",
                      input={"query": "page ticket transient blip maintenance slow burn"})
        else:
            decision = self._decide(ctx, samples, ended)
            if decision is None:
                b = Block(type="tool_use", id=f"m{n}", name="next_tick",
                          input={"service_id": service})
            else:
                b = Block(type="tool_use", id=f"m{n}", name="raise_alert",
                          input=decision)
        return Block(content=[b], stop_reason="tool_use",
                     usage=MockUsage(input_tokens=850 + 210 * n, output_tokens=70))

    @staticmethod
    def _service(text: str) -> str:
        for token in text.replace(".", " ").replace(",", " ").split():
            if "-" in token and token.replace("-", "").isalpha() and len(token) > 6:
                return token
        return "UNKNOWN"

    @staticmethod
    def _state(messages: list) -> tuple[dict, list, bool]:
        ctx, samples, ended = {}, [], False
        for m in messages:
            if m["role"] != "user" or not isinstance(m["content"], list):
                continue
            for b in m["content"]:
                if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                    continue
                try:
                    d = json.loads(b["content"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(d, dict):
                    continue
                if "maintenance_window_active" in d:
                    ctx = d
                elif d.get("end_of_window"):
                    ended = True
                elif "error_rate" in d:
                    samples.append(d)
        return ctx, samples, ended

    @staticmethod
    def _decide(ctx: dict, samples: list, ended: bool) -> dict | None:
        if ctx.get("maintenance_window_active"):
            return {"severity": "none", "reasoning": "mock: maintenance window active"}
        if not samples:
            return None
        last = samples[-1]
        breach = (last["error_rate"] > SLO_ERROR_RATE or last["p99_ms"] > SLO_P99_MS)
        # NOTE: no sustained-signal check — the engineered impatience gap.
        if breach:
            return {"severity": "page", "reasoning": "mock: SLO breach on latest sample"}
        if ended:
            worst_sat = max(s["saturation"] for s in samples)
            if worst_sat > SATURATION_WARN:
                return {"severity": "ticket", "reasoning": "mock: saturation trending high"}
            return {"severity": "none", "reasoning": "mock: window healthy"}
        return None
