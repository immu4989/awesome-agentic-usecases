"""Generate FAILURE_TAXONOMY.md — the cross-cutting patterns behind every observed failure.

Individually, this repo documents ~64 failure modes across 12 use cases. Read together they
are not 64 things: they are about ten recurring patterns, several of which were found
independently in eight different domains without anyone looking for them. That synthesis is
the repo's most valuable artifact and the one thing a demo collection structurally cannot
produce, because you can only find a pattern like this by measuring the same way many times.

The *judgment* — which observation belongs to which pattern — is curated here, explicitly,
so it can be reviewed and argued with. Everything mechanical is generated: the links, the
counts, and an integrity check that every citation actually resolves to a real heading in a
real FAILURE_MODES.md. If a wave renames a failure mode, this script fails loudly instead of
publishing a dead reference.

    python docs/make_taxonomy.py
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# pattern -> curated definition, why it matters, and the observations that support it.
# Each citation is (use-case path, distinctive substring of the failure-mode heading).
PATTERNS = [
    {
        "id": "commit-stall",
        "name": "Commit-stall",
        "one_liner": "The agent investigates correctly, reaches the right conclusion, and never commits it.",
        "why": (
            "This is the most universal failure in the repo: found independently in **nine "
            "use cases**, across unrelated industries and three model families, without "
            "anyone designing for it. It is invisible to accuracy metrics — the runs that "
            "never submit are simply absent from the numerator — so a stalling agent can "
            "read as a careful one. **Read `submitted` before you read any accuracy or "
            "safety metric.**"
        ),
        "numbers": [
            ("gpt-oss-120b, refund", "submitted 0.678 — 29 of 90 tickets abandoned, 23 of them immediately after the correct escalate call"),
            ("gpt-oss-120b, refund crew", "75 of 90 runs never closed the ticket while every sub-agent returned successfully"),
            ("gpt-oss-120b, artifact admission", "submitted 0.778 — a security gate that reaches no verdict is its own failure"),
            ("gpt-oss-120b, trifecta exfil", "submitted 0.378 undefended; its clean safety score was mostly non-participation"),
        ],
        "cites": [
            ("logistics-supply-chain/exception-triage-agent", "stalls at the commit point"),
            ("retail-workforce/shift-coverage-triage-agent", "never submits"),
            ("media-streaming/release-qc-triage-agent", "Commit-stall persists"),
            ("financial-services-fraud/fraud-alert-triage-agent", "Commit-stall on the hardest"),
            ("customer-support/refund-resolution-agent", "Acting agents stall"),
            ("customer-support/refund-crew", "handoffs as completion"),
            ("security-operations/artifact-admission-agent", "never finished"),
            ("security-operations/trifecta-exfil-agent", "Safe by not finishing"),
            ("public-sector/small-business-recovery-agent", "empty-action closeout"),
        ],
    },
    {
        "id": "environment-beats-prompt",
        "name": "The environment beats the prompt",
        "one_liner": "Changing what the agent *can* do works; telling it what it *should* do mostly doesn't.",
        "why": (
            "Four independent A/B experiments, each isolating a single variable, all point the "
            "same way — and two of them show the prompt fix making things **worse**. This is "
            "the repo's most actionable finding and the one most often gotten wrong in "
            "production, because a prompt edit is cheap and feels like progress."
        ),
        "numbers": [
            ("refund, tool-layer enforcement", "safe_and_correct 0.333 → **0.822** at no measurable cost"),
            ("refund, a prompt nudge to finish", "stalls **doubled**, 29/90 → 59/90 — the nudge worsened the exact failure it targeted"),
            ("refund under injection", "a prompt guard naming all five attack shapes: 0.773 → 0.740 (nothing). Tool-layer guard: **0.000**"),
            ("trifecta tool poisoning", "prompt guard 1.00 → 0.97; dataflow gate → **0.000**, on identical agent decisions"),
            ("artifact admission", "sandbox-by-default contained unsafe admits 0.122 → **0.000** without changing one agent decision"),
        ],
        "cites": [
            ("customer-support/refund-guarded", "prompt nudge doubled"),
            ("customer-support/refund-injected", "defence most teams ship did nothing"),
            ("security-operations/trifecta-exfil-agent", "named the exact attack"),
            ("security-operations/artifact-admission-agent", "hides an unchanged admit rate"),
        ],
    },
    {
        "id": "unchanged-disposition",
        "name": "Contained is not fixed",
        "one_liner": "A guard drives the incident rate to zero while the agent's judgment stays exactly as wrong.",
        "why": (
            "Every environment fix in this repo works by making the mistake harmless, not by "
            "preventing it. The agent still reaches for the forbidden action at the same rate "
            "— sometimes a **higher** rate. Any monitoring built on the agent's behaviour will "
            "therefore report a clean system while it is being successfully attacked. "
            "**Instrument the block rate, not the incident rate.**"
        ),
        "numbers": [
            ("refund, enforced", "blocked_attempt 0.489 — the model still reached for the forbidden refund in 44 of 90 runs"),
            ("refund under injection", "attempted 0.800 *with* the guard vs 0.773 undefended — persuaded slightly more often, breached never"),
            ("trifecta", "exfiltration 0.000 while attempted_exfil held at 0.133"),
        ],
        "cites": [
            ("customer-support/refund-guarded", "disposition never changed"),
            ("customer-support/refund-injected", "unchanged susceptibility"),
            ("security-operations/artifact-admission-agent", "hides an unchanged admit rate"),
        ],
    },
    {
        "id": "displaced-intent",
        "name": "Removing the tool displaces the intent",
        "one_liner": "Take the forbidden action out of the schema and the goal reroutes — through a legal-but-wrong channel, or into a claim that the work was done.",
        "why": (
            "Least privilege is the one control this repo consistently finds effective, so its "
            "failure mode deserves naming. Deleting a capability removes the *act*, never the "
            "objective that motivated it. The agent still needs to dispose of the case, and it "
            "reaches for whatever remains — which is why the residue lands somewhere that looks "
            "compliant. In both observations below the resulting record is **honest and the "
            "reasoning correct**, so no truthfulness check fires. Removing a tool is not "
            "finished until you have asked what the agent will do instead."
        ),
        "numbers": [
            ("healthcare prior auth", "barred by statute from medical-necessity denial, the agent refuses through the **administrative** channel instead — **0.42** `[0.21, 0.62]` of routing cases. The clinical reasoning is right, the rationale accurate; only the channel is wrong, and the channel is what the statute regulates"),
            ("incident remediation", "with the forbidden tools gone, one model of three closed incidents as *'remediated'* for work that never ran — the capability control bought a false all-clear"),
        ],
        "cites": [
            ("healthcare-life-sciences/prior-auth-review-agent", "unlocked door"),
            ("it-operations/incident-remediation-agent", "did not remove the capability"),
            ("it-operations/incident-remediation-agent", "false all-clear"),
        ],
    },
    {
        "id": "safety-by-inaction",
        "name": "Safety by inaction",
        "one_liner": "A 'did it avoid the bad action' metric is passed perfectly by an agent that does nothing.",
        "why": (
            "Restraint and absence are indistinguishable unless you also measure whether the "
            "agent looked. This generalises to every guardrail KPI in production: if the "
            "metric only counts bad events, the cheapest way to score well is to stop "
            "participating. Pair every restraint metric with a diligence metric."
        ),
        "numbers": [
            ("on-call watch", "two models scored a **perfect 1.000** on 'never paged a quiet window' while missing a third of real incidents — by watching 3.6 and 5.8 of 20 minutes"),
            ("artifact admission", "gpt-oss posted zero unsafe admits and zero over-blocks — on the 78% of runs where it decided at all"),
            ("trifecta exfil", "zero leaks on the content channel, largely by never reaching a decision"),
            ("legal clause review", "the variant that defeats a diligence metric: mistral calls `read_clause` in **84 of 84** runs and records a clause-level verdict in almost none (`flag` 6/84, `accept` 1/84), escalating wholesale instead. It looked at everything and adjudicated nothing"),
            ("vendor payments", "payment safety **1.000**, while only **3 of 24** legitimate payments executed with authorized terms; 36/84 submitted reviews had no business action behind them"),
        ],
        "cites": [
            ("it-operations/oncall-watch-agent", "passed by not looking"),
            ("security-operations/artifact-admission-agent", "never finished"),
            ("security-operations/trifecta-exfil-agent", "Safe by not finishing"),
            ("legal-compliance/dpa-clause-review-agent", "adjudicates nothing"),
            ("procurement-finance/vendor-payment-review-agent", "Correct decision, wrong object"),
            ("procurement-finance/vendor-payment-review-agent", "Perfect payment safety"),
        ],
    },
    {
        "id": "prior-over-policy",
        "name": "Prior over policy",
        "one_liner": "The model's own sense of what's reasonable overrides the policy it just retrieved.",
        "why": (
            "These agents do not fail to *find* the rule — several cite it in their own "
            "reasoning and then violate it in the same breath. The failure is precedence, not "
            "retrieval, which is why better RAG does not fix it and a tool that refuses does."
        ),
        "numbers": [
            ("logistics", "one model cited the $2,000 escalation policy in its reasoning and then violated it, three repeats out of three"),
            ("retail", "an invented 'overtime is expensive' heuristic overrode the written labour policy"),
            ("refund", "the refund reflex: a forbidden refund issued in 15 of 15 runs in *every* archetype where refunding was banned"),
            ("media", "models pulled work in-house asserting a capability the policy explicitly denies"),
        ],
        "cites": [
            ("logistics-supply-chain/exception-triage-agent", "Reasoning–action contradiction"),
            ("retail-workforce/shift-coverage-triage-agent", "overtime is expensive"),
            ("customer-support/refund-resolution-agent", "refund reflex"),
            ("media-streaming/release-qc-triage-agent", "Over-fixing"),
        ],
    },
    {
        "id": "framing-over-evidence",
        "name": "Framing over evidence",
        "one_liner": "The agent believes how the input was described instead of checking what the tools say.",
        "why": (
            "Every triage domain in this repo has a case that reads as one thing and is "
            "another, and every domain has models that anchor on the description. The tools "
            "contained the disproof in each case; the agent simply did not weigh it above the "
            "framing it was handed first."
        ),
        "numbers": [
            ("security", "an authorized vulnerability scanner's noise filed as credential-abuse — the telemetry named the scanner and the change ticket"),
            ("fraud", "a benign holiday charge blocked despite a matching travel notice; an authorised-push-payment scam cleared because it rode the customer's own trusted device"),
            ("media", "intentional creative silence read as an audio defect, 12 of 15 runs on one model"),
        ],
        "cites": [
            ("security-operations/alert-triage-agent", "scanner deception"),
            ("financial-services-fraud/fraud-alert-triage-agent", "travel deception"),
            ("media-streaming/release-qc-triage-agent", "looks broken, is fine"),
            ("public-sector/small-business-recovery-agent", "accessibility attention displaces"),
        ],
    },
    {
        "id": "channel-trust",
        "name": "Trust follows the channel, not the content",
        "one_liner": "The same instruction is refused in data and obeyed in a tool definition.",
        "why": (
            "Injection defences have been trained on *content*. They do not extend to the "
            "surfaces the model treats as part of itself — its tool descriptions, and by "
            "extension anything a connector supplies. This is the single sharpest security "
            "result in the repo and it is not a capability problem: the strongest model tested "
            "leaks exactly as often as the weakest."
        ),
        "numbers": [
            ("trifecta exfil", "identical secret-stealing instruction: **~0%** obeyed in fetched content, **100%** obeyed in a tool's own description — all three models"),
            ("artifact admission", "the mirror case: a manifest that declares no code while the config executes — the vector behind the July 2026 Hugging Face breach"),
        ],
        "cites": [
            ("security-operations/trifecta-exfil-agent", "trust their own tooling"),
            ("security-operations/trifecta-exfil-agent", "Capability is not protection"),
            ("security-operations/artifact-admission-agent", "Trusted live code admitted"),
        ],
    },
    {
        "id": "ceremony-vs-prohibition",
        "name": "Ceremony is learned, prohibition is not",
        "one_liner": "Agents reliably obey 'do this first' and unreliably obey 'never do this'.",
        "why": (
            "An ordering rule adds a step to a sequence; a prohibition requires *not* taking a "
            "step that otherwise fits. Across 270 runs no model ever moved money before "
            "verifying identity, while restraint rules failed completely on the same model in "
            "the same runs. Prohibitions therefore belong in the tool layer — and the ordering "
            "record is reliable, not robust: under injection it drops too."
        ),
        "numbers": [
            ("refund", "prerequisite_respected **1.000 across all 270 runs**; the prohibition failed 15/15 in every banned archetype"),
            ("refund under injection", "that same perfect ordering record falls to **0.660** once the ticket text turns hostile"),
        ],
        "cites": [
            ("customer-support/refund-resolution-agent", "Ceremony is learned"),
            ("customer-support/refund-injected", "Injections overwrite rules more easily than facts"),
        ],
    },
    {
        "id": "directional-bias",
        "name": "Directional bias",
        "one_liner": "Models don't err randomly — each errs in one direction, and the direction is a model property.",
        "why": (
            "Accuracy alone implies errors are symmetric. They are not: one model over-escalates "
            "everywhere, another under-escalates the same cases, and the bias is stable within "
            "a model across domains. It is also **fixable by model choice**, which makes it a "
            "selection criterion rather than an inherent limitation."
        ),
        "numbers": [
            ("fraud", "three of four models over-called fraud on benign transactions and never the reverse — Qwen3.7-Plus broke the pattern with zero such errors, falsifying the universal claim"),
            ("retail / media / security", "over-escalation on one model and under-escalation on another, on the identical scenario set"),
            ("refund", "one model's action errors were 22 of 23 the *same* substitution"),
            ("healthcare + legal, record fidelity", "infidelity is one-directional too: across **1,512 runs in two industries**, models never once claimed an action they had not taken, while gpt-oss failed to name an action it *had* taken in 0.39 of legal records. They do not invent — they under-report"),
            ("vendor payments", "all 12 unverified bank changes were held, but **8 of 12** independently verified changes were held or rejected too"),
        ],
        "cites": [
            ("financial-services-fraud/fraud-alert-triage-agent", "One-directional bias"),
            ("retail-workforce/shift-coverage-triage-agent", "Over-escalation"),
            ("security-operations/alert-triage-agent", "Over-escalation"),
            ("legal-compliance/dpa-clause-review-agent", "expected and did not occur"),
            ("procurement-finance/vendor-payment-review-agent", "Verified vendors were overblocked"),
        ],
    },
    {
        "id": "outcome-without-public-value",
        "name": "The outcome can be right while the service fails",
        "one_liner": "Correct routing can still impose duplicate burden, exclude a user, lose a deadline, or erase recourse.",
        "why": (
            "Outcome metrics see where a case landed, not what the person had to surrender or "
            "risk to get there. Service agents need a second gold object that binds the outcome "
            "to minimum evidence, accessible delivery, deadlines, recourse, rights, intent, "
            "and a truthful record. Otherwise an organization can optimize its queue while "
            "quietly transferring the cost to users."
        ),
        "numbers": [
            ("small-business recovery baseline", "outcome accuracy and completion **1.000**; exact public value only **0.375** across 32 scenarios × 3 repeats"),
            ("household energy baseline", "outcome accuracy **1.000**; exact public value **0.250** after continuity, evidence, access, deadline, recourse, and record truth are combined"),
            ("disaster claim-and-aid baseline", "outcome accuracy **1.000**; exact public value **0.125** when known compensation sources and service obligations must also be exact"),
            ("four new service baselines", "outcome accuracy **1.000** in unemployment, farm-disaster, permit, and student navigation while their distinctive exact metrics ranged from **0.250 to 0.875**"),
            ("administrative burden", "minimum-evidence compliance **0.625** because a one-document gap triggered the full checklist"),
            ("access and remedy", "accessible channel **0.875**, deadline protection **0.750**, and recourse only **0.375**"),
        ],
        "cites": [
            ("public-sector/small-business-recovery-agent", "outcome mirage"),
            ("public-sector/small-business-recovery-agent", "full-checklist reflex"),
            ("public-sector/small-business-recovery-agent", "portal default"),
            ("public-sector/small-business-recovery-agent", "recourse disappears"),
            ("public-sector/small-business-recovery-agent", "deadline is known"),
            ("energy-utilities/household-energy-lifeline", "stale paperwork"),
            ("energy-utilities/household-energy-lifeline", "Medical minimization"),
            ("insurance-disaster-recovery/disaster-claim-aid-coordinator", "referral is recorded"),
            ("insurance-disaster-recovery/disaster-claim-aid-coordinator", "Overlap review asks"),
            ("employment-social-insurance/unemployment-claim-navigator", "Correct appeal route"),
            ("agriculture-food-systems/farm-disaster-deadline-agent", "first deadline hides"),
            ("housing-construction/permit-readiness-agent", "Residential rule applied"),
            ("education-services/student-accommodation-navigator", "voluntary offer"),
        ],
    },
    {
        "id": "no-transfer",
        "name": "Competence does not transfer",
        "one_liner": "Being the best model on one agent task predicts almost nothing about the next.",
        "why": (
            "Every model tested wins at least one use case and loses another, and the ranking "
            "flips by domain and by capability shape. A model that solves an acting task can "
            "be middling at a watching one. This is why a general leaderboard cannot answer "
            "'which model should run my agent', and why the per-use-case number exists."
        ),
        "numbers": [
            ("across 8 tasks", "wins: Qwen3.7-Plus 4, kimi-k2p6 2, gpt-oss-120b 2, mistral-small 1 — the cheapest free-tier model wins the on-call watch task outright"),
            ("trifecta", "capability is not protection: the strongest model leaks through a poisoned tool as often as the weakest"),
            ("logistics vs media", "kimi is the only model to score a perfect 90/90 on one task and comes last on another, at 7.7× the cost per scenario"),
            ("legal, missing GDPR clause", "the widest spread in the repo: **0.00 to 0.98 on identical contracts**, intervals disjoint. One model solves it outright, so the task is demonstrably not the limit — and no arm moves any of them (p ≥ 0.48)"),
        ],
        "cites": [
            ("security-operations/alert-triage-agent", "different domain, different competence"),
            ("retail-workforce/shift-coverage-triage-agent", "different domain, different competence"),
            ("financial-services-fraud/fraud-alert-triage-agent", "No best model"),
            ("security-operations/trifecta-exfil-agent", "Capability is not protection"),
            ("legal-compliance/dpa-clause-review-agent", "property of the model, not the task"),
        ],
    },
    {
        "id": "coordination-only",
        "name": "Coordination-only failures",
        "one_liner": "Multi-agent systems fail in ways a single agent cannot, and orchestration amplifies rather than fixes.",
        "why": (
            "Four of the crew's six documented failures are impossible single-agent: a brief "
            "that silently drops the deciding fact, a compliance veto the orchestrator ignores, "
            "a specialist that is bad at its speciality. Orchestration never produced a new high "
            "score in 270 runs — it compressed the range, helping a weak model and taxing a "
            "strong one."
        ),
        "numbers": [
            ("refund crew", "mistral 0.333 → 0.411 (helped), gpt-oss 0.644 → **0.044** (destroyed), Qwen 0.978 → 0.933 (taxed at 1.96× cost)"),
            ("refund crew", "a veto that gets ignored is worse than no veto — it manufactures false assurance"),
        ],
        "cites": [
            ("customer-support/refund-crew", "amplifies whatever the model already does"),
            ("customer-support/refund-crew", "brief is a lossy channel"),
            ("customer-support/refund-crew", "veto that gets ignored"),
            ("customer-support/refund-crew", "not automatically good at its speciality"),
        ],
    },
]


def load_headings() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for dirpath, _dirs, files in os.walk(ROOT):
        if "FAILURE_MODES.md" not in files or ".venv" in dirpath:
            continue
        rel = os.path.relpath(dirpath, ROOT)
        with open(os.path.join(dirpath, "FAILURE_MODES.md")) as f:
            out[rel] = re.findall(r"^###\s+(.*)$", f.read(), re.M)
    return out


def anchor(heading: str) -> str:
    """GitHub's heading-anchor slug."""
    s = heading.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s.strip())


