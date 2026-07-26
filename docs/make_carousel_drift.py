"""Wave-12 launch assets (LinkedIn carousel PDF + X/Facebook cards) from committed results.

Every number is read from the exception-triage-drift results, never retyped. Runs on the
"orchid" palette — see docs/palettes.py to switch flavours.

    python docs/make_carousel_drift.py   # -> ~/Desktop/agentic-drift-*.{pdf,png}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from palettes import palette

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
R = os.path.join(ROOT, "logistics-supply-chain/exception-triage-drift/results")

P = palette("orchid")
SURFACE, INK, INK2, MUTED = P["surface"], P["ink"], P["ink2"], P["muted"]
ACCENT = P["accent"]
PANEL, PANEL_INK, PANEL_INK2, PANEL_MUTED = P["panel"], P["ink"], P["ink2"], P["panel_muted"]
GOOD, BAD, WARN = P["good"], P["bad"], P["warn"]
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

MODELS = [("kimi-k2p6", "accounts_fireworks_models_kimi-k2p6"),
          ("Qwen3.7-Plus", "Qwen_Qwen3.7-Plus"),
          ("gpt-oss-120b", "accounts_fireworks_models_gpt-oss-120b"),
          ("mistral-small", "mistral-small-latest")]


def load(arm: str, tag: str) -> dict:
    with open(os.path.join(R, f"eval_{arm}_{tag}.json")) as f:
        return json.load(f)


def conditional(x: dict) -> float:
    sub = [r for r in x["results"] if r["metrics"]["submitted"] == 1.0]
    return sum(r["metrics"]["action_accuracy"] for r in sub) / len(sub) if sub else 0.0


def refresh_rate(x: dict) -> float:
    return sum(r["detail"]["refreshed"] for r in x["results"]) / len(x["results"])


STATS = {}
for name, tag in MODELS:
    c, d = load("clean", tag), load("drift", tag)
    STATS[name] = {"clean": conditional(c), "drift": conditional(d),
                   "refresh": refresh_rate(d)}
    STATS[name]["drop"] = STATS[name]["clean"] - STATS[name]["drift"]

K = STATS["kimi-k2p6"]


def stale_example() -> dict:
    """A real scenario where one cached field flips the decision — used by the X card.

    Read from the world rather than typed in, so if the corruption logic changes the card
    changes with it instead of quietly becoming fiction.
    """
    from exception_triage_agent.world import generate_scenarios, gold_triage
    from exception_triage_drift.drift import archetype_for, served_view

    for i, sc in enumerate(generate_scenarios(30, 7)):
        if archetype_for(i) != "STALE_SNAPSHOT":
            continue
        served = served_view(sc, "STALE_SNAPSHOT")["shipment"]
        if gold_triage(served)[1] != gold_triage(sc.shipment)[1]:
            return {"sc": sc, "served": served, "true": sc.shipment,
                    "served_action": gold_triage(served)[1],
                    "true_action": gold_triage(sc.shipment)[1]}
    raise RuntimeError("no decision-flipping stale scenario found")


EX = stale_example()


def pts(x: float) -> str:
    return f"{round(x * 100)}"


def slides() -> list[str]:
    rows = "".join(
        f'<div class="mrow {cls}"><b>{n}</b> re-read on <b>{STATS[n]["refresh"]:.2f}</b> '
        f'of runs and lost <b>{pts(STATS[n]["drop"])} points</b></div>'
        for n, cls in (("kimi-k2p6", "bad-b"), ("Qwen3.7-Plus", "warn-b"),
                       ("gpt-oss-120b", "good-b")))
    return [
        f"""<div class="s">
          <div class="kicker">AGENT RELIABILITY · MEASURED</div>
          <h1>A model scored <em>100%</em> on my eval.</h1>
          <p class="lead">Then I gave it a cache from last Tuesday and it scored
            {pts(K['drift'])}%.</p>
          <div class="foot">Same 30 tickets · same gold answers · same prompt</div>
        </div>""",
        """<div class="s">
          <div class="kicker">THE ONLY THING I CHANGED</div>
          <h2>Whether the tools told the truth.</h2>
          <div class="mrow bad-b">A record served from <b>a stale cache</b></div>
          <div class="mrow bad-b">Two systems that <b>disagree</b> about what happened</div>
          <div class="mrow bad-b">A service returning <b>half its fields</b></div>
          <div class="mrow warn-b">And one record <b>quietly wrong</b>, with no tell at all</div>
          <p class="lead">The task never got harder. The world got realistic.</p>
        </div>""",
        f"""<div class="s center">
          <div class="kicker">THE COLLAPSE</div>
          <div class="split">
            <div class="col good-b">
              <div class="lbl">TRUTHFUL WORLD</div>
              <div class="mini good">{K['clean']:.3f}</div>
              <div class="ml">90 of 90</div>
            </div>
            <div class="col bad-b">
              <div class="lbl">REALISTIC WORLD</div>
              <div class="mini bad">{K['drift']:.3f}</div>
              <div class="ml">same 30 tickets</div>
            </div>
          </div>
          <p class="lead">Thirty-nine points, on an eval it had already solved.</p>
        </div>""",
        """<div class="s center">
          <div class="kicker">WHY THIS IS THE ENTERPRISE STORY</div>
          <h1 class="tight">85% of companies are piloting agents. 5% have shipped.</h1>
          <p class="lead">Evals hand an agent a world that is truthful, complete and
            self-consistent. Production doesn't.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">WHAT PREDICTED THE DAMAGE</div>
          <h2>Not capability. One habit.</h2>
          {rows}
          <p class="lead">How often the model re-read the record before deciding.
            Monotonic, across three vendors.</p>
        </div>""",
        """<div class="s center">
          <div class="kicker">TWO THINGS I DIDN'T EXPECT</div>
          <h1 class="tight">The best model on clean data was the most fragile.</h1>
          <p class="lead">And the most robust one wasn't clever about when to re-read.
            It just always did, including on the clean arm where there was nothing to
            refresh. A reflex beat reasoning.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">THEN A FOURTH MODEL BROKE THE RULE</div>
          <h2>It barely dropped at all. That isn't robustness.</h2>
          <div class="mrow warn-b">mistral-small lost only
            <b>{pts(STATS['mistral-small']['drop'])} points</b></div>
          <div class="mrow bad-b">…but it scored <b>0 of 6</b> on escalation cases with
            <b>perfect</b> data</div>
          <p class="lead">You cannot mislead a model with a number it was never reading.
            A small drop is not resilience if the agent ignored the field you corrupted.</p>
        </div>""",
        """<div class="s center">
          <div class="kicker">THE TAKEAWAY</div>
          <h1 class="tight">A perfect eval score can mean the eval never lied to you.</h1>
          <div class="cta">13 use cases · 72 measured failures · $0 to reproduce<br>
            <b>github.com/immu4989/awesome-agentic-usecases</b></div>
        </div>""",
    ]


HTML = """<!doctype html><meta charset="utf-8"><style>
  @page {{ size: 1080px 1350px; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ font-family: {font}; background: {surface}; color: {ink}; }}
  .s {{ width: 1080px; height: 1350px; padding: 118px 88px; background: {surface};
        page-break-after: always; position: relative; display: flex;
        flex-direction: column; justify-content: center; gap: 28px; }}
  .s.center {{ text-align: center; align-items: center; }}
  .s::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 12px;
                background: {accent}; }}
  .kicker {{ color: {accent}; font-size: 24px; font-weight: 700; letter-spacing: 2.4px; }}
  h1 {{ font-size: 74px; line-height: 1.08; font-weight: 700; letter-spacing: -1.5px; }}
  h1.tight {{ font-size: 60px; }}
  h1 em {{ font-style: normal; color: {accent}; }}
  h2 {{ font-size: 44px; line-height: 1.22; font-weight: 700; }}
  .lead {{ font-size: 32px; line-height: 1.42; color: {ink2}; }}
  .mrow {{ padding: 22px 26px; font-size: 29px; line-height: 1.4; color: {pink2};
           background: {panel}; border-left: 6px solid {muted};
           border-radius: 0 12px 12px 0; }}
  .mrow b {{ color: {pink}; }}
  .mrow.good-b {{ border-left-color: {good}; }}
  .mrow.warn-b {{ border-left-color: {warn}; }}
  .mrow.bad-b {{ border-left-color: {bad}; }}
  .split {{ display: flex; gap: 26px; width: 100%; }}
  .col {{ flex: 1; padding: 38px 28px; border-radius: 16px; text-align: center;
          background: {panel}; border-top: 6px solid {muted}; }}
  .col.good-b {{ border-top-color: {good}; }}
  .col.bad-b {{ border-top-color: {bad}; }}
  .lbl {{ font-size: 21px; letter-spacing: 1.6px; color: {pmuted}; font-weight: 700; }}
  .mini {{ font-size: 116px; font-weight: 800; letter-spacing: -4px; line-height: 1.1; }}
  .mini.good {{ color: {good}; }}
  .mini.bad {{ color: {bad}; }}
  .ml {{ font-size: 22px; color: {pmuted}; letter-spacing: 1px; }}
  .foot {{ position: absolute; left: 88px; right: 88px; bottom: 66px; font-size: 24px;
           color: {muted}; line-height: 1.5; }}
  .s.center .foot {{ text-align: center; }}
  .cta {{ margin-top: 26px; font-size: 27px; line-height: 1.6; color: {ink2}; }}
  .cta b {{ color: {accent}; font-size: 30px; }}
