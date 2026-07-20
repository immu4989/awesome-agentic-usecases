"""Generate per-use-case README assets (light + dark SVG) from committed results.

Charts are rendered from the eval JSON in each use case's results/ directory, so a
published chart can never drift from the numbers behind it. Re-run after any new eval:

    python docs/make_assets.py

Palette follows the repo's validated data-viz tokens: one hue per chart (single
measure — never a rainbow), text in ink tokens rather than the series colour, and
dark-mode steps chosen for the dark surface rather than flipped.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LIGHT = {
    "surface": "#fcfcfb", "border": "rgba(11,11,11,0.10)", "ink": "#0b0b0b",
    "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7",
    "good": "#0ca30c", "chip": "#e1e0d9",
}
DARK = {
    "surface": "#1a1a19", "border": "rgba(255,255,255,0.10)", "ink": "#ffffff",
    "ink2": "#c3c2b7", "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835",
    "good": "#0ca30c", "chip": "#2c2c2a",
}

# One accent per industry so the five pages read as siblings, not clones.
USE_CASES = {
    "logistics-supply-chain/exception-triage-agent": {
        "title": "Exception Triage Agent", "icon": "🎫",
        "industry": "Logistics & Supply Chain",
        "tagline": "Which queue owns this stuck shipment — and can it resolve itself?",
        "accent": ("#2a78d6", "#3987e5"),
        "metric": "action_accuracy", "metric_label": "Action accuracy",
    },
    "retail-workforce/shift-coverage-triage-agent": {
        "title": "Shift Coverage Triage Agent", "icon": "🧑‍🍳",
        "industry": "Retail & Workforce",
        "tagline": "Crew called out. What is the labour-law-compliant fill?",
        "accent": ("#eb6834", "#d95926"),
        "metric": "strategy_accuracy", "metric_label": "Strategy accuracy",
    },
    "security-operations/alert-triage-agent": {
        "title": "Alert Triage Agent", "icon": "🚨",
        "industry": "Security Operations",
        "tagline": "Believe the detector, or verify it?",
        "accent": ("#4a3aa7", "#9085e9"),
        "metric": "exact_match", "metric_label": "Exact match (queue + disposition)",
    },
    "financial-services-fraud/fraud-alert-triage-agent": {
        "title": "Fraud Alert Triage Agent", "icon": "🚩",
        "industry": "Financial Services & Fraud",
        "tagline": "A holiday charge looks like theft. A trusted device hides a scam.",
        "accent": ("#1baf7a", "#199e70"),
        "metric": "exact_match", "metric_label": "Exact match (queue + disposition)",
    },
    "media-streaming/release-qc-triage-agent": {
        "title": "Release QC Triage Agent", "icon": "🎞️",
        "industry": "Media & Streaming",
        "tagline": "Days from premiere, QC flags the master. Ship it or stop it?",
        "accent": ("#d55181", "#e87ba4"),
        "metric": "action_accuracy", "metric_label": "Action accuracy",
    },
}

PRETTY = {
    "accounts/fireworks/models/gpt-oss-120b": "gpt-oss-120b",
    "accounts/fireworks/models/kimi-k2p6": "kimi-k2p6",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": "Llama-3.3-70B",
    "mistral-small-latest": "mistral-small",
    "Qwen/Qwen3.7-Plus": "Qwen3.7-Plus",
    "mock": "mock (CI baseline)",
}
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_rows(rel: str, metric: str) -> list[dict]:
    """Read every committed eval for a use case, newest metric first."""
    rdir = os.path.join(ROOT, rel, "results")
    rows = []
    for fn in sorted(os.listdir(rdir)):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(rdir, fn)))
        means = d.get("metric_means", {})
        if metric not in means:
            continue
        is_mock = d.get("backend") == "mock"
        # early mock runs recorded the CLI's default --model rather than "mock";
        # the backend field is authoritative for labelling.
        model = "mock" if is_mock else d.get("model", "?")
        lo, hi = d.get("metric_ci95", {}).get(metric, [None, None])
        rows.append({
            "model": PRETTY.get(model, model),
            "value": means[metric],
            "lo": lo, "hi": hi,
            "cost": d.get("mean_cost_per_scenario_usd", 0.0),
            "is_mock": is_mock,
        })
    rows.sort(key=lambda r: (r["is_mock"], -r["value"]))
    return rows


def banner(cfg: dict, mode: str) -> str:
    t = LIGHT if mode == "light" else DARK
    accent = cfg["accent"][0 if mode == "light" else 1]
    W, H = 1200, 170
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(cfg['title'])} — {esc(cfg['tagline'])}">
  <rect x="1" y="1" width="{W-2}" height="{H-2}" rx="14" fill="{t['surface']}" stroke="{t['border']}"/>
  <rect x="1" y="1" width="6" height="{H-2}" rx="3" fill="{accent}"/>
  <g font-family="{FONT}">
    <text x="44" y="52" font-size="14" font-weight="600" fill="{accent}" letter-spacing="1.2">{esc(cfg['industry'].upper())}</text>
    <text x="44" y="98" font-size="38" font-weight="700" fill="{t['ink']}">{cfg['icon']}  {esc(cfg['title'])}</text>
    <text x="44" y="130" font-size="18" fill="{t['ink2']}">{esc(cfg['tagline'])}</text>
    <g font-size="13" fill="{t['muted']}">
      <text x="44" y="155">investigate · decide</text>
      <text x="200" y="155">single-agent</text>
      <text x="320" y="155">30 scenarios × 3 repeats</text>
      <text x="530" y="155">verified</text>
    </g>
    <circle cx="512" cy="151" r="4" fill="{t['good']}"/>
  </g>
</svg>
"""


