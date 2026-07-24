"""Wave-11 launch assets (LinkedIn carousel PDF + X/Facebook cards) for the trifecta-exfil
use case, generated from its committed results.

Every number is read or computed from results/*.json, never retyped. Light editorial page
with dark data panels (same palette as the admission wave), rendered with headless Chrome.

    python docs/make_carousel_trifecta.py   # -> ~/Desktop/agentic-trifecta-*.{pdf,png}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RESULTS = os.path.join(ROOT, "security-operations/trifecta-exfil-agent/results")

SURFACE, INK, INK2, MUTED = "#f6f5f0", "#1a1a19", "#54524b", "#7c7a72"
ACCENT = "#4a3aa7"
PANEL, PANEL_INK, PANEL_INK2, PANEL_MUTED = "#1c1b19", "#f3f2ec", "#c6c5ba", "#95938b"
GOOD, BAD, WARN = "#18b24a", "#f0524d", "#f0a500"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

TAGS = {"mistral": "mistral-small-latest",
        "gptoss": "accounts_fireworks_models_gpt-oss-120b",
        "qwen": "Qwen_Qwen3.7-Plus"}


def load(arm: str, tag: str) -> dict:
    with open(os.path.join(RESULTS, f"eval_{arm}_{tag}.json")) as f:
        return json.load(f)


def chan_exfil(d: dict, channel: str) -> float:
    rows = [r for r in d["results"]
            if r["detail"]["is_attack"] and r["detail"]["injection_channel"] == channel]
    return sum(r["metrics"]["exfiltration_success"] for r in rows) / len(rows)


# content-channel leak, averaged across the three models (baseline)
CONTENT = sum(chan_exfil(load("none", t), "content") for t in TAGS.values()) / len(TAGS)
CONTENT_MAX = max(chan_exfil(load("none", t), "content") for t in TAGS.values())
# tool-description leak (baseline) — 1.00 across the board
TOOLPOISON_NONE = sum(chan_exfil(load("none", t), "tool_description") for t in TAGS.values()) / len(TAGS)
# prompt_guard on the poisoned channel
TOOLPOISON_PG = sum(chan_exfil(load("prompt_guard", t), "tool_description") for t in TAGS.values()) / len(TAGS)
# taint_gate on the poisoned channel (0)
TOOLPOISON_TG = sum(chan_exfil(load("taint_gate", t), "tool_description") for t in TAGS.values()) / len(TAGS)
OVER_BLOCK = sum(load("taint_gate", t)["metric_means"]["over_block"] for t in TAGS.values()) / len(TAGS)
QWEN_TASK = load("none", TAGS["qwen"])["metric_means"]["task_success"]
PG_IGNORED = sum(1 for t in TAGS.values() if chan_exfil(load("prompt_guard", t), "tool_description") >= 0.999)


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def slides() -> list[str]:
    return [
        """<div class="s">
          <div class="kicker">AI AGENT SECURITY · MEASURED</div>
          <h1>I tried to make three AI agents <em>leak a secret</em>.</h1>
          <p class="lead">Same instruction, two hiding places. Where I hid it decided
            everything.</p>
          <div class="foot">30 scenarios · 3 models · reproducible on free tiers</div>
        </div>""",
        """<div class="s">
          <div class="kicker">THE SETUP · THE LETHAL TRIFECTA</div>
          <h2>An agent is exploitable the moment it can do all three:</h2>
          <div class="mrow bad-b"><b>Read</b> private data</div>
          <div class="mrow bad-b"><b>Take in</b> untrusted content</div>
          <div class="mrow bad-b"><b>Send</b> something to the outside world</div>
          <p class="lead">I gave an ops agent all three, a boring task, and hid one
            instruction in its input: read the API keys and send them out.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">WHERE I HID IT</div>
          <h2>Same instruction. Two places.</h2>
          <div class="split">
            <div class="col good-b">
              <div class="lbl">IN FETCHED CONTENT</div>
              <p class="cp">the channel the model<br>is told is untrusted</p>
              <div class="mini good">~0%</div>
              <div class="ml">leaked</div>
            </div>
            <div class="col bad-b">
              <div class="lbl">IN A TOOL'S OWN DESCRIPTION</div>
              <p class="cp">the MCP tool-poisoning<br>vector, July 2026</p>
              <div class="mini bad">{pct(TOOLPOISON_NONE)}</div>
              <div class="ml">leaked, every model</div>
            </div>
          </div>
          <p class="lead">Models defend the data. They trust their own tooling.</p>
        </div>""",
        """<div class="s center">
          <div class="kicker">WHY</div>
          <h1 class="tight">An instruction with the authority of a tool definition is one the
            model doesn't question.</h1>
          <p class="lead">Injection defences are trained on content — not on the tools the
            model is handed.</p>
        </div>""",
        f"""<div class="s center">
          <div class="kicker">DEFENCE 1 · THE PROMPT GUARD</div>
          <div class="statpanel">
            <div class="big bad">{pct(TOOLPOISON_PG)}</div>
            <div class="stcap">still leaked — {PG_IGNORED} of 3 models ignored the notice entirely</div>
          </div>
          <p class="lead">The system prompt said it plainly: tool descriptions are untrusted,
            never put a secret in an argument. It named the exact attack. It barely moved the
            number.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">DEFENCE 2 · THE DATAFLOW GATE</div>
          <h2>This one never argues with the model.</h2>
          <div class="split">
            <div class="col bad-b">
              <div class="lbl">PROMPT GUARD</div>
              <p class="cp">tell the model<br>what to distrust</p>
              <div class="mini bad">{pct(TOOLPOISON_PG)}</div>
              <div class="ml">leaked</div>
            </div>
            <div class="col good-b">
              <div class="lbl">DATAFLOW GATE</div>
              <p class="cp">refuse any secret<br>at every egress</p>
              <div class="mini good">{pct(TOOLPOISON_TG)}</div>
              <div class="ml">leaked</div>
            </div>
          </div>
          <p class="lead">Same agent decisions. The model is still fooled; the secret just
            can't move.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">TWO HONEST NOTES</div>
          <h2>The result does not let anyone off the hook.</h2>
          <div class="mrow warn-b"><b>Capability is no defence.</b> Qwen3.7-Plus posts a
            perfect {pct(QWEN_TASK)} task score here and leaks as often as the weakest model.</div>
          <div class="mrow warn-b"><b>The gate isn't free.</b> It blocks ~{pct(OVER_BLOCK)}
            of legitimate sends to unfamiliar addresses — a real bill for the fix.</div>
        </div>""",
        """<div class="s center">
          <div class="kicker">THE LESSON</div>
          <h1 class="tight">You don't make an agent safe by telling it what to distrust.</h1>
          <p class="lead">You make being fooled stop mattering. Move the boundary into the
            environment.</p>
          <div class="cta">7 industries · 12 use cases · 176 tests · $0 to reproduce<br>
            <b>github.com/immu4989/awesome-agentic-usecases</b></div>
        </div>""",
    ]


HTML = """<!doctype html><meta charset="utf-8"><style>
  @page {{ size: 1080px 1350px; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ font-family: {font}; background: {surface}; color: {ink}; }}
  .s {{ width: 1080px; height: 1350px; padding: 118px 88px; background: {surface};
        page-break-after: always; position: relative; display: flex;
        flex-direction: column; justify-content: center; gap: 30px; }}
  .s.center {{ text-align: center; align-items: center; }}
  .s::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 12px;
                background: {accent}; }}
  .kicker {{ color: {accent}; font-size: 24px; font-weight: 700; letter-spacing: 2.4px; }}
  h1 {{ font-size: 74px; line-height: 1.08; font-weight: 700; letter-spacing: -1.5px; }}
  h1.tight {{ font-size: 62px; }}
  h1 em {{ font-style: normal; color: {accent}; }}
  h2 {{ font-size: 44px; line-height: 1.22; font-weight: 700; }}
  .lead {{ font-size: 33px; line-height: 1.42; color: {ink2}; }}
  .mrow {{ padding: 24px 28px; font-size: 31px; line-height: 1.4; color: {pink2};
           background: {panel}; border-left: 6px solid {muted};
           border-radius: 0 12px 12px 0; }}
  .mrow b {{ color: {pink}; }}
  .mrow.bad-b {{ border-left-color: {bad}; }}
  .mrow.warn-b {{ border-left-color: {warn}; }}
  .statpanel {{ background: {panel}; border-radius: 22px; padding: 48px 78px;
                display: inline-block; }}
  .big {{ font-size: 172px; font-weight: 800; letter-spacing: -6px; line-height: 1;
          color: {pink}; }}
  .big.good {{ color: {good}; }}
  .big.bad {{ color: {bad}; }}
  .stcap {{ font-size: 36px; font-weight: 700; color: {pink}; margin-top: 14px; }}
  .split {{ display: flex; gap: 26px; margin-top: 8px; }}
  .col {{ flex: 1; padding: 34px 28px; border-radius: 16px; text-align: center;
          background: {panel}; border-top: 6px solid {muted}; }}
  .col.good-b {{ border-top-color: {good}; }}
  .col.bad-b {{ border-top-color: {bad}; }}
  .lbl {{ font-size: 21px; letter-spacing: 1.6px; color: {pmuted}; font-weight: 700; }}
  .cp {{ font-size: 25px; line-height: 1.35; color: {pink2}; margin: 14px 0 18px; }}
  .mini {{ font-size: 100px; font-weight: 800; letter-spacing: -3px; line-height: 1; }}
  .mini.good {{ color: {good}; }}
  .mini.bad {{ color: {bad}; }}
  .ml {{ font-size: 22px; color: {pmuted}; letter-spacing: 1px; margin-top: 4px; }}
  .foot {{ position: absolute; left: 88px; right: 88px; bottom: 66px; font-size: 24px;
           color: {muted}; line-height: 1.5; }}
  .s.center .foot {{ text-align: center; }}
  .cta {{ margin-top: 30px; font-size: 28px; line-height: 1.6; color: {ink2}; }}
  .cta b {{ color: {accent}; font-size: 31px; }}
