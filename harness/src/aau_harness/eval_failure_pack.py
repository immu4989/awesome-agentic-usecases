"""Source-bound, script-free reviewer packs for conditional failure-bound diagnostics."""

import argparse
from html import escape
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .authority_html import STYLE
from .eval_failure_bound import review_failure_bounds


FILES = {'plan.json', 'evaluation.json', 'report.json', 'review.html', 'manifest.json'}
LABELS = {'population_inference_withheld': 'Population inference withheld',
          'conditional_bounds_within_limits': 'Conditional numeric limits met',
          'conditional_bounds_exceed_limits': 'Conditional numeric limits exceeded',
          'conditional_bound_within_limit': 'Conditional numeric limit met',
          'conditional_bound_exceeds_limit': 'Conditional numeric limit exceeded'}
EXTRA_STYLE = '''
*{box-sizing:border-box}body{padding:32px 24px}main{max-width:960px;margin:auto}
h1{font-size:clamp(2rem,5vw,3rem);max-width:22ch;letter-spacing:-.03em}
h2,h3,p,td,th,summary{overflow-wrap:anywhere}a{color:#244e67;text-underline-offset:3px}
a:focus-visible,summary:focus-visible,.scroll:focus-visible{outline:3px solid #7d5c24;outline-offset:4px}
.lede{font-size:1.1rem;max-width:75ch}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin:24px 0}
.stat{background:white;border:1px solid #ccd5db;padding:16px}.stat strong{display:block;font-size:1.7rem;line-height:1.2}
.stat span{font-size:.9rem}.scope{background:white;border:1px solid #ccd5db;padding:20px;margin:24px 0}
.scope h2{margin-top:0}.result{font-weight:650}.scope figure{margin:24px 0}.scope svg{display:block;width:100%;height:auto}
.scale{display:flex;justify-content:space-between;font-size:.85rem}.legend{font-size:.9rem;margin:8px 0}
.readout{font-size:1rem}.readout strong{font-size:1.15rem}.scroll{max-width:100%}
details{margin:20px 0}summary{cursor:pointer;font-weight:650}td,th{overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere}
.steps{padding-left:24px}.steps li{padding:4px 0}.small{font-size:.9rem}footer{margin-top:40px;border-top:1px solid #ccd5db;padding-top:20px}
@media(max-width:520px){body{padding:24px 16px}.scope{padding:16px}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.stat{padding:12px}th,td{padding:10px}}
@media print{details{display:block}.scope{break-inside:avoid}.scroll{overflow:visible}body{padding:0}}
'''


def _text(value):
    return escape('Withheld' if value is None else str(value), quote=True)


