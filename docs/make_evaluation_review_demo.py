"""Publish only the fixed synthetic review twins; accepts no user evaluation input."""

import argparse
from html import escape
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import statistics
import zipfile

from aau_harness.eval_pack import pack_payloads
from aau_harness.eval_matrix import matrix_payloads


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/evaluation-review"


def archive(payloads: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        for name, payload in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            bundle.writestr(info, payload)
    return output.getvalue()


def cohort_story(reports: dict) -> str:
    cards = []
    for name, label in (("cohort-regressed", "Aggregate gain · assisted channel regresses"),
                        ("cohort-repaired", "Repaired twin · assisted channel preserved")):
        report = reports[name]
        comparisons = [("Overall", report["comparisons"][0])] + [
            (group["cohort_id"].capitalize(), group["comparisons"][0]) for group in report["cohort_reviews"]]
        rows = []
        for scope, comparison in comparisons:
            before = statistics.fmean(row["baseline_mean"] for row in comparison["scenarios"])
            after = statistics.fmean(row["candidate_mean"] for row in comparison["scenarios"])
            rows.append(f'<tr><th scope="row">{escape(scope)}<br><small>{comparison["scenario_count"]} scenario(s)</small></th>'
                        f'<td>{before:.0%}</td><td>{after:.0%}</td></tr>')
        status = "Constraints met" if report["status"] == "constraints_met" else "Constraints not met"
        cards.append(f'<article><p class="kicker">{label}</p><h3>{status}</h3>'
                     '<table><caption>Completion by declared group</caption><thead><tr><th scope="col">Scope</th>'
                     '<th scope="col">Baseline</th><th scope="col">Candidate</th></tr></thead>'
                     f'<tbody>{"".join(rows)}</tbody></table><p>{len(report["failed_constraints"])} failed constraints. '
                     'Group gains do not compensate for another group’s failed constraint.</p>'
                     f'<a class="button" href="{name}/review.html">Inspect the cohort review</a>'
                     f'<a class="download" href="{name}.zip" download>Download the six-file pack ↓</a></article>')
    return ('<section id="cohort-story" class="cohort-story"><p class="kicker">A second failure shape · declared cohorts</p>'
            '<h2>A stronger average.<br>A service channel left behind.</h2>'
            '<p>The next synthetic candidate completes more scenarios overall, yet stops completing the assisted-service case. '
            'Its global constraints pass. The explicit assisted-group limits fail. The repaired twin preserves that channel.</p>'
            f'<div class="twins">{"".join(cards)}</div>'
            '<p class="notice">These are deliberately tiny, constructed groups—not measured people or service outcomes. '
            'A one-scenario cohort has a degenerate interval; it cannot establish population performance or fairness. '
            'Membership and limits are supplied assumptions, not independently verified labels.</p>'
            '<p>The regressed twin exits <strong>1</strong> when verified; the repaired twin exits <strong>0</strong>. '
            'Both packs retain all cases, repeated observations, declared groups, limits, and scoped findings. '
            '<a href="https://github.com/immu4989/awesome-agentic-usecases/blob/main/harness/README.md#catch-regressions-concentrated-in-a-declared-cohort">'
            'Adapt a cohort policy for your own independently reviewed cases.</a></p></section>')


def operating_story(dossiers: dict) -> str:
    """Explain the measured fixture relationships using the packaged reports themselves."""
    cards = []
    for name, label in (("dossier-intermittent", "Intermittent · lower cost per attempt"),
                        ("dossier-repaired", "Repaired · every recorded attempt meets criteria")):
        evidence = dossiers[name]
        operating = evidence["candidate-operations.json"]["overall"]
        repeated = evidence["candidate-repeatability.json"]
        source = evidence["candidate.json"]
        passing = {(row["scenario_id"], repeat) for row in repeated["scenarios"] for repeat in row["passing_repeat_ids"]}
        attempts = []
        for row in source["results"]:
            passed = (row["scenario_id"], row["repeat"]) in passing
            attempts.append(f'<li><span>Repeat {row["repeat"] + 1}</span><strong>{"Pass" if passed else "Fail"}</strong>'
                            f'<small>${row["cost_usd"]:.2f} · {row["latency_s"]:g} s</small></li>')
        cost, latency = operating["cost"], operating["latency"]
        rows = [("Mean cost / attempt", f'${cost["mean_per_attempt_usd"]:.2f}'),
                ("All attempt costs / passing attempts", f'${cost["total_per_passing_attempt_usd"]:.2f}'),
                ("Cost of failed attempts (included)", f'${cost["spent_on_failed_attempts_usd"]:.2f}'),
                ("Median / nearest-rank p95 latency", f'{latency["p50_s"]:g} s / {latency["p95_s"]:g} s')]
        curve = repeated["curve"][-1]
        status = "Constraints met" if evidence["review.json"]["status"] == "constraints_met" else "Constraints not met"
        cards.append(f'<article><p class="kicker">{label}</p><h3>{status}</h3>'
                     f'<ol class="attempts" aria-label="Recorded synthetic attempts">{"".join(attempts)}</ol>'
                     f'<p><strong>{operating["passing_attempt_count"]}/{operating["attempt_count"]}</strong> attempts meet '
                     'both completion and authorization criteria.</p>'
                     '<table><caption>Synthetic operating evidence · USD and seconds</caption>'
                     '<thead><tr><th scope="col">Measure</th><th scope="col">Value</th></tr></thead><tbody>'
                     + ''.join(f'<tr><th scope="row">{escape(key)}</th><td>{escape(value)}</td></tr>' for key, value in rows)
                     + '</tbody></table>'
                     + f'<p>Across all {curve["draw_size"]} recorded repeats: '
                     f'<strong>{curve["any_pass_fraction"]:.0%}</strong> of subsets contain at least one pass; '
                     f'<strong>{curve["all_pass_fraction"]:.0%}</strong> contain only passes.</p>'
                     f'<a class="button" href="{name}/review.html#diagnostics">Inspect the complete dossier</a>'
                     f'<a class="download" href="{name}.zip" download>Download the eleven-file dossier ↓</a></article>')
    return ('<section id="operating-story" class="cohort-story"><p class="kicker">A third failure shape · cheap attempts, costly failures</p>'
            '<h2>Which denominator are you paying for?</h2>'
            '<p>A fictional service completes every attempt, but its first configuration misses authorization on three of four attempts. '
            'The repaired configuration costs more per attempt. Counting all costs against jointly passing attempts reverses the apparent cost advantage.</p>'
            f'<div class="twins">{"".join(cards)}</div>'
            '<p class="notice">One synthetic scenario, four repeats—not a production benchmark, savings estimate, ROI, or vendor ranking. '
            'The p95 here is the maximum of four values, not a stable tail-risk estimate. Subset fractions describe only the recorded observations, '
            'not future-run probabilities or permission to retry consequential actions. Repeats are not separate people served. '
            'The cost ratio excludes unrecorded infrastructure, human review, and other overhead.</p>'
            '<h3>Verify the whole handoff, not a screenshot</h3>'
            '<p>Extract either eleven-file dossier and require its diagnostic views:</p>'
            '<pre><code>python -m pip install -e harness\naau evaluation-pack verify /path/to/extracted-dossier --require-diagnostics</code></pre>'
            '<p>The intermittent dossier exits <strong>1</strong>; the repaired dossier exits <strong>0</strong>. '
            'Both recompute. Costs and repeat diagnostics never override a failed policy constraint. '
            'The folder includes the policy, both complete evaluations, diagnostic plan, four diagnostic reports, review JSON, HTML, and manifest.</p>'
            '<p><a href="https://github.com/immu4989/awesome-agentic-usecases/blob/main/harness/README.md#hand-off-one-complete-offline-review-dossier">'
            'Build a dossier from your own evidence</a> · '
            '<a href="https://github.com/immu4989/awesome-agentic-usecases/tree/main/.github/actions/aau-evaluation-review">'
            'Use independently pinned inputs in CI</a></p>'
            '<details><summary>Why these views?</summary><p>'
            '<a href="https://www.finops.org/framework/capabilities/unit-economics/">FinOps unit economics</a> motivates making the denominator explicit; '
            '<a href="https://sre.google/workbook/monitoring/">Google SRE monitoring guidance</a> explains why latency percentiles reveal information averages hide. '
            'These sources inform the questions, not validation of this synthetic fixture or its thresholds.</p></details></section>')


def render_index(reports: dict, cohorts: dict, dossiers: dict) -> str:
    cards = []
    for name, label in (("legitimate", "Candidate A · obligations preserved"), ("unsafe", "Candidate B · authorization missed")):
        report = reports[name]
        rows = []
        for comparison in report["comparisons"]:
            before = statistics.fmean(row["baseline_mean"] for row in comparison["scenarios"])
            after = statistics.fmean(row["candidate_mean"] for row in comparison["scenarios"])
            rows.append(f'<tr><th scope="row">{escape(comparison["metric"].capitalize())}</th>'
                        f'<td>{before:.0%}</td><td>{after:.0%}</td></tr>')
        status = "Constraints met" if report["status"] == "constraints_met" else "Constraints not met"
        cards.append(f'<article><p class="kicker">{label}</p><h2>{status}</h2>'
                     '<table><caption>Illustrative scenario averages</caption><thead><tr><th scope="col">Metric</th>'
                     '<th scope="col">Baseline</th><th scope="col">Candidate</th></tr></thead>'
                     f'<tbody>{"".join(rows)}</tbody></table>'
                     f'<p>{len(report["failed_constraints"])} failed constraints. '
                     'Both cases and both repeats remain in the evidence.</p>'
                     f'<a class="button" href="{name}/review.html">Read the complete review</a> '
                     f'<a class="download" href="{name}.zip" download>Download the six-file pack ↓</a></article>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Better averages are not enough · AAU evaluation review</title>
<style>
:root{font-family:system-ui,sans-serif;color:#202d35;background:#f5f5f2;color-scheme:light}
*{box-sizing:border-box}body{max-width:1120px;margin:auto;padding:32px 24px;line-height:1.65}
a{color:#224c60;text-underline-offset:4px}nav{display:flex;justify-content:space-between;gap:20px;font-size:.9rem}
header{max-width:860px;padding:60px 0 36px}h1,h2{line-height:1.15;letter-spacing:-.025em}
h1{font-size:clamp(2.4rem,5vw,4.2rem);margin:16px 0 24px}h2{font-size:1.6rem}
.kicker{font-size:.8rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#4a5d67}
.lead{font-size:1.2rem}.notice{border-left:3px solid #6a7e87;padding:14px 20px;background:#fff}
.twins{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{background:white;border:1px solid #d7dfe1;padding:28px;border-radius:10px}
table{border-collapse:collapse;width:100%;margin:20px 0}caption{text-align:left;color:#52636b;font-size:.9rem;padding-bottom:12px}
th,td{text-align:left;border-bottom:1px solid #dce2e4;padding:12px 8px}thead th{font-size:.8rem;font-weight:500;color:#52636b}
.button{display:inline-block;padding:9px 15px;border:1px solid #224c60;border-radius:5px;font-weight:600;text-decoration:none}
.download{display:block;margin-top:18px;font-size:.95rem}section{margin:48px 0;max-width:880px}pre{overflow-x:auto;background:#202d35;color:#f4f6f7;padding:24px;border-radius:8px;line-height:1.7}
code{font-size:.9rem}li{margin:10px 0}footer{border-top:1px solid #cbd4d7;padding:24px 0;color:#52636b}
.cohort-story{max-width:none;border-top:1px solid #cbd4d7;padding-top:32px}.cohort-story h3{font-size:1.4rem;line-height:1.2}small{font-weight:400;color:#52636b}
.attempts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;list-style:none;padding:0}.attempts li{border:1px solid #cbd4d7;border-radius:5px;padding:8px 4px;text-align:center;font-size:.8rem}.attempts span,.attempts strong,.attempts small{display:block}.attempts strong{font-size:1rem}td{white-space:nowrap}
@media(max-width:700px){.twins{grid-template-columns:1fr}header{padding-top:32px}article{padding:20px}nav{flex-wrap:wrap}}
@media print{body{background:white}pre{white-space:pre-wrap}.button{border:none;padding:0}}
</style></head><body><nav><a href="../index.html">← Explore the repository</a>
<a href="https://github.com/immu4989/awesome-agentic-usecases/tree/main/harness">Source and documentation ↗</a></nav>
<header><p class="kicker">Synthetic demonstration · no live agents</p><h1>Better averages<br>are not enough.</h1>
<p class="lead">Two candidates complete more tasks. Only one preserves the authorization requirement on every attempt.</p>
<p>Follow two fictional service requests: a routine case and a case requiring authorization.
Both candidates improve completion from 50% to 100%. Candidate B skips authorization in one of four observations.
The review keeps that failure visible instead of trading it against a better headline score.</p>
<p class="notice">These numbers are constructed fixtures, not measured model or government-service performance.
No person, agency, provider, or real transaction is involved. Cost and latency fields in the downloads are placeholders.</p></header>
<p><a href="#cohort-story">Explore channel regressions</a> · <a href="#operating-story">Explore cost and repeat failures</a> · <a href="budget-lab.html">Try the operating-budget lab</a></p>
<div class="twins">''' + "".join(cards) + '</div>' + cohort_story(cohorts) + operating_story(dossiers) + '''
<section><h2>Inspect it. Download it. Recompute it.</h2>
<ol><li>Read either review in your browser. Expand the scenario details to see what changed.</li>
<li>Download its pack and extract every file into one folder (six for the policy-only examples; eleven for diagnostic dossiers).</li>
<li>From a checkout of this repository, install the current harness and verify that folder:</li></ol>
<pre><code>python -m pip install -e harness
aau evaluation-pack verify /path/to/extracted-pack</code></pre>
<p>Candidate A exits <strong>0</strong>. Candidate B exits <strong>1</strong>: its pack verifies, but its constraints are not met.
Exit <strong>2</strong> indicates an invalid, incomplete, modified, or incompatible pack. Failure evidence is a useful result, not a broken download.</p>
<p>Verification recomputes the review, HTML, and byte manifest from the included policy and evaluations.
Keep the matching harness revision: changes to the renderer or scoring logic can make an older pack incompatible.</p></section>
<section><h2>Take this into your own workflow.</h2>
<p>Choose meaningful service obligations, independently review the policy and baseline, and collect complete candidate evidence.
Do not copy these illustrative thresholds as production policy.</p>
<ul><li><a href="https://github.com/immu4989/awesome-agentic-usecases/blob/main/harness/README.md#review-several-metrics-without-trading-away-obligations">Create a multi-metric review policy</a></li>
<li><a href="https://github.com/immu4989/awesome-agentic-usecases/tree/main/.github/actions/aau-evaluation-review">Add the pinned-input GitHub Action</a></li>
<li><a href="../evaluation-audit.html">Inspect the separate audit of historical evaluation summaries</a></li></ul>
<p class="notice">This demonstration grants no deployment approval. Matching hashes do not authenticate execution,
prove policy timing, establish scoring validity, or demonstrate real-world benefit. The general pack tool includes full source details;
inspect sensitive information before sharing your own packs. These particular downloads contain only fixed synthetic fixtures.</p></section>
<footer>No scripts, analytics, external fonts, or model calls. Generated from the same tested review implementation as the CLI.</footer>
</body></html>
'''


def render_budget_lab(dossiers: dict, matrix: dict) -> str:
    trap = dossiers["budget-aggregate-trap"]
    source = trap["candidate.json"]
    rows = sorted(source["results"], key=lambda r: (r["latency_s"], r["scenario_id"], r["repeat"]))
    rank = (95 * len(rows) + 99) // 100
    tail = trap["candidate-budget.json"]["scopes"][0]["summary"]["latency"]["p95_s"]
    slow = sum(r["latency_s"] > tail for r in rows)
    label = (f'{len(rows)} sorted synthetic attempts. Nearest-rank p95 is attempt {rank}, at {tail:g} s. '
             f'{slow} attempts are slower than that value.')
    cells = ''.join(f'<span class="cell{" tail" if r["latency_s"] > tail else ""}{" rank" if i == rank else ""}">'
                    f'{r["latency_s"]:g}</span>' for i, r in enumerate(rows, 1))
    cards = []
    for name, title in (("budget-aggregate-trap", "The aggregate trap"), ("budget-repaired", "The repaired twin")):
        evidence = dossiers[name]
        gate, budget = evidence["gate.json"], evidence["candidate-budget.json"]
        table_rows = []
        for scope in budget["scopes"]:
            summary = scope["summary"]
            scope_name = "Overall" if scope["scope"] == "overall" else scope["group_id"].capitalize()
            met = all(c["status"] == "met" for c in scope["checks"])
            table_rows.append(f'<tr><th scope="row">{escape(scope_name)}<small>{summary["attempt_count"]} attempts</small></th>'
                              f'<td>${summary["cost"]["total_per_passing_attempt_usd"]:g}</td>'
                              f'<td>{summary["latency"]["p95_s"]:g} s</td><td>{"Met" if met else "Not met"}</td></tr>')
        status = "Combined constraints met" if gate["status"] == "constraints_met" else "Combined constraints not met"
        policy_status = "Met" if gate["policy_status"] == "constraints_met" else "Not met"
        budget_status = "Met" if gate["candidate_budget_status"] == "constraints_met" else "Not met"
        cards.append(f'<article><p class="kicker">{title}</p><h3>{status}</h3>'
                     f'<p>Quality policy: <strong>{policy_status}</strong><br>Candidate operating budget: <strong>{budget_status}</strong></p>'
                     '<div class="scroll"><table><caption>Recorded values; limits apply independently to each scope</caption>'
                     '<thead><tr><th scope="col">Scope</th><th scope="col">USD / passing attempt</th><th scope="col">p95 latency</th>'
                     f'<th scope="col">Limits</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div>'
                     f'<a class="button" href="{name}/review.html#operating-budget">Inspect every check</a>'
                     f'<a class="download" href="{name}.zip" download>Download the 14-file dossier ↓</a></article>')
    limits = trap["operating-budget.json"]["limits"]
    eligible = ', '.join(matrix["operating_groups"][0]["eligible_candidates"]) or "None"
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="description" content="An offline synthetic lesson: good aggregate cost and p95 latency can hide a failing service route. Inspect, download, and verify the evidence.">
<title>The aggregate trap · AAU operating-budget lab</title>
<style>
:root{font-family:system-ui,sans-serif;color:#202d35;background:#f5f5f2;color-scheme:light}
*{box-sizing:border-box}body{max-width:1120px;margin:auto;padding:28px 24px;line-height:1.65}
a{color:#224c60;text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid #224c60;outline-offset:4px}
nav{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;font-size:.9rem}
header{max-width:860px;padding:48px 0 24px}h1,h2,h3{line-height:1.15;letter-spacing:-.025em}
h1{font-size:clamp(2.4rem,5vw,4.2rem);margin:16px 0 24px}h2{font-size:1.9rem}h3{font-size:1.45rem}
.kicker{font-size:.8rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#4a5d67}.lead{font-size:1.2rem}
.notice{border-left:3px solid #6a7e87;padding:14px 20px;background:white}section{padding:24px 0;border-top:1px solid #cbd4d7;margin-top:24px}
.twins{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{background:white;border:1px solid #d7dfe1;padding:24px;border-radius:10px}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:20px 0;font-size:.9rem}caption{text-align:left;color:#52636b;font-size:.85rem;padding-bottom:10px}
th,td{text-align:left;border-bottom:1px solid #dce2e4;padding:10px 6px}thead th{font-weight:500}td{white-space:nowrap}small{display:block;font-weight:400;color:#52636b}
.button{display:inline-block;padding:9px 15px;border:1px solid #224c60;border-radius:5px;font-weight:600;text-decoration:none}.download{display:block;margin-top:16px}
figure{margin:24px 0;padding:24px;background:white;border:1px solid #d7dfe1;border-radius:10px}.distribution{display:grid;grid-template-columns:repeat(20,minmax(0,1fr));gap:6px}
.cell{padding:9px 0;border:1px solid #c2cdd2;text-align:center;font-size:.8rem;background:#edf1f2}.tail{background:#4c5c65;color:white;border-color:#4c5c65}.rank{outline:3px solid #202d35;outline-offset:1px}
figcaption{margin-top:18px;color:#40545e}.rank-key{border:2px solid #202d35;padding:0 6px}.mono{font-variant-numeric:tabular-nums}
pre{overflow-x:auto;background:#202d35;color:#f4f6f7;padding:20px;border-radius:8px;line-height:1.7}code{font-size:.88rem}li{margin:8px 0}
footer{border-top:1px solid #cbd4d7;margin-top:32px;padding:24px 0;color:#52636b}.links{display:flex;gap:20px;flex-wrap:wrap}
@media(max-width:760px){.twins{grid-template-columns:1fr}header{padding-top:30px}article{padding:20px}.distribution{grid-template-columns:repeat(10,minmax(0,1fr))}figure{padding:18px 12px}}
@media print{body{background:white}pre{white-space:pre-wrap}.button{border:none;padding:0}.tail{border:2px solid #202d35;color:#202d35;background:white}}
</style></head><body><nav><a href="index.html">← More evaluation lessons</a>
<a href="https://github.com/immu4989/awesome-agentic-usecases">Repository and source ↗</a></nav>
<header><p class="kicker">Operating-budget lab · fixed synthetic evidence</p><h1>A good headline.<br>A failing service route.</h1>
<p class="lead">Every task completes. Overall cost and p95 latency meet their limits. One specialist route still fails both.</p>
<p>This lesson separates quality policy from operating requirements. It keeps the failing group visible, preserves both verdicts,
and carries the evidence into a combined CI gate. No API key or live agent is needed to read it.</p>
<p class="notice">Constructed scores, USD costs, and timings—not measured users, models, agencies, or production services.
The “repaired” twin is a controlled fixture, not evidence of a real-world improvement. These thresholds are not recommendations.</p></header>
<main><section><p class="kicker">01 · Inspect the distribution</p><h2>What can a p95 leave out?</h2>''' + (
        f'<p>The fixture has <strong>{source["n_scenarios"]} scenarios × {source["n_repeats"]} repeats = {len(rows)} attempts</strong>. '
        f'The nearest-rank p95 selects sorted attempt <strong>{rank}</strong>. Its latency is <strong>{tail:g} s</strong>—'
        f'even though <strong>{slow} attempts</strong> take longer.</p>'
        f'<figure><div role="img" aria-label="{escape(label, quote=True)}"><div class="distribution" aria-hidden="true">{cells}</div></div>'
        f'<figcaption>Each cell is one attempt, ordered by latency; its number is seconds. The outlined cell is '
        f'<span class="rank-key">p95, #{rank}</span>. Dark cells are slower, with their latency printed explicitly. '
        'These repeats are not distinct people served. See the scope table below for the underlying values.</figcaption></figure>'
        '<p>A percentile is a summary, not a promise about every case. A group-level p95 can also hide outliers within '
        'that group; use a separately reviewed maximum-latency limit if every attempt must fit a ceiling.</p></section>'
        '<section><p class="kicker">02 · Keep the group checks</p><h2>Both verdicts. Every scope.</h2>'
        f'<p>In this fixture, each overall/group scope must stay at or below <strong>${limits["cost_per_passing_attempt_usd"]:g} '
        f'per jointly passing attempt</strong> and <strong>{limits["p95_latency_s"]:g} seconds p95</strong>. '
        'Costs include failures; a “passing attempt” is defined by the declared scoring criteria, not a verified business outcome.</p>'
        f'<div class="twins">{"".join(cards)}</div>'
        '<p class="notice">Group membership and thresholds are supplied assumptions. The specialist group contains one scenario '
        'with four repeats, not a representative population sample. No fairness, production SLO, cost forecast, or deployment approval is claimed. '
        'The generic tool treats missing measurements as unverified rather than zero or a passing check.</p></section>'
        '<section><p class="kicker">03 · Compare without compensating</p><h2>A cheap aggregate cannot buy eligibility.</h2>'
        f'<p>The same two candidates enter a budget-aware matrix. Eligible for its recorded operating comparison: '
        f'<strong>{escape(eligible)}</strong>. The aggregate-trap candidate remains visible with its exclusion reason; '
        'it is not silently removed from the evidence. One eligible candidate is not a vendor recommendation or proof of superiority.</p>'
        '<p class="links"><a class="button" href="budget-matrix/matrix.html">Inspect the candidate matrix</a>'
        '<a href="budget-matrix.zip" download>Download the 14-file matrix ↓</a></p></section>'
        '<section><p class="kicker">04 · Recompute, then adapt</p><h2>A result you can inspect offline.</h2>'
        '<ol><li>Download a dossier or matrix above and extract every file into a new folder.</li>'
        '<li>Use the matching current repository harness; these commands are not in published PyPI 1.6.0.</li>'
        '<li>Run the corresponding verifier below. The browser page does not verify itself.</li></ol>'
        '<pre><code>python -m pip install -e harness\n\n'
        '# Dossier: require BOTH policy and operating checks\n'
        'aau evaluation-pack verify /path/to/extracted-dossier --require-budget\n\n'
        '# Matrix: verify the complete descriptive comparison\n'
        'aau candidate-matrix verify /path/to/extracted-matrix</code></pre>'
        '<p>The aggregate-trap dossier exits <strong>1</strong>: its evidence verifies but the combined constraints fail. '
        'The repaired dossier exits <strong>0</strong>. The matrix exits <strong>0</strong> even though it contains an excluded candidate—'
        'matrix verification is descriptive, not a deployment gate. Exit <strong>2</strong> means invalid or incompatible evidence.</p>'
        '<p>Each dossier retains policy, baseline, candidate, diagnostics, the operating budget, separate verdicts, the combined gate, '
        'HTML, and a manifest. Verification recomputes all 14 files, not just hashes. The matrix has its own complete 14-file source chain. '
        'Keep the matching harness revision. Hashes are not signatures or authenticated execution.</p>'
        '<h3>Put your own reviewed limits into CI</h3><p>Review meaningful cases and obligations, collect complete scored observations, '
        'and independently approve your baseline, quality policy, diagnostics, and budget. Protect their exact-byte approval hashes '
        'and workflow inputs outside candidate-controlled changes. Missing required evidence should not count as a pass.</p>'
        '<ul><li><a href="https://github.com/immu4989/awesome-agentic-usecases/blob/main/harness/README.md#enforce-policy-and-operating-limits-in-one-reviewer-dossier">'
        'Adapt the combined dossier for JSON, recorded observations, or CSV</a></li>'
        '<li><a href="https://github.com/immu4989/awesome-agentic-usecases/tree/main/.github/actions/aau-evaluation-review#require-an-independently-approved-candidate-operating-budget">'
        'Use the independently pinned CI budget gate</a></li>'
        '<li><a href="https://github.com/immu4989/awesome-agentic-usecases/blob/main/harness/examples/evaluation-review/operating_budget.py">'
        'Read and reproduce the complete synthetic example</a></li></ul>'
        '<p class="notice">Only fixed synthetic fixtures are published here. General-purpose review tools retain unsanitized source details; '
        'inspect your own evidence for sensitive information before sharing. Nothing is uploaded automatically by the harness.</p>'
        '<details><summary>Research behind the lesson</summary><p>'
        '<a href="https://sre.google/sre-book/service-level-objectives/">Google SRE on service-level objectives and aggregation</a> '
        'motivates examining distributions rather than relying on a headline. '
        '<a href="https://www.finops.org/framework/capabilities/unit-economics/">FinOps unit economics</a> motivates explicit units and measurement assumptions. '
        'Neither source validates these fictional thresholds or establishes production suitability.</p></details></section></main>'
        '<footer>No scripts, analytics, external fonts, model calls, or source uploads. Generated from the same tested reports as the CLI.</footer>'
        '</body></html>\n')


def budget_assets() -> dict[str, bytes]:
    spec = importlib.util.spec_from_file_location("public_budget_demo", ROOT / "harness/examples/evaluation-review/operating_budget.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    budget, matrix_plan, policy, candidates = module.budget_inputs()
    diagnostics = {"plan_version": "aau-evaluation-diagnostics/1.0", "criteria": budget["criteria"],
                   "draw_sizes": [1, 4], "cost_basis": {"baseline": "synthetic", "candidate": "synthetic"}}
    assets, dossiers = {}, {}
    for name, source in candidates.items():
        _, payloads = pack_payloads(policy, candidates["repaired"], source, diagnostics=diagnostics, operating_budget=budget)
        stem = f"budget-{name}"
        dossiers[stem] = {filename: json.loads(value) for filename, value in payloads.items() if filename.endswith(".json")}
        assets.update({f"{stem}/{filename}": value for filename, value in payloads.items()})
        assets[f"{stem}.zip"] = archive(payloads)
    matrix, payloads = matrix_payloads(matrix_plan, policy, candidates["repaired"], candidates)
    assets.update({f"budget-matrix/{filename}": value for filename, value in payloads.items()})
    assets["budget-matrix.zip"] = archive(payloads)
    assets["budget-lab.html"] = render_budget_lab(dossiers, matrix).encode("utf-8")
    return assets


def build_assets() -> dict[str, bytes]:
    source = ROOT / "harness/examples/evaluation-review/demo.py"
    spec = importlib.util.spec_from_file_location("public_evaluation_demo", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy, baseline, legitimate, unsafe = module.demo_inputs()
    assets, reports = {}, {}
    for name, candidate in (("legitimate", legitimate), ("unsafe", unsafe)):
        report, payloads = pack_payloads(policy, baseline, candidate)
        reports[name] = report
        assets.update({f"{name}/{filename}": value for filename, value in payloads.items()})
        assets[f"{name}.zip"] = archive(payloads)
    spec = importlib.util.spec_from_file_location("public_cohort_demo", ROOT / "harness/examples/evaluation-review/cohorts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy, baseline, regressed, repaired = module.demo_inputs()
    cohorts = {}
    for name, candidate in (("cohort-regressed", regressed), ("cohort-repaired", repaired)):
        report, payloads = pack_payloads(policy, baseline, candidate)
        cohorts[name] = report
        assets.update({f"{name}/{filename}": value for filename, value in payloads.items()})
        assets[f"{name}.zip"] = archive(payloads)
    spec = importlib.util.spec_from_file_location("public_dossier_demo", ROOT / "harness/examples/evaluation-review/dossier.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy, baseline, repaired, plan = module.demo_inputs()
    dossiers = {}
    for name, candidate in (("dossier-intermittent", baseline), ("dossier-repaired", repaired)):
        _, payloads = pack_payloads(policy, baseline, candidate, diagnostics=plan)
        dossiers[name] = {filename: json.loads(payload) for filename, payload in payloads.items() if filename.endswith(".json")}
        assets.update({f"{name}/{filename}": value for filename, value in payloads.items()})
        assets[f"{name}.zip"] = archive(payloads)
    assets["index.html"] = render_index(reports, cohorts, dossiers).encode("utf-8")
    assets.update(budget_assets())
    return assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assets = build_assets()
    if args.check:
        existing = {path.relative_to(TARGET).as_posix() for path in TARGET.rglob("*") if path.is_file()}
        if existing != set(assets) or any((TARGET / name).read_bytes() != value for name, value in assets.items()):
            raise SystemExit("public evaluation demonstration differs; review and regenerate its fixed synthetic assets")
    else:
        for name, payload in assets.items():
            target = TARGET / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    packs = sum(name.endswith(".zip") for name in assets)
    print(f"Public synthetic evaluation twins reproduce: {len(assets)} files, {packs} complete packs.")


if __name__ == "__main__":
    main()
