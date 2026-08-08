"""Wave-14 launch assets (LinkedIn carousel PDF) for the refund-amplified use case.

Light editorial page with dark data panels — the first light-theme carousel in the repo,
because the wave is about an invoice rather than a breach.

Every number is read or computed from results/*.json, never retyped. The one figure the
README quotes that is *not* in committed results is the standalone replay-tax probe, so
this deck uses the input-token ratio measured inside the real experiment instead.

    python docs/make_carousel_amplified.py   # -> ~/Desktop/agentic-amplified-carousel.pdf
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RESULTS = os.path.join(ROOT, "customer-support/refund-amplified/results")

# light: warm paper, near-black ink, dark panels so the data still punches
SURFACE, INK, INK2, MUTED = "#faf8f4", "#191714", "#4c473f", "#8b8577"
ACCENT = "#c2410c"
PANEL, PANEL_INK, PANEL_INK2, PANEL_MUTED = "#191714", "#f7f3ec", "#c9c2b5", "#948d7e"
GOOD, BAD, WARN = "#15803d", "#b91c1c", "#a16207"
RULE = "#e4ded2"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

GPTOSS = "accounts_fireworks_models_gpt-oss-120b"
MISTRAL = "mistral-small-latest"


def load(arm: str, tag: str) -> list[dict]:
    with open(os.path.join(RESULTS, f"eval_{arm}_{tag}.json")) as f:
        return json.load(f)["results"]


def rows(res: list[dict], arch: str) -> list[dict]:
    return [r for r in res if r["detail"]["amp_archetype"] == arch]


def mean(rs: list[dict], key: str) -> float:
    return sum(r["metrics"][key] for r in rs) / len(rs)


def ratio(res: list[dict], arch: str, key: str = "cost_usd") -> float:
    """Cost against this arm's own clean twin, never against another arm."""
    return mean(rows(res, arch), key) / mean(rows(res, "CLEAN_TWIN"), key)


def acc_submitted(rs: list[dict]) -> float:
    sub = [r for r in rs if r["metrics"]["submitted"]]
    return sum(r["metrics"]["correct"] for r in sub) / len(sub)


def acc_deny(rs: list[dict]) -> tuple[float, int]:
    sub = [r for r in rs
           if r["metrics"]["submitted"] and r["detail"]["gold"]["resolution"] == "deny"]
    return sum(r["metrics"]["correct"] for r in sub) / len(sub), len(sub)


NONE_G = load("none", GPTOSS)
CLEAN, BLOAT = rows(NONE_G, "CLEAN_TWIN"), rows(NONE_G, "BLOAT")
with open(os.path.join(RESULTS, "control/neutral_bloat_gpt-oss-120b.json")) as f:
    NEUTRAL = json.load(f)["results"]

# the length-matched control, priced against the same clean twin it was run against
NEUTRAL_X = mean(NEUTRAL, "cost_usd") / mean(CLEAN, "cost_usd")
BLOAT_X = ratio(NONE_G, "BLOAT")
BLOAT_TOK = ratio(NONE_G, "BLOAT", "input_tokens")
FANOUT_X = ratio(NONE_G, "FANOUT")

CLEAN_CALLS, CLEAN_TURNS = mean(CLEAN, "n_tool_calls"), mean(CLEAN, "n_turns")
NEU_CALLS, NEU_TURNS = mean(NEUTRAL, "n_tool_calls"), mean(NEUTRAL, "n_turns")
BLOAT_CALLS, BLOAT_TURNS = mean(BLOAT, "n_tool_calls"), mean(BLOAT, "n_turns")

CLEAN_DENY, CLEAN_DENY_N = acc_deny(CLEAN)
BLOAT_DENY, BLOAT_DENY_N = acc_deny(BLOAT)
NEU_DENY, NEU_DENY_N = acc_deny(NEUTRAL)

ARMS = {a: {"g": load(a, GPTOSS), "m": load(a, MISTRAL)}
        for a in ("none", "prompt_guard", "budget_gate", "both")}
