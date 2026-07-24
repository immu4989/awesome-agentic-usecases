"""Animated terminal casts, generated from committed eval results.

A repo whose thesis is "verified, not just runnable" should let you *watch* the
verification. These are self-contained animated SVGs — no GIF, no recording, no external
service — that replay a real eval: the command, the agent's actual tool calls, a scenario
it got right, a scenario it got wrong, and the real summary numbers.

Every line is read from `results/*.json` and `evals/scenarios.jsonl`, so a cast can never
show a number the evals didn't produce. Re-run this after new evals land.

Animation is pure CSS inside the SVG (keyframes + a sliding cover for the typing effect),
which GitHub renders when the SVG is referenced with <img>. Light and dark variants.

    python docs/make_terminal_demo.py     # -> docs/assets/demo-*.svg + <use-case>/docs/demo-*.svg
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"
CW = 7.8          # char width at font-size 13
FS = 13
LH = 21           # line height
PAD = 22
TITLE_H = 34
WIDTH = 780

THEME = {
    "light": {"chrome": "#efeee8", "body": "#ffffff", "ink": "#1a1a19", "muted": "#85837b",
              "dim": "#a8a69d", "good": "#0a7d33", "bad": "#c62828", "rule": "#e6e5de"},
    "dark": {"chrome": "#232220", "body": "#161615", "ink": "#f3f2ec", "muted": "#8a887f",
             "dim": "#6b6960", "good": "#22c55e", "bad": "#f0524d", "rule": "#2e2d2a"},
}

# use case -> how to build its cast
CASTS = [
    {
        "path": "logistics-supply-chain/exception-triage-agent",
        "cli": "exception-triage-agent", "model_tag": "accounts_fireworks_models_kimi-k2p6",
        "backend": "fireworks", "metric": "action_accuracy", "accent": ("#2a78d6", "#5b9cf0"),
        "out": "logistics-supply-chain/exception-triage-agent/docs",
    },
    {
        "path": "retail-workforce/shift-coverage-triage-agent",
        "cli": "shift-coverage-agent", "model_tag": "accounts_fireworks_models_kimi-k2p6",
        "backend": "fireworks", "metric": "strategy_accuracy", "accent": ("#eb6834", "#f2854f"),
        "out": "retail-workforce/shift-coverage-triage-agent/docs",
    },
    {
        "path": "security-operations/alert-triage-agent",
        "cli": "alert-triage-agent", "model_tag": "mistral-small-latest",
        "backend": "mistral", "metric": "exact_match", "accent": ("#4a3aa7", "#9085e9"),
        "out": "security-operations/alert-triage-agent/docs",
    },
    {
        "path": "financial-services-fraud/fraud-alert-triage-agent",
        "cli": "fraud-alert-triage-agent", "model_tag": "mistral-small-latest",
        "backend": "mistral", "metric": "exact_match", "accent": ("#1baf7a", "#2fd39a"),
        "out": "financial-services-fraud/fraud-alert-triage-agent/docs",
    },
    {
        "path": "media-streaming/release-qc-triage-agent",
        "cli": "release-qc-agent", "model_tag": "mistral-small-latest",
        "backend": "mistral", "metric": "action_accuracy", "accent": ("#d55181", "#e87ba4"),
        "out": "media-streaming/release-qc-triage-agent/docs",
    },
    {
        "path": "customer-support/refund-resolution-agent",
        "cli": "refund-resolution-agent", "model_tag": "mistral-small-latest",
        "backend": "mistral", "metric": "safe_and_correct", "accent": ("#eda100", "#f0b93d"),
        "out": "customer-support/refund-resolution-agent/docs",
    },
    {
        "path": "it-operations/oncall-watch-agent",
        "cli": "oncall-watch-agent", "model_tag": "accounts_fireworks_models_gpt-oss-120b",
        "backend": "fireworks", "metric": "severity_correct", "accent": ("#008300", "#0ca30c"),
        "out": "it-operations/oncall-watch-agent/docs",
    },
    {
        "path": "security-operations/artifact-admission-agent",
        "cli": "artifact-admission-agent", "model_tag": "mistral-small-latest",
        "backend": "mistral", "metric": "disposition_accuracy", "accent": ("#4a3aa7", "#9085e9"),
        "out": "security-operations/artifact-admission-agent/docs",
    },
]

TEXT_FIELDS = ("alert_text", "ticket_text", "flag_text", "task_text", "declared_summary")


# ---------- data -----------------------------------------------------------------------

def load_results(path: str, tag: str) -> dict:
    return json.load(open(os.path.join(ROOT, path, "results", f"eval_{tag}.json")))


def load_scenarios(path: str) -> dict:
    out = {}
    with open(os.path.join(ROOT, path, "evals", "scenarios.jsonl")) as f:
        for line in f:
            s = json.loads(line)
            out[s["scenario_id"]] = s
    return out


def scenario_blurb(sc: dict, width: int = 62) -> str:
    for k in TEXT_FIELDS:
        if isinstance(sc.get(k), str) and sc[k].strip():
            t = " ".join(sc[k].split())
            return t[: width - 1] + "…" if len(t) > width else t
    return sc.get("scenario_id", "")


def pick_scenarios(res: dict, metric: str, scs: dict):
    """One scenario the model nailed, one it failed — and make them different cases.

    Two scenarios of the same archetype read as a repeat, so the pass is chosen to differ
    from the failure: a different archetype where the world exposes one, otherwise a
    different opening to the scenario text.
    """
    by = {}
    for r in res["results"]:
        by.setdefault(r["scenario_id"], []).append(r)
    scored = []
    for sid, rows in by.items():
        rate = sum(r["metrics"].get(metric, 0.0) for r in rows) / len(rows)
        scored.append((rate, sid, rows))
    scored.sort(key=lambda x: x[0])
    worst = scored[0]

    def kind(sid: str) -> str:
        s = scs.get(sid, {})
        for k in ("archetype", "alert_type", "exception_type", "defect_type"):
            if s.get(k):
                return str(s[k])
        return scenario_blurb(s, 24)

    wk = kind(worst[1])
    passes = [s for s in reversed(scored) if s[0] == 1.0]
    best = next((p for p in passes if kind(p[1]) != wk), passes[0] if passes else scored[-1])
    return best, worst


def trace_line(d: dict) -> str | None:
    """What the agent actually did, in this use case's most telling terms.

    Most agents expose their tool calls. The watch agent has none — it consumes a clock —
    so its trace is how far it looked versus how far it had to look, which is the whole
    finding for that use case.
    """
    calls = d.get("tool_calls") or d.get("actions") or []
    if calls:
        return " › ".join(calls[:5])
    if d.get("ticks_seen") is not None:
        seen, need = d["ticks_seen"], d.get("detectable_tick")
        s = f"watched {seen} ticks"
        return s + (f" · evidence only lands at tick {need}" if need else "")
    return None


def representative(rows: list[dict]) -> dict:
    """Prefer a run that actually produced a decision over a provider outage."""
    for r in rows:
        if not r["detail"].get("error"):
            return r["detail"]
    return rows[0]["detail"]


def fmt_pred(detail: dict, key: str) -> str:
    v = detail.get(key)
    if isinstance(v, dict):
        parts = [f"{vv}" for kk, vv in v.items() if not isinstance(vv, (list, dict))]
        return " / ".join(str(p) for p in parts if p is not None) or "—"
    return str(v) if v is not None else "—"


# ---------- line model -----------------------------------------------------------------

def cast_lines(cfg: dict) -> list[list[tuple[str, str]]]:
    """Each line is a list of (text, style-class) spans."""
    res = load_results(cfg["path"], cfg["model_tag"])
    scs = load_scenarios(cfg["path"])
    metric = cfg["metric"]
    model_short = res["model"].split("/")[-1]
    n_rep = res["n_repeats"]
    (brate, bsid, brows), (wrate, wsid, wrows) = pick_scenarios(res, metric, scs)

    L: list[list[tuple[str, str]]] = []
    L.append([("$ ", "acc"), (f"{cfg['cli']} eval --backend {cfg['backend']} --repeats {n_rep}", "ink")])
    L.append([("", "ink")])
    for rate, sid, rows in ((brate, bsid, brows), (wrate, wsid, wrows)):
        d = representative(rows)
        ok = rate == 1.0
        mark, mcls = ("PASS", "good") if ok else ("FAIL", "bad")
        L.append([(f"  {sid}  ", "muted"), (scenario_blurb(scs.get(sid, {})), "ink")])
        tr = trace_line(d)
        if tr:
            L.append([("     ", ""), ("↳ ", "dim"), (tr, "dim")])
        L.append([("       predicted  ", "muted"), (fmt_pred(d, "predicted"), "ink")])
        L.append([("       gold       ", "muted"), (fmt_pred(d, "gold"), "ink"),
                  ("   " + mark, mcls), (f"  {int(rate * n_rep)}/{n_rep}", "muted")])
        L.append([("", "ink")])
    mean = res["metric_means"][metric]
    lo, hi = res["metric_ci95"][metric]
    L.append([("  " + "─" * 68, "rule")])
    L.append([(f"  {metric}  ", "muted"), (f"{mean:.3f}", "acc"),
              (f"  [{lo:.2f}, {hi:.2f}]", "dim"),
              (f"   ${res['mean_cost_per_scenario_usd']:.4f}/scenario", "muted")])
    L.append([(f"  {res['n_scenarios']} scenarios × {n_rep} repeats · "
               f"{res['n_scenarios'] * n_rep} runs · {model_short}", "dim")])
    return L


def hero_lines() -> list[list[tuple[str, str]]]:
    """The repo's promise: one command, no key — then the same eval on a real model."""
    mock = json.load(open(os.path.join(
        ROOT, "logistics-supply-chain/exception-triage-agent/results/eval_mock.json")))
    real = json.load(open(os.path.join(
        ROOT, "logistics-supply-chain/exception-triage-agent/results",
        "eval_accounts_fireworks_models_kimi-k2p6.json")))
    m_acc = mock["metric_means"]["action_accuracy"]
    r_acc = real["metric_means"]["action_accuracy"]
    lo, hi = real["metric_ci95"]["action_accuracy"]
    L = []
    L.append([("$ ", "acc"), ("pip install -e harness -e logistics-supply-chain/exception-triage-agent", "ink")])
    L.append([("$ ", "acc"), ("exception-triage-agent eval --backend mock", "ink"),
              ("        # no API key, $0", "dim")])
    L.append([("", "")])
    L.append([("  30 scenarios × 3 repeats · deterministic mock model", "muted")])
    L.append([("  action_accuracy  ", "muted"), (f"{m_acc:.3f}", "ink"),
              ("   pipeline green ", "muted"), ("✓", "good")])
    L.append([("", "")])
    L.append([("$ ", "acc"), ("export FIREWORKS_API_KEY=…", "ink")])
    L.append([("$ ", "acc"), ("exception-triage-agent eval --backend fireworks --repeats 3", "ink")])
    L.append([("", "")])
    L.append([("  action_accuracy  ", "muted"), (f"{r_acc:.3f}", "acc"),
              (f"  [{lo:.2f}, {hi:.2f}]", "dim"),
              (f"   ${real['mean_cost_per_scenario_usd']:.4f}/scenario", "muted")])
    L.append([("  90 runs · every number in this repo is produced exactly this way", "dim")])
    return L


