"""Generate a LinkedIn carousel (PDF) from a use case's committed results.

LinkedIn document posts are PDFs. This builds one page-per-slide HTML file and prints
it with headless Chrome, so the slides inherit the same palette as the repo's README
assets and the numbers come from results/ rather than being retyped.

    python docs/make_carousel.py            # -> ~/Desktop/agentic-refund-carousel.pdf

4:5 portrait (1080x1350) because it takes the most vertical space in the feed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RESULTS = os.path.join(
    ROOT, "customer-support/refund-resolution-agent/results"
)

SURFACE, INK, INK2, MUTED = "#1a1a19", "#ffffff", "#c3c2b7", "#898781"
ACCENT, GOOD, BAD = "#eda100", "#0ca30c", "#e34948"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"


def load(model_tag: str) -> dict:
    with open(os.path.join(RESULTS, f"eval_{model_tag}.json")) as f:
        return json.load(f)["metric_means"]


def slides() -> list[str]:
    mistral = load("mistral-small-latest")
    gptoss = load("accounts_fireworks_models_gpt-oss-120b")
    qwen = load("Qwen_Qwen3.7-Plus")

    def pct(x: float) -> str:
        return f"{x * 100:.0f}%"

    return [
        # 1 — hook
        """<div class="s">
          <div class="kicker">AGENT SAFETY · MEASURED</div>
          <h1>I gave an AI agent the power to <em>issue refunds</em>.</h1>
          <p class="lead">Then I checked what it actually did with that power.</p>
          <div class="foot">270 runs · 3 models · reproducible on free tiers</div>
        </div>""",
        # 2 — setup
        """<div class="s">
          <div class="kicker">THE SETUP</div>
          <h2>Eight tools. Two of them cannot be undone.</h2>
          <ul>
            <li><b>Read-only:</b> verify identity, account, order, policy search</li>
            <li><b>Irreversible:</b> issue refund, send replacement</li>
          </ul>
          <p class="lead">Two rules in the policy KB:</p>
          <div class="rule">Verify identity <b>before</b> touching money or account data</div>
          <div class="rule bad">Never refund a customer whose bank chargeback is already
            in flight. Paying then pays them twice, and neither payment comes back.</div>
        </div>""",
        # 3 — ordering rule held
        f"""<div class="s center">
          <div class="kicker">RESULT 1 · THE ORDERING RULE</div>
          <div class="big good">{pct(mistral['prerequisite_respected'])}</div>
          <h2>obeyed, across all 270 runs</h2>
          <p class="lead">Not one model ever moved money or opened account data before
            verifying identity. Zero violations, every model, every scenario.</p>
        </div>""",
        # 4 — prohibition failed
        """<div class="s center">
          <div class="kicker">RESULT 2 · THE PROHIBITION</div>
          <div class="big bad">15 / 15</div>
          <h2>forbidden refunds, in every banned scenario type</h2>
          <p class="lead">Mistral Small searched the policy. Quoted the policy.
            Refunded anyway. 45 of its 90 runs moved money it was not allowed to move.</p>
        </div>""",
        # 5 — the insight
        """<div class="s">
          <div class="kicker">WHY</div>
          <h2>Same model. Same policy. Same run.<br>One rule obeyed always, one violated always.</h2>
          <div class="split">
            <div class="col good-b">
              <div class="lbl">CEREMONY</div>
              <div class="q">&ldquo;Verify identity first&rdquo;</div>
              <p>A step you <b>add</b> to a sequence.<br>Models are reliably good at this.</p>
            </div>
            <div class="col bad-b">
              <div class="lbl">PROHIBITION</div>
              <div class="q">&ldquo;Never refund here&rdquo;</div>
              <p>A step you must <b>not</b> take.<br>A completely different ask.</p>
            </div>
          </div>
        </div>""",
        # 6 — takeaway
        """<div class="s center">
          <div class="kicker">THE TAKEAWAY</div>
          <h1 class="tight">Prohibitions do not belong<br>in the prompt.</h1>
          <p class="lead">Put them in the tool layer, where the tool <b>refuses</b>
            instead of the model <b>remembering</b>.</p>
          <div class="foot">If your agent has write access, this is the cheapest safety win available.</div>
        </div>""",
        # 7 — two more findings
        f"""<div class="s">
          <div class="kicker">TWO MORE THINGS FELL OUT</div>
          <h2>Handoff is not completion</h2>
          <p class="lead">gpt-oss-120b abandoned 29 tickets. <b>23 of those stalls came
            immediately after it called the escalate tool.</b> Right decision, right
            action, ticket never closed.</p>
          <h2 class="mt">Completion breaks before accuracy does</h2>
          <p class="lead">The same model commits to a decision 93–100% of the time on
            read-only triage. Given tools that act, it finished only
            <b>{pct(gptoss['submitted'])}</b> of tickets.</p>
        </div>""",
        # 8 — CTA
        f"""<div class="s center">
          <div class="kicker">IT IS SOLVABLE</div>
          <div class="big">{qwen['safe_and_correct']:.3f}</div>
          <h2>Qwen3.7-Plus, with zero unsafe actions in 90 runs</h2>
          <p class="lead">So the lesson is not that acting agents are unsafe. It is that
            <b>which</b> model you hand irreversible tools to is a decision worth making
            with evidence.</p>
          <div class="cta">6 industries · 21 model evals · 32 documented failure modes<br>
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
  h1 {{ font-size: 78px; line-height: 1.08; font-weight: 700; letter-spacing: -1.5px; }}
  h1.tight {{ font-size: 72px; }}
  h1 em {{ font-style: normal; color: {accent}; }}
  h2 {{ font-size: 44px; line-height: 1.22; font-weight: 700; }}
  h2.mt {{ margin-top: 30px; }}
  .lead {{ font-size: 34px; line-height: 1.42; color: {ink2}; }}
  ul {{ list-style: none; font-size: 32px; line-height: 1.7; color: {ink2}; }}
  li b {{ color: {ink}; }}
  .rule {{ border-left: 5px solid {good}; padding: 18px 26px; font-size: 30px;
           line-height: 1.4; color: {ink2}; background: rgba(255,255,255,.04);
           border-radius: 0 10px 10px 0; }}
  .rule.bad {{ border-left-color: {bad}; }}
  .rule b {{ color: {ink}; }}
  .big {{ font-size: 210px; font-weight: 800; letter-spacing: -6px; line-height: 1; }}
  .big.good {{ color: {good}; }}
  .big.bad {{ color: {bad}; }}
  .split {{ display: flex; gap: 26px; margin-top: 14px; }}
  .col {{ flex: 1; padding: 30px 28px; border-radius: 14px;
          background: rgba(255,255,255,.05); border-top: 5px solid {muted}; }}
  .col.good-b {{ border-top-color: {good}; }}
  .col.bad-b {{ border-top-color: {bad}; }}
  .lbl {{ font-size: 20px; letter-spacing: 2px; color: {muted}; font-weight: 700; }}
  .q {{ font-size: 32px; font-weight: 700; margin: 14px 0 16px; }}
  .col p {{ font-size: 26px; line-height: 1.45; color: {ink2}; }}
  .foot {{ position: absolute; left: 88px; right: 88px; bottom: 72px; font-size: 24px;
           color: {muted}; }}
  .s.center .foot {{ text-align: center; }}
  .cta {{ margin-top: 30px; font-size: 28px; line-height: 1.6; color: {ink2}; }}
  .cta b {{ color: {accent}; font-size: 32px; }}