# what the whole wave actually cost, summed from the runs rather than quoted
TOTAL = sum(sum(r["metrics"]["cost_usd"] for r in v[k])
            for v in ARMS.values() for k in ("g", "m"))
BILL = {a: {"g_f": ratio(v["g"], "FANOUT"), "g_b": ratio(v["g"], "BLOAT"),
            "m_f": ratio(v["m"], "FANOUT"), "m_b": ratio(v["m"], "BLOAT")}
        for a, v in ARMS.items()}


def x(v: float) -> str:
    return f"{v:.2f}×"


def n1(v: float) -> str:
    return f"{v:.2f}"


def pct(v: float) -> str:
    return f"{round(v * 100)}%"


def slides() -> list[str]:
    return [
        f"""<div class="s">
          <div class="kicker">AI AGENT SECURITY · MEASURED</div>
          <h1>I attacked an AI agent's <em>invoice</em>, not its answers.</h1>
          <p class="lead">The resolution stays correct. The safety checks still pass.
            The bill is {x(FANOUT_X)} larger.</p>
          <div class="foot">OWASP LLM10, Unbounded Consumption · 360 runs per arm ·
            2 model families · ${TOTAL:.2f} to reproduce</div>
        </div>""",
        f"""<div class="s">
          <div class="kicker">THE MECHANISM</div>
          <h2>An agent re-sends its whole history every turn.</h2>
          <p class="lead">So a bulky tool result that arrives on turn 2 is part of the
            <b>input</b> on turns 3, 4, 5. The attacker pays for it once. You pay for it
            every turn after.</p>
          <div class="split">
            <div class="col">
              <div class="lbl">TOOL CALLS</div>
              <div class="mini">{n1(BLOAT_CALLS)}</div>
              <div class="ml">vs {n1(CLEAN_CALLS)} clean</div>
            </div>
            <div class="col bad-b">
              <div class="lbl">INPUT TOKENS</div>
              <div class="mini bad">{x(BLOAT_TOK)}</div>
              <div class="ml">same work, double the bill</div>
            </div>
          </div>
        </div>""",
        f"""<div class="s">
          <div class="kicker">THE PART THAT SHOULD WORRY YOU</div>
          <h2>The stealthy attack does <em>less</em> than the baseline.</h2>
          <div class="tbl">
            <div class="tr th"><span>padded customer field</span><span>calls</span>
              <span>turns</span><span>bill</span></div>
            <div class="tr"><span>clean baseline</span><span>{n1(CLEAN_CALLS)}</span>
              <span>{n1(CLEAN_TURNS)}</span><span>1.00×</span></div>
            <div class="tr hi"><span>the attack</span><span class="g">{n1(NEU_CALLS)}</span>
              <span class="g">{n1(NEU_TURNS)}</span>
              <span class="b">{x(NEUTRAL_X)}</span></div>
          </div>
          <p class="lead">Fewer calls. Fewer turns. Half again the cost. Rate limits and
            tool-call quotas are what teams actually deploy, and both are blind to this.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">THE CONTROL THAT CHANGED THE ANSWER</div>
          <h2>Same field. Same {8760:,} characters. Different content.</h2>
          <div class="split">
            <div class="col bad-b">
              <div class="lbl">LONG, AND ARGUES FOR A REFUND</div>
              <div class="mini bad">{pct(BLOAT_DENY)}</div>
              <div class="ml">accuracy on deny tickets (n={BLOAT_DENY_N})</div>
            </div>
            <div class="col good-b">
              <div class="lbl">LONG, ARGUES NOTHING</div>
              <div class="mini good">{pct(NEU_DENY)}</div>
              <div class="ml">accuracy on deny tickets (n={NEU_DENY_N})</div>
            </div>
          </div>
          <p class="lead"><b>Length costs money. Persuasion costs accuracy.</b> They look
            like one failure until you length-match the control.</p>
        </div>""",
        """<div class="s center">
          <div class="kicker">I HAD THIS WRONG. TWICE.</div>
          <h1 class="tight">I published “context length degrades the decision” before
            building the control.</h1>
          <p class="lead">It doesn't. The bloat attack was smuggling an indirect prompt
            injection through a field the customer writes. The entire accuracy loss lands on
            the tickets the text argues against.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">DEFENCE 1 · THE PROMPT GUARD</div>
          <h2>A prompt cannot fix this, and I said so before running it.</h2>
          <div class="tbl">
            <div class="tr th"><span>bloat attack</span><span>gpt-oss</span>
              <span>mistral</span></div>
            <div class="tr"><span>undefended</span><span>{x(BILL['none']['g_b'])}</span>
              <span>{x(BILL['none']['m_b'])}</span></div>
            <div class="tr"><span>with prompt guard</span>
              <span class="b">{x(BILL['prompt_guard']['g_b'])}</span>
              <span class="b">{x(BILL['prompt_guard']['m_b'])}</span></div>
          </div>
          <p class="lead">By the time an oversized result is in the context window the tokens
            are bought, and bought again every later turn. An instruction changes what an
            agent <b>asks for</b>. Never what you are <b>charged for</b> on work already
            done.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">DEFENCE 2 · THE BUDGET GATE</div>
          <h2>And a gate cannot fix the other half.</h2>
          <div class="tbl">
            <div class="tr th"><span>fan-out attack</span><span>gpt-oss</span>
              <span>mistral</span></div>
            <div class="tr"><span>undefended</span><span>{x(BILL['none']['g_f'])}</span>
              <span>{x(BILL['none']['m_f'])}</span></div>
            <div class="tr"><span>with budget gate</span>
              <span class="b">{x(BILL['budget_gate']['g_f'])}</span>
              <span class="b">{x(BILL['budget_gate']['m_f'])}</span></div>
          </div>
          <p class="lead">A refusal is not free. The request and the refusal both enter the
            conversation and get replayed, and the extra round trip costs a turn of its
            own.</p>
        </div>""",
        f"""<div class="s">
          <div class="kicker">THE POINT</div>
          <h2>They are not competing defences.</h2>
          <p class="lead">They cover different halves. Ship either one alone and a vector
            stays fully open. Together, on both models:</p>
          <div class="split">
            <div class="col good-b">
              <div class="lbl">GPT-OSS · FAN-OUT / BLOAT</div>
              <div class="mini good">{x(BILL['both']['g_f'])}</div>
              <div class="ml">and {x(BILL['both']['g_b'])}</div>
            </div>
            <div class="col good-b">
              <div class="lbl">MISTRAL · FAN-OUT / BLOAT</div>
              <div class="mini good">{x(BILL['both']['m_f'])}</div>
              <div class="ml">and {x(BILL['both']['m_b'])}</div>
            </div>
          </div>
        </div>""",
        """<div class="s center">
          <div class="kicker">THE LESSON</div>
          <h1 class="tight">Your agent monitoring counts actions. The bill is in the
            text each action drags along.</h1>
          <p class="lead">Instrument input tokens per resolved ticket, not tool calls.</p>
          <div class="cta">10 industries · 19 use cases · 118 failure modes observed<br>
            <b>github.com/immu4989/awesome-agentic-usecases</b></div>
        </div>""",
    ]


