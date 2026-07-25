"""The baseline tool set, plus a way out.

`lookup_shipment` gains an optional `refresh` flag. That is deliberate: the drift arm hands
the agent everything it needs to rescue itself — a visible `as_of`, a `degraded` marker, a
carrier feed to cross-check, and a documented way to re-read the system of record — and
then measures whether it bothers. The failure this use case is about is not a missing
capability; it is an unused one.
"""

from __future__ import annotations

import copy
import json

from exception_triage_agent.tools import TOOL_SCHEMAS as BASE_SCHEMAS
from exception_triage_agent.world import CARRIER_DISPOSITIONS, EXCEPTIONS, Scenario, search_policy

from .drift import served_view

SOURCE_OF_TRUTH_DOC = {
    "id": "POL-SRC-07",
    "title": "Source of truth and stale records",
    "text": (
        "Where the shipment record and the carrier scan history disagree about what "
        "happened in transit, the carrier scan history is authoritative. Shipment records "
        "served from cache carry an as_of timestamp; re-read the record with refresh=true "
        "before acting on a cached or partial response."
    ),
}


def _schemas() -> list[dict]:
    out = []
    for t in BASE_SCHEMAS:
        t = copy.deepcopy(t)
        if t["name"] == "lookup_shipment":
            t["description"] += (
                " Records may be served from a cache and carry an as_of timestamp; pass "
                "refresh=true to re-read from the system of record."
            )
            t["input_schema"]["properties"]["refresh"] = {
                "type": "boolean",
                "description": "Re-read from the system of record instead of the cache",
            }
        out.append(t)
    return out


TOOL_SCHEMAS = _schemas()


class DriftSession:
    """Serves the arm-appropriate view of the world and records what the agent did."""

    def __init__(self, scenario: Scenario, archetype: str, arm: str):
        self.sc = scenario
        self.archetype = "CLEAN" if arm == "clean" else archetype
        self.arm = arm
        self.refreshed = False
        self.read_carrier = False
        self.served_corrupt = False
        self.gate_repaired: list[str] = []
        self._view = served_view(scenario, self.archetype)

    # -- what the tool layer hands back -------------------------------------------------
    def _shipment_payload(self, refresh: bool) -> dict:
        arch, meta = self.archetype, dict(self._view["meta"])
        ship = copy.deepcopy(self._view["shipment"])

        # the freshness gate repairs what it can detect, before the model sees it
        if self.arm == "freshness_gate" and arch in ("STALE_SNAPSHOT", "DEGRADED_PARTIAL"):
            ship = copy.deepcopy(self.sc.shipment)
            meta = {"repaired_by": "freshness gate", "as_of": "live"}
            if arch not in self.gate_repaired:
                self.gate_repaired.append(arch)
        elif self.arm == "freshness_gate" and arch == "SOURCE_CONFLICT":
            ship["exception_code"] = self.sc.shipment["exception_code"]
            meta = {"repaired_by": "freshness gate: carrier scan history is authoritative"}
            if arch not in self.gate_repaired:
                self.gate_repaired.append(arch)
        # an explicit refresh gets the truth for anything that was merely stale or partial
        elif refresh and arch in ("STALE_SNAPSHOT", "DEGRADED_PARTIAL"):
            ship = copy.deepcopy(self.sc.shipment)
            meta = {"as_of": "live"}

        if arch != "CLEAN" and self.arm != "freshness_gate":
            self.served_corrupt = True
        return {**ship, **meta}

    def __call__(self, name: str, tool_input: dict) -> str:
        sc = self.sc
        if name == "lookup_shipment":
            if tool_input.get("tracking_id") != sc.tracking_id:
                return json.dumps({"error": f"no shipment found for "
                                            f"{tool_input.get('tracking_id')!r}"})
            refresh = bool(tool_input.get("refresh"))
            if refresh:
                self.refreshed = True
            return json.dumps(self._shipment_payload(refresh))

        if name == "get_carrier_status":
            if tool_input.get("tracking_id") != sc.tracking_id:
                return json.dumps({"error": f"no carrier data for "
                                            f"{tool_input.get('tracking_id')!r}"})
            self.read_carrier = True
            # the carrier feed always reflects what actually happened
            events = copy.deepcopy(sc.carrier_events)
            true_code = sc.shipment["exception_code"]
            for e in events:
                if e.get("scan") == "EXCEPTION":
                    e["disposition"] = CARRIER_DISPOSITIONS[true_code]
                    e["exception_code"] = true_code
            return json.dumps({"tracking_id": sc.tracking_id, "events": events,
                               "source": "carrier scan history (authoritative)"})

        if name == "search_policy":
            docs = search_policy(tool_input.get("query", ""))
            q = tool_input.get("query", "").lower()
            if any(w in q for w in ("source", "truth", "cache", "stale", "conflict",
                                    "disagree", "refresh", "record")):
                docs = [SOURCE_OF_TRUTH_DOC] + [d for d in docs if d["id"] != "POL-SRC-07"]
            return json.dumps(docs[:3])

        return json.dumps({"error": f"unknown tool {name!r}"})


__all__ = ["TOOL_SCHEMAS", "DriftSession", "SOURCE_OF_TRUTH_DOC", "EXCEPTIONS"]