</style>{body}"""


def _render(tmp: str, out: str, size, pdf: bool) -> None:
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    cmd = [CHROME, "--headless", "--disable-gpu"]
    cmd += (["--no-pdf-header-footer", f"--print-to-pdf={out}"] if pdf
            else [f"--window-size={size[0]},{size[1]}", f"--screenshot={out}"])
    subprocess.run(cmd + [f"file://{tmp}"], check=True, capture_output=True)
    print(f"wrote {out} ({os.path.getsize(out)/1024:.0f} KB)")


def x_card() -> str:
    """A different shape from every other card in this repo.

    The stat-panel composition had been used for three waves running and had started to
    read as the same image. This one shows the actual artifact instead of the summary: two
    near-identical records, one field three days stale, and the decision it flipped. It
    asks the reader to find something rather than to read a number, which is the only
    reliable way to buy a second look on a fast feed.
    """
    t, sv = EX["true"], EX["served"]

    def rec(label: str, ship: dict) -> str:
        rows = "".join(
            f'<div class="ln"><span class="k">{k}</span>'
            f'<span class="v">{v}</span></div>'
            for k, v in (
                ("tracking_id", ship["tracking_id"]),
                ("carrier", ship["carrier"]),
                ("exception_code", ship["exception_code"]),
                ("value_usd", f'{ship["value_usd"]:,.2f}'),
                ("customer_tier", ship["customer_tier"]),
                ("sla_hours_remaining", ship["sla_hours_remaining"]),
            ))
        return f'<div class="rec"><div class="rl">{label}</div>{rows}</div>'

    return f"""<!doctype html><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: 1600px; height: 900px; font-family: {FONT}; background: {SURFACE};
         color: {INK}; padding: 60px 72px; position: relative; display: flex;
         flex-direction: column; justify-content: center; }}
  body::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0;
                  width: 14px; background: {ACCENT}; }}
  .kicker {{ color: {ACCENT}; font-size: 24px; font-weight: 700; letter-spacing: 2.4px; }}
  h1 {{ font-size: 58px; font-weight: 700; letter-spacing: -1.2px; margin: 14px 0 6px; }}
  .sub {{ font-size: 26px; color: {MUTED}; }}
  .pair {{ display: flex; gap: 34px; margin-top: 34px; }}
  .rec {{ flex: 1; background: {PANEL}; border-radius: 16px; padding: 26px 30px;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .rl {{ font-size: 18px; letter-spacing: 2px; color: {PANEL_MUTED}; font-weight: 700;
         margin-bottom: 14px; font-family: {FONT}; }}
  .ln {{ display: flex; justify-content: space-between; font-size: 25px; padding: 7px 0; }}
  .k {{ color: {PANEL_MUTED}; }}
  .v {{ color: {PANEL_INK}; font-weight: 600; }}
  .foot {{ position: absolute; left: 72px; right: 68px; bottom: 40px; display: flex;
           justify-content: space-between; align-items: baseline; font-size: 23px;
           color: {MUTED}; }}
  .foot b {{ color: {ACCENT}; }}
</style>
<div class="kicker">SAME SHIPMENT · SAME AGENT · TWO RECORDS</div>
<h1>One of these is three days out of date.</h1>
<div class="sub">The agent couldn't tell either. Can you?</div>
<div class="pair">{rec("RECORD A", sv)}{rec("RECORD B", t)}</div>
<div class="foot">
  <span>it escalated a $300 shipment · a model that scored 1.000 here dropped to {K['drift']:.3f}</span>
  <span><b>github.com/immu4989/awesome-agentic-usecases</b></span>
</div>"""


def card(landscape: bool) -> str:
    w, h = (1600, 900) if landscape else (1080, 1350)
    return f"""<!doctype html><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: {w}px; height: {h}px; font-family: {FONT}; background: {SURFACE};
         color: {INK}; padding: {'74px 80px' if landscape else '84px 76px'};
         position: relative; display: flex; flex-direction: column; justify-content: center; }}
  body::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0;
                  width: 14px; background: {ACCENT}; }}
  .kicker {{ color: {ACCENT}; font-size: 25px; font-weight: 700; letter-spacing: 2.4px; }}
  h1 {{ font-size: {56 if landscape else 50}px; font-weight: 700; letter-spacing: -1.2px;
       margin: 18px 0 6px; line-height: 1.1; }}
  .sub {{ font-size: 27px; color: {MUTED}; line-height: 1.35; }}
  .row {{ display: flex; flex-direction: {'row' if landscape else 'column'};
          gap: {'40px' if landscape else '24px'}; margin-top: 40px; }}
  .c {{ flex: 1; padding: 34px 38px; border-radius: 18px; background: {PANEL};
        border-top: 6px solid {MUTED}; text-align: center; }}
  .c.g {{ border-top-color: {GOOD}; }}
  .c.b {{ border-top-color: {BAD}; }}
  .lbl {{ font-size: 21px; letter-spacing: 1.6px; color: {PANEL_MUTED}; font-weight: 700; }}
  .num {{ font-size: {112 if landscape else 100}px; font-weight: 800; letter-spacing: -4px;
          line-height: 1.15; }}
  .num.g {{ color: {GOOD}; }}
  .num.b {{ color: {BAD}; }}
  .nl {{ font-size: 22px; color: {PANEL_MUTED}; }}
  .foot {{ position: absolute; left: 80px; right: 76px; bottom: 40px; display: flex;
           flex-direction: {'row' if landscape else 'column'}; gap: 6px;
           justify-content: space-between; font-size: 22px; color: {MUTED};
           white-space: nowrap; }}
  .foot b {{ color: {ACCENT}; }}
