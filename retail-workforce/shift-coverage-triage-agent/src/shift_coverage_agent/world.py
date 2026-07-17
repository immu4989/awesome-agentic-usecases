"""Synthetic world: store shifts, worker rosters, a labor-policy knowledge base,
and the scenario generator whose rules are the eval's ground truth.

The manager's ticket deliberately underdetermines the answer: the shift window,
peak-day flag, candidate roster, weekly hours, and minor status are only
reachable through tools, and the compliance clauses (weekly-hour caps, minor
work-hour limits) live in the policy KB, not in the agent's instructions.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

STRATEGIES = [
    "offer_overtime",
    "borrow_from_nearby",
    "run_reduced",
    "escalate_to_district",
]

SHIFT_LEN_H = 8
OT_WEEKLY_CAP_H = 46
BORROW_WEEKLY_CAP_H = 40
BORROW_MAX_KM = 25
REDUCED_MAX_GAP = 0.20
MINOR_LATEST_END = 22  # hour, 24h clock

POLICY_KB = [
    {
        "id": "POL-PREF-00",
        "title": "Coverage fill preference order",
        "text": (
            "When a shift is short-staffed, prefer offering overtime to home-store "
            "staff first, then borrowing from a nearby store, then running reduced "
            "coverage. Escalate to the district manager only when no compliant fill "
            "exists."
        ),
    },
    {
        "id": "POL-OT-01",
        "title": "Overtime limits",
        "text": (
            f"Overtime may be offered to home-store staff up to a hard weekly cap of "
            f"{OT_WEEKLY_CAP_H} scheduled hours including the extra shift. "
            "Minors are never eligible for overtime."
        ),
    },
    {
        "id": "POL-MINOR-02",
        "title": "Minor work-hour limits",
        "text": (
            f"Workers under 18 cannot be scheduled on any shift that ends after "
            f"{MINOR_LATEST_END}:00, and are never eligible for overtime."
        ),
    },
    {
        "id": "POL-BORROW-03",
        "title": "Borrowing between stores",
        "text": (
            f"Staff may be borrowed from stores within {BORROW_MAX_KM} km. Borrowed "
            f"staff must stay within {BORROW_WEEKLY_CAP_H} scheduled hours per week "
            "including the extra shift — borrowing never creates overtime."
        ),
    },
    {
        "id": "POL-RED-04",
        "title": "Reduced coverage",
        "text": (
            f"A shift may run at reduced coverage when the staffing gap is at most "
            f"{int(REDUCED_MAX_GAP * 100)}% of required headcount AND the day is not "
            "flagged as a peak day. Peak days always require full coverage."
        ),
    },
    {
        "id": "POL-ESC-05",
        "title": "District escalation",
        "text": (
            "Escalate to the district manager when no compliant fill exists: no "
            "eligible overtime candidate, no eligible borrow candidate, and reduced "
            "coverage not permitted."
        ),
    },
]

TICKETS = [
    "Store {sid}: {n} crew called out for tomorrow's {window_name} shift. Need coverage ASAP.",
    "{n} call-out(s) at {sid} for the {window_name} shift tomorrow — what do I do for coverage?",
    "Short {n} people on tomorrow's {window_name} at {sid}. Customers lined up last time this happened.",
]

FIRST_NAMES = ["Avery", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Quinn", "Reese",
               "Devon", "Hayden", "Skyler", "Rowan"]


@dataclass
class Scenario:
    scenario_id: str
    ticket_text: str
    store_id: str
    shift: dict
    workers: list
    gold_strategy: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _shift_ends_late(shift: dict) -> bool:
    return shift["end_hour"] > MINOR_LATEST_END


def ot_eligible(worker: dict, shift: dict) -> bool:
    return (
        worker["home_store"]
        and not worker["is_minor"]
        and worker["weekly_hours_scheduled"] + SHIFT_LEN_H <= OT_WEEKLY_CAP_H
        and not (worker["is_minor"] and _shift_ends_late(shift))
    )


def borrow_eligible(worker: dict, shift: dict) -> bool:
    return (
        not worker["home_store"]
        and worker["distance_km"] <= BORROW_MAX_KM
        and worker["weekly_hours_scheduled"] + SHIFT_LEN_H <= BORROW_WEEKLY_CAP_H
        and not (worker["is_minor"] and _shift_ends_late(shift))
    )


def gold_plan(shift: dict, workers: list) -> str:
    """The ground-truth rules. Generator and scorer share this function; the
    agent has to reconstruct it from the roster and the policy KB."""
    if any(ot_eligible(w, shift) for w in workers):
        return "offer_overtime"
    if any(borrow_eligible(w, shift) for w in workers):
        return "borrow_from_nearby"
    gap_frac = shift["callouts"] / shift["required_headcount"]
    if gap_frac <= REDUCED_MAX_GAP and not shift["is_peak_day"]:
        return "run_reduced"
    return "escalate_to_district"


def generate_scenarios(n: int = 30, seed: int = 11) -> list[Scenario]:
    rng = random.Random(seed)
    scenarios = []
    for i in range(n):
        sid = f"S{rng.randrange(100, 999)}"
        window_name, end_hour = rng.choice([("opening", 14), ("closing", 23)])
        required = rng.randrange(5, 11)
        callouts = rng.randrange(1, 4)
        shift = {
            "date": "2026-07-17",
            "window_name": window_name,
            "start_hour": end_hour - SHIFT_LEN_H,
            "end_hour": end_hour,
            "required_headcount": required,
            "confirmed_headcount": required - callouts,
            "callouts": callouts,
            "is_peak_day": rng.random() < 0.35,
            "role": rng.choice(["barista", "cashier", "floor", "stock"]),
        }
        workers = []
        for w in range(rng.randrange(3, 7)):
            home = rng.random() < 0.55
            workers.append({
                "worker_id": f"W{rng.randrange(1000, 9999)}",
                "name": rng.choice(FIRST_NAMES),
                "home_store": home,
                "distance_km": 0 if home else rng.randrange(4, 45),
                "weekly_hours_scheduled": rng.randrange(28, 45),
                "is_minor": rng.random() < 0.22,
                "role_match": True,
            })
        ticket = rng.choice(TICKETS).format(sid=sid, n=callouts, window_name=window_name)
        scenarios.append(
            Scenario(
                scenario_id=f"sc-{i:03d}",
                ticket_text=ticket,
                store_id=sid,
                shift=shift,
                workers=workers,
                gold_strategy=gold_plan(shift, workers),
            )
        )
    return scenarios


def save_scenarios(scenarios: list[Scenario], path: str) -> None:
    with open(path, "w") as f:
        for sc in scenarios:
            f.write(json.dumps(sc.as_dict()) + "\n")


def load_scenarios(path: str) -> list[Scenario]:
    with open(path) as f:
        return [Scenario(**json.loads(line)) for line in f]


def search_policy(query: str, top_k: int = 2) -> list[dict]:
    terms = {w.strip(".,?!").lower() for w in query.split() if len(w) > 3}
    scored = []
    for doc in POLICY_KB:
        text = (doc["title"] + " " + doc["text"]).lower()
        score = sum(1 for t in terms if t in text)
        scored.append((score, doc))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [doc for score, doc in scored[:top_k] if score > 0] or [scored[0][1]]
