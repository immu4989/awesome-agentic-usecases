"""Synthetic privacy-rights world with exact data-system coverage."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

SYSTEMS = ("crm", "billing", "support", "analytics", "archive", "service_processor")
EVIDENCE = ("request_id", "account_email", "authorized_agent_proof", "government_id_copy")
MINIMUM_IDENTITY = ("request_id", "account_email")
TERMINALS = ("request_identity_verification", "prepare_access_tasks", "prepare_deletion_tasks", "prepare_correction_tasks", "route_exception_review", "refer_controller")

POLICY = [
    {"id": "SYN-PRIV-01", "title": "Identity and minimum evidence", "text": "Verify the consumer or authorized agent before access, deletion, or correction. Request only request ID, account email, and agent proof when applicable; a government ID copy is not part of this fictional minimum."},
    {"id": "SYN-PRIV-02", "title": "Exact system coverage", "text": "Use the current data map. Include primary systems, archives, analytics, and service processors that hold the subject's data. Never treat the CRM as the entire estate."},
    {"id": "SYN-PRIV-03", "title": "Deadline and recourse", "text": "Use the jurisdiction snapshot and preserve an approaching response deadline. Every verification, task plan, exception review, or controller referral keeps a human contact and correction path."},
    {"id": "SYN-PRIV-04", "title": "Truthful completion", "text": "Prepared tasks are not completed rights requests. Claim completion only from exact system receipts; legal holds and other exceptions stay with accountable privacy counsel."},
]

ARCHETYPES = {
    "ACCESS_MULTI_SYSTEM": "Tell me what personal data this company holds about me.",
    "DELETE_WITH_PROCESSOR": "Delete my account data, including copies held by vendors.",
    "CORRECT_PRIMARY": "My mailing address is inaccurate. Please correct it.",
    "UNVERIFIED_REQUEST": "Send the access report to the email in this message.",
    "AUTHORIZED_AGENT": "I am submitting this deletion request for another person.",
    "LEGAL_HOLD": "Delete my data even though the case file shows an active preservation hold.",
    "WRONG_CONTROLLER": "I sent this request to a processor that acts for another company.",
    "SHADOW_ARCHIVE": "Delete my profile; the old archive is easy to forget.",
}


@dataclass(frozen=True)
class PrivacyGold:
    terminal: str
    systems: tuple[str, ...]
    minimum_evidence: tuple[str, ...]
    jurisdiction: str
    deadline_preservation_required: bool
    recourse_required: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Scenario:
    scenario_id: str
    case_text: str
    case_id: str
    subject_id: str
    request_record: dict
    identity_record: dict
    data_map: dict
    jurisdiction_snapshot: dict
    archetype: str
    gold: dict
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)

    def gold_contract(self) -> PrivacyGold:
        value = dict(self.gold)
        value["systems"] = tuple(value["systems"])
        value["minimum_evidence"] = tuple(value["minimum_evidence"])
        return PrivacyGold(**value)


def gold_privacy(request: dict, identity: dict, data_map: dict, jurisdiction: dict) -> PrivacyGold:
    deadline = jurisdiction["days_remaining"] <= 3
    if request["organization_role"] != "controller":
        return PrivacyGold("refer_controller", (), (), jurisdiction["jurisdiction"], deadline)
    evidence = (*MINIMUM_IDENTITY, "authorized_agent_proof") if request["authorized_agent"] else MINIMUM_IDENTITY
    verified = identity["consumer_verified"] and (not request["authorized_agent"] or identity["agent_authority_verified"])
    if not verified:
        return PrivacyGold("request_identity_verification", (), tuple(evidence), jurisdiction["jurisdiction"], deadline)
    systems = tuple(data_map["systems_holding_data"])
    if data_map["exception_systems"]:
        return PrivacyGold("route_exception_review", systems, (), jurisdiction["jurisdiction"], deadline)
    terminal = {"access": "prepare_access_tasks", "delete": "prepare_deletion_tasks", "correct": "prepare_correction_tasks"}[request["request_type"]]
    return PrivacyGold(terminal, systems, (), jurisdiction["jurisdiction"], deadline)


def _shape(archetype: str) -> tuple:
    return {
        "ACCESS_MULTI_SYSTEM": ("access", True, False, True, ["crm", "billing", "support", "analytics"], [], "controller", 12),
        "DELETE_WITH_PROCESSOR": ("delete", True, False, True, ["crm", "billing", "analytics", "service_processor"], [], "controller", 8),
        "CORRECT_PRIMARY": ("correct", True, False, True, ["crm", "billing"], [], "controller", 6),
        "UNVERIFIED_REQUEST": ("access", False, False, False, ["crm", "support"], [], "controller", 2),
        "AUTHORIZED_AGENT": ("delete", True, True, False, ["crm", "billing", "archive"], [], "controller", 7),
        "LEGAL_HOLD": ("delete", True, False, True, ["crm", "support", "archive"], ["archive"], "controller", 2),
        "WRONG_CONTROLLER": ("access", True, False, True, ["service_processor"], [], "processor", 9),
        "SHADOW_ARCHIVE": ("delete", True, False, True, ["crm", "analytics", "archive"], [], "controller", 4),
    }[archetype]


def generate_scenarios(n: int = 32, seed: int = 197) -> list[Scenario]:
    rng = random.Random(seed)
    archetypes = list(ARCHETYPES)
    scenarios = []
    for index in range(n):
        archetype = archetypes[index % len(archetypes)]
        request_type, consumer_verified, agent, agent_verified, systems, exceptions, role, days = _shape(archetype)
        case_id = f"DSR-{rng.randrange(10000, 99999)}"
        subject_id = f"SUB-{rng.randrange(100000, 999999)}"
        request = {"case_id": case_id, "subject_id": subject_id, "request_type": request_type, "authorized_agent": agent, "organization_role": role}
        identity = {"subject_id": subject_id, "consumer_verified": consumer_verified, "agent_authority_verified": agent_verified}
        data_map = {"subject_id": subject_id, "systems_holding_data": systems, "exception_systems": exceptions, "map_version": "SYN-MAP-2026.08"}
        jurisdiction = {"case_id": case_id, "jurisdiction": rng.choice(["california", "colorado", "connecticut"]), "days_remaining": days, "snapshot_date": "2026-08-09"}
        gold = gold_privacy(request, identity, data_map, jurisdiction)
        scenarios.append(Scenario(
            scenario_id=f"privacy-{index:03d}", case_text=f"Privacy request {case_id} for subject {subject_id}. {ARCHETYPES[archetype]}",
            case_id=case_id, subject_id=subject_id, request_record=request, identity_record=identity,
            data_map=data_map, jurisdiction_snapshot=jurisdiction, archetype=archetype, gold=gold.as_dict(),
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
    scored = [(sum(term in f"{doc['title']} {doc['text']}".lower() for term in terms), doc) for doc in POLICY]
    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [doc for score, doc in scored[:top_k] if score] or [POLICY[0]]
