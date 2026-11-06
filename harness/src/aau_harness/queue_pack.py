"""Portable, source-retaining offline review packs for finite queue diagnostics."""

import argparse
from html import escape
from pathlib import Path
import sys

from .agent_bom import MAX_JSON_BYTES, _parse_json, digest, load_json, rendered
from .authority_html import STYLE
from .eval_failure_pack import EXTRA_STYLE
from .inspect_pack import InspectionError, _capture
from .intake_review import _read_request
from .review_queue import _controls, review_queue


FILES = {'queue-plan.json', 'routing-plan.json', 'evaluation.json', 'work-items.json',
         'report.json', 'review.html', 'README.txt', 'manifest.json'}
GUIDE = '''Finite queue reviewer pack — offline diagnostic, not approval

Verify before opening review.html, using a matching trusted harness and the queue-plan hash
obtained independently from your reviewer-controlled channel:

  aau queue-pack verify PATH --queue-plan-sha256 YOUR_INDEPENDENTLY_CONTROLLED_HASH

Do not take the expected approval hash from this delivered folder. The pinned queue plan binds
the exact routing-plan bytes and a declared threshold. Complete evaluation/timing sources are
retained. Verification recomputes the original routing and queue reports and every presentation
byte; editing a manifest cannot bless changed HTML, data, or favorable summaries.

Exit 0 verifies this finite diagnostic, even when work remains, deadlines fail, or routing limits
are exceeded. It is NOT successful human resolution, legal compliance, staffing advice, an observed
human study, or deployment approval. Inspect the full report and both plans, including the nested
routing failures. Unknown deadlines, unserved waits, and blocked jobs must not be dropped.

Queue/routing plan bytes are preserved exactly; evaluation/work-items JSON is reserialized without
changing parsed values. The HTML is script-free, contains no remote assets, and does not verify
itself. This pack is not routed by generic inspect-pack: use queue-pack with the independent pin.
Every source remains included and may contain sensitive identifiers, times, or measurements.
This is NOT sanitized or permission to share. No model, adapter, human action, or upload is run.
'''


def _text(value):
    return escape('Not available' if value is None else str(value), quote=True)


def _table(caption, headings, rows):
    body = ''.join('<tr>' + ''.join(f'<td>{_text(cell)}</td>' for cell in row) + '</tr>' for row in rows)
    if not body:
        body = f'<tr><td colspan="{len(headings)}">No observations in this table.</td></tr>'
    return (f'<div class="scroll" role="region" tabindex="0" aria-label="{_text(caption)}"><table>'
            f'<caption>{_text(caption)}</caption><thead><tr>'
            + ''.join(f'<th scope="col">{_text(name)}</th>' for name in headings)
            + f'</tr></thead><tbody>{body}</tbody></table></div>')


def _plot(report):
    timeline = report['timeline']
    horizon = report['plan']['horizon_s']
    maximum = max(1, *(max(row['waiting_after_events'], row['in_service_after_events']) for row in timeline))
    paths = []
    for key, color, dash in [('waiting_after_events', '#31576d', ''), ('in_service_after_events', '#8b6a29', ' stroke-dasharray="7 4"')]:
        points = [(40 + 640 * row['time_s'] / horizon, 180 - 140 * row[key] / maximum) for row in timeline]
        path = f'M {points[0][0]:.4f} {points[0][1]:.4f}'
        for x, y in points[1:]:
            path += f' H {x:.4f} V {y:.4f}'
        paths.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"{dash}/>')
    return ('<figure><svg viewBox="0 0 720 220" role="img" aria-labelledby="queue-title queue-desc">'
            '<title id="queue-title">Finite queue occupancy</title>'
            '<desc id="queue-desc">Step paths show waiting and in-service observations after all events at each second. '
            'Solid blue: waiting. Dashed ochre: in service. Exact values are in the following table.</desc>'
            '<path d="M 40 35 V 180 H 680" fill="none" stroke="#536c79"/>'
            f'<text x="20" y="184" font-size="12">0</text><text x="12" y="44" font-size="12">{maximum}</text>'
            '<text x="40" y="205" font-size="12">0 seconds</text>'
            f'<text x="680" y="205" text-anchor="end" font-size="12">{horizon} seconds</text>'
            + ''.join(paths) + '</svg><figcaption>Solid blue: waiting. Dashed ochre: in service. '
            'Supplied relative seconds; simulated occupancy, not observed human activity.</figcaption></figure>')


