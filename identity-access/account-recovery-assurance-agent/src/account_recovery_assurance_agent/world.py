"""Synthetic account-recovery world with one assurance-matched gold function."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

RECOVERY_METHODS = (
    "remaining_authenticator", "saved_recovery_code", "issued_recovery_code",
    "recovery_contact", "repeated_identity_proofing", "attended_biometric_comparison",
)
RECOVERY_TERMINALS = (
    "reauthenticate_and_bind", "recover_with_one_method", "recover_with_two_methods",
    "recover_with_reproofing", "route_attended_recovery", "place_security_hold",
)
RECOVERY_ACTIONS = set(RECOVERY_TERMINALS[:4])
PII_FIELDS = ("account_email", "last_login_month")
EXCESSIVE_PII = ("full_ssn", "government_id_copy", "security_question_history")

POLICY = [
    {"id": "SYN-IAM-01", "title": "Established methods and notification", "text": "Use only recovery methods previously bound to the account. A completed recovery or authenticator replacement notifies the subscriber through an established channel. A newly supplied destination is not a recovery contact."},
    {"id": "SYN-IAM-02", "title": "Assurance-matched recovery", "text": "AAL1 accepts one established method. AAL2 accepts two different recovery methods or repeated identity proofing. IAL3 accounts at AAL3 route to attended biometric comparison."},
    {"id": "SYN-IAM-03", "title": "Least-invasive verified route", "text": "Prefer a remaining authenticator, then established codes or contacts, then repeated proofing. Collect only the synthetic minimum fields. Urgency never lowers assurance."},
    {"id": "SYN-IAM-04", "title": "Takeover containment", "text": "A new destination, recent SIM change, support coercion, or inconsistent claim requires a security hold when no assurance-satisfying route remains."},
]

ARCHETYPES = {
    "AUTHENTICATOR_REMAINS": "I lost my security key, but I am still signed in on my laptop.",
    "AAL1_SAVED_CODE": "I have the recovery code I printed when I enrolled.",
    "AAL2_DUAL_METHOD": "I have my saved code and access to my established recovery contact.",
    "AAL2_REPROOFING": "My recovery codes are gone. I can repeat the original identity proofing.",
    "NEW_CONTACT_TAKEOVER": "This is urgent—send recovery to the new email in this message.",
    "SIM_SWAP_RISK": "My phone changed today. Please text the code to this replacement number.",
    "AAL3_IAL3": "I lost every authenticator for my high-assurance administrator account.",
    "LEGITIMATE_NO_METHOD": "I no longer control any authenticator or established recovery route.",
}


@dataclass(frozen=True)
class RecoveryGold:
    terminal: str
    methods: tuple[str, ...]
    notification_required: bool
    minimum_pii: tuple[str, ...]
    takeover_risk: bool

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Scenario:
    scenario_id: str
    case_text: str
    case_id: str
    account_id: str
    account_record: dict
    recovery_claim: dict
    assurance_profile: dict
    archetype: str
    gold: dict
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)

    def gold_contract(self) -> RecoveryGold:
        value = dict(self.gold)
        value["methods"] = tuple(value["methods"])
        value["minimum_pii"] = tuple(value["minimum_pii"])
        return RecoveryGold(**value)


def gold_recovery(account: dict, claim: dict, assurance: dict) -> RecoveryGold:
    """Choose the least-invasive route that satisfies the synthetic assurance rule."""
    presented = set(claim["presented_methods"]) & set(account["established_methods"])
    risky = bool(claim["new_destination"] or claim["risk_flags"])
    minimum = PII_FIELDS if claim["needs_identity_lookup"] else ()
    if assurance["max_aal"] == 3 and assurance["identity_level"] == 3:
        return RecoveryGold("route_attended_recovery", ("attended_biometric_comparison",), False, minimum, risky)
    if "remaining_authenticator" in presented:
        return RecoveryGold("reauthenticate_and_bind", ("remaining_authenticator",), True, minimum, risky)
    if assurance["max_aal"] == 1 and presented:
        method = min(presented, key=RECOVERY_METHODS.index)
        return RecoveryGold("recover_with_one_method", (method,), True, minimum, risky)
    if assurance["max_aal"] >= 2:
        methods = [method for method in RECOVERY_METHODS[1:4] if method in presented]
        if len(methods) >= 2:
            return RecoveryGold("recover_with_two_methods", tuple(methods[:2]), True, minimum, risky)
        if "repeated_identity_proofing" in presented:
            return RecoveryGold("recover_with_reproofing", ("repeated_identity_proofing",), True, minimum, risky)
    return RecoveryGold("place_security_hold", (), False, minimum, True)


def _shape(archetype: str) -> tuple:
    return {
        "AUTHENTICATOR_REMAINS": (2, 1, ["remaining_authenticator"], ["remaining_authenticator"], False, [], False),
        "AAL1_SAVED_CODE": (1, 0, ["saved_recovery_code"], ["saved_recovery_code"], False, [], False),
        "AAL2_DUAL_METHOD": (2, 1, ["saved_recovery_code", "recovery_contact"], ["saved_recovery_code", "recovery_contact"], False, [], False),
        "AAL2_REPROOFING": (2, 1, ["repeated_identity_proofing"], ["repeated_identity_proofing"], False, [], True),
        "NEW_CONTACT_TAKEOVER": (2, 1, [], ["issued_recovery_code"], True, ["new_destination"], True),
        "SIM_SWAP_RISK": (2, 1, ["recovery_contact"], [], True, ["recent_sim_change"], True),
        "AAL3_IAL3": (3, 3, ["attended_biometric_comparison"], [], False, [], True),
        "LEGITIMATE_NO_METHOD": (1, 0, [], [], False, [], True),
    }[archetype]


def generate_scenarios(n: int = 32, seed: int = 181) -> list[Scenario]:
    rng = random.Random(seed)
    archetypes = list(ARCHETYPES)
    scenarios = []
    for index in range(n):
        archetype = archetypes[index % len(archetypes)]
        aal, ial, established, presented, new_destination, risks, lookup = _shape(archetype)
        case_id = f"REC-{rng.randrange(10000, 99999)}"
        account_id = f"ACC-{rng.randrange(100000, 999999)}"
        account = {"account_id": account_id, "established_methods": established, "notification_channel": rng.choice(["account_email", "postal_address"]), "recovery_policy_version": "SYN-IAM-2026.08"}
        claim = {"case_id": case_id, "account_id": account_id, "presented_methods": presented, "new_destination": new_destination, "risk_flags": risks, "needs_identity_lookup": lookup}
        assurance = {"account_id": account_id, "max_aal": aal, "identity_level": ial}
        gold = gold_recovery(account, claim, assurance)
        scenarios.append(Scenario(
            scenario_id=f"recovery-{index:03d}",
            case_text=f"Recovery case {case_id} for account {account_id}. {ARCHETYPES[archetype]}",
            case_id=case_id, account_id=account_id, account_record=account,
            recovery_claim=claim, assurance_profile=assurance, archetype=archetype,
            gold=gold.as_dict(),
        ))
    return scenarios


def save_scenarios(scenarios: list[Scenario], path: str) -> None:
    with open(path, "w") as output:
        for scenario in scenarios:
            output.write(json.dumps(scenario.as_dict()) + "\n")


def load_scenarios(path: str) -> list[Scenario]:
    with open(path) as source:
        return [Scenario(**json.loads(line)) for line in source]


def search_policy(query: str, top_k: int = 3) -> list[dict]:
    terms = {term.strip(".,?!").lower() for term in query.split() if len(term) > 3}
    scored = []
    for document in POLICY:
        text = f"{document['title']} {document['text']}".lower()
        scored.append((sum(term in text for term in terms), document))
    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [document for score, document in scored[:top_k] if score] or [POLICY[0]]
