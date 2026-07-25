"""Making the world unreliable, without moving the right answer.

Every corruption here targets a field the gold rule actually reads, and is constructed so
the corrupted view implies a *different* action than the truth. A corruption that leaves
the answer unchanged would measure nothing.

What never changes is the gold itself: `gold_triage(true_shipment)` from the baseline world
remains the answer in every arm. That is what makes the comparison honest — any accuracy
change is the world's doing, and the numbers line up directly against the committed
baseline results for the same 30 scenarios.
"""

from __future__ import annotations

import copy

from exception_triage_agent.world import (
    ESCALATION_PLATINUM_SLA_H,
    ESCALATION_VALUE_USD,
    EXCEPTIONS,
    Scenario,
    gold_triage,
)

ARCHETYPES = ("CLEAN", "STALE_SNAPSHOT", "SOURCE_CONFLICT", "DEGRADED_PARTIAL", "SILENT_WRONG")
ARMS = ("clean", "drift", "prompt_guard", "freshness_gate")

# archetypes whose corruption the agent can, in principle, detect from inside the run
DETECTABLE = ("STALE_SNAPSHOT", "SOURCE_CONFLICT", "DEGRADED_PARTIAL")

STALE_AS_OF = "2026-07-09T02:14:00Z"

PROMPT_GUARD = (
    "\n\nDATA RELIABILITY NOTICE: shipment records may be served from a cache. Check the "
    "`as_of` timestamp and the `cached` and `degraded` flags on anything you read. If a "
    "record is stale or has missing fields, call lookup_shipment again with refresh=true "
    "before deciding. If the shipment record and the carrier scan history disagree about "
    "what happened in transit, the carrier scan history is authoritative. Do not commit a "
    "decision on data you have reason to distrust."
)


def archetype_for(index: int) -> str:
    return ARCHETYPES[index % len(ARCHETYPES)]


def _flip_value(shipment: dict) -> dict:
    """Move the shipment across the escalation threshold, whichever side it starts on."""
    s = copy.deepcopy(shipment)
    true_action = gold_triage(shipment)[1]
    if true_action == "escalate_to_human":
        # truth escalates — serve a view that looks routine
        s["value_usd"] = round(ESCALATION_VALUE_USD * 0.45, 2)
        s["customer_tier"] = "standard"
        s["sla_hours_remaining"] = max(shipment["sla_hours_remaining"],
                                       ESCALATION_PLATINUM_SLA_H + 12)
    else:
        # truth is routine — serve a view that looks like it needs a human
        s["value_usd"] = round(ESCALATION_VALUE_USD * 1.9, 2)
    return s


def _wrong_code(shipment: dict) -> str:
    codes = [c for c in EXCEPTIONS if c != shipment["exception_code"]]
    # deterministic pick so scenarios stay reproducible
    return codes[hash(shipment["tracking_id"]) % len(codes)]


def served_view(scenario: Scenario, archetype: str) -> dict:
    """The (possibly corrupted) shipment record the tools hand back, plus its metadata."""
    true_ship = scenario.shipment
    if archetype == "CLEAN":
        return {"shipment": copy.deepcopy(true_ship), "meta": {}}

    if archetype == "STALE_SNAPSHOT":
        return {"shipment": _flip_value(true_ship),
                "meta": {"cached": True, "as_of": STALE_AS_OF,
                         "note": "served from cache; call again with refresh=true for the "
                                 "system-of-record value"}}

    if archetype == "SOURCE_CONFLICT":
        s = copy.deepcopy(true_ship)
        s["exception_code"] = _wrong_code(true_ship)
        return {"shipment": s, "meta": {"as_of": STALE_AS_OF}}

    if archetype == "DEGRADED_PARTIAL":
        s = copy.deepcopy(true_ship)
        s["value_usd"] = None
        s["customer_tier"] = None
        s["sla_hours_remaining"] = None
        return {"shipment": s,
                "meta": {"degraded": True,
                         "note": "partial response: some fields unavailable from the "
                                 "pricing service; retry with refresh=true"}}

    # SILENT_WRONG — wrong, and nothing about the response says so
    return {"shipment": _flip_value(true_ship), "meta": {}}


def recovering_step(archetype: str) -> str | None:
    """What a careful agent would do about this corruption."""
    if archetype in ("STALE_SNAPSHOT", "DEGRADED_PARTIAL"):
        return "refresh"
    if archetype == "SOURCE_CONFLICT":
        return "read_carrier"
    return None