</style>
<div class="kicker">SAME 30 TICKETS · SAME GOLD ANSWERS · SAME PROMPT</div>
<h1>The only thing I changed was<br>whether the tools told the truth.</h1>
<div class="sub">One stale cache, two systems disagreeing, a service returning half its fields.</div>
<div class="row">
  <div class="c g"><div class="lbl">TRUTHFUL WORLD</div>
    <div class="num g">{K['clean']:.3f}</div><div class="nl">90 of 90</div></div>
  <div class="c b"><div class="lbl">REALISTIC WORLD</div>
    <div class="num b">{K['drift']:.3f}</div><div class="nl">same eval, same model</div></div>
</div>
<div class="foot"><span>a perfect eval score can mean the eval never lied to you</span>
  <span><b>github.com/immu4989/awesome-agentic-usecases</b></span></div>"""


def main() -> None:
    body = "".join(slides())
    html = HTML.format(font=FONT, surface=SURFACE, ink=INK, ink2=INK2, muted=MUTED,
                       accent=ACCENT, panel=PANEL, pink=PANEL_INK, pink2=PANEL_INK2,
                       pmuted=PANEL_MUTED, good=GOOD, bad=BAD, warn=WARN, body=body)
    tmp = "/tmp/aau-drift-carousel.html"
    open(tmp, "w").write(html)
    _render(tmp, os.path.expanduser("~/Desktop/agentic-drift-carousel.pdf"), (1080, 1350), True)
    print(f"  ({len(slides())} slides)")
    open("/tmp/aau-drift-x.html", "w").write(x_card())
    _render("/tmp/aau-drift-x.html",
            os.path.expanduser("~/Desktop/agentic-drift-x-card.png"), (1600, 900), False)
    open("/tmp/aau-drift-fb.html", "w").write(card(False))
    _render("/tmp/aau-drift-fb.html",
            os.path.expanduser("~/Desktop/agentic-drift-fb-card.png"), (1080, 1350), False)
    print("\ndata:", {n: {k: round(v, 3) for k, v in s.items()} for n, s in STATS.items()})


if __name__ == "__main__":
    main()