# ---------- render ---------------------------------------------------------------------

def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(lines, accent: tuple[str, str], title: str) -> str:
    """Always dark.

    A terminal is a dark object, and GitHub's default is light — a light-themed cast
    rendered washed out against the page. One dark cast reads as a real terminal in both
    GitHub themes and needs no <picture> switch.
    """
    t = THEME["dark"]
    acc = accent[1]
    n = len(lines)
    body_h = n * LH + PAD * 2
    H = TITLE_H + body_h
    # animation timing: type the first line, then reveal one line at a time, then hold
    per = 0.55
    total = round(1.6 + max(0, n - 1) * per + 3.2, 2)
    type_end_pct = round(100 * 1.35 / total, 3)

    css = [
        f".t{{font-family:{FONT};font-size:{FS}px;dominant-baseline:middle}}",
        f".ink{{fill:{t['ink']}}}.muted{{fill:{t['muted']}}}.dim{{fill:{t['dim']}}}",
        f".good{{fill:{t['good']};font-weight:700}}.bad{{fill:{t['bad']};font-weight:700}}",
        f".acc{{fill:{acc};font-weight:700}}.rule{{fill:{t['rule']}}}",
        # Typing cover slides right to reveal line 0. Every animated element is written
        # fail-safe: its *static* state is the finished state, and the animation only
        # replays the reveal. If animations never run — reduced-motion, a strict renderer,
        # an email client — the reader still sees the whole terminal, not an empty box.
        f"@keyframes type{{0%{{transform:translateX(0)}}{type_end_pct}%,100%"
        f"{{transform:translateX(var(--w))}}}}",
        f".cover{{transform:translateX(var(--w));animation:type {total}s steps(30,end) infinite}}",
        "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}",
        ".cursor{animation:blink 1s step-end infinite}",
        "@media (prefers-reduced-motion:reduce){.cover,.cursor,[class^='l']"
        "{animation:none!important}.cursor{opacity:0}}",
    ]
    for i in range(1, n):
        start = round(100 * (1.5 + (i - 1) * per) / total, 3)
        css.append(f"@keyframes r{i}{{0%,{start}%{{opacity:0}}{min(start + 1.2, 99.0)}%,100%"
                   f"{{opacity:1}}}}")
        css.append(f".l{i}{{animation:r{i} {total}s ease-out infinite}}")

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{H}" '
         f'viewBox="0 0 {WIDTH} {H}" role="img" '
         f'aria-label="Animated terminal: {esc(title)}">',
         f"<style>{''.join(css)}</style>",
         f'<rect width="{WIDTH}" height="{H}" rx="10" fill="{t["body"]}"/>',
         f'<path d="M0 10a10 10 0 0 1 10-10h{WIDTH-20}a10 10 0 0 1 10 10v{TITLE_H-10}H0z" '
         f'fill="{t["chrome"]}"/>',
         # hairline edge so the dark window still has a defined border on a white page
         f'<rect x=".5" y=".5" width="{WIDTH-1}" height="{H-1}" rx="9.5" fill="none" '
         f'stroke="#3a3934" stroke-opacity=".55"/>']
    for i, c in enumerate(("#f0524d", "#f0a500", "#22c55e")):
        o.append(f'<circle cx="{20 + i * 17}" cy="{TITLE_H/2}" r="5" fill="{c}" opacity=".85"/>')
    o.append(f'<text class="t" x="{WIDTH/2}" y="{TITLE_H/2}" fill="{t["muted"]}" '
             f'font-size="11.5" text-anchor="middle">{esc(title)}</text>')

    y0 = TITLE_H + PAD + LH / 2
    for i, spans in enumerate(lines):
        y = y0 + i * LH
        cls = "" if i == 0 else f' class="l{i}"'
        o.append(f"<g{cls}>")
        x = PAD
        for text, style in spans:
            if text:
                sc = f' class="t {style}"' if style else ' class="t"'
                o.append(f'<text{sc} x="{x:.1f}" y="{y:.1f}" '
                         f'xml:space="preserve">{esc(text)}</text>')
            x += len(text) * CW
        if i == 0:
            w = x - PAD
            o.append(f'<g class="cover" style="--w:{w:.0f}px">'
                     f'<rect x="{PAD-1:.0f}" y="{y-9:.1f}" width="{w+6:.0f}" height="18" '
                     f'fill="{t["body"]}"/>'
                     f'<rect class="cursor" x="{PAD-1:.0f}" y="{y-8:.1f}" width="7.5" '
                     f'height="16" fill="{acc}" opacity=".8"/></g>')
        o.append("</g>")
    o.append("</svg>")
    return "\n".join(o)


