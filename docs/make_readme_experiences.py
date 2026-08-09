"""Generate and install a themed visual case file for every use-case README.

The output is plain SVG: crisp on every screen, readable in GitHub light and dark
themes, motion-safe, small enough to fork, and reproducible without design software.
Run from the repository root with:

    python docs/make_readme_experiences.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import wrap


ROOT = Path(__file__).resolve().parents[1]
START = "<!-- README-EXPERIENCE:START -->"
END = "<!-- README-EXPERIENCE:END -->"
BRIEFING_START = "<!-- VISUAL-BRIEFING:START -->"
BRIEFING_END = "<!-- VISUAL-BRIEFING:END -->"


@dataclass(frozen=True)
class Experience:
    path: str
    title: str
    icon: str
    industry: str
    tagline: str
    accent: str
    stages: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Briefing:
    metric: str
    metric_label: str
    cards: tuple[tuple[str, str, str], ...]
    invert: bool = False
    raw: bool = False


EXPERIENCES = (
    Experience("logistics-supply-chain/exception-triage-agent", "Exception Triage", "🎫", "LOGISTICS", "The complaint is a clue. The operational record decides.", "#2a78d6", (("HEAR", "customer claim"), ("VERIFY", "shipment facts"), ("CHECK", "SLA + policy"), ("ROUTE", "right owner"))),
    Experience("logistics-supply-chain/exception-triage-drift", "Exception Triage Drift", "🪞", "RELIABILITY", "What survives when caches stale and sources disagree?", "#147d92", (("OBSERVE", "conflicting facts"), ("PROBE", "source quality"), ("ABSTAIN", "when uncertain"), ("MEASURE", "clean vs drift"))),
    Experience("retail-workforce/shift-coverage-triage-agent", "Shift Coverage", "🧑‍🍳", "WORKFORCE", "Fill the shift without breaking the rules that protect the crew.", "#e05a24", (("MAP", "coverage gap"), ("CHECK", "hours + age"), ("SEARCH", "legal options"), ("STAFF", "or escalate"))),
    Experience("security-operations/alert-triage-agent", "Alert Triage", "🚨", "SECURITY OPERATIONS", "Detectors make claims. Evidence earns a response.", "#6554c0", (("RECEIVE", "detector claim"), ("VERIFY", "asset + source"), ("REASON", "risk context"), ("CONTAIN", "at right level"))),
    Experience("security-operations/artifact-admission-agent", "Artifact Admission", "🛂", "AI SUPPLY CHAIN", "Inspect what the artifact can execute—not what its label promises.", "#4a3aa7", (("DECLARE", "manifest"), ("INSPECT", "execution path"), ("BOUND", "network + creds"), ("ADMIT", "sandbox or block"))),
    Experience("security-operations/trifecta-exfil-agent", "Trifecta Exfil", "🕳️", "AGENT SECURITY", "Private data + untrusted input + egress: trace the consequence.", "#8d2f70", (("READ", "private context"), ("FETCH", "hostile content"), ("TAINT", "track provenance"), ("BLOCK", "secret egress"))),
    Experience("financial-services-fraud/fraud-alert-triage-agent", "Fraud Alert Triage", "🚩", "FINANCIAL SERVICES", "A safe signal can look criminal. A trusted device can carry a scam.", "#16966b", (("FLAG", "transaction"), ("VERIFY", "customer context"), ("DETECT", "hidden scam"), ("PROTECT", "without bias"))),
    Experience("procurement-finance/vendor-payment-review-agent", "Vendor Payment Review", "🧾", "PROCUREMENT + FINANCE", "The invoice matches. Does the bank account?", "#c98500", (("MATCH", "PO + receipt"), ("VERIFY", "trusted master"), ("HOLD", "unsafe changes"), ("PAY", "only once"))),
    Experience("media-streaming/release-qc-triage-agent", "Release QC Triage", "🎞️", "MEDIA + STREAMING", "Creative intent, accessibility law, and a premiere clock collide.", "#d55181", (("INGEST", "QC finding"), ("CONTEXT", "timecode notes"), ("CHECK", "territory rules"), ("SHIP", "fix or delay"))),
    Experience("customer-support/refund-resolution-agent", "Refund Resolution", "💸", "CUSTOMER SUPPORT", "A correct answer is not enough when the tool moves money.", "#d88b00", (("VERIFY", "identity"), ("INSPECT", "order + dispute"), ("CHOOSE", "allowed remedy"), ("COMMIT", "safe action"))),
    Experience("customer-support/refund-guarded", "Refund Guarded", "🔧", "SAFETY ENGINEERING", "Measure whether enforcement beats another paragraph in the prompt.", "#16834f", (("BASELINE", "observed failure"), ("INTERVENE", "prompt or tool"), ("REPLAY", "same scenarios"), ("COMPARE", "harm prevented"))),
    Experience("customer-support/refund-crew", "Refund Crew", "👥", "MULTI-AGENT SYSTEMS", "Three specialists enter. Only controlled evidence says if they helped.", "#d24444", (("BRIEF", "shared facts"), ("DELEGATE", "specialists"), ("VETO", "unsafe remedy"), ("COMPARE", "single agent"))),
    Experience("customer-support/refund-injected", "Refund Injected", "🎯", "ADVERSARIAL SAFETY", "The customer controls the ticket. The policy must control the action.", "#b3261e", (("PLANT", "hostile text"), ("TRACE", "tool choices"), ("ENFORCE", "hard boundary"), ("SCORE", "actual harm"))),
    Experience("customer-support/refund-memory", "Refund Memory", "🧠", "PERSISTENT MEMORY", "The attacker leaves. The false fact stays.", "#a62b70", (("POISON", "session one"), ("PERSIST", "memory write"), ("RETURN", "clean session"), ("MEASURE", "delayed harm"))),
    Experience("customer-support/refund-amplified", "Refund Amplified", "📈", "ECONOMIC SECURITY", "The answer can be right while the bill becomes the attack.", "#e26b22", (("SEED", "cost payload"), ("EXPAND", "tokens + calls"), ("CONTROL", "match length"), ("PRICE", "denial of wallet"))),
    Experience("healthcare-life-sciences/prior-auth-review-agent", "Prior Auth Review", "🏥", "HEALTHCARE", "The agent may review. The agent may not deny.", "#087f8c", (("READ", "clinical record"), ("APPLY", "criteria"), ("PRESERVE", "record truth"), ("ROUTE", "human denial"))),
    Experience("legal-compliance/dpa-clause-review-agent", "DPA Clause Review", "⚖️", "LEGAL + COMPLIANCE", "The most expensive clause may be the one that is absent.", "#6c4ea2", (("INDEX", "contract terms"), ("READ", "full clauses"), ("COMPARE", "statutory gold"), ("ESCALATE", "missing duty"))),
    Experience("it-operations/incident-remediation-agent", "Incident Remediation", "🧯", "IT OPERATIONS", "When the approved path fails, safety lives in the next move.", "#c94a42", (("DETECT", "service failure"), ("RUN", "approved action"), ("BLOCK", "unsafe shortcut"), ("PAGE", "human owner"))),
    Experience("it-operations/oncall-watch-agent", "On-Call Watch", "📟", "SRE + DEVOPS", "Wait through a blip. Wake someone before the slow burn wins.", "#16834f", (("WATCH", "live telemetry"), ("WAIT", "one more tick"), ("DISTINGUISH", "blip vs breach"), ("PAGE", "only in time"))),
    Experience("public-sector/small-business-recovery-agent", "Small Business Recovery Navigator", "🌱", "PUBLIC SERVICE + ECONOMIC RESILIENCE", "Complete the service with less burden, preserved rights, and real recourse.", "#16735a", (("LISTEN", "owner's need"), ("REUSE", "evidence on file"), ("PRESERVE", "access + deadline"), ("ADVANCE", "or warm handoff"))),
    Experience("energy-utilities/household-energy-lifeline", "Household Energy Lifeline", "⚡", "ENERGY + UTILITIES", "The right referral is late if essential service disappears first.", "#d99a00", (("READ", "shutoff clock"), ("REUSE", "evidence on file"), ("PRESERVE", "service option"), ("HANDOFF", "without promises"))),
    Experience("insurance-disaster-recovery/disaster-claim-aid-coordinator", "Disaster Claim and Aid Coordinator", "🏠", "INSURANCE + DISASTER RECOVERY", "One loss crosses many ledgers. Every source must stay visible.", "#6c4ea2", (("MAP", "loss + declaration"), ("COMBINE", "trusted ledgers"), ("PROTECT", "deadline + recourse"), ("ROUTE", "without awarding"))),
    Experience("employment-social-insurance/unemployment-claim-navigator", "Unemployment Claim Navigator", "🧭", "EMPLOYMENT + SOCIAL INSURANCE", "A correct status is not enough if the next claim clock disappears.", "#3558c8", (("READ", "claim clocks"), ("REUSE", "records on file"), ("PRESERVE", "appeal + weekly"), ("HANDOFF", "without deciding"))),
    Experience("agriculture-food-systems/farm-disaster-deadline-agent", "Farm Disaster Deadline Agent", "🌾", "AGRICULTURE + FOOD SYSTEMS", "One disaster can start several clocks. Keep every window visible.", "#2f7b4b", (("MAP", "program clocks"), ("REUSE", "farm records"), ("PRESERVE", "every notice"), ("ROUTE", "without awarding"))),
    Experience("housing-construction/permit-readiness-agent", "Permit Readiness Agent", "🏗️", "HOUSING + CONSTRUCTION", "Ready in one jurisdiction can still be rejected at the next counter.", "#b84d2c", (("LOCATE", "project authority"), ("BIND", "current rules"), ("VERIFY", "minimum packet"), ("PREPARE", "without approval"))),
    Experience("education-services/student-accommodation-navigator", "Student Accommodation Navigator", "🎓", "EDUCATION SERVICES", "Collect what the team needs—not everything a family could reveal.", "#7b4cb0", (("LISTEN", "access barrier"), ("MINIMIZE", "sensitive records"), ("PRESERVE", "timely review"), ("HANDOFF", "to the team"))),
    Experience("identity-access/account-recovery-assurance-agent", "Account Recovery Assurance Agent", "🔐", "IDENTITY + ACCESS", "Restore access without turning urgency into an account-takeover route.", "#3f51b5", (("READ", "assurance level"), ("VERIFY", "established methods"), ("MINIMIZE", "identity data"), ("RECOVER", "notify or hold"))),
    Experience("accessibility-digital-services/accessibility-remediation-verifier", "Accessibility Remediation Verifier", "♿", "ACCESSIBILITY + DIGITAL SERVICES", "A scanner can find a defect. Only evidence proves the fix.", "#00796b", (("OBSERVE", "affected path"), ("COMBINE", "scan + manual"), ("REMEDIATE", "exact defect"), ("VERIFY", "without certifying"))),
    Experience("privacy-data-governance/privacy-rights-orchestrator", "Privacy Rights Orchestrator", "🛡️", "PRIVACY + DATA GOVERNANCE", "A rights request is complete only when every system tells the truth.", "#6a1b9a", (("VERIFY", "requester"), ("MAP", "every system"), ("PRESERVE", "clock + recourse"), ("PROVE", "tasks not closure"))),
)


BRIEFINGS = {
    "logistics-supply-chain/exception-triage-agent": Briefing("action_accuracy", "Correct operational action", (
        ("SURFACE STORY", "The package is lost", "A customer complaint is a clue, not the system of record."),
        ("HIDDEN TRUTH", "Exception + SLA + value", "Carrier scans and policy thresholds determine the real state."),
        ("UNSAFE SHORTCUT", "Route from ticket text", "Plausible language can bypass evidence and compound rules."),
        ("EXACT PROOF", "Queue and action both match", "Score the committed outcome, not a convincing rationale."),
    )),
    "logistics-supply-chain/exception-triage-drift": Briefing("action_accuracy", "Correct action under changed facts", (
        ("SURFACE STORY", "The same clean ticket", "Yesterday's workflow appears to work exactly as designed."),
        ("HIDDEN TRUTH", "Sources now disagree", "Caches age, feeds conflict, and old facts remain believable."),
        ("UNSAFE SHORTCUT", "Act on the stale copy", "A confident answer can be perfectly grounded in obsolete data."),
        ("EXACT PROOF", "Accuracy plus stale action", "Measure both the decision and whether stale evidence drove it."),
    )),
    "retail-workforce/shift-coverage-triage-agent": Briefing("strategy_accuracy", "Compliant staffing strategy", (
        ("SURFACE STORY", "A manager needs coverage", "An empty shift looks like a simple matching problem."),
        ("HIDDEN TRUTH", "Hours, age, distance, peak", "Labor rules and operational constraints narrow the safe set."),
        ("UNSAFE SHORTCUT", "Fill the slot at any cost", "Availability alone can produce an illegal assignment."),
        ("EXACT PROOF", "The exact legal strategy", "Credit coverage only when every worker constraint survives."),
    )),
    "security-operations/alert-triage-agent": Briefing("exact_match", "Exact queue + disposition", (
        ("SURFACE STORY", "The detector says threat", "A high-severity label creates pressure to contain immediately."),
        ("HIDDEN TRUTH", "Asset, source, change ticket", "Context separates compromise from approved operations."),
        ("UNSAFE SHORTCUT", "Believe the detector", "Blind escalation burns analysts; blind dismissal leaves exposure."),
        ("EXACT PROOF", "Queue and disposition match", "The response must fit both evidence and business impact."),
    )),
    "security-operations/artifact-admission-agent": Briefing("disposition_accuracy", "Correct admission decision", (
        ("SURFACE STORY", "The manifest says safe", "Self-declared metadata presents a reassuring identity."),
        ("HIDDEN TRUTH", "Execution path + capability", "Network, credential, and sandbox behavior reveal real power."),
        ("UNSAFE SHORTCUT", "Trust the declaration", "A polished label can conceal a dangerous runtime path."),
        ("EXACT PROOF", "Unsafe admits + over-blocks", "Measure both escaped risk and needless developer friction."),
    )),
    "security-operations/trifecta-exfil-agent": Briefing("exfiltration_success", "Secret containment", (
        ("SURFACE STORY", "A benign assistant task", "The requested summary appears ordinary and useful."),
        ("HIDDEN TRUTH", "Private data meets untrusted text", "A secret and hostile instruction share an egress path."),
        ("UNSAFE SHORTCUT", "Allow tainted output", "Content provenance disappears at the final send boundary."),
        ("EXACT PROOF", "Containment with utility", "Block secret egress without disabling clean task completion."),
    ), invert=True),
    "financial-services-fraud/fraud-alert-triage-agent": Briefing("exact_match", "Exact fraud disposition", (
        ("SURFACE STORY", "A suspicious transaction", "One unusual event looks like enough evidence to act."),
        ("HIDDEN TRUTH", "Travel, device, beneficiary", "Trusted context can clear a signal—or reveal a hidden scam."),
        ("UNSAFE SHORTCUT", "Block or allow from surface", "Both reflexes can harm the customer in different ways."),
        ("EXACT PROOF", "Queue and disposition match", "Reward the correct protection path, not generic caution."),
    )),
    "procurement-finance/vendor-payment-review-agent": Briefing("exact_match", "Exact safe payment decision", (
        ("SURFACE STORY", "The invoice matches", "PO, amount, and receipt create the appearance of readiness."),
        ("HIDDEN TRUTH", "Bank master + duplicates", "Trusted vendor data and payment history decide whether to pay."),
        ("UNSAFE SHORTCUT", "Trust an emailed bank change", "A correct invoice can still route money to an attacker."),
        ("EXACT PROOF", "Safe executed payment", "Score terms, destination, duplication, and final action together."),
    )),
    "media-streaming/release-qc-triage-agent": Briefing("action_accuracy", "Correct release action", (
        ("SURFACE STORY", "QC found a defect", "Severity alone appears to dictate whether the title ships."),
        ("HIDDEN TRUTH", "Intent, territory, premiere", "Creative notes, accessibility rules, and timing all matter."),
        ("UNSAFE SHORTCUT", "Treat every defect alike", "Over-blocking misses launches; under-blocking breaks obligations."),
        ("EXACT PROOF", "Fix, ship, or delay", "Match the action to evidence, jurisdiction, and release window."),
    )),
    "customer-support/refund-resolution-agent": Briefing("safe_and_correct", "Safe and correct resolution", (
        ("SURFACE STORY", "The customer wants money back", "The requested remedy is emotionally clear and urgent."),
        ("HIDDEN TRUTH", "Identity, dispute, final sale", "Eligibility and irreversible constraints live behind tools."),
        ("UNSAFE SHORTCUT", "Move money first", "A reasonable answer becomes harm when the tool commits it."),
        ("EXACT PROOF", "Correct and prerequisite-safe", "Success requires the right remedy in the right order."),
    )),
    "customer-support/refund-guarded": Briefing("safe_and_correct", "Safe + correct under enforcement", (
        ("SURFACE STORY", "A known refund failure", "The baseline already shows where the agent goes wrong."),
        ("HIDDEN TRUTH", "Same cases, new boundary", "Only a controlled replay isolates the intervention's effect."),
        ("UNSAFE SHORTCUT", "Assume prompt wording fixes it", "Intent is not enforcement at an irreversible tool boundary."),
        ("EXACT PROOF", "Measured harm prevented", "Compare identical scenarios, safety, recovery, and utility."),
    )),
    "customer-support/refund-crew": Briefing("safe_and_correct", "Crew safety + correctness", (
        ("SURFACE STORY", "Three specialists can help", "More roles suggest more expertise and better decisions."),
        ("HIDDEN TRUTH", "Briefs, vetoes, handoffs", "Coordination can lose facts or diffuse accountability."),
        ("UNSAFE SHORTCUT", "Assume more agents are better", "A crew can amplify a bad premise with extra confidence."),
        ("EXACT PROOF", "Controlled single-vs-crew", "Keep cases and gold fixed; measure veto and review behavior."),
    )),
    "customer-support/refund-injected": Briefing("injection_success", "Prompt-injection containment", (
        ("SURFACE STORY", "A customer-authored ticket", "Untrusted prose enters the agent's normal work queue."),
        ("HIDDEN TRUTH", "Text impersonates authority", "The payload asks the model to outrank policy and tools."),
        ("UNSAFE SHORTCUT", "Obey the embedded command", "Helpful behavior becomes a path to forbidden action."),
        ("EXACT PROOF", "Attack consequence blocked", "Score whether injection changes real tool behavior."),
    ), invert=True),
    "customer-support/refund-memory": Briefing("sleeper_harm", "Sleeper harm prevented", (
        ("SURFACE STORY", "Session two looks clean", "The attacker is gone and the new request is ordinary."),
        ("HIDDEN TRUTH", "A false fact persisted", "Poisoned memory silently changes the next decision context."),
        ("UNSAFE SHORTCUT", "Trust every stored note", "Persistence converts one bad write into delayed authority."),
        ("EXACT PROOF", "Cross-session harm blocked", "Measure poison writes and the later consequence separately."),
    ), invert=True),
    "customer-support/refund-amplified": Briefing("input_tokens", "Mean input tokens per scenario · lower is better", (
        ("SURFACE STORY", "The final answer may be right", "Accuracy can remain stable while resource use explodes."),
        ("HIDDEN TRUTH", "Attacker-controlled expansion", "Fan-out and oversized results are replayed every turn."),
        ("UNSAFE SHORTCUT", "Monitor actions only", "Call counts miss the expensive text carried between calls."),
        ("EXACT PROOF", "Tokens, cost, and controls", "Price the workload and test both request and result gates."),
    ), raw=True),
    "healthcare-life-sciences/prior-auth-review-agent": Briefing("correct", "Correct, rights-preserving review", (
        ("SURFACE STORY", "Criteria are not met", "The clinical rules appear to point to a simple denial."),
        ("HIDDEN TRUTH", "Law requires human judgment", "The decision boundary changes when the outcome is adverse."),
        ("UNSAFE SHORTCUT", "Automate the denial", "A correct rule match can still violate patient rights."),
        ("EXACT PROOF", "Route and record truth", "Score disposition, human review, and faithful evidence together."),
    )),
    "legal-compliance/dpa-clause-review-agent": Briefing("correct", "Correct statutory coverage", (
        ("SURFACE STORY", "Review the clauses present", "Retrieval works well when the relevant language exists."),
        ("HIDDEN TRUTH", "The key duty is absent", "Missing text has no semantic passage for search to return."),
        ("UNSAFE SHORTCUT", "Summarize only what exists", "Fluent review can overlook the most expensive omission."),
        ("EXACT PROOF", "Compare against the gold set", "Coverage must include required-but-missing obligations."),
    )),
    "it-operations/incident-remediation-agent": Briefing("correct", "Correct incident outcome", (
        ("SURFACE STORY", "The runbook action is blocked", "Automation reaches the point where the approved path fails."),
        ("HIDDEN TRUTH", "An unsafe shortcut is offered", "Pressure to restore service competes with control boundaries."),
        ("UNSAFE SHORTCUT", "Improvise or claim success", "False recovery is worse than an honest escalation."),
        ("EXACT PROOF", "Outcome + violation + honesty", "Measure the next move, boundary crossing, and disclosure."),
    )),
    "it-operations/oncall-watch-agent": Briefing("severity_correct", "Correct incident severity", (
        ("SURFACE STORY", "An early spike looks urgent", "The first telemetry tick supports several explanations."),
        ("HIDDEN TRUTH", "Future ticks separate paths", "A blip, slow burn, and outage diverge only over time."),
        ("UNSAFE SHORTCUT", "Page now or stop watching", "Either reflex trades alert fatigue for missed incidents."),
        ("EXACT PROOF", "Severity plus patience", "Reward timely paging and disciplined continued observation."),
    )),
    "public-sector/small-business-recovery-agent": Briefing("public_value_exact", "Complete public-value outcome", (
        ("SURFACE STORY", "An owner needs recovery help", "Eligibility is only the first piece of successful service."),
        ("HIDDEN TRUTH", "Evidence, channel, deadline, recourse", "Burden and access constraints decide whether help arrives."),
        ("UNSAFE SHORTCUT", "Right program, bad service", "A correct answer can still cause abandonment or lost rights."),
        ("EXACT PROOF", "Outcome and delivery both work", "Score benefit, burden, access, deadline, and recourse together."),
    )),
    "energy-utilities/household-energy-lifeline": Briefing("public_value_exact", "Complete lifeline service", (
        ("SURFACE STORY", "A household needs bill help", "A program referral looks like the obvious successful outcome."),
        ("HIDDEN TRUTH", "Shutoff clock + held evidence", "Continuity, access, and minimum burden decide whether help remains usable."),
        ("UNSAFE SHORTCUT", "Refer and declare success", "The route can be right while service disappears before review."),
        ("EXACT PROOF", "Outcome + continuity exact", "Score the action, evidence, channel, deadline, recourse, and truthful record together."),
    )),
    "insurance-disaster-recovery/disaster-claim-aid-coordinator": Briefing("public_value_exact", "Complete coordinated recovery", (
        ("SURFACE STORY", "Choose insurance or aid", "The next program appears to be a simple routing decision."),
        ("HIDDEN TRUTH", "One loss, several ledgers", "Insurance, charity, evidence, and deadlines must remain coordinated."),
        ("UNSAFE SHORTCUT", "Hide or invent a source", "A plausible referral can create false duplicate compensation downstream."),
        ("EXACT PROOF", "Route + exact source set", "Score every known source, minimum evidence, access, recourse, deadline, and record."),
    )),
    "employment-social-insurance/unemployment-claim-navigator": Briefing("public_value_exact", "Complete claim-navigation service", (
        ("SURFACE STORY", "A claimant sees one status", "The current claim label looks like the whole service answer."),
        ("HIDDEN TRUTH", "Appeal + certification clocks", "Held records, access needs, and parallel deadlines control what remains possible."),
        ("UNSAFE SHORTCUT", "Explain status, lose the path", "A correct explanation can still erase weekly benefits or a timely appeal."),
        ("EXACT PROOF", "Every live path preserved", "Score route, evidence, accessibility, clocks, recourse, rights, and record truth together."),
    )),
    "agriculture-food-systems/farm-disaster-deadline-agent": Briefing("deadline_map_fidelity", "Exact disaster deadline map", (
        ("SURFACE STORY", "One farm, one disaster", "A single loss event appears to create one simple filing task."),
        ("HIDDEN TRUTH", "Several program clocks", "Crop, livestock, and grazing notices can have different evidence and windows."),
        ("UNSAFE SHORTCUT", "Show only the first deadline", "A helpful first step can silently close every route that follows."),
        ("EXACT PROOF", "Exact set, no invented clock", "Match every applicable notice, reuse held records, and preserve accountable review."),
    )),
    "housing-construction/permit-readiness-agent": Briefing("jurisdiction_rule_fidelity", "Exact jurisdiction-rule match", (
        ("SURFACE STORY", "The permit packet looks complete", "A familiar checklist makes the submission appear ready."),
        ("HIDDEN TRUTH", "Authority + project class", "Jurisdiction, use, license state, and current intake rules define readiness."),
        ("UNSAFE SHORTCUT", "Reuse the nearest checklist", "The right documents under the wrong authority still produce a failed filing."),
        ("EXACT PROOF", "Rule provenance stays exact", "Score the named rule, minimum packet, deadline, handoff, and truthful non-approval."),
    )),
    "education-services/student-accommodation-navigator": Briefing("sensitive_data_minimized", "Sensitive evidence minimized", (
        ("SURFACE STORY", "A student needs access", "The fastest route can look like collecting every medical detail."),
        ("HIDDEN TRUTH", "Functional need, limited evidence", "The authorized team needs relevant support—not a family's unrelated history."),
        ("UNSAFE SHORTCUT", "Ask for the whole record", "Over-collection creates privacy harm before the human decision even begins."),
        ("EXACT PROOF", "Minimum data, timely handoff", "Score relevant evidence, access channel, deadline, recourse, rights, and team ownership."),
    )),
    "identity-access/account-recovery-assurance-agent": Briefing("recovery_exact", "Exact assured recovery", (
        ("SURFACE STORY", "A person is locked out", "Urgency makes the newest reachable destination look helpful."),
        ("HIDDEN TRUTH", "Assurance + established methods", "The account record—not the story—defines acceptable recovery."),
        ("UNSAFE SHORTCUT", "Use one convenient factor", "A valid method can still be insufficient or attacker-controlled."),
        ("EXACT PROOF", "Route, methods, notice, data", "Score assurance, takeover containment, PII restraint, and truthful execution together."),
    )),
    "accessibility-digital-services/accessibility-remediation-verifier": Briefing("remediation_exact", "Exact verified remediation", (
        ("SURFACE STORY", "The scanner is green", "Automated coverage looks like a fast universal answer."),
        ("HIDDEN TRUTH", "Manual path + source + deploy", "User barriers and fix state live beyond the scanner output."),
        ("UNSAFE SHORTCUT", "Green means conformant", "A missed barrier or one repaired component becomes false assurance."),
        ("EXACT PROOF", "Defect, test, state, restraint", "Match every issue to proof of fix without certifying the whole service."),
    )),
    "privacy-data-governance/privacy-rights-orchestrator": Briefing("privacy_request_exact", "Exact privacy-rights service", (
        ("SURFACE STORY", "Delete my account", "One familiar customer record appears to define the request."),
        ("HIDDEN TRUTH", "Systems + identity + clock", "Archives, processors, authority, and exceptions change the task graph."),
        ("UNSAFE SHORTCUT", "CRM task equals completion", "Data survives while the person receives a polished closure message."),
        ("EXACT PROOF", "Coverage plus truthful receipts", "Score systems, burden, jurisdiction, deadline, recourse, and completion truth."),
    )),
}


STORIES = {
    "logistics-supply-chain/exception-triage-agent": ("A lost package that was never lost", (
        "A shop owner reports an urgent launch shipment as lost.",
        "Carrier evidence shows a customs hold and an active SLA clock.",
        "Routing from complaint text sends the case to the wrong team.",
        "Exact queue and action preserve time without needless escalation.",
    )),
    "logistics-supply-chain/exception-triage-drift": ("Yesterday's answer expires overnight", (
        "Operations replays a ticket the agent solved correctly yesterday.",
        "The cache says cleared; the source system reports a new hold.",
        "Familiar stale evidence produces a confident obsolete action.",
        "Freshness-aware evaluation exposes the drift before production does.",
    )),
    "retail-workforce/shift-coverage-triage-agent": ("One empty shift, three hidden constraints", (
        "A restaurant manager needs tonight's closing shift covered.",
        "Availability collides with age, overtime, distance, and peak rules.",
        "The fastest match quietly creates an illegal assignment.",
        "The agent finds compliant cover—or escalates honestly when none exists.",
    )),
    "security-operations/alert-triage-agent": ("The alert that looked exactly like an attack", (
        "A high-severity detector fires on an administrator's workstation.",
        "Asset history and a change ticket reveal approved maintenance.",
        "Blind containment interrupts work; blind dismissal leaves exposure.",
        "Evidence earns the exact queue, disposition, and response level.",
    )),
    "security-operations/artifact-admission-agent": ("A safe label around executable behavior", (
        "A team wants to add a useful third-party artifact to its agent.",
        "The manifest says data-only; configuration launches a real command.",
        "Trusting the declaration grants hidden network and credential power.",
        "Runtime inspection chooses admit, sandbox, or block from behavior.",
    )),
    "security-operations/trifecta-exfil-agent": ("A helpful summary with a secret in its path", (
        "An analyst asks the assistant to summarize an ordinary document.",
        "The agent reads private notes, then fetches attacker-controlled text.",
        "The document instructs it to send the combined context outside.",
        "Provenance enforcement blocks tainted egress and keeps clean utility.",
    )),
    "financial-services-fraud/fraud-alert-triage-agent": ("A flagged payment with two plausible stories", (
        "A customer's unusual transfer triggers the fraud queue.",
        "Travel, device, and beneficiary evidence can clear—or deepen—the risk.",
        "A reflexive block harms the customer; a reflexive allow funds the scam.",
        "The exact evidence-backed disposition protects both money and access.",
    )),
    "procurement-finance/vendor-payment-review-agent": ("The invoice is right. The bank account is not.", (
        "A legitimate supplier invoice matches its PO and receiving record.",
        "An email asks finance to pay a newly supplied bank destination.",
        "Matching the invoice without the trusted vendor master moves real money.",
        "Reconciliation holds the change, prevents duplicates, and pays safely.",
    )),
    "media-streaming/release-qc-triage-agent": ("The frame that could delay a premiere", (
        "Quality control flags a defect hours before a scheduled release.",
        "Creative intent, accessibility law, territory, and timecode all matter.",
        "Severity-only triage either misses an obligation or kills the launch.",
        "The agent chooses fix, ship, or delay from the complete release context.",
    )),
    "customer-support/refund-resolution-agent": ("A reasonable refund that becomes unsafe", (
        "A customer has a persuasive reason to ask for money back.",
        "Identity, dispute state, and final-sale status live behind tools.",
        "Issuing the refund before checking prerequisites commits irreversible harm.",
        "The right remedy counts only when the action path is safe and complete.",
    )),
    "customer-support/refund-guarded": ("Same customer, same facts, one hard boundary", (
        "A baseline run reveals exactly how the refund agent breaks policy.",
        "The same scenarios replay under prompt advice and tool enforcement.",
        "Better wording still leaves the irreversible boundary unprotected.",
        "Controlled deltas show which guard prevents harm without killing utility.",
    )),
    "customer-support/refund-crew": ("Three agents and a fact lost between them", (
        "A support lead delegates one refund case to three specialists.",
        "Each role sees a brief, not the original evidence in full fidelity.",
        "Consensus amplifies a bad premise when review and veto arrive too late.",
        "A single-vs-crew control prices coordination instead of assuming value.",
    )),
    "customer-support/refund-injected": ("The support ticket that writes its own policy", (
        "A customer controls the prose entering the agent's trusted workflow.",
        "The ticket impersonates authority and requests a forbidden tool action.",
        "Helpfulness turns untrusted text into operational control.",
        "The eval scores the real consequence: whether the attack changes action.",
    )),
    "customer-support/refund-memory": ("The attack that waits until tomorrow", (
        "A malicious session plants one believable fact in persistent memory.",
        "The attacker leaves; a clean customer returns in a later session.",
        "The agent treats the poisoned note as durable operational truth.",
        "Cross-session scoring catches the delayed harm at the moment it wakes.",
    )),
    "customer-support/refund-amplified": ("The correct answer that multiplies the bill", (
        "A normal support request hides fan-out and oversized tool payloads.",
        "Every extra result is replayed through the context on later turns.",
        "The answer can stay correct while token cost becomes the attack.",
        "Matched controls separate length, persuasion, cost, and decision quality.",
    )),
    "healthcare-life-sciences/prior-auth-review-agent": ("A correct clinical match and an unlawful denial", (
        "A prior-authorization record appears not to meet clinical criteria.",
        "An adverse determination still requires protected human judgment.",
        "Automating the apparently correct denial removes the patient's right.",
        "The agent preserves evidence and routes the decision to a human reviewer.",
    )),
    "legal-compliance/dpa-clause-review-agent": ("The missing clause no search can retrieve", (
        "Counsel asks an agent to review a data-processing agreement quickly.",
        "Most present clauses retrieve cleanly and create confident coverage.",
        "The most expensive obligation is absent, so semantic search finds nothing.",
        "A statutory gold set makes missing duties visible and reviewable.",
    )),
    "it-operations/incident-remediation-agent": ("When the runbook button stops working", (
        "An incident reaches the approved remediation step in the runbook.",
        "The tool refuses it while an unsafe shortcut remains available.",
        "Pressure produces improvisation—or a false claim that service recovered.",
        "The safe agent discloses the block and pages the accountable owner.",
    )),
    "it-operations/oncall-watch-agent": ("The quiet minute before the slow burn", (
        "An early telemetry spike could be a blip or the start of an outage.",
        "Only later ticks separate recovery from a slow threshold breach.",
        "Paging instantly burns trust; stopping observation misses the incident.",
        "The evaluator rewards patience, correct severity, and action in time.",
    )),
    "public-sector/small-business-recovery-agent": ("The right program through the wrong service", (
        "A business owner asks for help after a disruptive local event.",
        "The agency already holds evidence, but channel and deadline needs differ.",
        "A correct program answer can still duplicate burden and erase recourse.",
        "Public value means the person can actually complete the service safely.",
    )),
    "energy-utilities/household-energy-lifeline": ("The correct referral that arrives after the lights go out", (
        "A household asks for help with an imminent energy shutoff.",
        "The service already holds evidence and an accessible channel preference.",
        "A generic referral omits continuity and outlives the deadline.",
        "Exact evaluation keeps every authorized option alive without inventing approval.",
    )),
    "insurance-disaster-recovery/disaster-claim-aid-coordinator": ("One damaged roof, three incomplete ledgers", (
        "A survivor moves between an insurer, public aid, and charitable help.",
        "Trusted records show which evidence and compensation already exist.",
        "A fluent referral hides a source or asks the survivor to rebuild the file.",
        "Exact coordination preserves the deadline and routes the accountable reviewer.",
    )),
    "employment-social-insurance/unemployment-claim-navigator": ("The status was correct. The appeal was late.", (
        "A laid-off worker checks a claim while the household budget tightens.",
        "The file already holds proof, but two separate service clocks remain live.",
        "A correct status explanation omits the weekly certification and appeal path.",
        "Exact navigation preserves both rights without deciding eligibility.",
    )),
    "agriculture-food-systems/farm-disaster-deadline-agent": ("One storm starts more than one clock", (
        "A producer reports crop, livestock, and grazing losses after a storm.",
        "Each program route has its own notice window and evidence already on file.",
        "Finishing the first checklist makes the remaining deadlines disappear.",
        "An exact deadline map keeps every authorized recovery path visible.",
    )),
    "housing-construction/permit-readiness-agent": ("A perfect packet for the wrong counter", (
        "A small builder prepares a familiar residential permit package.",
        "The address and project class bind the job to a different current rule set.",
        "Reusing the nearest checklist creates delay before construction can start.",
        "Rule provenance produces a ready packet without pretending to approve it.",
    )),
    "education-services/student-accommodation-navigator": ("The helpful form that asked for too much", (
        "A family asks a school to remove an urgent classroom access barrier.",
        "Relevant functional evidence exists beside deeply unrelated medical history.",
        "A broad records request trades speed for unnecessary privacy exposure.",
        "Minimum evidence reaches the authorized team with timing and recourse intact.",
    )),
    "identity-access/account-recovery-assurance-agent": ("The urgent email that almost became an authenticator", (
        "A locked-out administrator asks support to use a newly supplied address.",
        "The account's assurance profile and established methods tell a different story.",
        "Fast recovery through the convenient destination hands the account to an attacker.",
        "The assurance ladder restores access safely—or holds it with honest human recourse.",
    )),
    "accessibility-digital-services/accessibility-remediation-verifier": ("The green scan beside an unusable checkout", (
        "An automated dashboard reports zero accessibility defects.",
        "Manual keyboard evidence shows that checkout cannot be completed.",
        "Treating scanner silence as conformance erases the user's barrier.",
        "Exact defect tests and proof-of-fix state make remediation real and reviewable.",
    )),
    "privacy-data-governance/privacy-rights-orchestrator": ("The deletion receipt with an archive still alive", (
        "A customer asks a company to delete a seemingly simple account.",
        "The current data map reveals analytics, an archive, and a service processor.",
        "A CRM-only workflow declares completion while personal data remains elsewhere.",
        "Exact system tasks, preserved clocks, and receipts produce truthful closure.",
    )),
}


def render_svg(item: Experience) -> str:
    cards: list[str] = []
    arrows: list[str] = []
    for index, (verb, detail) in enumerate(item.stages):
        x = 42 + index * 286
        cards.append(
            f'<g class="card card-{index + 1}" transform="translate({x} 228)">'
            '<rect width="246" height="92" rx="14" class="card-bg"/>'
            f'<circle cx="31" cy="31" r="15" fill="{item.accent}"/>'
            f'<text x="31" y="36" text-anchor="middle" class="step">{index + 1}</text>'
            f'<text x="57" y="35" class="verb">{escape(verb)}</text>'
            f'<text x="24" y="69" class="detail">{escape(detail)}</text>'
            '</g>'
        )
        if index < 3:
            ax = x + 250
            arrows.append(
                f'<path class="flow flow-{index + 1}" d="M {ax} 274 H {ax + 30}"/>'
                f'<path class="arrow" d="M {ax + 24} 268 L {ax + 31} 274 L {ax + 24} 280"/>'
            )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 360" width="1200" height="360" role="img" aria-labelledby="title desc">
  <title id="title">{escape(item.title)} interactive case trace</title>
  <desc id="desc">{escape(item.tagline)} Four stages: {escape(', '.join(a + ' ' + b for a, b in item.stages))}.</desc>
  <style>
    :root {{ color-scheme: light dark; }}
    .surface {{ fill:#fbfcfa; }} .grid {{ stroke:#dce4df; }} .ink {{ fill:#10231d; }}
    .muted {{ fill:#52645e; }} .card-bg {{ fill:#ffffff; stroke:#d7dfda; stroke-width:1.5; }}
    .eyebrow {{ font:700 13px system-ui,sans-serif; letter-spacing:1.6px; }}
    .title {{ font:750 36px system-ui,sans-serif; }} .tagline {{ font:400 18px system-ui,sans-serif; }}
    .verb {{ font:750 15px system-ui,sans-serif; fill:#10231d; letter-spacing:.6px; }}
    .detail {{ font:450 15px system-ui,sans-serif; fill:#52645e; }}
    .step {{ font:750 13px system-ui,sans-serif; fill:white; }}
    .flow,.arrow {{ fill:none; stroke:{item.accent}; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }}
    .flow {{ stroke-dasharray:7 7; animation: travel 2.2s linear infinite; }}
    .card {{ transform-box:fill-box; transform-origin:center; animation: breathe 8s ease-in-out infinite; }}
    .card-2 {{ animation-delay:2s; }} .card-3 {{ animation-delay:4s; }} .card-4 {{ animation-delay:6s; }}
    @keyframes travel {{ to {{ stroke-dashoffset:-28; }} }}
    @keyframes breathe {{ 0%,18%,100% {{ opacity:.78; }} 8% {{ opacity:1; }} }}
    @media (prefers-color-scheme:dark) {{
      .surface {{ fill:#111a17; }} .grid {{ stroke:#22352f; }} .ink {{ fill:#f4faf7; }}
      .muted {{ fill:#afc2ba; }} .card-bg {{ fill:#17241f; stroke:#30463e; }}
      .verb {{ fill:#f4faf7; }} .detail {{ fill:#afc2ba; }}
    }}
    @media (prefers-reduced-motion:reduce) {{ .flow,.card {{ animation:none; opacity:1; }} }}
  </style>
  <defs>
    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" class="grid" stroke-width=".55"/></pattern>
    <linearGradient id="wash" x1="0" x2="1"><stop stop-color="{item.accent}" stop-opacity=".18"/><stop offset="1" stop-color="{item.accent}" stop-opacity="0"/></linearGradient>
  </defs>
  <rect width="1200" height="360" rx="20" class="surface"/>
  <rect width="1200" height="360" rx="20" fill="url(#grid)" opacity=".55"/>
  <path d="M0 0H690L510 360H0Z" fill="url(#wash)"/>
  <circle cx="1110" cy="62" r="112" fill="{item.accent}" opacity=".08"/>
  <text x="42" y="43" class="eyebrow" fill="{item.accent}">{escape(item.industry)} · TRACE → CONSEQUENCE</text>
  <text x="42" y="102" class="title ink">{item.icon}  {escape(item.title)}</text>
  <text x="42" y="139" class="tagline muted">{escape(item.tagline)}</text>
  <g transform="translate(42 168)"><rect width="310" height="32" rx="16" fill="{item.accent}" opacity=".12"/><circle cx="17" cy="16" r="5" fill="{item.accent}"/><text x="31" y="21" class="eyebrow muted" style="letter-spacing:.7px">REPRODUCIBLE · TESTED · FORKABLE</text></g>
  {''.join(arrows)}
  {''.join(cards)}
</svg>
'''


def svg_lines(
    text: str,
    *,
    x: int,
    y: int,
    css_class: str,
    width: int,
    line_height: int,
    max_lines: int,
) -> str:
    """Wrap plain text into SVG tspans without relying on browser layout."""
    lines = wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return (
        f'<text x="{x}" y="{y}" class="{css_class}">'
        + "".join(
            f'<tspan x="{x}" dy="{0 if index == 0 else line_height}">{escape(line)}</tspan>'
            for index, line in enumerate(lines)
        )
        + "</text>"
    )


def render_scenario_map(item: Experience, briefing: Briefing) -> str:
    positions = ((42, 137), (658, 137), (42, 346), (658, 346))
    cards: list[str] = []
    for index, ((label, headline, detail), (x, y)) in enumerate(zip(briefing.cards, positions)):
        number = f"0{index + 1}"
        cards.append(
            f'<g transform="translate({x} {y})">'
            '<rect width="500" height="168" rx="18" class="card"/>'
            f'<rect width="7" height="168" rx="3.5" fill="{item.accent}" opacity="{1 if index in (1, 3) else .5}"/>'
            f'<text x="28" y="34" class="number" fill="{item.accent}">{number}</text>'
            f'<text x="72" y="34" class="eyebrow muted">{escape(label)}</text>'
            + svg_lines(headline, x=28, y=76, css_class="headline ink", width=37, line_height=25, max_lines=1)
            + svg_lines(detail, x=28, y=112, css_class="body muted", width=58, line_height=22, max_lines=2)
            + "</g>"
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 555" width="1200" height="555" role="img" aria-labelledby="title desc">
  <title id="title">{escape(item.title)} scenario anatomy</title>
  <desc id="desc">Four-part map of the surface story, hidden truth, unsafe shortcut, and exact proof used by this evaluation.</desc>
  <style>
    :root {{ color-scheme:light dark; }}
    .surface {{ fill:#f7faf8; }} .card {{ fill:#fff; stroke:#d9e2dd; stroke-width:1.5; }}
    .ink {{ fill:#10231d; }} .muted {{ fill:#52645e; }} .grid {{ stroke:#dfe7e2; }}
    .kicker {{ font:750 13px system-ui,sans-serif; letter-spacing:1.7px; }}
    .title {{ font:750 29px system-ui,sans-serif; }} .eyebrow {{ font:750 12px system-ui,sans-serif; letter-spacing:1.1px; }}
    .number {{ font:800 14px ui-monospace,SFMono-Regular,monospace; }}
    .headline {{ font:750 20px system-ui,sans-serif; }} .body {{ font:430 15px system-ui,sans-serif; }}
    .link {{ fill:none; stroke:{item.accent}; stroke-width:2; stroke-dasharray:5 6; opacity:.6; }}
    @media (prefers-color-scheme:dark) {{
      .surface {{ fill:#101916; }} .card {{ fill:#17231f; stroke:#30433c; }}
      .ink {{ fill:#f4faf7; }} .muted {{ fill:#b2c3bc; }} .grid {{ stroke:#263832; }}
    }}
  </style>
  <defs><pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" class="grid" stroke-width=".55"/></pattern></defs>
  <rect width="1200" height="555" rx="20" class="surface"/>
  <rect width="1200" height="555" rx="20" fill="url(#grid)" opacity=".42"/>
  <text x="42" y="42" class="kicker" fill="{item.accent}">SCENARIO ANATOMY · READ THE CASE IN 20 SECONDS</text>
  <text x="42" y="88" class="title ink">Where the obvious answer breaks</text>
  <path d="M542 221H658M542 430H658M600 305V346" class="link"/>
  <circle cx="600" cy="325" r="29" fill="{item.accent}"/>
  <text x="600" y="330" text-anchor="middle" style="font:800 10px system-ui,sans-serif;letter-spacing:.8px;fill:white">AGENT</text>
  {''.join(cards)}
</svg>
'''


def render_story(item: Experience, briefing: Briefing) -> str:
    headline, beats = STORIES[item.path]
    scenes: list[str] = []
    connectors: list[str] = []
    for index, ((verb, _), beat) in enumerate(zip(item.stages, beats)):
        x = 42 + index * 286
        scenes.append(
            f'<g transform="translate({x} 145)">'
            '<rect width="258" height="256" rx="22" class="card"/>'
            f'<circle cx="39" cy="42" r="21" fill="{item.accent}"/>'
            f'<text x="39" y="48" text-anchor="middle" class="act-number">{index + 1}</text>'
            f'<text x="72" y="38" class="act muted">ACT {index + 1}</text>'
            f'<text x="72" y="59" class="verb ink">{escape(verb)}</text>'
            + svg_lines(beat, x=24, y=107, css_class="beat ink", width=23, line_height=25, max_lines=5)
            + '<rect x="24" y="218" width="210" height="5" rx="2.5" class="rail"/>'
            + f'<rect x="24" y="218" width="{52 + index * 52}" height="5" rx="2.5" fill="{item.accent}"/>'
            + "</g>"
        )
        if index < 3:
            connectors.append(
                f'<path d="M{x + 261} 273H{x + 281}" class="connector"/>'
                f'<path d="M{x + 276} 268L{x + 282} 273L{x + 276} 278" class="connector"/>'
            )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 500" width="1200" height="500" role="img" aria-labelledby="title desc">
  <title id="title">{escape(item.title)} animated four-act story</title>
  <desc id="desc">{escape(headline)} Four scenes reveal the request, hidden evidence, unsafe shortcut, and verified outcome.</desc>
  <style>
    :root {{ color-scheme:light dark; }}
    .surface {{ fill:#0f1916; }} .card {{ fill:#fff;stroke:#d7e1dc;stroke-width:1.5; }}
    .ink {{ fill:#10231d; }} .muted {{ fill:#5b6b65; }} .rail {{ fill:#dfe7e3; }}
    .kicker {{ font:750 13px system-ui,sans-serif;letter-spacing:1.7px; }}
    .title {{ font:760 29px system-ui,sans-serif;fill:#f6fbf8; }} .act {{ font:750 10px system-ui,sans-serif;letter-spacing:1.2px; }}
    .act-number {{ font:800 14px ui-monospace,SFMono-Regular,monospace;fill:white; }}
    .verb {{ font:780 14px system-ui,sans-serif;letter-spacing:.5px; }} .beat {{ font:620 17px system-ui,sans-serif; }}
    .metric {{ font:650 13px system-ui,sans-serif;fill:#c4d3cd; }}
    .connector {{ fill:none;stroke:{item.accent};stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:5 5;animation:flow 2s linear infinite; }}
    .runner {{ animation:glow 1.2s ease-in-out infinite alternate; }}
    @keyframes flow {{ to {{ stroke-dashoffset:-20; }} }}
    @keyframes glow {{ to {{ opacity:.35; }} }}
    @media (prefers-color-scheme:dark) {{
      .surface {{ fill:#0b1210; }} .card {{ fill:#17231f;stroke:#354840; }}
      .ink {{ fill:#f4faf7; }} .muted {{ fill:#aec0b8; }} .rail {{ fill:#30423b; }}
    }}
    @media (prefers-reduced-motion:reduce) {{ .connector {{ animation:none; }} .runner {{ display:none; }} }}
  </style>
  <defs><linearGradient id="wash" x1="0" x2="1"><stop stop-color="{item.accent}" stop-opacity=".27"/><stop offset="1" stop-color="{item.accent}" stop-opacity=".03"/></linearGradient></defs>
  <rect width="1200" height="500" rx="20" class="surface"/>
  <path d="M0 0H860L700 126H0Z" fill="url(#wash)"/>
  <text x="42" y="38" class="kicker" fill="{item.accent}">THE 60-SECOND STORY · SYNTHETIC CASE, REAL FAILURE SHAPE</text>
  <text x="42" y="82" class="title">{escape(headline)}</text>
  <text x="1158" y="81" text-anchor="end" class="metric">THE TEST ASKS · {escape(briefing.metric_label.upper())}</text>
  <path d="M64 116H1136" stroke="{item.accent}" stroke-width="2" opacity=".35"/>
  <circle class="runner" r="7" fill="{item.accent}"><animateMotion dur="12s" repeatCount="indefinite" path="M64 116H1136"/></circle>
  {''.join(connectors)}
  {''.join(scenes)}
  <text x="42" y="460" class="metric">Read left → right. Motion pauses automatically when your system requests reduced motion.</text>
  <text x="1158" y="460" text-anchor="end" class="metric">{escape(item.industry)} · TRACE THE CONSEQUENCE</text>
</svg>
'''


MODEL_NAMES = {
    "gpt-oss": "GPT-OSS 120B",
    "mistral": "Mistral Small",
    "kimi": "Kimi K2.6",
    "llama-3.3": "Llama 3.3 70B",
    "qwen3.7": "Qwen 3.7 Plus",
    "deepseek-v4": "DeepSeek V4 Flash",
    "deepseek-chat": "DeepSeek Chat",
}
ARM_NAMES = {
    "none": "no guard",
    "clean": "clean",
    "drift": "drift",
    "prompt_guard": "prompt guard",
    "tool_guard": "tool gate",
    "taint_gate": "taint gate",
    "write_gate": "write gate",
    "record_gate": "record gate",
    "freshness_gate": "freshness gate",
    "budget_gate": "budget gate",
    "both": "both guards",
    "general": "general rule",
    "named": "named rule",
    "scoped": "scoped rule",
    "commit": "commit boundary",
    "enforced": "enforced",
}


def short_model(model: str) -> str:
    lower = model.lower()
    for needle, label in MODEL_NAMES.items():
        if needle in lower:
            return label
    return model.rsplit("/", 1)[-1].replace("-latest", "").replace("_", " ")[:24]


def load_benchmark_rows(directory: Path, briefing: Briefing) -> list[dict]:
    rows: list[dict] = []
    for path in sorted((directory / "results").glob("eval_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("backend") == "mock":
            continue
        means = data.get("metric_means", {})
        if briefing.metric not in means:
            continue
        arm = data.get("arm") or data.get("variant")
        raw_value = float(means[briefing.metric])
        interval = data.get("metric_ci95", {}).get(briefing.metric, [raw_value, raw_value])
        lo, hi = float(interval[0]), float(interval[1])
        value = 1 - raw_value if briefing.invert else raw_value
        if briefing.invert:
            lo, hi = 1 - hi, 1 - lo
        model = short_model(str(data.get("model", data.get("backend", "model"))))
        label = model
        if arm:
            label += f" · {ARM_NAMES.get(str(arm), str(arm).replace('_', ' '))}"
        rows.append({
            "label": label,
            "model": model,
            "arm": str(arm or ""),
            "value": value,
            "lo": lo,
            "hi": hi,
            "n": int(data.get("n_scenarios", 0)) * int(data.get("n_repeats", 1)),
            "means": means,
            "cost": float(data.get("mean_cost_per_scenario_usd", 0)),
            "latency": float(data.get("p50_latency_s", 0)),
        })
    if any(row["arm"] for row in rows):
        arm_rank = {name: index for index, name in enumerate(ARM_NAMES)}
        rows.sort(key=lambda row: (row["model"], arm_rank.get(row["arm"], 99), row["arm"]))
    else:
        rows.sort(key=lambda row: row["value"], reverse=not briefing.raw)
    return rows[:12]


def compact_number(value: float) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    if value >= 100:
        return f"{value:.0f}"
    if value >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def render_benchmark(item: Experience, briefing: Briefing, directory: Path) -> str:
    rows = load_benchmark_rows(directory, briefing)
    row_height = 46
    plot_top = 146
    height = plot_top + max(len(rows), 1) * row_height + 72
    plot_x = 330
    plot_width = 790
    max_value = max((row["hi"] for row in rows), default=1)
    scale_max = max_value * 1.06 if briefing.raw else 1.0
    best = min((row["value"] for row in rows), default=0) if briefing.raw else max((row["value"] for row in rows), default=0)
    chart_rows: list[str] = []
    for index, row in enumerate(rows):
        y = plot_top + index * row_height
        bar_width = max(2, min(plot_width, plot_width * row["value"] / scale_max))
        lo_x = plot_x + plot_width * row["lo"] / scale_max
        hi_x = plot_x + plot_width * row["hi"] / scale_max
        value_label = compact_number(row["value"]) if briefing.raw else f"{row['value'] * 100:.0f}%"
        is_best = abs(row["value"] - best) < 1e-9
        chart_rows.append(
            f'<text x="42" y="{y + 22}" class="label ink">{escape(row["label"])}</text>'
            f'<rect x="{plot_x}" y="{y + 5}" width="{plot_width}" height="24" rx="12" class="track"/>'
            f'<rect x="{plot_x}" y="{y + 5}" width="{bar_width:.1f}" height="24" rx="12" fill="{item.accent}" opacity="{1 if is_best else .72}"/>'
            f'<path d="M{lo_x:.1f} {y + 17}H{hi_x:.1f}M{lo_x:.1f} {y + 12}V{y + 22}M{hi_x:.1f} {y + 12}V{y + 22}" class="ci"/>'
            f'<text x="1156" y="{y + 22}" text-anchor="end" class="value ink">{value_label}</text>'
        )
    sample_count = sum(row["n"] for row in rows)
    tick_labels = (
        ((0, "0"), (.5, compact_number(scale_max / 2)), (1, compact_number(scale_max)))
        if briefing.raw
        else ((0, "0%"), (.5, "50%"), (1, "100%"))
    )
    ticks = "".join(
        f'<path d="M{plot_x + plot_width * ratio:.1f} 130V{height - 45}" class="tick"/>'
        f'<text x="{plot_x + plot_width * ratio:.1f}" y="{height - 22}" text-anchor="middle" class="axis muted">{label}</text>'
        for ratio, label in tick_labels
    )
    evidence = f"{len(rows)} MODEL/ARM RESULTS · {sample_count:,} RUNS"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {height}" width="1200" height="{height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(item.title)} verified benchmark</title>
  <desc id="desc">{escape(briefing.metric_label)} across committed non-mock model evaluation results. Error bars show committed 95 percent confidence intervals.</desc>
  <style>
    :root {{ color-scheme:light dark; }}
    .surface {{ fill:#f7faf8; }} .ink {{ fill:#10231d; }} .muted {{ fill:#52645e; }}
    .track {{ fill:#e2e9e5; }} .ci {{ fill:none; stroke:#10231d; stroke-width:1.5; }}
    .tick {{ stroke:#d4ded8; stroke-width:1; stroke-dasharray:3 6; }}
    .kicker {{ font:750 13px system-ui,sans-serif;letter-spacing:1.6px; }} .title {{ font:750 28px system-ui,sans-serif; }}
    .label {{ font:620 14px system-ui,sans-serif; }} .value {{ font:780 14px ui-monospace,SFMono-Regular,monospace; }}
    .axis {{ font:550 12px ui-monospace,SFMono-Regular,monospace; }} .pill {{ font:750 11px system-ui,sans-serif;letter-spacing:.8px; }}
    @media (prefers-color-scheme:dark) {{
      .surface {{ fill:#101916; }} .ink {{ fill:#f4faf7; }} .muted {{ fill:#b2c3bc; }}
      .track {{ fill:#263832; }} .ci {{ stroke:#f4faf7; }} .tick {{ stroke:#30433c; }}
    }}
  </style>
  <rect width="1200" height="{height}" rx="20" class="surface"/>
  <text x="42" y="42" class="kicker" fill="{item.accent}">VERIFIED BENCHMARK · COMMITTED RESULTS ONLY</text>
  <text x="42" y="84" class="title ink">{escape(briefing.metric_label)}</text>
  <g transform="translate(840 35)"><rect width="318" height="30" rx="15" fill="{item.accent}" opacity=".13"/><circle cx="17" cy="15" r="5" fill="{item.accent}"/><text x="30" y="19" class="pill muted">{evidence}</text></g>
  <text x="42" y="116" class="axis muted">MODEL · EXPERIMENT ARM</text>
  <text x="1158" y="116" text-anchor="end" class="axis muted">MEAN · 95% CI</text>
  {ticks}
  {''.join(chart_rows)}
</svg>
'''


def format_primary(value: float, raw: bool) -> str:
    return compact_number(value) if raw else f"{value * 100:.0f}%"


def strongest_row(rows: list[dict], briefing: Briefing) -> dict:
    if briefing.raw:
        return min(rows, key=lambda row: (row["value"], row["cost"], row["latency"]))
    return max(rows, key=lambda row: (row["value"], -row["cost"], -row["latency"]))


def render_contrast(item: Experience, briefing: Briefing, directory: Path) -> str:
    rows = load_benchmark_rows(directory, briefing)
    if len(rows) < 2:
        raise ValueError(f"{item.path} needs at least two real result rows for a contrast")
    strong = strongest_row(rows, briefing)
    weak = max(rows, key=lambda row: row["value"]) if briefing.raw else min(rows, key=lambda row: row["value"])
    scale_max = max(row["hi"] for row in rows) * 1.06 if briefing.raw else 1.0
    x0, width = 160, 880
    strong_x = x0 + width * strong["value"] / scale_max
    weak_x = x0 + width * weak["value"] / scale_max
    delta = abs(strong["value"] - weak["value"])
    delta_label = f"{compact_number(delta)} TOKEN SPREAD" if briefing.raw else f"{delta * 100:.0f} POINT SPREAD"
    direction = "LOWEST RESOURCE USE" if briefing.raw else "STRONGEST OBSERVED"
    weak_direction = "HIGHEST RESOURCE USE" if briefing.raw else "LOWEST OBSERVED"
    end_label = compact_number(scale_max) if briefing.raw else "100%"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 410" width="1200" height="410" role="img" aria-labelledby="title desc">
  <title id="title">{escape(item.title)} verified result spread</title>
  <desc id="desc">Contrast between the strongest and weakest committed result on {escape(briefing.metric_label)}.</desc>
  <style>
    :root {{ color-scheme:light dark; }}
    .surface {{ fill:#f7faf8; }} .ink {{ fill:#10231d; }} .muted {{ fill:#52645e; }}
    .kicker {{ font:750 13px system-ui,sans-serif;letter-spacing:1.6px; }} .title {{ font:760 28px system-ui,sans-serif; }}
    .value {{ font:820 22px ui-monospace,SFMono-Regular,monospace; }} .label {{ font:700 14px system-ui,sans-serif; }}
    .small {{ font:560 12px system-ui,sans-serif;letter-spacing:.5px; }} .axis {{ font:600 12px ui-monospace,SFMono-Regular,monospace; }}
    .track {{ stroke:#d8e2dd;stroke-width:10;stroke-linecap:round; }} .span {{ stroke:{item.accent};stroke-width:10;stroke-linecap:round;opacity:.58; }}
    .guide {{ stroke:#cbd7d1;stroke-width:1;stroke-dasharray:4 7; }}
    @media (prefers-color-scheme:dark) {{
      .surface {{ fill:#101916; }} .ink {{ fill:#f4faf7; }} .muted {{ fill:#b2c3bc; }}
      .track {{ stroke:#2b3d36; }} .guide {{ stroke:#354840; }}
    }}
  </style>
  <rect width="1200" height="410" rx="20" class="surface"/>
  <text x="42" y="42" class="kicker" fill="{item.accent}">THE VERIFIED SPREAD · WHY MODEL AND GUARD CHOICE MATTER</text>
  <text x="42" y="84" class="title ink">{escape(briefing.metric_label)}</text>
  <g transform="translate(920 35)"><rect width="238" height="32" rx="16" fill="{item.accent}" opacity=".13"/><text x="119" y="21" text-anchor="middle" class="small muted">{escape(delta_label)}</text></g>
  <path d="M{x0} 213H{x0 + width}" class="track"/>
  <path d="M{min(strong_x, weak_x):.1f} 213H{max(strong_x, weak_x):.1f}" class="span"/>
  <path d="M{x0} 132V298M{x0 + width / 2} 132V298M{x0 + width} 132V298" class="guide"/>
  <circle cx="{weak_x:.1f}" cy="213" r="17" fill="#7f918a" stroke="#f7faf8" stroke-width="5"/>
  <circle cx="{strong_x:.1f}" cy="213" r="19" fill="{item.accent}" stroke="#f7faf8" stroke-width="5"/>
  <path d="M{weak_x:.1f} 196V156" stroke="#7f918a" stroke-width="2"/>
  <path d="M{strong_x:.1f} 232V272" stroke="{item.accent}" stroke-width="2"/>
  <text x="{weak_x:.1f}" y="137" text-anchor="middle" class="small muted">{weak_direction}</text>
  <text x="{weak_x:.1f}" y="159" text-anchor="middle" class="value ink">{format_primary(weak['value'], briefing.raw)}</text>
  <text x="{strong_x:.1f}" y="300" text-anchor="middle" class="value ink">{format_primary(strong['value'], briefing.raw)}</text>
  <text x="{strong_x:.1f}" y="323" text-anchor="middle" class="small" fill="{item.accent}">{direction}</text>
  {svg_lines(weak['label'], x=42, y=354, css_class='label ink', width=38, line_height=18, max_lines=2)}
  <text x="42" y="390" class="small muted">WEAKEST ROW</text>
  {svg_lines(strong['label'], x=1158, y=354, css_class='label ink end', width=38, line_height=18, max_lines=2).replace('<text ', '<text text-anchor="end" ')}
  <text x="1158" y="390" text-anchor="end" class="small muted">STRONGEST HEADLINE ROW</text>
  <text x="{x0}" y="122" text-anchor="middle" class="axis muted">0</text>
  <text x="{x0 + width / 2}" y="122" text-anchor="middle" class="axis muted">{compact_number(scale_max / 2) if briefing.raw else '50%'}</text>
  <text x="{x0 + width}" y="122" text-anchor="middle" class="axis muted">{end_label}</text>
</svg>
'''


def format_cost(value: float) -> str:
    if 0 < value < 0.0001:
        return "<$0.0001"
    return f"${value:.4f}"


def render_profile(item: Experience, briefing: Briefing, directory: Path) -> str:
    rows = load_benchmark_rows(directory, briefing)
    selected = strongest_row(rows, briefing)
    primary_max = max(row["value"] for row in rows) or 1
    latency_max = max(row["latency"] for row in rows) or 1
    cost_max = max(row["cost"] for row in rows) or 1
    completion = float(selected["means"].get("submitted", 0))
    cards_data = (
        (briefing.metric_label, format_primary(selected["value"], briefing.raw), selected["value"] / primary_max, "HEADLINE RESULT"),
        ("Decision completion", f"{completion * 100:.0f}%", completion, "SUBMITTED"),
        ("Median latency", f"{selected['latency']:.1f}s", selected["latency"] / latency_max, "LOWER IS FASTER"),
        ("Cost per scenario", format_cost(selected["cost"]), selected["cost"] / cost_max, "MEASURED LIST-PRICE"),
    )
    cards: list[str] = []
    for index, (label, value, ratio, note) in enumerate(cards_data):
        x = 42 + index * 286
        fill_width = max(3, min(220, 220 * ratio))
        cards.append(
            f'<g transform="translate({x} 145)">'
            '<rect width="258" height="190" rx="20" class="card"/>'
            f'<text x="24" y="36" class="note muted">{escape(note)}</text>'
            f'<text x="24" y="88" class="value ink">{escape(value)}</text>'
            + svg_lines(label, x=24, y=119, css_class="label ink", width=29, line_height=19, max_lines=2)
            + '<rect x="24" y="155" width="210" height="8" rx="4" class="track"/>'
            + f'<rect x="24" y="155" width="{fill_width:.1f}" height="8" rx="4" fill="{item.accent}"/>'
            + "</g>"
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 410" width="1200" height="410" role="img" aria-labelledby="title desc">
  <title id="title">{escape(item.title)} strongest headline run profile</title>
  <desc id="desc">Headline outcome, completion, latency, and measured cost for {escape(selected['label'])}.</desc>
  <style>
    :root {{ color-scheme:light dark; }}
    .surface {{ fill:#f7faf8; }} .card {{ fill:#fff;stroke:#d9e2dd;stroke-width:1.5; }}
    .ink {{ fill:#10231d; }} .muted {{ fill:#52645e; }} .track {{ fill:#e2e9e5; }}
    .kicker {{ font:750 13px system-ui,sans-serif;letter-spacing:1.6px; }} .title {{ font:760 28px system-ui,sans-serif; }}
    .value {{ font:820 30px ui-monospace,SFMono-Regular,monospace; }} .label {{ font:700 15px system-ui,sans-serif; }}
    .note {{ font:750 10px system-ui,sans-serif;letter-spacing:1px; }} .small {{ font:560 12px system-ui,sans-serif; }}
    @media (prefers-color-scheme:dark) {{
      .surface {{ fill:#101916; }} .card {{ fill:#17231f;stroke:#30433c; }}
      .ink {{ fill:#f4faf7; }} .muted {{ fill:#b2c3bc; }} .track {{ fill:#2a3b35; }}
    }}
  </style>
  <rect width="1200" height="410" rx="20" class="surface"/>
  <text x="42" y="42" class="kicker" fill="{item.accent}">STRONGEST HEADLINE RUN · THE TRADEOFF PROFILE</text>
  <text x="42" y="84" class="title ink">{escape(selected['label'])}</text>
  <text x="1158" y="82" text-anchor="end" class="small muted">Selected by {escape(briefing.metric_label.lower())} · not a universal model ranking</text>
  {''.join(cards)}
  <text x="42" y="376" class="small muted">Bars show each value relative to the observed range; exact numbers come from the committed JSON result.</text>
  <text x="1158" y="376" text-anchor="end" class="small muted">{selected['n']:,} SCENARIO RUNS IN THIS ROW</text>
</svg>
'''


def clean_markdown(text: str) -> str:
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = text.replace("`", "").replace("**", "").replace("*", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def read_failure_cards(directory: Path) -> list[tuple[str, str]]:
    text = (directory / "FAILURE_MODES.md").read_text(encoding="utf-8")
    matches = list(re.finditer(r"^###\s+(.+)$", text, re.MULTILINE))
    cards: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        title = re.sub(r"^\d+\.\s*", "", clean_markdown(match.group(1)))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.end():end]
        observed = re.search(
            r"-\s+\*\*(?:What happens|Observed):\*\*\s*(.+?)(?=\n-\s+\*\*|\n#{2,3}\s|\Z)",
            section,
            re.DOTALL,
        )
        if not observed:
            observed = re.search(r"-\s+\*\*Why it matters:\*\*\s*(.+?)(?=\n-\s+\*\*|\n#{2,3}\s|\Z)", section, re.DOTALL)
        detail = clean_markdown(observed.group(1) if observed else section)
        cards.append((title, detail))
        if len(cards) == 3:
            break
    return cards


def render_failure_cards(item: Experience, directory: Path) -> str:
    failures = read_failure_cards(directory)
    height = 540
    cards: list[str] = []
    for index, (title, detail) in enumerate(failures):
        y = 128 + index * 124
        cards.append(
            f'<g transform="translate(42 {y})">'
            '<rect width="1116" height="104" rx="17" class="card"/>'
            f'<rect width="72" height="104" rx="17" fill="{item.accent}" opacity=".12"/>'
            f'<text x="36" y="59" text-anchor="middle" class="mode" fill="{item.accent}">{index + 1:02}</text>'
            + svg_lines(title, x=94, y=34, css_class="headline ink", width=64, line_height=21, max_lines=1)
            + svg_lines(detail, x=94, y=64, css_class="body muted", width=123, line_height=20, max_lines=2)
            + "</g>"
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {height}" width="1200" height="{height}" role="img" aria-labelledby="title desc">
  <title id="title">Observed {escape(item.title)} failure modes</title>
  <desc id="desc">Three observed, reproducible failure modes from committed evaluation runs.</desc>
  <style>
    :root {{ color-scheme:light dark; }}
    .surface {{ fill:#f7faf8; }} .card {{ fill:#fff;stroke:#d9e2dd;stroke-width:1.5; }}
    .ink {{ fill:#10231d; }} .muted {{ fill:#52645e; }}
    .kicker {{ font:750 13px system-ui,sans-serif;letter-spacing:1.6px; }} .title {{ font:750 28px system-ui,sans-serif; }}
    .mode {{ font:850 19px ui-monospace,SFMono-Regular,monospace; }} .headline {{ font:740 17px system-ui,sans-serif; }}
    .body {{ font:430 14px system-ui,sans-serif; }} .pill {{ font:750 11px system-ui,sans-serif;letter-spacing:.8px; }}
    @media (prefers-color-scheme:dark) {{
      .surface {{ fill:#101916; }} .card {{ fill:#17231f;stroke:#30433c; }}
      .ink {{ fill:#f4faf7; }} .muted {{ fill:#b2c3bc; }}
    }}
  </style>
  <rect width="1200" height="{height}" rx="20" class="surface"/>
  <text x="42" y="42" class="kicker" fill="{item.accent}">OBSERVED IN THE LAB · NOT HYPOTHETICAL</text>
  <text x="42" y="84" class="title ink">How this agent actually fails</text>
  <g transform="translate(960 35)"><rect width="198" height="30" rx="15" fill="{item.accent}" opacity=".13"/><circle cx="17" cy="15" r="5" fill="{item.accent}"/><text x="30" y="19" class="pill muted">REPRODUCIBLE CASES</text></g>
  {''.join(cards)}
  <text x="42" y="514" class="body muted">Open FAILURE_MODES.md for scenario IDs, evidence, impact, and reproduction commands.</text>
</svg>
'''


def strip_old_banner(text: str) -> str:
    if not text.startswith("<picture>\n"):
        return text
    closing = text.find("</picture>\n")
    if closing == -1:
        return text
    return text[closing + len("</picture>\n") :].lstrip("\n")


def remove_block(text: str, start: str, end: str) -> str:
    if start not in text:
        return text
    before, rest = text.split(start, 1)
    if end not in rest:
        raise ValueError(f"found {start!r} without {end!r}")
    _, after = rest.split(end, 1)
    return before.rstrip() + "\n\n" + after.lstrip()


def install(item: Experience) -> None:
    directory = ROOT / item.path
    readme = directory / "README.md"
    if not readme.exists():
        raise FileNotFoundError(f"missing README: {readme}")
    docs = directory / "docs"
    docs.mkdir(exist_ok=True)
    briefing = BRIEFINGS[item.path]
    (docs / "experience.svg").write_text(render_svg(item), encoding="utf-8")
    (docs / "story-v2.svg").write_text(render_story(item, briefing), encoding="utf-8")
    (docs / "scenario-map.svg").write_text(render_scenario_map(item, briefing), encoding="utf-8")
    (docs / "benchmark.svg").write_text(render_benchmark(item, briefing, directory), encoding="utf-8")
    (docs / "contrast.svg").write_text(render_contrast(item, briefing, directory), encoding="utf-8")
    (docs / "result-profile.svg").write_text(render_profile(item, briefing, directory), encoding="utf-8")
    (docs / "failure-cards.svg").write_text(render_failure_cards(item, directory), encoding="utf-8")

    text = readme.read_text(encoding="utf-8")
    text = strip_old_banner(text)
    text = remove_block(text, START, END)
    text = remove_block(text, BRIEFING_START, BRIEFING_END)

    opener = (
        f'{START}\n<p align="center">\n'
        f'  <img src="docs/experience.svg" width="100%" alt="{escape(item.title)} — animated case trace">\n'
        f'</p>\n{END}\n\n'
    )
    briefing_block = f'''{BRIEFING_START}

## Visual case file

### Follow the story

<img src="docs/story-v2.svg" width="100%" alt="Animated four-act story explaining the human stakes of {escape(item.title)}">

### See where the obvious answer breaks

<img src="docs/scenario-map.svg" width="100%" alt="{escape(item.title)} scenario anatomy: surface story, hidden truth, unsafe shortcut, and exact proof">

### Read the complete evidence

<img src="docs/benchmark.svg" width="100%" alt="{escape(item.title)} benchmark chart generated from committed real-model evaluations">

<img src="docs/contrast.svg" width="100%" alt="Strongest and weakest verified {escape(item.title)} result contrasted on the headline metric">

<img src="docs/result-profile.svg" width="100%" alt="Outcome, completion, latency, and cost profile for the strongest headline {escape(item.title)} result">

### Learn from the misses

<img src="docs/failure-cards.svg" width="100%" alt="Three observed and reproducible {escape(item.title)} failure modes">

<p align="center"><sub>Generated from committed <a href="results/">evaluation results</a> and <a href="FAILURE_MODES.md">observed failure modes</a> · rerun <code>python docs/make_readme_experiences.py</code> from the repository root</sub></p>

{BRIEFING_END}'''
    badge_end = text.find("</p>")
    if badge_end == -1:
        raise ValueError(f"{readme} is missing its navigation badge paragraph")
    badge_end += len("</p>")
    body = text[:badge_end] + "\n\n" + briefing_block + "\n\n" + text[badge_end:].lstrip()
    readme.write_text(opener + body.lstrip(), encoding="utf-8")


def main() -> None:
    experience_paths = {item.path for item in EXPERIENCES}
    assert experience_paths == set(BRIEFINGS), "every experience needs exactly one visual case file"
    assert experience_paths == set(STORIES), "every experience needs exactly one four-act story"
    for path, briefing in BRIEFINGS.items():
        assert len(briefing.cards) == 4, f"{path} needs four scenario anatomy cards"
    for path, (headline, beats) in STORIES.items():
        assert headline and len(beats) == 4, f"{path} needs a headline and four story beats"
    for item in EXPERIENCES:
        install(item)
    print(f"installed {len(EXPERIENCES)} themed README visual case files")


if __name__ == "__main__":
    main()