def render_review(report):
    counts, routing = report['counts'], report['routing_review']
    selected = next(row for row in routing['thresholds'] if row['threshold'] == report['plan']['threshold'])
    stats = ''.join(f'<div class="stat"><strong>{counts[key]}</strong><span>{label}</span></div>' for key, label in (
        ('deferred_observations', 'hypothetical referrals'), ('scheduled', 'scheduled service intervals'),
        ('not_scheduled', 'unscheduled observations'), ('known_deadline_failures', 'declared-deadline failures')))
    outcome = _table('Incomplete work and unknown outcomes', ('Measure', 'Value'), [
        ('Declared timing basis', report['plan']['timing_basis']), ('Selected declared score threshold', report['plan']['threshold']),
        ('Maximum scheduled wait (seconds)', report['maximum_scheduled_wait_s']),
        ('Maximum unserved wait at horizon (seconds)', report['maximum_unserved_wait_at_horizon_s']),
        ('Declared deadlines', counts['declared_deadlines']), ('Unknown or unresolved deadline outcomes', counts['deadline_unknown_or_unresolved']),
        ('Human resolution', 'Not measured'), ('All original recorded joint failures', routing['recorded_joint_failures']),
        ('Source summary audit', routing['source_audit']['status'])])
    scopes = _table('Routing evidence at the declared threshold — not a policy gate',
                    ('Scope', 'Automated', 'Automated joint failures', 'Deferred', 'Recorded-limit diagnostic'),
                    [(row['scope_id'], row['automated_observations'], row['automated_joint_failures'], row['deferred_observations'], row['status'])
                     for row in selected['scopes']])
    jobs = _table('Every referral, including blocked work',
                  ('Scenario / repeat', 'Arrival / service seconds', 'Slot', 'Start / finish', 'Scheduled wait', 'Unserved wait at horizon', 'Deadline / outcome', 'Unscheduled reason'),
                  [(f"{r['scenario_id']} / {r['repeat']}", f"{r['arrival_s']} / {r['service_s']}", r['worker_id'],
                    f"{_text(r['start_s'])} / {_text(r['finish_s'])}", r['scheduled_wait_s'], r['unserved_wait_at_horizon_s'],
                    f"{r['deadline_s'] if r['deadline_s'] is not None else 'Unknown'} / {r['deadline_status']}", r['reason'] or 'None') for r in report['jobs']])
    points = _table('Exact timeline after same-time events', ('Seconds', 'Waiting', 'In service'),
                    [(r['time_s'], r['waiting_after_events'], r['in_service_after_events']) for r in report['timeline']])
    links = ''.join(f'<li><a href="{name}">{name}</a></li>' for name in sorted(FILES - {'review.html'}))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            f'<title>Finite human-review queue evidence</title><style>{STYLE}{EXTRA_STYLE}</style></head><body><main>'
            '<p class="eyebrow">Offline reviewer pack · finite what-if model</p><h1>A referral is not a resolved case.</h1>'
            '<p class="lede">Inspect modeled waiting time, unavailable capacity, and unfinished work alongside the original routing failures.</p>'
            '<p class="notice">Scheduled service is simulated time, not correct human review. Exit 0 verifies a diagnostic, '
            'not staffing suitability, deadline compliance, or deployment approval.</p>'
            f'<div class="stats">{stats}</div><section class="scope"><h2>What remains unresolved</h2>{outcome}</section>'
            f'<section class="scope"><h2>Queue over the declared horizon</h2>{_plot(report)}'
            f'<details><summary>Read all exact timeline values</summary>{points}</details></section>'
            f'<section class="scope"><h2>Retain the automation evidence</h2>{scopes}</section>'
            f'<section class="scope"><h2>Inspect every referral</h2>{jobs}</section>'
            '<h2>Verify before relying on this page</h2><pre>aau queue-pack verify PATH --queue-plan-sha256 YOUR_INDEPENDENTLY_CONTROLLED_HASH</pre>'
            '<p>Obtain the expected hash independently, not from this delivered folder. Full source inputs are included, '
            'not sanitized. This page does not verify itself. Use the specialized queue-pack command, not generic inspect-pack.</p>'
            f'<ul>{links}</ul><footer><h2>Model boundaries</h2><p>{_text(report["boundary"])}</p></footer></main></body></html>\n')


