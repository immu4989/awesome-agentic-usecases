"""Synthetic world: streaming release QC flags, title/release context, production
annotations, a release-policy knowledge base, and the scenario generator whose rules
are the eval's ground truth.

Modelled on the publicly documented streaming delivery pipeline (package validation →
spec inspection → automated QC) and on US accessibility law: captions on IP-delivered
programming that aired on TV with captions are mandatory (CVAA), reinforced for
streaming-only services by NAD v. Netflix. The agent triages *already-flagged* defects;
it does not detect them.

Three traps, deliberately pointing in different directions:
- Looks broken, is fine: a flagged 22-second audio dropout that a director-intent
  annotation covers exactly — waive it.
- Looks minor, is blocking: an ~800 ms subtitle drift is cosmetic by severity, but a
  caption defect in a CVAA-covered territory can never be waived.
- Over-generalizing the caption rule: the same caption defect outside a covered
  territory is an ordinary minor defect again.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field

QUEUES = ["video-eng", "audio-eng", "timed-text", "no-defect"]
ACTIONS = [
    "waive_and_release",
    "vendor_redelivery",
    "expedite_internal_fix",
    "delay_release",
    "escalate_to_release_board",
]

VENDOR_SLA_DAYS = 5
INHOUSE_FIX_DAYS = 2
RELEASE_WINDOW_DAYS = 3

POLICY_KB = [
    {
        "id": "RQ-PREF-00",
        "title": "Release remediation preference order",
        "text": (
            "When a QC flag lands before release, prefer an in-house fix, then vendor "
            "redelivery, then delaying the release. Waive only where policy explicitly "
            "allows it. Escalate to the release board only when no compliant remediation "
            "fits the schedule."
        ),
    },
    {
        "id": "RQ-CVAA-01",
        "title": "Caption defects are a legal hard block",
        "text": (
            "Closed-caption and subtitle-for-the-deaf defects on titles releasing in "
            "CVAA-covered territories are never waived, regardless of severity, title "
            "tier, or premiere pressure. US accessibility law (CVAA) and the NAD v. "
            "Netflix consent decree require full caption coverage on streaming "
            "programming. Fix in house if the schedule allows, otherwise delay the "
            "release. This rule outranks every severity-based rule below. Outside "
            "covered territories a caption defect is treated as an ordinary defect of "
            "its severity."
        ),
    },
    {
        "id": "RQ-CREATIVE-02",
        "title": "Creative intent overrides detector flags",
        "text": (
            "A production annotation from the creative team that covers the flagged "
            "timecode range establishes the flagged behaviour as intentional — silent "
            "scenes, stylised grain, deliberate clipping. Such a flag is not a defect: "
            "record it as no-defect and release. An annotation that does not cover the "
            "flagged range does not excuse the flag."
        ),
    },
    {
        "id": "RQ-MINOR-03",
        "title": "Minor defects and the release window",
        "text": (
            f"Minor defects inside the {RELEASE_WINDOW_DAYS}-day release window ship on "
            "time and are patched post-release. Outside that window there is room to "
            "have the originating vendor redeliver a corrected package."
        ),
    },
    {
        "id": "RQ-FIX-04",
        "title": "In-house remediation capability",
        "text": (
            f"Timed-text and audio defects can be repaired in house in about "
            f"{INHOUSE_FIX_DAYS} days. Picture defects baked into the video essence "
            f"cannot be fixed in house and require vendor redelivery, which takes about "
            f"{VENDOR_SLA_DAYS} days."
        ),
    },
    {
        "id": "RQ-BOARD-05",
        "title": "Release board escalation",
        "text": (
            "A major defect that cannot be fixed in house, on a tentpole title, with too "
            "little time left for vendor redelivery, is a commercial decision: escalate "
            "to the release board rather than unilaterally delaying a marketed premiere."
        ),
    },
]

# archetype -> (component, severity, is_caption_defect, flag-text templates)
ARCHETYPES = {
    "INTENTIONAL_CREATIVE": ("audio", "major", False, [
        "QC flag on asset {aid} (title {tid}): audio dropout detected {tc}, 22s of digital silence.",
        "Asset {aid} / title {tid}: automated QC reports total audio loss across {tc}.",
    ]),
    "CAPTION_SYNC": ("timed_text", "minor", True, [
        "Asset {aid} (title {tid}): subtitle timing drift ~800ms across 14 caption events near {tc}.",
        "QC flag on {aid}, title {tid}: closed-caption events drift out of sync by roughly 0.8s around {tc}.",
    ]),
    "AUDIO_SYNC": ("audio", "major", False, [
        "Asset {aid} (title {tid}): audio/video sync offset of 120ms sustained from {tc}.",
        "Title {tid}, asset {aid}: lip-sync error detected, audio leads picture by ~4 frames at {tc}.",
    ]),
    "HDR_METADATA": ("video", "major", False, [
        "Asset {aid} (title {tid}): HDR10 mastering-display metadata missing from the essence header at {tc}.",
        "QC flag {aid} / {tid}: colour metadata in the package descriptor does not match the video essence ({tc}).",
    ]),
    "BAKED_IN_VIDEO": ("video", "major", False, [
        "Asset {aid} (title {tid}): compression artefacts baked into the picture essence at {tc}.",
        "Title {tid}, asset {aid}: dropped-frame judder visible in the delivered master around {tc}.",
    ]),
    "LOUDNESS_SPEC": ("audio", "minor", False, [
        "Asset {aid} (title {tid}): integrated loudness -21.4 LKFS, outside the -27/-23 delivery spec.",
        "QC flag on {aid} (title {tid}): dialogue loudness drifts 1.4 LU above spec after {tc}.",
    ]),
}

# 5 values against 6 archetypes: over 30 scenarios every (archetype, days) pair
# appears exactly once, so each gold branch is exercised without random luck.
DAYS_POOL = [1, 2, 3, 8, 20]

TERRITORY_SETS = [
    (["US", "CA", "UK"], True),
    (["US"], True),
    (["US", "LATAM"], True),
    (["UK", "EU"], False),
    (["APAC", "EU"], False),
]


@dataclass
class Scenario:
    scenario_id: str
    flag_text: str
    title_id: str
    asset_id: str
    title: dict
    flag: dict
    annotations: list
    archetype: str
    gold_queue: str
    gold_action: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _inhouse_fixable(component: str) -> bool:
    """Capability lives in the policy KB (RQ-FIX-04), never as a flag field —
    the agent has to retrieve it rather than read it off the record."""
    return component in ("timed_text", "audio")


def gold_triage(flag: dict, title: dict) -> tuple[str, str]:
    """Ground-truth rules, ordered — first match wins. Generator and scorer share
    this function; the agent must reconstruct it from the tools and the policy KB."""
    # 1. Creative intent covering the flagged range: not a defect at all.
    if flag["creative_intent_match"]:
        return "no-defect", "waive_and_release"

    queue = {"video": "video-eng", "audio": "audio-eng", "timed_text": "timed-text"}[
        flag["component"]
    ]
    days = title["days_to_premiere"]

    # 2. Legal hard block: caption defects in covered territories are never waived.
    if flag["is_caption_defect"] and title["cvaa_covered"]:
        return queue, (
            "expedite_internal_fix" if days >= INHOUSE_FIX_DAYS else "delay_release"
        )

    # 3. Minor defects: ship-and-patch inside the window, else vendor redelivery.
    if flag["severity"] == "minor":
        return queue, (
            "waive_and_release" if days <= RELEASE_WINDOW_DAYS else "vendor_redelivery"
        )

    # 4. Major defects.
    if _inhouse_fixable(flag["component"]) and days >= INHOUSE_FIX_DAYS:
        return queue, "expedite_internal_fix"
    if days > VENDOR_SLA_DAYS:
        return queue, "vendor_redelivery"
    if title["tier"] == "tentpole":
        return queue, "escalate_to_release_board"
    return queue, "delay_release"


def generate_scenarios(n: int = 30, seed: int = 19) -> list[Scenario]:
    rng = random.Random(seed)
    types = list(ARCHETYPES)
    scenarios = []
    for i in range(n):
        archetype = types[i % len(types)]
        component, severity, is_caption, templates = ARCHETYPES[archetype]
        days = DAYS_POOL[i % len(DAYS_POOL)]
        territories, cvaa = TERRITORY_SETS[rng.randrange(len(TERRITORY_SETS))]
        tid = f"TTL-{rng.randrange(10000, 99999)}"
        aid = f"AST-{rng.randrange(10000, 99999)}"
        start_m = rng.randrange(4, 95)
        timecode = f"00:{start_m:02d}:{rng.randrange(0, 60):02d}"

        title = {
            "title_id": tid,
            "name": rng.choice(["Northwind", "Glass Harbour", "The Long Quiet",
                                "Aster & Vale", "Sixteen Winters", "Paper Cities"]),
            "tier": "tentpole" if rng.random() < 0.35 else "standard",
            "days_to_premiere": days,
            "territories": territories,
            "cvaa_covered": cvaa,
            "marketing_locked": days <= RELEASE_WINDOW_DAYS,
        }
        creative_match = archetype == "INTENTIONAL_CREATIVE"
        flag = {
            "asset_id": aid,
            "title_id": tid,
            "component": component,
            "severity": severity,
            "is_caption_defect": is_caption,
            "timecode": timecode,
            "detector_stage": rng.choice(["package-validation", "spec-inspection",
                                          "automated-qc"]),
            "creative_intent_match": creative_match,
        }
        # Annotations: an exact-range note for genuine creative intent; for a slice of
        # the rest, a non-matching note as a distractor — "annotations exist" must not
        # be read as "waive".
        annotations = []
        if creative_match:
            annotations.append({
                "range_start": timecode,
                "range_end": f"00:{start_m:02d}:{59:02d}",
                "covers_flagged_range": True,
                "note": rng.choice([
                    "Intentional silence — director's cut, scene plays without score or room tone.",
                    "Deliberate audio blackout for dramatic effect, approved by post supervisor.",
                ]),
            })
        elif rng.random() < 0.3:
            other_m = (start_m + rng.randrange(10, 30)) % 96
            annotations.append({
                "range_start": f"00:{other_m:02d}:00",
                "range_end": f"00:{other_m:02d}:40",
                "covers_flagged_range": False,
                "note": rng.choice([
                    "Stylised film-grain pass retained by the colourist.",
                    "Handheld camera shake is intentional in this sequence.",
                ]),
            })

        gold_queue, gold_action = gold_triage(flag, title)
        scenarios.append(
            Scenario(
                scenario_id=f"sc-{i:03d}",
                flag_text=rng.choice(templates).format(aid=aid, tid=tid, tc=timecode),
                title_id=tid,
                asset_id=aid,
                title=title,
                flag=flag,
                annotations=annotations,
                archetype=archetype,
                gold_queue=gold_queue,
                gold_action=gold_action,
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
