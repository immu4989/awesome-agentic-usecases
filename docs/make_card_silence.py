"""Social card for the Wave-15 result, built from the committed results.

The visual *is* the finding. Two stacked bars, one per defence, split into the three
outcomes the use case scores. Both bars have no red, because both defences drive violations
to zero — and that is exactly why a two-way instrument would call them equivalent. The
difference is the amber band on the second bar: incidents the agent closed as "remediated"
after the approved action had been refused and it did nothing else.

Numbers are read from `results/`, never typed in, so the card and the README cannot drift.

    python docs/make_card_silence.py    # -> ~/Desktop/agentic-silence-*.png
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palettes import PALETTES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "it-operations", "incident-remediation-agent", "results")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

P = PALETTES["ember"]          # amber: the alert that never fired. Wave 12 was orchid.
MODEL = "mistral-small-latest"
CONDITION = "BLOCKED"


def outcomes(arm: str) -> dict[str, float]:
    """Incident-level means for one arm, so the card matches the clustered analysis."""
    path = next(p for p in glob.glob(os.path.join(RESULTS, f"eval_{arm}_*.json"))
                if MODEL in p)
    with open(path) as f:
        doc = json.load(f)
    per: dict[str, dict[str, list[float]]] = {}
    for r in doc["results"]:
        if r["detail"]["condition"] != CONDITION:
            continue
        g = per.setdefault(r["detail"]["incident_id"], {})
        for k in ("violated", "escalated", "neither", "false_success"):
            g.setdefault(k, []).append(r["metrics"][k])
    n = len(per)
    return {k: sum(sum(g[k]) / len(g[k]) for g in per.values()) / n
            for k in ("violated", "escalated", "neither", "false_success")}


def bar(label: str, sub: str, o: dict[str, float], compact: bool) -> str:
    seg = []
    for key, colour, name in (("violated", P["bad"], "took the shortcut"),
                              ("escalated", P["good"], "paged a human"),
                              ("neither", P["warn"], 'filed "remediated"')):
        pct = o[key] * 100
        if pct < 0.5:
            continue
        show = pct >= 12
        seg.append(
            f'<div style="width:{pct:.4f}%;background:{colour};display:flex;'
            f'align-items:center;justify-content:center;color:#12100e;'
            f'font-weight:800;font-size:{15 if compact else 17}px;letter-spacing:.2px">'
            f'{name + " · " + format(o[key], ".2f") if show else ""}</div>')
    h = 118 if compact else 116
    return f"""<div style="margin-bottom:{26 if compact else 30}px">
  <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:7px">
    <span style="font-size:{21 if compact else 25}px;font-weight:800;color:{P['ink']}">{label}</span>
    <span style="font-size:{14 if compact else 16}px;color:{P['muted']}">{sub}</span>
  </div>
  <div style="display:flex;height:{h}px;border-radius:9px;overflow:hidden;
              background:{P['panel']}">{''.join(seg)}</div>
</div>"""


def card(data: dict[str, dict[str, float]], landscape: bool) -> str:
    w, h = (1600, 900) if landscape else (1080, 1350)
    c = landscape
    pad = 62 if c else 66
    return f"""<html><body style="margin:0;width:{w}px;height:{h}px;background:{P['surface']};
  font-family:{FONT};color:{P['ink']};box-sizing:border-box;padding:{pad}px;
  display:flex;flex-direction:column;gap:{34 if c else 44}px">

<div>
  <div style="font-size:{14 if c else 16}px;font-weight:800;letter-spacing:1.8px;
              color:{P['accent']};margin-bottom:{16 if c else 20}px">
    IT OPS · WHEN THE APPROVED PATH IS BLOCKED</div>
  <div style="font-size:{50 if c else 56}px;font-weight:800;line-height:1.08;
              letter-spacing:-1.2px;max-width:{1180 if c else 940}px">
    Least privilege didn't make<br>it safe. It made it lie.</div>
  <div style="font-size:{19 if c else 22}px;color:{P['ink2']};margin-top:{14 if c else 18}px;
              max-width:{1120 if c else 930}px;line-height:1.45">
    Same incidents, same model. Both defences take violations to zero, so a scoreboard
    that only counts violations calls them identical.</div>
</div>

<div>
  {bar("Name the forbidden tools", "in the system prompt", data["named"], c)}
  {bar("Remove them from the schema", "classic least privilege", data["scoped"], c)}
  <div style="display:flex;gap:14px;align-items:flex-start;background:{P['panel']};
              border-radius:10px;padding:{18 if c else 22}px {22 if c else 26}px;
              margin-top:{4 if c else 8}px">
    <span style="width:16px;height:16px;border-radius:4px;background:{P['warn']};
                 flex:none;margin-top:{5 if c else 6}px"></span>
    <span style="font-size:{20 if c else 23}px;color:{P['ink']};line-height:1.42">
      The amber band closed the ticket as <b>remediated</b>. The runbook step had returned
      a lock error and never ran. &ldquo;Applied a rate limit to tenant TEN-437&hellip;&rdquo;
      &mdash; it did not. The incident is still open and nobody was told.</span>
  </div>
</div>

<div style="display:flex;justify-content:space-between;align-items:flex-end;
            font-size:{15 if c else 17}px;color:{P['muted']};margin-top:auto;
            border-top:1px solid {P['panel']};padding-top:{18 if c else 22}px">
  <span>mistral-small · 24 incidents × 3 repeats · clustered on incident · blocked runs</span>
  <span style="color:{P['ink2']};font-weight:700">github.com/immu4989/awesome-agentic-usecases</span>
</div>
</body></html>"""


def main() -> None:
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    data = {arm: outcomes(arm) for arm in ("named", "scoped")}
    for arm, o in data.items():
        print(f"  {arm:7} violated={o['violated']:.2f} escalated={o['escalated']:.2f} "
              f"neither={o['neither']:.2f}")
    for land, name, size in ((True, "x", (1600, 900)), (False, "li", (1080, 1350))):
        tmp = f"/tmp/aau-silence-{name}.html"
        with open(tmp, "w") as f:
            f.write(card(data, land))
        out = os.path.expanduser(f"~/Desktop/agentic-silence-{name}-card.png")
        subprocess.run([CHROME, "--headless", "--disable-gpu",
                        f"--window-size={size[0]},{size[1]}",
                        f"--screenshot={out}", f"file://{tmp}"],
                       check=True, capture_output=True)
        print(f"wrote {out} ({os.path.getsize(out) / 1024:.0f} KB, {size[0]}x{size[1]})")


if __name__ == "__main__":
    main()