def chart(cfg: dict, rows: list[dict], mode: str) -> str:
    t = LIGHT if mode == "light" else DARK
    accent = cfg["accent"][0 if mode == "light" else 1]
    W = 1200
    top, row_h = 96, 54
    H = top + row_h * len(rows) + 58
    x0, x1 = 300, 1120           # plot area
    span = x1 - x0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{esc(cfg["metric_label"])} by model">',
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="14" fill="{t["surface"]}" stroke="{t["border"]}"/>',
        f'<g font-family="{FONT}">',
        f'<text x="44" y="46" font-size="19" font-weight="700" fill="{t["ink"]}">{esc(cfg["metric_label"])}</text>',
        f'<text x="44" y="70" font-size="13" fill="{t["muted"]}">whiskers are 95% bootstrap CIs · bar labels show cost per scenario · generated from results/</text>',
    ]
    # gridlines at quarters
    for frac in (0.25, 0.5, 0.75, 1.0):
        gx = x0 + span * frac
        parts.append(f'<path d="M {gx:.0f} {top-14} V {top + row_h*len(rows) - 10}" stroke="{t["grid"]}"/>')
    parts.append(f'<path d="M {x0} {top-14} V {top + row_h*len(rows) - 10}" stroke="{t["axis"]}" stroke-width="1.5"/>')

    for i, r in enumerate(rows):
        y = top + i * row_h
        bar_w = max(3, span * r["value"])
        fill = t["axis"] if r["is_mock"] else accent
        parts.append(f'<text x="284" y="{y+6}" font-size="15" font-weight="600" fill="{t["ink"]}" text-anchor="end">{esc(r["model"])}</text>')
        cost = "free tier / $0" if r["cost"] == 0 else f'${r["cost"]:.4f}/scenario'
        parts.append(f'<text x="284" y="{y+24}" font-size="12" fill="{t["muted"]}" text-anchor="end">{cost}</text>')
        parts.append(f'<rect x="{x0}" y="{y-12}" width="{bar_w:.0f}" height="24" rx="4" fill="{fill}"/>')
        # CI whisker
        if r["lo"] is not None and r["hi"] != r["lo"]:
            wl, wr = x0 + span * r["lo"], x0 + span * r["hi"]
            stroke = "#ffffff" if mode == "dark" else "#0b0b0b"
            parts.append(f'<g stroke="{stroke}" stroke-opacity="0.45" stroke-width="1.5">'
                         f'<path d="M {wl:.0f} {y} H {wr:.0f}"/>'
                         f'<path d="M {wl:.0f} {y-5} V {y+5}"/>'
                         f'<path d="M {wr:.0f} {y-5} V {y+5}"/></g>')
        # value label: inside the bar when there is room, else just outside
        if bar_w > 90:
            # white reads on the accent, but not on the light-mode grey mock bar
            label_fill = t["ink"] if (r["is_mock"] and mode == "light") else "#ffffff"
            parts.append(f'<text x="{x0 + bar_w - 12:.0f}" y="{y+6}" font-size="15" font-weight="700" fill="{label_fill}" text-anchor="end">{r["value"]:.3f}</text>')
        else:
            lx = max(x0 + bar_w + 12, (x0 + span * (r["hi"] or r["value"])) + 12)
            parts.append(f'<text x="{lx:.0f}" y="{y+6}" font-size="15" font-weight="700" fill="{t["ink"]}">{r["value"]:.3f}</text>')

    ty = top + row_h * len(rows) + 14
    for frac, lab in ((0, "0"), (0.25, "0.25"), (0.5, "0.50"), (0.75, "0.75"), (1.0, "1.00")):
        parts.append(f'<text x="{x0 + span*frac:.0f}" y="{ty}" font-size="12" fill="{t["muted"]}" text-anchor="middle">{lab}</text>')
    parts += ["</g>", "</svg>", ""]
    return "\n".join(parts)


def main() -> None:
    made = 0
    for rel, cfg in USE_CASES.items():
        out = os.path.join(ROOT, rel, "docs")
        os.makedirs(out, exist_ok=True)
        rows = load_rows(rel, cfg["metric"])
        for mode in ("light", "dark"):
            open(os.path.join(out, f"banner-{mode}.svg"), "w").write(banner(cfg, mode))
            open(os.path.join(out, f"results-{mode}.svg"), "w").write(chart(cfg, rows, mode))
            made += 2
        print(f"{rel}: {len(rows)} models charted")
    print(f"wrote {made} SVGs")


if __name__ == "__main__":
    main()