def pack_payloads(queue_raw, routing_raw, evaluation, work_items, *, queue_plan_sha256):
    report = review_queue(queue_raw, routing_raw, evaluation, work_items, queue_plan_sha256=queue_plan_sha256)
    files = {'queue-plan.json': queue_raw, 'routing-plan.json': routing_raw, 'evaluation.json': rendered(evaluation),
             'work-items.json': rendered(work_items), 'report.json': rendered(report),
             'review.html': render_review(report).encode('utf-8'), 'README.txt': GUIDE.encode('utf-8')}
    files['manifest.json'] = rendered({'pack_version': 'aau-human-review-queue-pack/1.0',
                                       'renderer_sha256': digest(Path(__file__).read_bytes()),
                                       'style_sha256': digest((STYLE + EXTRA_STYLE).encode('utf-8')),
                                       'files_sha256': {name: digest(value) for name, value in sorted(files.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in files.values()):
        raise InspectionError('queue_pack_member_exceeds_limit')
    return report, files


def create_pack(queue_raw, routing_raw, evaluation, work_items, directory, *, queue_plan_sha256):
    if directory.exists() or directory.is_symlink():
        raise InspectionError('queue_pack_destination_already_exists')
    report, files = pack_payloads(queue_raw, routing_raw, evaluation, work_items, queue_plan_sha256=queue_plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, payload in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(payload)
    return report


def verify_pack(directory, *, queue_plan_sha256):
    files, folders = _capture(directory)
    if folders or set(files) != FILES:
        raise InspectionError('queue_pack_requires_exact_regular_members')
    _controls(files['queue-plan.json'], files['routing-plan.json'], queue_plan_sha256)
    report, expected = pack_payloads(files['queue-plan.json'], files['routing-plan.json'],
                                     _parse_json(files['evaluation.json']), _parse_json(files['work-items.json']),
                                     queue_plan_sha256=queue_plan_sha256)
    if files != expected:
        raise InspectionError('queue_pack_does_not_recompute')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau queue-pack', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('queue_plan', 'routing_plan', 'evaluation', 'work_items'):
        create.add_argument(name, type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    for command in (create, verify):
        command.add_argument('--queue-plan-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            queue_raw, routing_raw = _read_request(args.queue_plan), _read_request(args.routing_plan)
            _controls(queue_raw, routing_raw, args.queue_plan_sha256)
            report = create_pack(queue_raw, routing_raw, load_json(args.evaluation), load_json(args.work_items), args.out,
                                 queue_plan_sha256=args.queue_plan_sha256)
        else:
            report = verify_pack(args.directory, queue_plan_sha256=args.queue_plan_sha256)
        print(f"Verified finite queue diagnostic: {report['counts']['not_scheduled']} unscheduled; "
              f"{report['counts']['known_deadline_failures']} declared-deadline failures. Not human resolution or approval.")
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'queue_pack_input_or_output_rejected'
        print(f'error: {reason}; no verified queue pack.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
