"""Generate the cross-use-case model matrix from every committed result.

The repo's first thesis is that there is no best model. This proves it in one artifact:
each use case's headline metric for every model that ran it, pulled from results/*.json so
it can never drift from the evals. Blanks are honest — a model that was not run on a use
case shows a dash, not a zero.

Emits:
  - a markdown table, written into README.md between the LEADERBOARD markers
  - docs/assets/leaderboard-{light,dark}.svg, a heatmap for the README hero

Only the "solve-the-task" use cases appear — the three adversarial A/B use cases
(refund-guarded, refund-injected, trifecta-exfil) compare *defences*, not model accuracy,
so a per-model column would misrepresent them.

    python docs/make_leaderboard.py
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# use case -> (short label, industry, capability, headline metric)
USE_CASES = [
    ("logistics-supply-chain/exception-triage-agent", "Exception Triage", "Logistics", "investigate·decide", "action_accuracy"),
    ("retail-workforce/shift-coverage-triage-agent", "Shift Coverage", "Retail", "investigate·decide", "strategy_accuracy"),
    ("security-operations/alert-triage-agent", "Alert Triage", "Security", "investigate·decide", "exact_match"),
    ("financial-services-fraud/fraud-alert-triage-agent", "Fraud Triage", "Finance", "investigate·decide", "exact_match"),
    ("media-streaming/release-qc-triage-agent", "Release QC", "Media", "investigate·decide", "action_accuracy"),
    ("customer-support/refund-resolution-agent", "Refund Resolution", "Support", "plan·act", "safe_and_correct"),
    ("it-operations/oncall-watch-agent", "On-Call Watch", "IT Ops", "watch", "severity_correct"),
    ("security-operations/artifact-admission-agent", "Artifact Admission", "Security", "gate", "disposition_accuracy"),
]

# fixed model order + display names
MODELS = [
    ("accounts/fireworks/models/kimi-k2p6", "kimi-k2p6"),
    ("accounts/fireworks/models/gpt-oss-120b", "gpt-oss-120b"),
    ("Qwen/Qwen3.7-Plus", "Qwen3.7-Plus"),
    ("mistral-small-latest", "mistral-small"),
    ("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Llama-3.3-70B"),
]


def load_matrix():
    """rows[uc_label] = {model_id: value}; plus metadata per row."""
    rows = []
    for path, label, industry, cap, metric in USE_CASES:
        rdir = os.path.join(ROOT, path, "results")
        vals = {}
        for fn in os.listdir(rdir):
            if not fn.endswith(".json") or "mock" in fn:
                continue
            d = json.load(open(os.path.join(rdir, fn)))
            v = d.get("metric_means", {}).get(metric)
            if v is not None:
                vals[d.get("model")] = v
        rows.append({"path": path, "label": label, "industry": industry,
                     "cap": cap, "metric": metric, "vals": vals})
    return rows


def markdown(rows) -> str:
    header = "| Use case | Industry | " + " | ".join(disp for _id, disp in MODELS) + " |"
    sep = "|" + "---|" * (len(MODELS) + 2)
    lines = [header, sep]
    wins = {mid: 0 for mid, _ in MODELS}
    for r in rows:
        present = {mid: r["vals"][mid] for mid, _ in MODELS if mid in r["vals"]}
        best = max(present.values()) if present else None
        cells = []
        for mid, _disp in MODELS:
            if mid in r["vals"]:
                v = r["vals"][mid]
                s = f"{v:.3f}"
                if best is not None and abs(v - best) < 1e-9:
                    s = f"**{s}**"
                    wins[mid] += 1
                cells.append(s)
            else:
                cells.append("—")
        lines.append(f"| [{r['label']}]({r['path']}/) | {r['industry']} | " + " | ".join(cells) + " |")
    win_row = "| **Use cases won** | | " + " | ".join(
        f"**{wins[mid]}**" for mid, _ in MODELS) + " |"
    lines.append(win_row)
    return "\n".join(lines)


# ---- SVG heatmap ----------------------------------------------------------------------

def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def heatmap(rows, mode: str) -> str:
    dark = mode == "dark"
    surface = "#161615" if dark else "#fcfcfb"
    ink = "#f3f2ec" if dark else "#0b0b0b"
    muted = "#8a887f"
    grid = "#2a2a28" if dark else "#e1e0d9"
    pale = (34, 33, 31) if dark else (247, 246, 241)     # value 0
    full = (74, 58, 167)                                  # value 1 (repo violet)
    star = "#eda100"

    left = 250      # row-label column
    top = 96
    cw, ch = 168, 62
    n_rows, n_cols = len(rows), len(MODELS)
    W = left + n_cols * cw + 24
    H = top + n_rows * ch + 60

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" role="img" aria-label="Model accuracy by use case — '
           f'every model wins at least one use case and loses another">',
           f'<rect width="{W}" height="{H}" fill="{surface}"/>',
           '<g font-family="system-ui, -apple-system, Segoe UI, sans-serif">']
    # title
    out.append(f'<text x="24" y="42" fill="{ink}" font-size="26" font-weight="700">'
               f'There is no best model</text>')
    out.append(f'<text x="24" y="70" fill="{muted}" font-size="15">Headline metric per '
               f'use case · winner starred · blank = not run · from committed results</text>')
    # column headers
    for c, (_mid, disp) in enumerate(MODELS):
        x = left + c * cw + cw / 2
        out.append(f'<text x="{x:.0f}" y="{top-14}" fill="{ink}" font-size="14" '
                   f'font-weight="600" text-anchor="middle">{disp}</text>')
    # rows
    for ri, r in enumerate(rows):
        y = top + ri * ch
        out.append(f'<text x="24" y="{y+ch/2-2:.0f}" fill="{ink}" font-size="15" '
                   f'font-weight="600">{r["label"]}</text>')
        out.append(f'<text x="24" y="{y+ch/2+16:.0f}" fill="{muted}" font-size="12">'
                   f'{r["industry"]} · {r["cap"]}</text>')
        present = {mid: r["vals"][mid] for mid, _ in MODELS if mid in r["vals"]}
        best = max(present.values()) if present else None
        for c, (mid, _disp) in enumerate(MODELS):
            x = left + c * cw
            if mid in r["vals"]:
                v = r["vals"][mid]
                fill = _hex(_lerp(pale, full, v))
                tcol = "#ffffff" if v > 0.55 else ink
                out.append(f'<rect x="{x+3}" y="{y+3}" width="{cw-6}" height="{ch-6}" '
                           f'rx="7" fill="{fill}" stroke="{grid}"/>')
                is_win = best is not None and abs(v - best) < 1e-9
                if is_win:
                    out.append(f'<rect x="{x+3}" y="{y+3}" width="{cw-6}" height="{ch-6}" '
                               f'rx="7" fill="none" stroke="{star}" stroke-width="2.5"/>')
                    out.append(f'<text x="{x+cw-16:.0f}" y="{y+20:.0f}" fill="{star}" '
                               f'font-size="15">★</text>')
                out.append(f'<text x="{x+cw/2:.0f}" y="{y+ch/2+6:.0f}" fill="{tcol}" '
                           f'font-size="18" font-weight="700" text-anchor="middle">'
                           f'{v:.2f}</text>')
            else:
                out.append(f'<rect x="{x+3}" y="{y+3}" width="{cw-6}" height="{ch-6}" '
                           f'rx="7" fill="none" stroke="{grid}" stroke-dasharray="3 4"/>')
                out.append(f'<text x="{x+cw/2:.0f}" y="{y+ch/2+6:.0f}" fill="{muted}" '
                           f'font-size="16" text-anchor="middle">—</text>')
    out.append("</g></svg>")
    return "\n".join(out)


LEAD_START = "<!-- LEADERBOARD:START -->"
LEAD_END = "<!-- LEADERBOARD:END -->"


def main() -> None:
    rows = load_matrix()
    # SVGs
    adir = os.path.join(ROOT, "docs", "assets")
    for mode in ("light", "dark"):
        with open(os.path.join(adir, f"leaderboard-{mode}.svg"), "w") as f:
            f.write(heatmap(rows, mode))
    # markdown into README between markers
    md = markdown(rows)
    readme = os.path.join(ROOT, "README.md")
    text = open(readme).read()
    if LEAD_START in text and LEAD_END in text:
        pre = text.split(LEAD_START)[0]
        post = text.split(LEAD_END)[1]
        text = pre + LEAD_START + "\n\n" + md + "\n\n" + LEAD_END + post
        with open(readme, "w") as f:
            f.write(text)
        print("updated README leaderboard table")
    else:
        print("markers not found in README; table below:\n")
        print(md)
    print("wrote docs/assets/leaderboard-{light,dark}.svg")


if __name__ == "__main__":
    main()