def _table(caption, headings, rows):
    head = ''.join(f'<th scope="col">{_text(value)}</th>' for value in headings)
    body = ''.join('<tr>' + ''.join(f'<td>{_text(value)}</td>' for value in row) + '</tr>' for row in rows)
    if not rows:
        body = f'<tr><td colspan="{len(headings)}">None recorded.</td></tr>'
    return (f'<div class="scroll" tabindex="0" role="region" aria-label="{_text(caption)}">'
            f'<table><caption>{_text(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def _plot(scope, index):
    bound = scope['one_sided_upper_failure_bound']
    observed = scope['observed_bundle_failure_fraction']
    limit = scope['maximum_failure_probability']
    conditional = bound is not None
    description = (f'Observed fraction {observed}. Conditional upper bound {bound}. Declared limit {limit}.'
                   if conditional else f'Observed fraction {observed}. Population bound withheld; no probability comparison shown.')
    marks = (f'<rect x="0" y="8" width="600" height="24" fill="#edf0f2"/>'
             f'<rect x="0" y="8" width="{600 * observed:.10f}" height="24" fill="#526a76"/>')
    if conditional:
        x = 600 * limit
        marks += (f'<rect x="0" y="56" width="600" height="24" fill="#edf0f2"/>'
                  f'<rect x="0" y="56" width="{600 * bound:.10f}" height="24" fill="#a17b38"/>'
                  f'<line x1="{x:.10f}" x2="{x:.10f}" y1="0" y2="92" stroke="#182630" stroke-width="3" stroke-dasharray="5 4"/>')
    legend = ('Upper row: observed fraction. Lower row: conditional upper bound. Dashed line: declared limit.'
              if conditional else 'Observed benchmark fraction only. A population confidence bound is withheld.')
    return (f'<figure><svg viewBox="0 0 600 {96 if conditional else 40}" role="img" '
            f'aria-labelledby="plot-title-{index} plot-desc-{index}"><title id="plot-title-{index}">'
            f'{_text(scope["scope_id"])} — recorded outcomes and interpretation</title>'
            f'<desc id="plot-desc-{index}">{_text(description)}</desc>{marks}</svg>'
            '<div class="scale" aria-hidden="true"><span>0%</span><span>100%</span></div>'
            f'<figcaption class="legend">{legend}</figcaption></figure>')


def render_failure_review(report):
    """Render only a freshly recomputed report; never trust received HTML or report values."""
    method, audit = report['method'], report['source_audit']
    failed = sum(row['bundle_failed'] for row in report['scenario_outcomes'])
    stats = ''.join(f'<div class="stat"><strong>{value}</strong><span>{label}</span></div>' for value, label in (
        (report['scenario_count'], 'distinct scenario bundles'), (report['repeats_per_scenario'], 'repeats per bundle'),
        (report['observation_count'], 'recorded observations'), (failed, 'bundles with a recorded failure')))
    scopes = []
    for index, scope in enumerate(report['scopes']):
        bound, planning = scope['one_sided_upper_failure_bound'], scope['zero_failure_planning']
        bound_text = 'Withheld' if bound is None else f'{bound:.3%}'
        planning_text = (f'{planning["minimum_scenarios"]} distinct scenario bundles with zero failures'
                         if planning['minimum_scenarios'] is not None else
                         'No finite zero-failure sample supports a zero-risk target' if planning['status'] == 'no_finite_zero_failure_sample'
                         else 'Required size exceeds the supported planning range')
        rows = [('Observed failed-bundle fraction', scope['observed_bundle_failure_fraction']),
                ('Conditional one-sided upper bound', bound),
                ('Declared maximum failure probability', scope['maximum_failure_probability']),
                ('Failed / declared scenario bundles', f'{scope["failed_scenario_count"]} / {scope["scenario_count"]}')]
        membership = _table('Complete scope membership', ('Scenario', 'Recorded bundle outcome'),
                            [(name, 'Has a failure' if name in scope['failed_scenario_ids'] else 'All recorded criteria met')
                             for name in scope['scenario_ids']])
        heading = 'Overall workload' if index == 0 else f'Declared group: {scope["scope_id"]}'
        scopes.append(f'<section class="scope" id="scope-{index}"><h2>{_text(heading)}</h2>'
                      f'<p class="result">{_text(LABELS[scope["status"]])} — not deployment approval</p>'
                      f'<p class="readout"><strong>{scope["failed_scenario_count"]} / {scope["scenario_count"]}</strong> '
                      f'bundles have a recorded failure. Conditional upper bound: <strong>{bound_text}</strong>.</p>'
                      + _plot(scope, index) + _table('Full-precision reported probabilities (0 to 1)', ('Measure', 'Value'), rows)
                      + f'<p><strong>Hypothetical zero-failure planning:</strong> {_text(planning_text)}. '
                      'This is for a new fixed-horizon design, not instructions to collect until a result passes.</p>'
                      f'<details><summary>Inspect all {scope["scenario_count"]} scope members</summary>{membership}</details></section>')
    failures = [(row['scenario_id'], failure['repeat'], criterion['metric'], criterion['value'])
                for row in report['scenario_outcomes'] for failure in row['failed_repeats'] for criterion in failure['failed_criteria']]
    rules = _table('Joint criteria applied to every repeat', ('Metric', 'Inclusive requirement', 'Limit'),
                   [(rule['metric'], 'At least' if rule['direction'] == 'higher' else 'At most', rule['limit'])
                    for rule in report['criteria']])
    warnings = ''.join(f'<li>{_text(warning)}</li>' for warning in report['warnings'])
    mismatch_text = json.dumps(audit['mismatches'], ensure_ascii=False, indent=2)
    title = LABELS[report['status']]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            f'<title>Failure-bound evidence — {title}</title><style>{STYLE}{EXTRA_STYLE}</style></head><body><main>'
            '<p class="eyebrow">AAU · offline reviewer evidence</p>'
            f'<h1>{title}</h1><p class="lede">What do the supplied observations support—and what assumptions '
            'would a population-risk claim require?</p>'
            '<p class="notice"><strong>Diagnostic only. No deployment approval.</strong> A conditional numeric limit '
            'is meaningful only if the declared sampling design is valid. Those assumptions are not verified here.</p>'
            f'<div class="stats">{stats}</div><p>One unit is the entire scenario bundle. Any criterion failure on any '
            'repeat fails that bundle; later success does not erase it. More repeats are not more independent scenarios.</p>'
            '<nav aria-label="Review sections"><a href="#assumptions">Sampling assumptions</a> · '
            '<a href="#scope-0">Scope findings</a> · <a href="#failures">Recorded failures</a> · '
            '<a href="#verification">Verify this pack</a></nav>'
            f'<section id="assumptions"><h2>Read the assumptions first</h2><p>Declared design: '
            f'<strong>{_text(report["sampling_design"])}</strong>.</p><p class="notice">{_text(report["sampling_basis"])}</p>'
            f'<p>Family confidence setting: {_text(method["confidence_level"])}. Declared scopes: {_text(method["family_size"])}. '
            f'Tail probability per scope: {_text(method["tail_probability_per_scope"])}. '
            f'Population bounds applied: {"Yes, conditional on the declaration" if method["bound_applied"] else "No"}.</p>'
            '<p>The family includes the overall scope and every declared group, including overlapping groups. '
            'It does not cover repeated peeking, selecting the best candidate, or outcome-selected groups.</p>'
            f'{rules}<ul>{warnings}</ul></section>'
            '<p class="small">Plots use a common 0–100% scale. Percentage labels and plot widths are rounded; '
            'the tables retain full reported numeric precision. Status is computed from unrounded values.</p>'
            + ''.join(scopes)
            + '<section id="failures"><h2>Every recorded criterion failure</h2>'
            + _table('Failures retained across all planned repeats', ('Scenario', 'Repeat ID', 'Metric', 'Observed value'), failures)
            + '<h3>Outside this diagnostic</h3><p>'
            + _text(', '.join(report['unreviewed_metrics']) or 'No additional metric names found. Unmeasured risks remain unreviewed.')
            + f'</p><h3>Stored-summary consistency: {_text(audit["status"])}</h3>'
            '<p>Bounds use the observations, not stored summaries. This diagnostic does not repair a mismatching source.</p>'
            f'<details><summary>Inspect all stored-summary mismatches</summary><pre>{_text(mismatch_text)}</pre></details></section>'
            '<section id="verification"><h2>A page is not its own verifier</h2><ol class="steps">'
            '<li>Keep all five files together and review the source data for sensitive detail.</li>'
            '<li>Before relying on the page, run <code>aau failure-bound-pack verify PATH</code> with a trusted matching harness.</li>'
            '<li>Independently review the sampling plan, ground truth, and authority to make any deployment decision.</li></ol>'
            '<p><a href="plan.json">Plan JSON</a> · <a href="evaluation.json">Complete evaluation JSON</a> · '
            '<a href="report.json">Diagnostic JSON</a> · <a href="manifest.json">Manifest</a></p>'
            '<p><strong>Not sanitized:</strong> the complete supplied evaluation and plan remain in this folder, '
            'including detail fields not displayed here. No upload occurs. Inspect before sharing.</p>'
            f'<dl><dt>Plan JSON-value SHA-256</dt><dd><code>{_text(report["plan_sha256"])}</code></dd>'
            f'<dt>Evaluation JSON-value SHA-256</dt><dd><code>{_text(report["source_sha256"])}</code></dd></dl>'
            '<p>Verification recomputes every file, including this page. Coordinated replacement of inputs and outputs '
            'can still verify: hashes are not signatures or independent approval. Source JSON values, not original '
            'file formatting, are retained. Exit 0 means the diagnostic verifies, even if limits are exceeded.</p></section>'
            f'<footer><h2>Interpretation limits</h2><p>{_text(report["boundary"])}</p></footer></main></body></html>\n')


