"""Social cards for the "there is no best model" matrix, from committed results.

Reuses `make_leaderboard.load_matrix()` so the card and the README table are the same
numbers by construction. Dark theme, matching the Wave-11 launch assets.

    python docs/make_card_leaderboard.py   # -> ~/Desktop/agentic-matrix-*.png
"""

from __future__ import annotations

import os
import subprocess
import sys

from make_leaderboard import MODELS, load_matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SURFACE, INK, MUTED = "#161615", "#f3f2ec", "#8a887f"
ACCENT, PANEL, STAR = "#9085e9", "#262521", "#f0a500"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"


def cell_bg(v: float) -> str:
    """Violet ramp on dark: faint for weak scores, saturated for strong ones."""
    a, b = (38, 37, 34), (74, 58, 167)
    rgb = tuple(round(a[i] + (b[i] - a[i]) * v) for i in range(3))
    return "#%02x%02x%02x" % rgb


def grid_html(rows, compact: bool) -> str:
    fs_lbl = 15 if compact else 17
    fs_num = 19 if compact else 22
    pad = "7px 4px" if compact else "10px 4px"
    out = ['<table style="border-collapse:separate;border-spacing:6px;width:100%">']
    out.append('<tr><td></td>')
    for _mid, disp in MODELS:
        out.append(f'<td style="text-align:center;font-size:{fs_lbl-2}px;color:{MUTED};'
                   f'font-weight:700;padding-bottom:2px">{disp}</td>')
    out.append("</tr>")
    for r in rows:
        present = {m: r["vals"][m] for m, _ in MODELS if m in r["vals"]}
        best = max(present.values()) if present else None
        out.append(f'<tr><td style="font-size:{fs_lbl}px;color:{INK};font-weight:600;'
                   f'white-space:nowrap;padding-right:10px">{r["label"]}</td>')
        for mid, _disp in MODELS:
            if mid in r["vals"]:
                v = r["vals"][mid]
                win = best is not None and abs(v - best) < 1e-9
                ring = f"box-shadow:inset 0 0 0 2px {STAR};" if win else ""
                col = "#ffffff" if v > 0.5 else "#cfcec4"
                out.append(f'<td style="background:{cell_bg(v)};{ring}border-radius:8px;'
                           f'padding:{pad};text-align:center;font-size:{fs_num}px;'
                           f'font-weight:800;color:{col}">{v:.2f}'
                           + (f'<span style="color:{STAR};font-size:12px"> ★</span>' if win else "")
                           + "</td>")
            else:
                out.append(f'<td style="border:1px dashed #3a3934;border-radius:8px;'
                           f'padding:{pad};text-align:center;font-size:{fs_num}px;'
                           f'color:#55534c">—</td>')
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def card(rows, landscape: bool) -> str:
    w, h = (1600, 900) if landscape else (1080, 1350)
    pad = "58px 70px" if landscape else "70px 60px"
    h1 = 62 if landscape else 56
    return f"""<!doctype html><meta charset="utf-8"><style>
  *{{box-sizing:border-box;margin:0}}
  body{{width:{w}px;height:{h}px;font-family:{FONT};background:{SURFACE};color:{INK};
        padding:{pad};position:relative;display:flex;flex-direction:column;
        justify-content:center}}
  body::before{{content:"";position:absolute;left:0;top:0;bottom:0;width:14px;
                background:{ACCENT}}}
  .kicker{{color:{ACCENT};font-size:23px;font-weight:700;letter-spacing:2.4px}}
  h1{{font-size:{h1}px;font-weight:700;letter-spacing:-1.2px;margin:14px 0 6px}}
  .sub{{font-size:26px;color:{MUTED};margin-bottom:{"22px" if landscape else "30px"}}}
  .foot{{position:absolute;left:{"70px" if landscape else "60px"};right:60px;bottom:34px;
         display:flex;flex-direction:{"row" if landscape else "column"};
         justify-content:space-between;gap:6px;
         font-size:{22 if landscape else 21}px;color:{MUTED};white-space:nowrap}}
  .foot b{{color:{ACCENT}}}
</style>
<div class="kicker">5 MODELS · 8 AGENT TASKS · 45 VERIFIED EVALS</div>
<h1>There is no best model.</h1>
<div class="sub">Every model tested wins at least one task and loses another. ★ = winner.</div>
{grid_html(rows, compact=landscape)}
<div class="foot"><span>measured, not vibes · reproducible on free tiers</span>
  <span><b>github.com/immu4989/awesome-agentic-usecases</b></span></div>"""


def main() -> None:
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    rows = load_matrix()
    for land, name, size in ((True, "x", (1600, 900)), (False, "fb", (1080, 1350))):
        tmp = f"/tmp/aau-matrix-{name}.html"
        open(tmp, "w").write(card(rows, land))
        out = os.path.expanduser(f"~/Desktop/agentic-matrix-{name}-card.png")
        subprocess.run([CHROME, "--headless", "--disable-gpu",
                        f"--window-size={size[0]},{size[1]}",
                        f"--screenshot={out}", f"file://{tmp}"],
                       check=True, capture_output=True)
        print(f"wrote {out} ({os.path.getsize(out)/1024:.0f} KB, {size[0]}x{size[1]})")
    wins = {}
    for r in rows:
        present = {m: r["vals"][m] for m, _ in MODELS if m in r["vals"]}
        if present:
            b = max(present.values())
            for m, v in present.items():
                if abs(v - b) < 1e-9:
                    wins[m] = wins.get(m, 0) + 1
    print("wins:", {d: wins.get(m, 0) for m, d in MODELS})


if __name__ == "__main__":
    main()