</style>{body}"""


def main() -> None:
    out_pdf = os.path.expanduser("~/Desktop/agentic-refund-carousel.pdf")
    tmp_html = "/tmp/aau-carousel.html"
    html = HTML.format(font=FONT, surface=SURFACE, ink=INK, ink2=INK2, muted=MUTED,
                       accent=ACCENT, good=GOOD, bad=BAD, body="".join(slides()))
    with open(tmp_html, "w") as f:
        f.write(html)
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out_pdf}", f"file://{tmp_html}"],
        check=True, capture_output=True,
    )
    size = os.path.getsize(out_pdf)
    print(f"wrote {out_pdf} ({size/1024:.0f} KB, {len(slides())} slides)")

    # X card: 16:9 so it renders full-width in the timeline without cropping.
    out_png = os.path.expanduser("~/Desktop/agentic-refund-x-card.png")
    tmp_card = "/tmp/aau-x-card.html"
    with open(tmp_card, "w") as f:
        f.write(x_card())
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--window-size=1600,900",
         "--default-background-color=00000000", f"--screenshot={out_png}",
         f"file://{tmp_card}"],
        check=True, capture_output=True,
    )
    print(f"wrote {out_png} ({os.path.getsize(out_png)/1024:.0f} KB, 1600x900)")


def x_card() -> str:
    """One landscape frame carrying the whole contrast: the rule they obeyed
    against the rule they broke."""
    return f"""<!doctype html><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: 1600px; height: 900px; font-family: {FONT}; background: {SURFACE};
         color: {INK}; padding: 74px 80px; position: relative;
         display: flex; flex-direction: column; justify-content: center; }}
  body::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0;
                  width: 14px; background: {ACCENT}; }}
  .kicker {{ color: {ACCENT}; font-size: 25px; font-weight: 700; letter-spacing: 2.6px; }}
  h1 {{ font-size: 62px; font-weight: 700; letter-spacing: -1.2px; margin: 18px 0 8px; }}
  .sub {{ font-size: 29px; color: {MUTED}; }}
  .row {{ display: flex; gap: 40px; margin-top: 46px; }}
  .card {{ flex: 1; padding: 34px 38px; border-radius: 18px;
           background: rgba(255,255,255,.05); border-top: 6px solid {MUTED}; }}
  .card.g {{ border-top-color: {GOOD}; }}
  .card.b {{ border-top-color: {BAD}; }}
  .lbl {{ font-size: 21px; letter-spacing: 2px; color: {MUTED}; font-weight: 700; }}
  .num {{ font-size: 116px; font-weight: 800; letter-spacing: -4px; line-height: 1.05;
          margin: 10px 0 6px; }}
  .num.g {{ color: {GOOD}; }}
  .num.b {{ color: {BAD}; }}
  .cap {{ font-size: 27px; line-height: 1.34; color: {INK2}; }}
  .foot {{ position: absolute; left: 80px; right: 80px; bottom: 46px;
           display: flex; justify-content: space-between; font-size: 24px;
           color: {MUTED}; }}
  .foot b {{ color: {ACCENT}; }}
</style>
<div class="kicker">AGENT SAFETY · 270 RUNS · 3 MODELS</div>
<h1>Same policy document. Same run.</h1>
<div class="sub">One rule obeyed every single time. One violated every single time.</div>
<div class="row">
  <div class="card g">
    <div class="lbl">CEREMONY &mdash; &ldquo;verify identity first&rdquo;</div>
    <div class="num g">100%</div>
    <div class="cap">No model ever moved money before verifying. Zero violations
      across all 270 runs.</div>
  </div>
  <div class="card b">
    <div class="lbl">PROHIBITION &mdash; &ldquo;never refund here&rdquo;</div>
    <div class="num b">15 / 15</div>
    <div class="cap">Mistral Small searched the policy, quoted it, and refunded
      anyway. Every banned scenario type.</div>
  </div>
</div>
<div class="foot"><span>Put prohibitions in the tool layer, not the prompt.</span>
  <span><b>github.com/immu4989/awesome-agentic-usecases</b></span></div>"""


if __name__ == "__main__":
    main()
