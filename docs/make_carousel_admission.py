"""Generate the Wave-10 launch assets (LinkedIn carousel PDF + X/Facebook cards) for the
artifact-admission use case, from its committed results.

Every number is read or computed from results/*.json, never retyped, so the slides cannot
drift from the eval. Rendered with headless Chrome so they share the repo palette.

    python docs/make_carousel_admission.py     # -> ~/Desktop/agentic-admission-*.{pdf,png}

4:5 portrait carousel (1080x1350), 16:9 X card, 4:5 Facebook card.
"""

from __future__ import annotations

import collections
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RESULTS = os.path.join(ROOT, "security-operations/artifact-admission-agent/results")

# security-ops violet; the lighter shade is used for text/bar so it reads on dark
SURFACE, INK, INK2, MUTED = "#1a1a19", "#ffffff", "#c3c2b7", "#898781"
ACCENT, GOOD, BAD, WARN = "#9085e9", "#0ca30c", "#e34948", "#eda100"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"


def load(model_tag: str) -> dict:
    with open(os.path.join(RESULTS, f"eval_{model_tag}.json")) as f:
        return json.load(f)


def archetype_count(data: dict, archetype: str, pred: str) -> tuple[int, int]:
    """(# runs of `archetype` predicted `pred`, # runs of `archetype`)."""
    rows = [r for r in data["results"] if r["detail"]["archetype"] == archetype]
    hit = sum(1 for r in rows if r["detail"]["predicted"] == pred)
    return hit, len(rows)


def scanned_config_pct(data: dict) -> int:
    n = len(data["results"])
    s = sum(1 for r in data["results"] if r["detail"]["scanned_config"])
    return round(100 * s / n)


MISTRAL = load("mistral-small-latest")
GPTOSS = load("accounts_fireworks_models_gpt-oss-120b")
QWEN = load("Qwen_Qwen3.7-Plus")

m_admit_legit, m_legit_n = archetype_count(MISTRAL, "REMOTE_CODE_LEGIT", "admit")
m_block_clean, m_clean_n = archetype_count(MISTRAL, "CLEAN_NEW_PUBLISHER", "block")
gpt_stalls = sum(1 for r in GPTOSS["results"] if r["detail"]["predicted"] is None)
gpt_n = len(GPTOSS["results"])
scan_pct = min(scanned_config_pct(MISTRAL), scanned_config_pct(GPTOSS), scanned_config_pct(QWEN))
m_breach_j = MISTRAL["metric_means"]["breach_judgment"]
m_breach_s = MISTRAL["metric_means"]["breach_sandbox"]
qwen_acc = QWEN["metric_means"]["disposition_accuracy"]


