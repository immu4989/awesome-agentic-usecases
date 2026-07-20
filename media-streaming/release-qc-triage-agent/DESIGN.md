# Build spec: release-qc-triage-agent

Locked design for the Media & Streaming vertical (industry row 16, new). Execute
mechanically on the Wave-2/3 template (fraud-alert-triage-agent is the closest
skeleton: two decision axes, queue + action). Package `release_qc_agent`, CLI
`release-qc-agent`, directory `media-streaming/release-qc-triage-agent/`, seed **19**
(continuing 7/11/13/17).

## Problem framing (README lead)

Automated QC flags an issue on a delivered streaming asset before release. The agent
triages the *already-flagged* defect — it does not detect defects. Decisions: which
engineering queue, and what happens to the release. Grounding: Netflix's documented
3-stage inspection pipeline (Photon → IaaS → Automated QC), CVAA + NAD v. Netflix
caption mandates. Cite both in README (links in the 2026-07-20 conversation / memory).

## Decision axes

- queue: `video-eng` | `audio-eng` | `timed-text` | `no-defect`
- action: `waive_and_release` | `vendor_redelivery` | `expedite_internal_fix` |
  `delay_release` | `escalate_to_release_board`

Metrics: `queue_accuracy`, `action_accuracy`, `exact_match`, `submitted` (fraud shape).

## Constants

```python
VENDOR_SLA_DAYS = 5      # vendor redelivery turnaround
INHOUSE_FIX_DAYS = 2     # in-house fix turnaround (timed text, audio remaps)
RELEASE_WINDOW_DAYS = 3  # inside this window, minor defects ship-and-patch
```

## Gold rules — ordered, first match wins

```python
def gold_triage(flag, title) -> tuple[queue, action]:
    # 1. Creative-intent annotation on file matching the flagged range → false positive
    if flag["creative_intent_match"]:
        return ("no-defect", "waive_and_release")
    queue = {"video": "video-eng", "audio": "audio-eng", "timed_text": "timed-text"}[flag["component"]]
    days = title["days_to_premiere"]
    # 2. Caption defect in a CVAA-covered territory → NEVER waive, legal hard block
    if flag["is_caption_defect"] and title["cvaa_covered"]:
        return (queue, "expedite_internal_fix" if days >= INHOUSE_FIX_DAYS else "delay_release")
    # 3. Minor severity → far out: vendor fixes it; close in: ship now, patch post-release
    if flag["severity"] == "minor":
        return (queue, "waive_and_release" if days <= RELEASE_WINDOW_DAYS else "vendor_redelivery")
    # 4. Major severity
    if flag["inhouse_fixable"] and days >= INHOUSE_FIX_DAYS:
        return (queue, "expedite_internal_fix")
    if days > VENDOR_SLA_DAYS:
        return (queue, "vendor_redelivery")
    if title["tier"] == "tentpole":
        return (queue, "escalate_to_release_board")   # ship-vs-delay is a money decision
    return (queue, "delay_release")
```

`inhouse_fixable`: timed_text True, audio True, video False. Do NOT expose this as a
flag field — it lives in the policy KB text only (forces KB retrieval).

## Defect archetypes (6, balanced via `i % 6`)

| Archetype | component | severity | key fields | gold path |
|---|---|---|---|---|
| INTENTIONAL_CREATIVE | audio | major | creative_intent_match=True (always) | rule 1 → waive. **Deception A: looks broken, is fine** |
| CAPTION_SYNC | timed_text | minor | is_caption_defect=True | rule 2 in CVAA territory; **falls to rule 3 in non-CVAA** — punishes over-generalizing the caption rule. **Deception B: looks minor, is blocking** |
| AUDIO_SYNC | audio | major | — | rule 4, inhouse path |
| HDR_METADATA | video | major | — | rule 4, vendor/board/delay by days+tier |
| BAKED_IN_VIDEO | video | major | — | rule 4; generate biased close-in+tentpole → board |
| LOUDNESS_SPEC | audio | minor | — | rule 3 both branches |

Randomize: tier (~30% tentpole), days_to_premiere 1–30, territory mix (~60% includes
US → cvaa_covered=True; caption defects in non-US-only scenarios are the
over-generalization trap). Flag text templates underdetermine/mislead: "audio dropout
detected 00:41:22–00:41:44" (the intentional silence), "subtitle timing drift ~800ms
on 14 events" (the blocking one).

## Tools (strict schemas, per template)

1. `get_release_context(title_id)` → tier, premiere_date, days_to_premiere,
   territories, cvaa_covered, marketing_lock
2. `get_qc_flag(asset_id)` → component, severity, description, timecode_range,
   detector stage (photon | iaas | auto-qc — flavor from Netflix pipeline),
   is_caption_defect
3. `check_creative_annotations(asset_id)` → production annotations on file
   (director-intent notes w/ timecode ranges) or none
4. `search_release_policy(query)` → keyword KB (same retrieval fn as other verticals)
5. `submit_release_decision(queue, action, reasoning)` — terminal

## Policy KB (6 docs)

- RQ-PREF-00 preference order (fix in-house > vendor redelivery > delay; waive only
  where policy allows)
- RQ-CVAA-01 caption hard block: caption defects in CVAA-covered territories are
  never waived regardless of tier/premiere pressure (flavor: CVAA, NAD v. Netflix
  100%-captioning consent decree)
- RQ-CREATIVE-02 creative-intent annotations override detector flags
- RQ-MINOR-03 minor defects: ship-and-patch inside RELEASE_WINDOW_DAYS, vendor
  redelivery otherwise
- RQ-FIX-04 in-house capability: timed text + audio fixable in INHOUSE_FIX_DAYS;
  picture/IMF-metadata defects require vendor redelivery (VENDOR_SLA_DAYS)
- RQ-BOARD-05 board escalation: unfixable major defect on a tentpole inside the
  vendor SLA window

## Mock backend's engineered gap

Mock applies all rules EXCEPT rule 2's precedence — it treats caption defects as
ordinary minor defects (rule 3), so it waives close-in caption defects in CVAA
territories. Script: get_release_context → get_qc_flag → check_creative_annotations →
search_release_policy → submit. (4 investigation calls — one more than prior mocks;
mirror the n_assistant laddering accordingly.)

## Checklist (same as Waves 2/3)

tests incl.: determinism, all queues+actions covered at n=120, rule-2-vs-rule-3
precedence unit test, non-CVAA caption fall-through test, strict schemas, mock e2e,
mock eval error band, archetype-trap presence. Then: scenarios.jsonl committed, CI
matrix row (seed 19), mock eval, real evals (mistral free → gpt-oss → kimi →
Qwen/Qwen3.7-Plus via together, ~$0.55 total), mine transcripts → FAILURE_MODES.md
(expect: caption-waive violations, creative-intent false blocks, board over/under-use),
README with results table, vertical README, root README row + industry row 16
"🎬 Media & Streaming ✅", stats SVG bump, push, CI green, memory update.