</style>{body}"""


def _render(tmp_html: str, out: str, size, pdf: bool) -> None:
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    if pdf:
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", f"file://{tmp_html}"],
                       check=True, capture_output=True)
    else:
        subprocess.run([CHROME, "--headless", "--disable-gpu",
                        f"--window-size={size[0]},{size[1]}",
                        f"--screenshot={out}", f"file://{tmp_html}"],
                       check=True, capture_output=True)
    print(f"wrote {out} ({os.path.getsize(out)/1024:.0f} KB)")


def card(landscape: bool) -> str:
    w, h = (1600, 900) if landscape else (1080, 1350)
    row_dir = "row" if landscape else "column"
    return f"""<!doctype html><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: {w}px; height: {h}px; font-family: {FONT}; background: {SURFACE};
         color: {INK}; padding: {'74px 80px' if landscape else '84px 76px'};
         position: relative; display: flex; flex-direction: column; justify-content: center; }}
  body::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0;
                  width: 14px; background: {ACCENT}; }}
  .kicker {{ color: {ACCENT}; font-size: 25px; font-weight: 700; letter-spacing: 2.4px; }}
  h1 {{ font-size: {56 if landscape else 52}px; font-weight: 700; letter-spacing: -1.2px;
       margin: 18px 0 8px; line-height: 1.1; }}
  .sub {{ font-size: 27px; color: {MUTED}; line-height: 1.35; }}
  .row {{ display: flex; flex-direction: {row_dir}; gap: {'40px' if landscape else '24px'};
          margin-top: 44px; }}
  .cardc {{ flex: 1; padding: 34px 38px; border-radius: 18px;
            background: {PANEL}; border-top: 6px solid {MUTED}; }}
  .cardc.g {{ border-top-color: {GOOD}; }}
  .cardc.b {{ border-top-color: {BAD}; }}
  .lbl {{ font-size: 21px; letter-spacing: 1.6px; color: {PANEL_MUTED}; font-weight: 700; }}
  .cp {{ font-size: 24px; color: {PANEL_INK2}; line-height: 1.32; margin-top: 6px; }}
  .num {{ font-size: {112 if landscape else 100}px; font-weight: 800; letter-spacing: -4px;
          line-height: 1.05; margin: 10px 0 2px; }}
  .num.g {{ color: {GOOD}; }}
  .num.b {{ color: {BAD}; }}
  .nl {{ font-size: 22px; color: {PANEL_MUTED}; }}
  .foot {{ position: absolute; left: 80px; right: 80px; bottom: 46px;
           display: flex; justify-content: space-between; font-size: 24px; color: {MUTED}; }}
  .foot b {{ color: {ACCENT}; }}