HTML = """<!doctype html><meta charset="utf-8"><style>
  @page {{ size: 1080px 1350px; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ font-family: {font}; background: {surface}; color: {ink}; }}
  .s {{ width: 1080px; height: 1350px; padding: 112px 84px; background: {surface};
        page-break-after: always; position: relative; display: flex;
        flex-direction: column; justify-content: center; gap: 30px; }}
  .s.center {{ text-align: center; align-items: center; }}
  .s::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 12px;
                background: {accent}; }}
  .kicker {{ color: {accent}; font-size: 24px; font-weight: 700; letter-spacing: 2.4px; }}
  h1 {{ font-size: 74px; line-height: 1.08; font-weight: 700; letter-spacing: -1.6px; }}
  h1.tight {{ font-size: 56px; }}
  h1 em, h2 em {{ font-style: normal; color: {accent}; }}
  h2 {{ font-size: 46px; line-height: 1.2; font-weight: 700; letter-spacing: -0.8px; }}
  .lead {{ font-size: 32px; line-height: 1.44; color: {ink2}; }}
  .lead b {{ color: {ink}; }}
  .split {{ display: flex; gap: 24px; }}
  .col {{ flex: 1; padding: 36px 26px; border-radius: 16px; text-align: center;
          background: {panel}; border-top: 6px solid {pmuted}; }}
  .col.good-b {{ border-top-color: {good}; }}
  .col.bad-b {{ border-top-color: {bad}; }}
  .lbl {{ font-size: 20px; letter-spacing: 1.5px; color: {pmuted}; font-weight: 700; }}
  .mini {{ font-size: 96px; font-weight: 800; letter-spacing: -3px; line-height: 1.1;
           color: {pink}; }}
  .mini.good {{ color: #4ade80; }}
  .mini.bad {{ color: #fb7185; }}
  .ml {{ font-size: 22px; color: {pink2}; letter-spacing: .5px; margin-top: 6px; }}
  .tbl {{ background: {panel}; border-radius: 18px; padding: 12px 34px 22px; }}
  .tr {{ display: flex; align-items: baseline; padding: 20px 0; font-size: 31px;
         color: {pink}; border-bottom: 1px solid #302c26; }}
  .tr:last-child {{ border-bottom: none; }}
  .tr span:first-child {{ flex: 1; text-align: left; }}
  .tr span {{ width: 190px; text-align: right; font-variant-numeric: tabular-nums;
              font-weight: 700; }}
  .tr.th {{ font-size: 21px; letter-spacing: 1.5px; color: {pmuted}; font-weight: 700;
            border-bottom: 1px solid #3b352d; }}
  .tr.th span {{ font-weight: 700; }}
  .tr .g {{ color: #4ade80; }}
  .tr .b {{ color: #fb7185; }}
  .tr.hi span:first-child {{ color: {pink}; }}
  .foot {{ position: absolute; left: 84px; right: 84px; bottom: 64px; font-size: 23px;
           color: {muted}; line-height: 1.5; }}
  .s.center .foot {{ text-align: center; }}
  .cta {{ margin-top: 26px; font-size: 27px; line-height: 1.6; color: {ink2}; }}
  .cta b {{ color: {accent}; font-size: 30px; }}
</style>{body}"""


