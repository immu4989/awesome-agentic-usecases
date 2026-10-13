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
<p><a href="#cohort-story">Explore channel regressions</a> · <a href="#operating-story">Explore cost and repeat failures</a></p>
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
    print(f"Public synthetic evaluation twins reproduce: {len(assets)} files, six complete packs.")


if __name__ == "__main__":
    main()