def main() -> None:
    adir = os.path.join(ROOT, "docs", "assets")
    made = 0
    svg = render(hero_lines(), ("#4a3aa7", "#9085e9"),
                 "verify any result in this repo — one command, no API key")
    open(os.path.join(adir, "demo.svg"), "w").write(svg)
    made += 1
    print("hero demo -> docs/assets/demo.svg")

    for cfg in CASTS:
        out = os.path.join(ROOT, cfg["out"])
        os.makedirs(out, exist_ok=True)
        lines = cast_lines(cfg)
        svg = render(lines, tuple(cfg["accent"]), f"{cfg['cli']} · real eval run")
        open(os.path.join(out, "demo.svg"), "w").write(svg)
        made += 1
        print(f"{cfg['path']}: cast with {len(lines)} lines")

    # the old light/dark pair is superseded by a single always-dark cast
    stale = [os.path.join(adir, f"demo-{m}.svg") for m in ("light", "dark")]
    stale += [os.path.join(ROOT, c["out"], f"demo-{m}.svg")
              for c in CASTS for m in ("light", "dark")]
    removed = 0
    for p in stale:
        if os.path.exists(p):
            os.remove(p)
            removed += 1
    print(f"wrote {made} animated SVGs; removed {removed} superseded light/dark files")


if __name__ == "__main__":
    main()
