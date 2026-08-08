"""Generate and install a themed, animated opener for every use-case README.

The output is plain SVG: crisp on every screen, readable in GitHub light and dark
themes, motion-safe, small enough to fork, and reproducible without design software.
Run from the repository root with:

    python docs/make_readme_experiences.py
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = "<!-- README-EXPERIENCE:START -->"
END = "<!-- README-EXPERIENCE:END -->"


@dataclass(frozen=True)
class Experience:
    path: str
    title: str
    icon: str
    industry: str
    tagline: str
    accent: str
    stages: tuple[tuple[str, str], ...]


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
)


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


def strip_old_banner(text: str) -> str:
    if not text.startswith("<picture>\n"):
        return text
    closing = text.find("</picture>\n")
    if closing == -1:
        return text
    return text[closing + len("</picture>\n") :].lstrip("\n")


def install(item: Experience) -> None:
    directory = ROOT / item.path
    readme = directory / "README.md"
    if not readme.exists():
        raise FileNotFoundError(f"missing README: {readme}")
    docs = directory / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "experience.svg").write_text(render_svg(item), encoding="utf-8")

    text = readme.read_text(encoding="utf-8")
    text = strip_old_banner(text)
    if START in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        text = before.rstrip() + "\n\n" + after.lstrip()

    opener = (
        f'{START}\n<p align="center">\n'
        f'  <img src="docs/experience.svg" width="100%" alt="{escape(item.title)} — animated case trace">\n'
        f'</p>\n{END}\n\n'
    )
    readme.write_text(opener + text.lstrip(), encoding="utf-8")


def main() -> None:
    for item in EXPERIENCES:
        install(item)
    print(f"installed {len(EXPERIENCES)} themed README experiences")


if __name__ == "__main__":
    main()