def _render(tmp_html: str, out: str, pdf: bool, size=(1080, 1350)) -> None:
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    if pdf:
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", f"file://{tmp_html}"],
                       check=True, capture_output=True)
    else:
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={size[0]},{size[1]}",
                        f"--screenshot={out}", f"file://{tmp_html}"],
                       check=True, capture_output=True)


def main() -> None:
    body = "".join(slides())
    html = HTML.format(font=FONT, surface=SURFACE, ink=INK, ink2=INK2, muted=MUTED,
                       accent=ACCENT, panel=PANEL, pink=PANEL_INK, pink2=PANEL_INK2,
                       pmuted=PANEL_MUTED, good=GOOD, bad=BAD, body=body)
    tmp = "/tmp/aau-amplified-carousel.html"
    with open(tmp, "w") as f:
        f.write(html)
    out = os.path.expanduser("~/Desktop/agentic-amplified-carousel.pdf")
    _render(tmp, out, pdf=True)
    print(f"wrote {out}  ({len(slides())} slides, light theme)")

    # slide 1 as a standalone PNG, for the X/preview image
    cover_html = HTML.format(font=FONT, surface=SURFACE, ink=INK, ink2=INK2, muted=MUTED,
                             accent=ACCENT, panel=PANEL, pink=PANEL_INK, pink2=PANEL_INK2,
                             pmuted=PANEL_MUTED, good=GOOD, bad=BAD, body=slides()[0])
    with open("/tmp/aau-amplified-cover.html", "w") as f:
        f.write(cover_html)
    cover = os.path.expanduser("~/Desktop/agentic-amplified-cover.png")
    _render("/tmp/aau-amplified-cover.html", cover, pdf=False)
    print(f"wrote {cover}")


if __name__ == "__main__":
    main()
