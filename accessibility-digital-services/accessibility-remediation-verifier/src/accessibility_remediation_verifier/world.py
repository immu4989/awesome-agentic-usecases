"""Synthetic accessibility-remediation world with fix-state provenance."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

DEFECTS = ("missing_alt", "keyboard_trap", "missing_label", "low_contrast", "missing_captions")
TEST_FOR = {
    "missing_alt": "image_alt_manual",
    "keyboard_trap": "keyboard_path_manual",
    "missing_label": "name_role_value_manual",
    "low_contrast": "contrast_measurement",
    "missing_captions": "caption_equivalence_manual",
}
TESTS = tuple(TEST_FOR.values())
TERMINALS = ("prepare_remediation_plan", "record_verified_fix", "route_expert_review", "record_no_defect")

POLICY = [
    {"id": "SYN-A11Y-01", "title": "Automation is evidence, not conformance", "text": "Automated scans are one input. Never claim WCAG or legal conformance from an automated result or one repaired component."},
    {"id": "SYN-A11Y-02", "title": "Test the user path", "text": "Every proposed defect needs its matching manual or measured verification step. Keyboard, accessible name, alternative text, captions, and contrast use different tests."},
    {"id": "SYN-A11Y-03", "title": "Verified fix state", "text": "A fix is verified only after the candidate is deployed and the matching post-fix tests pass. Planned, coded, deployed, and verified are different states."},
    {"id": "SYN-A11Y-04", "title": "Conflicting evidence", "text": "Conflicts between scans, source inspection, and affected-user or manual tests route expert review; do not erase the report."},
]

ARCHETYPES = {
    "ALT_TEXT": "A meaningful service image has no text alternative.",
    "KEYBOARD_TRAP": "Keyboard focus enters a dialog and cannot leave it.",
    "FORM_LABEL": "The benefits form input has no accessible name.",
    "LOW_CONTRAST": "Instruction text is hard to distinguish from its background.",
    "CAPTIONS": "The emergency briefing video has no equivalent captions.",
    "CLEAN_SCAN_MANUAL_DEFECT": "The scanner is green, but keyboard users cannot finish checkout.",
    "CONFLICTING_EVIDENCE": "The scanner flags contrast while source and manual measurement disagree.",
    "FIX_DEPLOYED": "A candidate alt-text repair is deployed and awaiting proof of fix.",
}


@dataclass(frozen=True)
class AccessibilityGold:
    terminal: str
    defects: tuple[str, ...]
    tests: tuple[str, ...]
    verified_fix: bool

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Scenario:
    scenario_id: str
    case_text: str
    case_id: str
    asset_id: str
    automated_scan: dict
    manual_evidence: dict
    source_inspection: dict
    deployment_record: dict
    archetype: str
    gold: dict
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)

    def gold_contract(self) -> AccessibilityGold:
        value = dict(self.gold)
        value["defects"] = tuple(value["defects"])
        value["tests"] = tuple(value["tests"])
        return AccessibilityGold(**value)


def gold_remediation(scan: dict, manual: dict, source: dict, deployment: dict) -> AccessibilityGold:
    defects = tuple(source["confirmed_defects"])
    if manual["evidence_conflict"]:
        disputed = tuple(dict.fromkeys([*scan["flagged_defects"], *manual["reported_defects"]]))
        return AccessibilityGold("route_expert_review", disputed, tuple(TEST_FOR[item] for item in disputed), False)
    tests = tuple(TEST_FOR[item] for item in defects)
    if not defects:
        return AccessibilityGold("record_no_defect", (), (), False)
    if deployment["candidate_fix_deployed"] and set(manual["post_fix_passed"]) == set(tests):
        return AccessibilityGold("record_verified_fix", defects, tests, True)
    return AccessibilityGold("prepare_remediation_plan", defects, tests, False)


def _shape(archetype: str) -> tuple[list[str], list[str], list[str], bool, bool, list[str]]:
    defect = {
        "ALT_TEXT": "missing_alt", "KEYBOARD_TRAP": "keyboard_trap", "FORM_LABEL": "missing_label",
        "LOW_CONTRAST": "low_contrast", "CAPTIONS": "missing_captions",
    }.get(archetype)
    if defect:
        return [defect], [defect], [defect], False, False, []
    if archetype == "CLEAN_SCAN_MANUAL_DEFECT":
        return [], ["keyboard_trap"], ["keyboard_trap"], False, False, []
    if archetype == "CONFLICTING_EVIDENCE":
        return ["low_contrast"], [], [], True, False, []
    return ["missing_alt"], ["missing_alt"], ["missing_alt"], False, True, ["image_alt_manual"]


def generate_scenarios(n: int = 32, seed: int = 191) -> list[Scenario]:
    rng = random.Random(seed)
    archetypes = list(ARCHETYPES)
    scenarios = []
    for index in range(n):
        archetype = archetypes[index % len(archetypes)]
        scan_items, reports, confirmed, conflict, deployed, passed = _shape(archetype)
        case_id = f"A11Y-{rng.randrange(10000, 99999)}"
        asset_id = f"WEB-{rng.randrange(1000, 9999)}"
        scan = {"asset_id": asset_id, "flagged_defects": scan_items, "scanner_version": "synthetic-4.2"}
        manual = {"asset_id": asset_id, "reported_defects": reports, "evidence_conflict": conflict, "post_fix_passed": passed}
        source = {"asset_id": asset_id, "confirmed_defects": confirmed, "revision": rng.randrange(20, 90)}
        deployment = {"asset_id": asset_id, "candidate_fix_deployed": deployed, "environment": "synthetic-staging"}
        gold = gold_remediation(scan, manual, source, deployment)
        scenarios.append(Scenario(
            scenario_id=f"access-{index:03d}", case_text=f"Accessibility case {case_id} for asset {asset_id}. {ARCHETYPES[archetype]}",
            case_id=case_id, asset_id=asset_id, automated_scan=scan, manual_evidence=manual,
            source_inspection=source, deployment_record=deployment, archetype=archetype, gold=gold.as_dict(),
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
