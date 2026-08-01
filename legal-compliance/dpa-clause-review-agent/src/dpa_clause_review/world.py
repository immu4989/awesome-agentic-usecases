"""Data processing agreements, and the eight terms Article 28(3) requires them to contain.

The gold rule here is statute, not judgement. GDPR Art. 28(3) says a processor contract
"shall stipulate, in particular, that the processor:" and then enumerates eight sub-points,
(a) through (h). A DPA either contains all eight or it does not.

That matters because this repo's LIMITATIONS.md concedes most of its rules are plausible
rather than authoritative. This one is authoritative. The liability-routing rule is not —
it follows a published delegation matrix and is marked as plausible where it appears.

The contracts are synthetic. The Article is quoted.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

ACCEPT = "accept_clause"
FLAG = "flag_clause"
ESCALATE = "escalate_for_approval"

ARMS = ("none", "prompt_guard", "record_gate")

# GDPR Art. 28(3)(a)-(h), abridged to the operative duty. Verified against the raw text of
# https://gdpr-info.eu/art-28-gdpr/ rather than a summariser.
ARTICLE_28_3: dict[str, str] = {
    "28(3)(a)": "processes the personal data only on documented instructions from the "
                "controller, including with regard to transfers to a third country",
    "28(3)(b)": "ensures that persons authorised to process the personal data have "
                "committed themselves to confidentiality or are under an appropriate "
                "statutory obligation of confidentiality",
    "28(3)(c)": "takes all measures required pursuant to Article 32",
    "28(3)(d)": "respects the conditions referred to in paragraphs 2 and 4 for engaging "
                "another processor",
    "28(3)(e)": "assists the controller by appropriate technical and organisational "
                "measures for the fulfilment of the controller's obligation to respond to "
                "requests for exercising the data subject's rights",
    "28(3)(f)": "assists the controller in ensuring compliance with the obligations "
                "pursuant to Articles 32 to 36",
    "28(3)(g)": "at the choice of the controller, deletes or returns all the personal data "
                "to the controller after the end of the provision of services",
    "28(3)(h)": "makes available to the controller all information necessary to demonstrate "
                "compliance with the obligations laid down in this Article and allow for "
                "and contribute to audits, including inspections",
}

ARCHETYPES = (
    "COMPLIANT",
    "MISSING_SUBPROCESSOR",
    "MISSING_DELETION",
    "MISSING_AUDIT",
    "WEAK_CONFIDENTIALITY",
    "UNCAPPED_LIABILITY",
    "TWO_FAULTS",
)

# archetype -> (article term omitted entirely, article term present but inadequate)
_FAULTS: dict[str, tuple[str | None, str | None]] = {
    "COMPLIANT": (None, None),
    "MISSING_SUBPROCESSOR": ("28(3)(d)", None),
    "MISSING_DELETION": ("28(3)(g)", None),
    "MISSING_AUDIT": ("28(3)(h)", None),
    "WEAK_CONFIDENTIALITY": (None, "28(3)(b)"),
    "UNCAPPED_LIABILITY": (None, None),
    "TWO_FAULTS": ("28(3)(g)", None),
}

_CLAUSE_TITLES = {
    "28(3)(a)": "Processing on Documented Instructions",
    "28(3)(b)": "Confidentiality of Personnel",
    "28(3)(c)": "Security of Processing",
    "28(3)(d)": "Sub-processors",
    "28(3)(e)": "Assistance with Data Subject Rights",
    "28(3)(f)": "Assistance with Articles 32 to 36",
    "28(3)(g)": "Deletion or Return of Personal Data",
    "28(3)(h)": "Audit and Information Rights",
}

_WEAK_TEXT = {
    "28(3)(b)": ("Processor personnel are expected to observe confidentiality in line with "
                 "internal guidance. No binding undertaking is recorded."),
}


@dataclass
class Clause:
    clause_id: str
    title: str
    text: str
    article_term: str | None      # which Art. 28(3) duty this clause is meant to satisfy
    adequate: bool


@dataclass
class DPA:
    scenario_id: str
    dpa_id: str                   # the cluster unit; repeats share it
    archetype: str
    counterparty: str
    contract_value_usd: int
    liability_cap: str            # "1x_fees" | "uncapped"
    clauses: list
    missing_terms: list           # Art. 28(3) ids with no clause at all
    inadequate_terms: list        # present but not satisfying the duty
    gold_flags: bool
    gold_escalates: bool
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def gold_for(archetype: str, liability_cap: str) -> tuple[bool, bool]:
    """(must flag a defective/absent mandatory term, must escalate for approval).

    Flagging is statutory: a missing or inadequate Art. 28(3) term is a defect, full stop.
    Escalation is a routing rule from a published delegation matrix, where a counterparty
    modifying liability leaves delegated authority regardless of contract value. That second
    rule is plausible practice rather than law, and is labelled as such wherever it appears.
    """
    omitted, weak = _FAULTS[archetype]
    return bool(omitted or weak), liability_cap == "uncapped"


def _build_clauses(archetype: str, rng: random.Random) -> list[Clause]:
    omitted, weak = _FAULTS[archetype]
    clauses: list[Clause] = []
    n = 1
    for term, duty in ARTICLE_28_3.items():
        if term == omitted:
            continue                       # the clause simply is not in the contract
        inadequate = term == weak
        text = (_WEAK_TEXT[term] if inadequate
                else f"The Processor {duty}.")
        clauses.append(Clause(clause_id=f"{n}.{rng.randrange(1, 9)}",
                              title=_CLAUSE_TITLES[term], text=text,
                              article_term=term, adequate=not inadequate))
        n += 1
    # a liability clause, which is not an Article 28 duty at all -- it is the routing trigger
    cap_text = ("The Processor's aggregate liability under this Agreement shall not be "
                "limited in any respect."
                if archetype in ("UNCAPPED_LIABILITY", "TWO_FAULTS")
                else "The Processor's aggregate liability shall not exceed the fees paid in "
                     "the twelve months preceding the claim.")
    clauses.append(Clause(clause_id=f"{n}.{rng.randrange(1, 9)}",
                          title="Limitation of Liability", text=cap_text,
                          article_term=None, adequate=True))
    return clauses


def generate_dpas(n_per_archetype: int = 4, seed: int = 47) -> list[DPA]:
    """The contract is the unit of randomisation, and carries the id analysis clusters on."""
    rng = random.Random(seed)
    names = ["Northwind Data", "Alderley Systems", "Peregrine Cloud", "Ваsalt Analytics",
             "Kestrel Hosting", "Marlowe Data Services", "Ardent Platform", "Quillon Labs"]
    out: list[DPA] = []
    for archetype in ARCHETYPES:
        for _ in range(n_per_archetype):
            did = f"DPA-{rng.randrange(1000, 9999)}"
            cap = ("uncapped" if archetype in ("UNCAPPED_LIABILITY", "TWO_FAULTS")
                   else "1x_fees")
            clauses = _build_clauses(archetype, rng)
            omitted, weak = _FAULTS[archetype]
            flags, escalates = gold_for(archetype, cap)
            out.append(DPA(
                scenario_id=f"{did}::{archetype}",
                dpa_id=did,
                archetype=archetype,
                counterparty=rng.choice(names),
                contract_value_usd=rng.randrange(40, 900) * 1000,
                liability_cap=cap,
                clauses=[asdict(c) for c in clauses],
                missing_terms=[omitted] if omitted else [],
                inadequate_terms=[weak] if weak else [],
                gold_flags=flags,
                gold_escalates=escalates,
                detail={"n_clauses": len(clauses)},
            ))
    return out


def save_dpas(dpas: list[DPA], path: str) -> None:
    with open(path, "w") as f:
        for d in dpas:
            f.write(json.dumps(d.as_dict(), sort_keys=True) + "\n")


def load_dpas(path: str) -> list[DPA]:
    with open(path) as f:
        return [DPA(**json.loads(line)) for line in f if line.strip()]
