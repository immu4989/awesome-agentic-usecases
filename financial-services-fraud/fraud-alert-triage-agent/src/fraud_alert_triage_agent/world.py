"""Synthetic world: transaction-fraud alerts, customer records, transaction
telemetry, a fraud-policy knowledge base, and the scenario generator whose
rules are the eval's ground truth.

Two deceptions, in opposite directions:
- A foreign high-value charge on a new device reads as card fraud — but the
  customer filed a travel notice that matches, so it is benign.
- An authorized push payment rides the customer's own device and login, so
  every classic fraud signal is absent — but the beneficiary is a freshly added
  known scam mule, so it is active fraud.

Customer segment (private banking), the regulatory review threshold, and the
auto-action exception clauses are only reachable through tools.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

QUEUES = ["card-fraud", "account-takeover", "app-scam", "false-positive"]
DISPOSITIONS = ["allow", "hold_for_review", "block_and_notify", "escalate_to_fraud_ops"]

REG_REVIEW_THRESHOLD_USD = 10000

POLICY_KB = [
    {
        "id": "FP-ESC-01",
        "title": "Fraud-ops escalation criteria",
        "text": (
            "Escalate to the fraud-operations team when active fraud touches a "
            "high-value customer: private-banking segment, or any transaction above "
            f"the ${REG_REVIEW_THRESHOLD_USD} regulatory review threshold. Standard "
            "customers with confirmed fraud are blocked and notified automatically."
        ),
    },
    {
        "id": "FP-FP-02",
        "title": "Benign activity and auto-release",
        "text": (
            "Alerts explained by a benign source — a travel notice on file matching "
            "the transaction location, or a beneficiary on the customer's verified "
            "allowlist — may be auto-released (allow). Exception: private-banking "
            "customers and transactions above the regulatory review threshold are "
            "held for manual review even when benign, never auto-released."
        ),
    },
    {
        "id": "FP-CARD-03",
        "title": "Card fraud",
        "text": (
            "Card-not-present charges from a new device in an unexpected geography go "
            "to the card-fraud queue. Check for a matching travel notice before "
            "treating the geography as unexpected."
        ),
    },
    {
        "id": "FP-ATO-04",
        "title": "Account takeover",
        "text": (
            "A credential reset or new-device login followed by a new payee and an "
            "outbound transfer indicates account takeover. Route to the "
            "account-takeover queue."
        ),
    },
    {
        "id": "FP-APP-05",
        "title": "Authorized push payment scams",
        "text": (
            "In an APP scam the customer authorizes the payment themselves, so device, "
            "login, and velocity look normal. The signal is the beneficiary: a newly "
            "added account matching a known mule pattern. Do not clear an APP-scam "
            "alert just because the device and login are trusted — route to app-scam."
        ),
    },
]

# fraud_type -> (gold queue, alert-text templates)
FRAUD_TYPES = {
    "CARD_FRAUD": ("card-fraud", [
        "Card-not-present charge ${amt} at an overseas merchant on a device first seen today for {entity}.",
        "${amt} online purchase for {entity} from a new device, billing geo far from home region.",
    ]),
    "ACCOUNT_TAKEOVER": ("account-takeover", [
        "Password reset + new-device login for {entity}, then a new payee added and a ${amt} transfer queued.",
        "{entity} logged in from an unrecognized device after a credential reset and initiated a ${amt} outbound transfer.",
    ]),
    "APP_SCAM": ("app-scam", [
        "{entity} authorized a ${amt} transfer from their usual device to a beneficiary added 6 minutes ago.",
        "Customer-approved ${amt} payment for {entity}; login and device trusted, payee is brand new.",
    ]),
    "TRAVEL_BENIGN": ("false-positive", [
        "Foreign ${amt} charge on a new device for {entity} — flagged as possible card fraud.",
        "${amt} charge for {entity} from an overseas merchant, unfamiliar device. Possible fraud?",
    ]),
    "ALLOWLIST_BENIGN": ("false-positive", [
        "Large ${amt} transfer from {entity} flagged by the amount rule.",
        "${amt} payment for {entity} tripped the high-value alert.",
    ]),
}


@dataclass
class Scenario:
    scenario_id: str
    alert_text: str
    entity_id: str
    customer: dict
    transaction: dict
    fraud_type: str
    gold_queue: str
    gold_disposition: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def gold_triage(fraud_type: str, customer: dict, transaction: dict) -> tuple[str, str]:
    """Ground-truth rules; generator and scorer share this function."""
    high_value = (
        customer["segment"] == "private_banking"
        or transaction["amount_usd"] > REG_REVIEW_THRESHOLD_USD
    )
    if transaction["known_benign_source"]:
        return "false-positive", ("hold_for_review" if high_value else "allow")
    queue = FRAUD_TYPES[fraud_type][0]
    return queue, ("escalate_to_fraud_ops" if high_value else "block_and_notify")


def generate_scenarios(n: int = 30, seed: int = 17) -> list[Scenario]:
    rng = random.Random(seed)
    types = list(FRAUD_TYPES)
    scenarios = []
    for i in range(n):
        fraud_type = types[i % len(types)]
        entity = f"acct-{rng.randrange(10**7, 10**8)}"
        # ~22% private banking; amounts long-tailed, ~25% above the reg threshold
        segment = "private_banking" if rng.random() < 0.22 else "retail"
        amount = round(rng.lognormvariate(7.4, 1.15), 2)
        benign = fraud_type in ("TRAVEL_BENIGN", "ALLOWLIST_BENIGN")
        customer = {
            "entity_id": entity,
            "segment": segment,
            "tenure_months": rng.randrange(2, 240),
            "prior_disputes": rng.randrange(0, 4),
            "home_region": rng.choice(["US-NE", "US-W", "UK", "EU", "APAC"]),
        }
        transaction = {
            "amount_usd": amount,
            "channel": "card_not_present" if fraud_type in ("CARD_FRAUD", "TRAVEL_BENIGN") else "transfer",
            "new_device": fraud_type in ("CARD_FRAUD", "ACCOUNT_TAKEOVER", "TRAVEL_BENIGN"),
            "foreign_geo": fraud_type in ("CARD_FRAUD", "TRAVEL_BENIGN"),
            "new_payee": fraud_type in ("ACCOUNT_TAKEOVER", "APP_SCAM"),
            "credential_reset": fraud_type == "ACCOUNT_TAKEOVER",
            "beneficiary_mule_match": fraud_type == "APP_SCAM",
            "customer_authorized": fraud_type == "APP_SCAM",
            "travel_notice_matches": fraud_type == "TRAVEL_BENIGN",
            "beneficiary_allowlisted": fraud_type == "ALLOWLIST_BENIGN",
            "known_benign_source": benign,
            "source_note": {
                "TRAVEL_BENIGN": "travel notice on file matches the charge geography and dates",
                "ALLOWLIST_BENIGN": "beneficiary is on the customer's verified allowlist (32 prior payments)",
            }.get(fraud_type, "no benign explanation on file"),
        }
        text = rng.choice(FRAUD_TYPES[fraud_type][1]).format(
            entity=entity, amt=f"{amount:,.0f}"
        )
        queue, disposition = gold_triage(fraud_type, customer, transaction)
        scenarios.append(
            Scenario(
                scenario_id=f"sc-{i:03d}",
                alert_text=text,
                entity_id=entity,
                customer=customer,
                transaction=transaction,
                fraud_type=fraud_type,
                gold_queue=queue,
                gold_disposition=disposition,
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
