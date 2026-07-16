"""Synthetic world: shipments, carrier feeds, a policy knowledge base, and the
scenario generator whose own rules are the eval's ground truth.

The ticket text a scenario shows the agent deliberately underdetermines the
answer — the exception code, shipment value, customer tier, and escalation
thresholds are only reachable through tools. Customer complaints are sometimes
wrong about what actually happened (they say "lost" when the shipment is in a
customs hold), which is exactly why triage-by-ticket-text-alone fails.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

QUEUES = [
    "address-correction",
    "customs-clearance",
    "carrier-claims",
    "returns",
    "customer-notification",
]
ACTIONS = ["auto_resolve", "route_to_queue", "escalate_to_human"]

CARRIERS = ["VELOX", "NORTHFREIGHT", "PARCELINE"]
TIERS = ["standard", "standard", "standard", "gold", "gold", "platinum"]

ESCALATION_VALUE_USD = 2000
ESCALATION_PLATINUM_SLA_H = 24

POLICY_KB = [
    {
        "id": "POL-ESC-01",
        "title": "Escalation thresholds",
        "text": (
            "Escalate to a human operator when the declared shipment value exceeds "
            f"${ESCALATION_VALUE_USD}, or when the customer is Platinum tier and fewer than "
            f"{ESCALATION_PLATINUM_SLA_H} hours remain on the delivery SLA. Escalation "
            "overrides any automation eligibility."
        ),
    },
    {
        "id": "POL-ADDR-02",
        "title": "Address correction automation",
        "text": (
            "Invalid-address exceptions with a validated candidate address from the "
            "address service may be auto-resolved by applying the candidate. Without a "
            "validated candidate, route to the address-correction queue for manual research."
        ),
    },
    {
        "id": "POL-CUST-03",
        "title": "Customs holds",
        "text": (
            "Customs holds always route to the customs-clearance queue; brokers own the "
            "resolution. Never auto-resolve a customs hold."
        ),
    },
    {
        "id": "POL-CLM-04",
        "title": "Damage and loss claims",
        "text": (
            "Confirmed damage or loss in transit routes to carrier-claims. A claim "
            "requires the carrier's scan history as evidence."
        ),
    },
    {
        "id": "POL-WX-05",
        "title": "Weather delays",
        "text": (
            "Weather delays are informational: send the customer a proactive notification "
            "with the revised ETA. These may be auto-resolved via the customer-notification "
            "workflow."
        ),
    },
    {
        "id": "POL-RET-06",
        "title": "Refused deliveries",
        "text": (
            "Deliveries refused by the recipient route to the returns queue to initiate "
            "return-to-sender and refund review."
        ),
    },
]

# exception_code -> (gold queue, customer complaint templates)
EXCEPTIONS = {
    "ADDRESS_INVALID": (
        "address-correction",
        [
            "Package {tid} hasn't moved in days — the tracking page just says 'delivery exception'. I need this resolved.",
            "Courier said they couldn't find the address for {tid}?? I've received packages here before.",
        ],
    ),
    "CUSTOMS_HOLD": (
        "customs-clearance",
        [
            "My order {tid} seems completely lost, no updates for a week. Where is it?",
            "Shipment {tid} is stuck, tracking says 'held for processing'. What is going on?",
        ],
    ),
    "DAMAGED_IN_TRANSIT": (
        "carrier-claims",
        [
            "I got a notification that {tid} had an incident at the sort facility. Is my order OK?",
            "Tracking for {tid} says 'exception — contact support'. This was a gift, please help.",
        ],
    ),
    "LOST_IN_TRANSIT": (
        "carrier-claims",
        [
            "Order {tid} shows no scans since it left the origin hub two weeks ago. I think it's lost.",
            "Where is {tid}? The last update was 12 days ago. I want a refund or a replacement.",
        ],
    ),
    "DELIVERY_REFUSED": (
        "returns",
        [
            "The recipient for {tid} says they never ordered this and turned the driver away.",
            "Delivery attempt for {tid} failed — front desk refused the parcel, sender unknown to them.",
        ],
    ),
    "WEATHER_DELAY": (
        "customer-notification",
        [
            "Is {tid} delayed? I saw there was a storm along the route. Need it by Friday.",
            "Tracking for {tid} says 'delayed'. No other info. When will it arrive?",
        ],
    ),
}

CARRIER_DISPOSITIONS = {
    "ADDRESS_INVALID": "Delivery attempted; address not found. Held at destination facility pending correction.",
    "CUSTOMS_HOLD": "Held by customs at port of entry. Awaiting broker documentation.",
    "DAMAGED_IN_TRANSIT": "Package reported damaged during sortation. Contents inspection filed.",
    "LOST_IN_TRANSIT": "No scan activity for 10+ days. Trace initiated; presumed lost.",
    "DELIVERY_REFUSED": "Delivery refused by recipient. Package returning to origin facility.",
    "WEATHER_DELAY": "Ground transport suspended due to severe weather. ETA revised +72h.",
}


@dataclass
class Scenario:
    scenario_id: str
    ticket_text: str
    tracking_id: str
    shipment: dict
    carrier_events: list
    gold_queue: str
    gold_action: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def gold_triage(shipment: dict) -> tuple[str, str]:
    """The ground-truth rules. The generator and the scorer share this function;
    the agent has to reconstruct it from tools and the policy KB."""
    code = shipment["exception_code"]
    queue = EXCEPTIONS[code][0]
    if shipment["value_usd"] > ESCALATION_VALUE_USD or (
        shipment["customer_tier"] == "platinum"
        and shipment["sla_hours_remaining"] < ESCALATION_PLATINUM_SLA_H
    ):
        return queue, "escalate_to_human"
    if code == "ADDRESS_INVALID" and shipment["has_validated_address_candidate"]:
        return queue, "auto_resolve"
    if code == "WEATHER_DELAY":
        return queue, "auto_resolve"
    return queue, "route_to_queue"


def generate_scenarios(n: int = 30, seed: int = 7) -> list[Scenario]:
    rng = random.Random(seed)
    codes = list(EXCEPTIONS)
    scenarios = []
    for i in range(n):
        code = codes[i % len(codes)]  # balanced across exception types
        tid = f"{rng.choice(CARRIERS)[:2]}{rng.randrange(10**9, 10**10)}"
        tier = rng.choice(TIERS)
        # long-tailed values; ~20% above the escalation threshold
        value = round(rng.lognormvariate(5.6, 1.1), 2)
        sla = rng.randrange(4, 96)
        shipment = {
            "tracking_id": tid,
            "carrier": rng.choice(CARRIERS),
            "origin": rng.choice(["Memphis, TN", "Shenzhen, CN", "Rotterdam, NL", "Louisville, KY"]),
            "destination": rng.choice(["Austin, TX", "Newark, NJ", "Seattle, WA", "Miami, FL"]),
            "value_usd": value,
            "customer_tier": tier,
            "sla_hours_remaining": sla,
            "exception_code": code,
            "has_validated_address_candidate": rng.random() < 0.5,
        }
        events = [
            {"ts": f"2026-07-{rng.randrange(1, 10):02d}T08:00:00Z", "scan": "Picked up at origin"},
            {"ts": f"2026-07-{rng.randrange(10, 14):02d}T14:00:00Z", "scan": "Departed origin hub"},
            {
                "ts": f"2026-07-{rng.randrange(14, 16):02d}T09:30:00Z",
                "scan": "EXCEPTION",
                "disposition": CARRIER_DISPOSITIONS[code],
            },
        ]
        ticket = rng.choice(EXCEPTIONS[code][1]).format(tid=tid)
        queue, action = gold_triage(shipment)
        scenarios.append(
            Scenario(
                scenario_id=f"sc-{i:03d}",
                ticket_text=ticket,
                tracking_id=tid,
                shipment=shipment,
                carrier_events=events,
                gold_queue=queue,
                gold_action=action,
            )
        )
    return scenarios


def save_scenarios(scenarios: list[Scenario], path: str) -> None:
    with open(path, "w") as f:
        for sc in scenarios:
            f.write(json.dumps(sc.as_dict()) + "\n")


def load_scenarios(path: str) -> list[Scenario]:
    scenarios = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            scenarios.append(Scenario(**d))
    return scenarios


def search_policy(query: str, top_k: int = 2) -> list[dict]:
    """Keyword-overlap retrieval over the policy KB. Deliberately simple — the
    point is that the thresholds live here, not in the agent's prompt."""
    terms = {w.strip(".,?!").lower() for w in query.split() if len(w) > 3}
    scored = []
    for doc in POLICY_KB:
        text = (doc["title"] + " " + doc["text"]).lower()
        score = sum(1 for t in terms if t in text)
        scored.append((score, doc))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [doc for score, doc in scored[:top_k] if score > 0] or [scored[0][1]]