def failure_bound_payloads(plan, source):
    report = review_failure_bounds(plan, source)
    payloads = {name: rendered(value) for name, value in (
        ('plan.json', plan), ('evaluation.json', source), ('report.json', report))}
    payloads['review.html'] = render_failure_review(report).encode('utf-8')
    payloads['manifest.json'] = rendered({'pack_version': 'aau-failure-bound-pack/1.0',
                                        'files': {name: digest(value) for name, value in sorted(payloads.items())},
                                        'boundary': 'Unsigned diagnostic pack; no sampling, scoring, authenticity, or release approval is established.'})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError('failure-bound pack member exceeds 2 MB; no evidence is truncated')
    return report, payloads


def create_failure_bound_pack(plan, source, directory: Path):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite failure-bound pack destination')
    report, payloads = failure_bound_payloads(plan, source)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in payloads.items():  # Manifest last; incomplete writes cannot verify.
        with (directory / name).open('xb') as stream:
            stream.write(value)
    return report


def verify_failure_bound_pack(directory: Path):
    if directory.is_symlink() or not directory.is_dir() or {path.name for path in directory.iterdir()} != FILES:
        raise AgentBomError('failure-bound pack requires its exact five-file set in a real directory')
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError('failure-bound pack requires bounded regular non-symlink members')
    report, expected = failure_bound_payloads(load_json(directory / 'plan.json'), load_json(directory / 'evaluation.json'))
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f'failure-bound pack member does not recompute: {name}')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau failure-bound-pack', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('plan', type=Path)
    create.add_argument('evaluation', type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    try:
        report = (create_failure_bound_pack(load_json(args.plan), load_json(args.evaluation), args.out)
                  if args.command == 'create' else verify_failure_bound_pack(args.directory))
        print(f"Failure-bound pack: {report['status']}. Diagnostic only; no deployment approval.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