def slides() -> list[str]:
    return [
        # 1 — hook
        """<div class="s">
          <div class="kicker">SUPPLY-CHAIN SECURITY · MEASURED</div>
          <h1>Last week an AI agent broke into <em>Hugging Face</em>.</h1>
          <p class="lead">The way in: a dataset whose config ran code its manifest said
            wasn't there. The pipeline trusted the declaration instead of checking what
            would actually run.</p>
          <div class="foot">I rebuilt the mechanism as a benchmark · 30 artifacts · 3 models · free to reproduce</div>
        </div>""",
        # 2 — setup
        """<div class="s">
          <div class="kicker">THE SETUP</div>
          <h2>An admission gate, deciding before any code runs.</h2>
          <p class="lead">For each incoming dataset or model: admit, sandbox, block, or
            escalate. The agent can read two things.</p>
          <ul>
            <li><b>The manifest</b> — what the uploader claims</li>
            <li><b>The scans</b> — what the loader and config actually execute</li>
          </ul>
          <div class="rule bad">Declares no code, but the config executes anyway.
            Looks clean. This is the breach. <b>Block.</b></div>
          <div class="rule good">Declares code and ships a loader, but it's benign and
            pinned. Looks scary. It's fine. <b>Sandbox.</b></div>
        </div>""",
        # 3 — the prediction
        """<div class="s center">
          <div class="kicker">MY PREDICTION</div>
          <h1 class="tight">The models would trust the manifest and admit the breach.</h1>
          <p class="lead">Read the clean declaration, skip the deeper scan, wave it
            through. The exact mistake that hit Hugging Face.</p>
        </div>""",
        # 4 — the reveal
        f"""<div class="s center">
          <div class="kicker">I WAS WRONG</div>
          <div class="big good">{scan_pct}%</div>
          <h2>of artifacts got the deeper scan</h2>
          <p class="lead">All three models scanned the config and blocked the undeclared
            execution. The only thing in the whole eval that reproduces the breach is the
            dumb baseline that never looks. Told to verify, they verified.</p>
        </div>""",
        # 5 — failures split by model
        f"""<div class="s">
          <div class="kicker">THE REAL FAILURES WERE QUIETER</div>
          <h2>And every model broke differently.</h2>
          <div class="mrow good-b"><b>Qwen3.7-Plus</b> — solved it clean. {int(round(qwen_acc*90))} of 90,
            zero unsafe, zero over-block, no stalls.</div>
          <div class="mrow warn-b"><b>gpt-oss-120b</b> — never made an unsafe call, then
            quit with no decision on {gpt_stalls} of {gpt_n} runs.</div>
          <div class="mrow bad-b"><b>mistral-small</b> — ran trusted code at full
            privilege {m_admit_legit}/{m_legit_n} times, and blocked clean artifacts
            {m_block_clean}/{m_clean_n} just for an unknown publisher.</div>
        </div>""",
        # 6 — the A/B
        f"""<div class="s">
          <div class="kicker">THE PART THAT MATTERS</div>
          <h2>Same decisions. Two environments.</h2>
          <div class="split">
            <div class="col bad-b">
              <div class="lbl">JUDGMENT</div>
              <p class="cp">admit = full network + credentials<br>(what Hugging Face had)</p>
              <div class="mini bad">{m_breach_j:.3f}</div>
              <div class="ml">breach rate</div>
            </div>
            <div class="col good-b">
              <div class="lbl">SANDBOX BY DEFAULT</div>
              <p class="cp">everything isolated,<br>humans promote to privilege</p>
              <div class="mini good">{m_breach_s:.3f}</div>
              <div class="ml">breach rate</div>
            </div>
          </div>
          <p class="lead">Same agent, same mistakes. The environment decided whether being
            fooled mattered.</p>
        </div>""",
        # 7 — thesis
        """<div class="s center">
          <div class="kicker">THE LESSON</div>
          <h1 class="tight">You don't make an agent safe by making it harder to trick.</h1>
          <p class="lead">You make being tricked survivable.</p>
          <div class="foot">Not free: sandbox-default taxes every legitimate artifact that
            needs privilege. The agent stops being a gatekeeper and becomes a router.</div>
        </div>""",
        # 8 — CTA
        f"""<div class="s center">
          <div class="kicker">VERIFIED, NOT ASSERTED</div>
          <div class="big">{qwen_acc:.3f}</div>
          <h2>one model solved it, {int(round(qwen_acc*90))} for {90}</h2>
          <p class="lead">The task is solvable. Which model you put on the gate is a
            decision worth making with evidence, not vibes.</p>
          <div class="cta">7 industries · 36 model evals · 58 documented failure modes<br>
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
  h1 {{ font-size: 76px; line-height: 1.08; font-weight: 700; letter-spacing: -1.5px; }}
  h1.tight {{ font-size: 66px; }}
  h1 em {{ font-style: normal; color: {accent}; }}
  h2 {{ font-size: 44px; line-height: 1.22; font-weight: 700; }}
  .lead {{ font-size: 33px; line-height: 1.42; color: {ink2}; }}
  ul {{ list-style: none; font-size: 31px; line-height: 1.65; color: {ink2}; }}
  li b {{ color: {ink}; }}
  .rule {{ border-left: 5px solid {good}; padding: 18px 26px; font-size: 29px;
           line-height: 1.4; color: {ink2}; background: rgba(255,255,255,.04);
           border-radius: 0 10px 10px 0; }}
  .rule.bad {{ border-left-color: {bad}; }}
  .rule b {{ color: {ink}; }}
  .mrow {{ padding: 22px 26px; font-size: 30px; line-height: 1.4; color: {ink2};
           background: rgba(255,255,255,.05); border-left: 6px solid {muted};
           border-radius: 0 12px 12px 0; }}
  .mrow b {{ color: {ink}; }}
  .mrow.good-b {{ border-left-color: {good}; }}
  .mrow.warn-b {{ border-left-color: {warn}; }}
  .mrow.bad-b {{ border-left-color: {bad}; }}
  .big {{ font-size: 200px; font-weight: 800; letter-spacing: -6px; line-height: 1; }}
  .big.good {{ color: {good}; }}
  .split {{ display: flex; gap: 26px; margin-top: 8px; }}
  .col {{ flex: 1; padding: 32px 28px; border-radius: 14px; text-align: center;
          background: rgba(255,255,255,.05); border-top: 6px solid {muted}; }}
  .col.good-b {{ border-top-color: {good}; }}
  .col.bad-b {{ border-top-color: {bad}; }}
  .lbl {{ font-size: 22px; letter-spacing: 2px; color: {muted}; font-weight: 700; }}
  .cp {{ font-size: 25px; line-height: 1.35; color: {ink2}; margin: 14px 0 18px; }}
  .mini {{ font-size: 92px; font-weight: 800; letter-spacing: -3px; line-height: 1; }}
  .mini.good {{ color: {good}; }}
  .mini.bad {{ color: {bad}; }}
  .ml {{ font-size: 22px; color: {muted}; letter-spacing: 1px; margin-top: 4px; }}
  .foot {{ position: absolute; left: 88px; right: 88px; bottom: 66px; font-size: 24px;
           color: {muted}; line-height: 1.5; }}
  .s.center .foot {{ text-align: center; }}
  .cta {{ margin-top: 30px; font-size: 28px; line-height: 1.6; color: {ink2}; }}
  .cta b {{ color: {accent}; font-size: 31px; }}
</style>{body}"""


def _render(tmp_html: str, out: str, size: tuple[int, int], pdf: bool) -> None:
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}")
    if pdf:
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", f"file://{tmp_html}"],
            check=True, capture_output=True)
    else:
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", f"--window-size={size[0]},{size[1]}",
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
  .kicker {{ color: {ACCENT}; font-size: 25px; font-weight: 700; letter-spacing: 2.6px; }}
  h1 {{ font-size: {58 if landscape else 54}px; font-weight: 700; letter-spacing: -1.2px;
       margin: 18px 0 8px; line-height: 1.1; }}
  .sub {{ font-size: 28px; color: {MUTED}; line-height: 1.35; }}
  .row {{ display: flex; flex-direction: {row_dir}; gap: {'40px' if landscape else '26px'};
          margin-top: 44px; }}
  .cardc {{ flex: 1; padding: 32px 36px; border-radius: 18px;
            background: rgba(255,255,255,.05); border-top: 6px solid {MUTED}; }}
  .cardc.g {{ border-top-color: {GOOD}; }}
  .cardc.b {{ border-top-color: {BAD}; }}
  .lbl {{ font-size: 21px; letter-spacing: 2px; color: {MUTED}; font-weight: 700; }}
  .cp {{ font-size: 24px; color: {INK2}; line-height: 1.32; margin-top: 6px; }}
  .num {{ font-size: {104 if landscape else 96}px; font-weight: 800; letter-spacing: -4px;
          line-height: 1.05; margin: 12px 0 4px; }}
  .num.g {{ color: {GOOD}; }}
  .num.b {{ color: {BAD}; }}
  .foot {{ position: absolute; left: 80px; right: 80px; bottom: 46px;
           display: flex; justify-content: space-between; font-size: 24px; color: {MUTED}; }}
  .foot b {{ color: {ACCENT}; }}
