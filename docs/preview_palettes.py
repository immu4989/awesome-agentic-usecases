"""Render every palette as a real card, so a flavour is chosen by eye rather than by hex.

    python docs/preview_palettes.py   # -> ~/Desktop/agentic-palettes.png
"""

from __future__ import annotations

import os
import subprocess
import sys

from palettes import PALETTES

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

NOTES = {
    "violet": "cool · clinical · terminal — used for the security waves",
    "ember": "warm · oxidised — currently on Wave 12 (stale data)",
    "signal": "telemetry blue — for a watch or monitoring wave",
    "moss": "deep green — for a cost or efficiency wave",
    "orchid": "plum + fuchsia — loud, reads like an opinion",
    "copper": "teal + copper — complementary, reads expensive",
    "lime": "charcoal + electric lime — highest energy, developer-tool",
    "noir": "near-black + soft gold — restrained, one number carries it",
}


def tile(name: str, p: dict[str, str]) -> str:
    return f"""
<div class="tile" style="background:{p['surface']}">
  <div class="bar" style="background:{p['accent']}"></div>
  <div class="in">
    <div class="k" style="color:{p['accent']}">{name.upper()} · SAME EVAL, SAME MODEL</div>
    <div class="h" style="color:{p['ink']}">The only thing I changed was<br>whether the tools told the truth.</div>
    <div class="row">
      <div class="c" style="background:{p['panel']};border-top:5px solid {p['good']}">
        <div class="l" style="color:{p['panel_muted']}">TRUTHFUL</div>
        <div class="n" style="color:{p['good']}">1.000</div>
      </div>
      <div class="c" style="background:{p['panel']};border-top:5px solid {p['bad']}">
        <div class="l" style="color:{p['panel_muted']}">REALISTIC</div>
        <div class="n" style="color:{p['bad']}">0.611</div>
      </div>
      <div class="c" style="background:{p['panel']};border-top:5px solid {p['warn']}">
        <div class="l" style="color:{p['panel_muted']}">CAVEAT</div>
        <div class="n" style="color:{p['warn']}">0.03</div>
      </div>
    </div>
    <div class="note" style="color:{p['muted']}">{NOTES.get(name, '')}</div>
  </div>
</div>"""


def main() -> None:
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    tiles = "".join(tile(n, p) for n, p in PALETTES.items())
    html = f"""<!doctype html><meta charset="utf-8"><style>
  *{{box-sizing:border-box;margin:0}}
  body{{background:#f4f3ee;font-family:{FONT};padding:26px;width:1500px;
        display:grid;grid-template-columns:1fr 1fr;gap:22px}}
  .tile{{position:relative;border-radius:14px;overflow:hidden;height:330px}}
  .bar{{position:absolute;left:0;top:0;bottom:0;width:9px}}
  .in{{padding:30px 34px 26px 40px;height:100%;display:flex;flex-direction:column;
       justify-content:center;gap:14px}}
  .k{{font-size:14px;font-weight:700;letter-spacing:1.8px}}
  .h{{font-size:29px;font-weight:700;line-height:1.15;letter-spacing:-0.5px}}
  .row{{display:flex;gap:14px;margin-top:4px}}
  .c{{flex:1;border-radius:11px;padding:14px 10px;text-align:center}}
  .l{{font-size:11px;font-weight:700;letter-spacing:1.4px}}
  .n{{font-size:40px;font-weight:800;letter-spacing:-1.5px;line-height:1.25}}
  .note{{font-size:14px}}
</style>{tiles}"""
    tmp = "/tmp/aau-palettes.html"
    open(tmp, "w").write(html)
    out = os.path.expanduser("~/Desktop/agentic-palettes.png")
    rows = (len(PALETTES) + 1) // 2
    subprocess.run([CHROME, "--headless", "--disable-gpu",
                    f"--window-size=1500,{rows * 352 + 52}", "--hide-scrollbars",
                    f"--screenshot={out}", f"file://{tmp}"], check=True, capture_output=True)
    print(f"wrote {out} ({os.path.getsize(out)/1024:.0f} KB) — {len(PALETTES)} palettes")


if __name__ == "__main__":
    main()