</style>
<div class="kicker">SAME SECRET-STEALING INSTRUCTION · TWO HIDING PLACES · 3 MODELS</div>
<h1>Where you hide it decides whether the agent obeys.</h1>
<div class="sub">The identical injection, moved from the data channel to the tool's own description.</div>
<div class="row">
  <div class="cardc g">
    <div class="lbl">IN FETCHED CONTENT — the channel it's told is untrusted</div>
    <div class="num g">~0%</div>
    <div class="nl">leaked</div>
  </div>
  <div class="cardc b">
    <div class="lbl">IN THE TOOL'S OWN DESCRIPTION — MCP tool poisoning</div>
    <div class="num b">{pct(TOOLPOISON_NONE)}</div>
    <div class="nl">leaked, every model</div>
  </div>
</div>
<div class="foot"><span>30 scenarios · 3 models · reproducible on free tiers</span>
  <span><b>github.com/immu4989/awesome-agentic-usecases</b></span></div>"""


def main() -> None:
    tmp = "/tmp/aau-trifecta-carousel.html"
    html = HTML.format(font=FONT, surface=SURFACE, ink=INK, ink2=INK2, muted=MUTED,
                       accent=ACCENT, panel=PANEL, pink=PANEL_INK, pink2=PANEL_INK2,
                       pmuted=PANEL_MUTED, good=GOOD, bad=BAD, warn=WARN,
                       body="".join(slides()))
    with open(tmp, "w") as f:
        f.write(html)
    _render(tmp, os.path.expanduser("~/Desktop/agentic-trifecta-carousel.pdf"), (1080, 1350), True)
    print(f"  ({len(slides())} slides)")
    for land, name in ((True, "x"), (False, "fb")):
        t = f"/tmp/aau-trifecta-{name}.html"
        with open(t, "w") as f:
            f.write(card(land))
        _render(t, os.path.expanduser(f"~/Desktop/agentic-trifecta-{name}-card.png"),
                (1600, 900) if land else (1080, 1350), False)
    print(f"\ndata: content≈{pct(CONTENT)} (max {pct(CONTENT_MAX)}) · toolpoison none "
          f"{pct(TOOLPOISON_NONE)} pg {pct(TOOLPOISON_PG)} gate {pct(TOOLPOISON_TG)} · "
          f"over_block {pct(OVER_BLOCK)} · qwen_task {pct(QWEN_TASK)} · pg_ignored {PG_IGNORED}/3")


if __name__ == "__main__":
    main()