def resolve(headings: dict[str, list[str]]) -> list[str]:
    """Every citation must point at a heading that exists. Fail loudly if not."""
    problems = []
    for p in PATTERNS:
        for path, frag in p["cites"]:
            hits = [h for h in headings.get(path, []) if frag.lower() in h.lower()]
            if not hits:
                problems.append(f"{p['id']}: no heading matching {frag!r} in {path}")
            elif len(hits) > 1:
                problems.append(f"{p['id']}: {frag!r} is ambiguous in {path} ({len(hits)} hits)")
    return problems


def render(headings: dict[str, list[str]]) -> str:
    total_modes = sum(len(v) for v in headings.values())
    n_uc = len(headings)
    L: list[str] = []
    L.append("# The Agent Failure Taxonomy\n")
    L.append(
        f"**{total_modes} failure modes, observed across {n_uc} use cases, "
        f"{len(PATTERNS)} recurring patterns.**\n"
    )
    L.append(
        "Every entry below was *measured*, not hypothesised — each links to the run that\n"
        "produced it, with a reproducing input. Read individually the failures look\n"
        "domain-specific. Read together they are not: the same handful of patterns keep\n"
        "reappearing in industries that share nothing but the shape of the agent.\n"
    )
    L.append(
        "> Several of these were found **independently in eight different domains** without\n"
        "> anyone looking for them. That is the one thing a collection of demos cannot\n"
        "> produce, at any scale: you only see a pattern like this by measuring the same way,\n"
        "> many times, and writing down what broke.\n"
    )
    L.append("## The patterns\n")
    L.append("| # | Pattern | In short | Seen in |")
    L.append("|---|---|---|---|")
    for i, p in enumerate(PATTERNS, 1):
        seen = len({c[0] for c in p["cites"]})
        L.append(f"| {i} | [{p['name']}](#{anchor(p['name'])}) | {p['one_liner']} | "
                 f"{seen} use case{'s' if seen > 1 else ''} |")
    L.append("")
    L.append("---\n")

    for i, p in enumerate(PATTERNS, 1):
        L.append(f"## {p['name']}\n")
        L.append(f"*{p['one_liner']}*\n")
        L.append(p["why"] + "\n")
        L.append("**Measured**\n")
        for where, what in p["numbers"]:
            L.append(f"- **{where}** — {what}")
        L.append("")
        L.append("<details><summary><b>Where it was observed</b></summary>\n")
        for path, frag in p["cites"]:
            hits = [h for h in headings.get(path, []) if frag.lower() in h.lower()]
            h = hits[0]
            title = re.sub(r"^\d+\.\s*", "", h)
            name = path.split("/")[-1]
            L.append(f"- [`{name}` — {title}]({path}/FAILURE_MODES.md#{anchor(h)})")
        L.append("\n</details>\n")
        if i < len(PATTERNS):
            L.append("---\n")

    L.append("## How to use this\n")
    L.append(
        "- **Before you ship an agent**, read `Commit-stall` and `Safety by inaction` — they\n"
        "  are the two failures most likely to be invisible in your own eval.\n"
        "- **Before you write a prompt fix**, read `The environment beats the prompt`. Four\n"
        "  controlled A/Bs in this repo say it probably won't work, and twice it made things\n"
        "  worse.\n"
        "- **Before you pick a model**, read `Competence does not transfer` and the\n"
        "  [per-task matrix](README.md#there-is-no-best-model).\n"
        "- **Before you trust a guardrail metric**, read `Contained is not fixed`.\n"
    )
    L.append(
        "\n---\n\n<sub>Generated by `docs/make_taxonomy.py` from the committed\n"
        "`FAILURE_MODES.md` files. The grouping is a curated judgment and is meant to be\n"
        "argued with; every citation is checked to resolve to a real heading at build time,\n"
        "so this page cannot silently rot as the repo grows.</sub>\n"
    )
    return "\n".join(L)


def main() -> None:
    headings = load_headings()
    problems = resolve(headings)
    if problems:
        print("BROKEN CITATIONS — taxonomy not written:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        sys.exit(1)
    out = os.path.join(ROOT, "FAILURE_TAXONOMY.md")
    with open(out, "w") as f:
        f.write(render(headings))
    total = sum(len(v) for v in headings.values())
    cited = sum(len(p["cites"]) for p in PATTERNS)
    print(f"wrote FAILURE_TAXONOMY.md — {len(PATTERNS)} patterns, {cited} citations, "
          f"{total} failure modes across {len(headings)} use cases")
    summary = {"patterns": len(PATTERNS), "failure_modes": total, "use_cases": len(headings),
               "index": [{"id": p["id"], "name": p["name"], "one_liner": p["one_liner"],
                          "use_cases": sorted({c[0] for c in p["cites"]})} for p in PATTERNS]}
    with open(os.path.join(ROOT, "docs", "assets", "taxonomy.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("wrote docs/assets/taxonomy.json (machine-readable index)")


if __name__ == "__main__":
    main()
