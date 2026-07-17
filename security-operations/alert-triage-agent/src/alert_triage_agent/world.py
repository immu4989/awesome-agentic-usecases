"""Synthetic world: SOC alerts, asset/identity records, event telemetry, a
response-runbook knowledge base, and the scenario generator whose rules are the
eval's ground truth.

The alert text deliberately underdetermines the answer — and sometimes actively
misleads (a vulnerability scanner's noise reads exactly like a brute-force
attack until you check the source against the telemetry). Asset criticality,
identity privilege, and the auto-close exception clauses are only reachable
through tools.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

QUEUES = ["phishing", "malware", "credential-abuse", "false-positive"]
DISPOSITIONS = ["auto_close", "route_to_analyst", "escalate_to_incident"]

RUNBOOK_KB = [
    {
        "id": "RB-ESC-01",
        "title": "Incident escalation criteria",
        "text": (
            "Escalate to incident response when an active threat touches a crown-jewel "
            "asset or a privileged (admin) identity. Active threat means any confirmed "
            "malicious activity: malware detections, credential abuse, or phishing with "
            "user interaction. Standard assets and identities route to the analyst queue."
        ),
    },
    {
        "id": "RB-FP-02",
        "title": "Known-benign sources and auto-close",
        "text": (
            "Alerts attributable to a known-benign source (authorized vulnerability "
            "scanners, penetration-test windows, health probes) may be auto-closed as "
            "false positives. Exception: when the target is a crown-jewel asset or the "
            "identity involved is privileged, route to an analyst for confirmation "
            "instead of auto-closing."
        ),
    },
    {
        "id": "RB-CRED-03",
        "title": "Credential abuse",
        "text": (
            "Failed-login bursts followed by a success, or logins that violate travel "
            "feasibility, go to the credential-abuse queue. Verify the source is not a "
            "known-benign scanner before treating the pattern as an attack. MFA passing "
            "does not clear the alert on its own."
        ),
    },
    {
        "id": "RB-MAL-04",
        "title": "Malware and EDR detections",
        "text": (
            "Confirmed EDR detections (ransomware behavior, malicious macros) go to the "
            "malware queue. Never auto-close a confirmed detection."
        ),
    },
    {
        "id": "RB-PHISH-05",
        "title": "Phishing reports",
        "text": (
            "User-reported phishing goes to the phishing queue. Reports with a clicked "
            "link or opened attachment count as active threats."
        ),
    },
]

# alert_type -> (gold queue, alert-text templates, event profile builder)
ALERT_TYPES = {
    "PHISHING_REPORT": ("phishing", [
        "User {entity} reported a suspicious email 'Invoice overdue — action required' with a link. Reports clicking it.",
        "Phish report from {entity}: email claims to be IT asking to re-validate credentials. Attachment opened.",
    ]),
    "MACRO_MALWARE": ("malware", [
        "EDR flagged a macro-enabled document spawning PowerShell on host {entity}.",
        "Office process on {entity} wrote an executable to startup after opening 'PO_4471.docm'.",
    ]),
    "RANSOM_BEHAVIOR": ("malware", [
        "Mass file-rename with high entropy detected on {entity}. Shadow-copy deletion attempted.",
        "EDR: encryption-like burst I/O on {entity}, suspicious service installed minutes earlier.",
    ]),
    "BRUTE_FORCE_SUCCESS": ("credential-abuse", [
        "412 failed logins for {entity} in 20 minutes followed by a successful login.",
        "Password-spray pattern hit {entity}; last attempt succeeded from an unfamiliar ASN.",
    ]),
    "IMPOSSIBLE_TRAVEL": ("credential-abuse", [
        "{entity} authenticated from Frankfurt 40 minutes after a login from Dallas.",
        "Geo-velocity violation for {entity}: two logins 8,000 km apart within an hour.",
    ]),
    "SCANNER_NOISE": ("false-positive", [
        "2,100 failed logins against {entity} from a single internal IP overnight.",
        "Repeated SSH probes hitting {entity} from 10.20.8.14 — looks like a brute-force attempt.",
    ]),
}


@dataclass
class Scenario:
    scenario_id: str
    alert_text: str
    entity_id: str
    asset: dict
    events: dict
    alert_type: str
    gold_queue: str
    gold_disposition: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def gold_triage(alert_type: str, asset: dict, events: dict) -> tuple[str, str]:
    """Ground-truth rules; generator and scorer share this function."""
    high_value = asset["criticality"] == "crown_jewel" or asset["privilege"] == "admin"
    if events["known_benign_source"]:
        return "false-positive", ("route_to_analyst" if high_value else "auto_close")
    queue = ALERT_TYPES[alert_type][0]
    return queue, ("escalate_to_incident" if high_value else "route_to_analyst")


def generate_scenarios(n: int = 30, seed: int = 13) -> list[Scenario]:
    rng = random.Random(seed)
    types = list(ALERT_TYPES)
    scenarios = []
    for i in range(n):
        alert_type = types[i % len(types)]
        is_host = alert_type in ("MACRO_MALWARE", "RANSOM_BEHAVIOR", "SCANNER_NOISE")
        entity = (f"HST-{rng.randrange(1000, 9999)}" if is_host
                  else f"u.{rng.choice(['jsmith', 'mgarcia', 'twong', 'apatel', 'kdiaz', 'lnovak'])}{rng.randrange(10, 99)}")
        asset = {
            "entity_id": entity,
            "criticality": "crown_jewel" if rng.random() < 0.28 else "standard",
            "privilege": "admin" if (not is_host and rng.random() < 0.3) else "standard",
            "owner_dept": rng.choice(["finance", "engineering", "sales", "hr", "it-ops"]),
            "tags": [],
        }
        events = {
            "failed_logins_24h": rng.randrange(300, 3000) if alert_type in ("BRUTE_FORCE_SUCCESS", "SCANNER_NOISE") else rng.randrange(0, 6),
            "success_after_failures": alert_type == "BRUTE_FORCE_SUCCESS",
            "new_geo_login": alert_type in ("BRUTE_FORCE_SUCCESS", "IMPOSSIBLE_TRAVEL"),
            "edr_detection": {"MACRO_MALWARE": "W97M.Downloader", "RANSOM_BEHAVIOR": "Behavior:Ransom.FileCrypt"}.get(alert_type),
            "known_benign_source": alert_type == "SCANNER_NOISE",
            "source_note": ("source IP is the authorized Nessus scanner pool (change CHG-88213)"
                            if alert_type == "SCANNER_NOISE" else "no allowlisted source match"),
            "mfa_passed": rng.random() < 0.5,
        }
        text = rng.choice(ALERT_TYPES[alert_type][1]).format(entity=entity)
        queue, disposition = gold_triage(alert_type, asset, events)
        scenarios.append(
            Scenario(
                scenario_id=f"sc-{i:03d}",
                alert_text=text,
                entity_id=entity,
                asset=asset,
                events=events,
                alert_type=alert_type,
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


def search_runbook(query: str, top_k: int = 2) -> list[dict]:
    terms = {w.strip(".,?!").lower() for w in query.split() if len(w) > 3}
    scored = []
    for doc in RUNBOOK_KB:
        text = (doc["title"] + " " + doc["text"]).lower()
        score = sum(1 for t in terms if t in text)
        scored.append((score, doc))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [doc for score, doc in scored[:top_k] if score > 0] or [scored[0][1]]