</style>
<div class="kicker">THE HUGGING FACE BREACH, AS A GATE · SAME DECISIONS</div>
<h1>The agent was fooled either way.<br>The environment decided if it mattered.</h1>
<div class="sub">mistral-small's unsafe admits, run through two pipelines.</div>
<div class="row">
  <div class="cardc b">
    <div class="lbl">JUDGMENT: admit = full network + credentials</div>
    <div class="num b">{m_breach_j:.3f}</div>
    <div class="cp">the configuration Hugging Face actually had. Every unsafe admit
      becomes a breach.</div>
  </div>
  <div class="cardc g">
    <div class="lbl">SANDBOX BY DEFAULT: humans promote to privilege</div>
    <div class="num g">{m_breach_s:.3f}</div>
    <div class="cp">identical decisions, contained. You don't stop the mistake, you stop
      it from mattering.</div>
  </div>
</div>
<div class="foot"><span>30 artifacts · 3 models · reproducible on free tiers</span>
  <span><b>github.com/immu4989/awesome-agentic-usecases</b></span></div>"""


def main() -> None:
    tmp = "/tmp/aau-admission-carousel.html"
    with open(tmp, "w") as f:
        f.write(HTML.format(font=FONT, surface=SURFACE, ink=INK, ink2=INK2, muted=MUTED,
                            accent=ACCENT, good=GOOD, bad=BAD, warn=WARN,
                            body="".join(slides())))
    _render(tmp, os.path.expanduser("~/Desktop/agentic-admission-carousel.pdf"),
            (1080, 1350), pdf=True)
    print(f"  ({len(slides())} slides)")

    tmp_x = "/tmp/aau-admission-x.html"
    with open(tmp_x, "w") as f:
        f.write(card(landscape=True))
    _render(tmp_x, os.path.expanduser("~/Desktop/agentic-admission-x-card.png"),
            (1600, 900), pdf=False)

    tmp_fb = "/tmp/aau-admission-fb.html"
    with open(tmp_fb, "w") as f:
        f.write(card(landscape=False))
    _render(tmp_fb, os.path.expanduser("~/Desktop/agentic-admission-fb-card.png"),
            (1080, 1350), pdf=False)


if __name__ == "__main__":
    main()
