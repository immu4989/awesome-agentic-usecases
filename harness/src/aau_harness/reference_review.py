"""Retain panel disagreements and explicit adjudications before exporting fallible references."""

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, _parse_json, digest, rendered
from .authority_html import STYLE
from .eval_pack import _table
from .grader_review import REFERENCE_STATES, SPLITS, _ids, _ratio, validate_plan as validate_grader_plan
from .inspect_pack import _capture
from .intake_review import _read_request, _sha


FILES = {'plan.json', 'ratings.json', 'adjudications.json', 'reference.json', 'grader-plan.json',
         'review.json', 'review.html', 'manifest.json'}
STATES = ('pass', 'fail', 'abstain', 'missing')
BOUNDARY = (
    'Descriptive reconstruction of supplied panel labels and adjudications, not verified ground truth, '
    'expert consensus, human research, grader certification, compliance, or deployment approval. '
    'Every declared rater is assigned every item/criterion pair. Only a fully submitted, unanimous, '
    'non-abstaining panel yields an automatic pass/fail reference. Any observed pass/fail conflict '
    'remains disputed, even if a majority agrees. Otherwise incomplete or abstained panels remain '
    'unreviewed. An explicitly supplied adjudication may change the reference only when all assigned '
    'ratings are present (including abstentions); it never erases original ratings or conflicts. '
    'This is the repository protocol, not a government-required adjudication procedure. Role identifiers '
    'and reasons are declarations, not authenticated identities, qualifications, independence, blinding, '
    'preregistration, chronology, or proof that evidence was read. Different IDs can refer to the same person. '
    'Rubric/evidence hashes bind declarations, not the underlying contents or their correctness. '
    'Distinct fingerprints do not establish independent tasks. Agreement is not accuracy. No majority '
    'vote, reliability coefficient, confidence interval, population claim, or model score is inferred. '
    'Calibration/validation and criteria remain separate; overlapping groups must not be pooled. '
    'No model, network, adapter, or subprocess is invoked. Keep plan pins independently and retain '
    'the whole pack with a trusted matching harness. Names, reasons, labels, and hashes may be sensitive; '
    'this packet is not sanitized and does not authorize sharing or agency use.'
)


def _fail(message):
    raise AgentBomError('reference review: ' + message)


def _object(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        _fail('fields differ from the documented contract')


def _document(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_JSON_BYTES:
        _fail('input must contain 1 to 2000000 bytes')
    try:
        value = _parse_json(raw)
        json.dumps(value, allow_nan=False)
        if not isinstance(value, dict):
            raise ValueError('object required')
        return value
    except (ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise AgentBomError('reference review: finite JSON object without duplicate keys required') from exc


def _plan(raw, pin):
    if not isinstance(raw, bytes) or not _sha(pin) or digest(raw) != pin:
        _fail('plan byte pin mismatch')
    plan = _document(raw)
    common = ('rubric_sha256', 'reference_basis', 'criteria', 'items', 'groups')
    _object(plan, ('plan_version', 'raters', 'adjudicators', *common))
    if plan['plan_version'] != 'aau-reference-review-plan/1.0':
        _fail('unsupported plan version')
    # Reuse the downstream contract's census, split, hash, and group checks.
    template = {'plan_version': 'aau-grader-review-plan/1.0', 'reference_sha256': '0' * 64,
                **{name: plan[name] for name in common}}
    template_raw = rendered(template)
    validate_grader_plan(template_raw, digest(template_raw))
    raters, adjudicators = _ids(plan['raters'], 10), _ids(plan['adjudicators'], 10)
    if len(raters) < 2 or raters & adjudicators:
        _fail('require 2 to 10 raters and separate declared adjudicator IDs')
    if len(raters) * len(plan['items']) * len(plan['criteria']) > 10000:
        _fail('assigned panel census exceeds 10000 ratings')
    return plan, template


def _rows(raw, plan, *, adjudication, ratings_sha256=None):
    value = _document(raw)
    _object(value, ('format_version', 'rubric_sha256', 'rows', *(['ratings_sha256'] if adjudication else [])))
    version = 'aau-reference-adjudications/1.0' if adjudication else 'aau-reference-ratings/1.0'
    if value['format_version'] != version or value['rubric_sha256'] != plan['rubric_sha256']:
        _fail('label version or rubric mismatch')
    if adjudication and value['ratings_sha256'] != ratings_sha256:
        _fail('adjudications are not bound to these exact rating bytes')
    items = {item['item_id']: item for item in plan['items']}
    census = {(item, criterion) for item in items for criterion in plan['criteria']}
    rows = value['rows']
    limit = len(census) * (1 if adjudication else len(plan['raters']))
    if not isinstance(rows, list) or len(rows) > limit:
        _fail('too many or invalid label rows')
    indexed = {}
    role = 'adjudicator_id' if adjudication else 'rater_id'
    allowed = plan['adjudicators'] if adjudication else plan['raters']
    for row in rows:
        _object(row, ('item_id', 'criterion', 'evidence_sha256', role, 'verdict', 'rationale'))
        if not isinstance(row['item_id'], str) or not isinstance(row['criterion'], str):
            _fail('label identity must be a string')
        pair = row['item_id'], row['criterion']
        if pair not in census or row[role] not in allowed:
            _fail('unplanned label or reviewer role')
        key = pair if adjudication else (*pair, row[role])
        if key in indexed:
            _fail('duplicate rating or competing adjudications')
        if row['evidence_sha256'] != items[row['item_id']]['evidence_sha256']:
            _fail('label evidence fingerprint mismatch')
        if row['verdict'] not in (REFERENCE_STATES if adjudication else STATES[:-1]):
            _fail('unsupported verdict; missing ratings must be omitted, not fabricated')
        reason = row['rationale']
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            _fail('every submitted rating/adjudication needs a nonblank rationale within 1000 characters')
        indexed[key] = row
    return indexed


def _scope(rows, split, criterion, group, raters):
    selected = set(group['item_ids'])
    rows = [r for r in rows if r['split'] == split and r['criterion'] == criterion and r['item_id'] in selected]
    counts = Counter(r['reference'] for r in rows)
    return {'split': split, 'criterion': criterion, 'group_id': group['group_id'], 'planned_items': len(rows),
            'rating_counts': {state: sum(r['rating_counts'][state] for r in rows) for state in STATES},
            'submitted_rating_coverage': _ratio(sum(raters - r['rating_counts']['missing'] for r in rows), len(rows) * raters),
            'decided_reference_coverage': _ratio(sum(counts[s] for s in ('pass', 'fail')), len(rows)),
            'panel_conflict_count': sum(r['rating_counts']['pass'] > 0 and r['rating_counts']['fail'] > 0 for r in rows),
            'adjudicated_count': sum(r['adjudication'] is not None for r in rows),
            'reference_counts': {state: counts[state] for state in REFERENCE_STATES}}


def render_review(report):
    scopes = [(f"{r['split']}\n{r['criterion']}\n{r['group_id']}", r['planned_items'],
               f"{r['submitted_rating_coverage']['numerator']}/{r['submitted_rating_coverage']['denominator']}",
               r['panel_conflict_count'], r['adjudicated_count'],
               ', '.join(f'{s}: {n}' for s, n in r['reference_counts'].items())) for r in report['scopes']]
    def table(caption, headers, rows):
        html = _table(caption, headers, rows)
        return html.replace('<div class="scroll">',
                            f'<div class="scroll" tabindex="0" role="region" aria-label="{escape(caption, quote=True)}">', 1)
    sections = []
    for row in report['observations']:
        adjudication = row['adjudication']
        decision = (f"{adjudication['adjudicator_id']}: {adjudication['verdict']} — {adjudication['rationale']}"
                    if adjudication else 'No adjudication supplied')
        sections.append('<section class="case">'
                        f'<h3>{escape(row["item_id"])} / {escape(row["criterion"])}</h3>'
                        f'<p>Split: {row["split"]}. Panel reference: <strong>{row["panel_reference"]}</strong>. '
                        f'Exported reference: <strong>{row["reference"]}</strong>.</p>'
                        + table(f'Assigned ratings for {row["item_id"]} / {row["criterion"]}',
                                ('Declared rater', 'Recorded judgment', 'Rationale'),
                                [(r['rater_id'], r['verdict'], r['rationale'] or 'No rating supplied') for r in row['ratings']])
                        + f'<p><strong>Adjudication:</strong> {escape(decision)}</p>'
                        + f'<p><strong>Review flags:</strong> {escape(", ".join(row["flags"]) or "None")}</p></section>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>Reference label review</title><style>{STYLE}'
            'td{white-space:pre-line;overflow-wrap:break-word}table{min-width:700px}'
            '.case{margin:2rem 0;padding:1rem;background:white;border:1px solid #ccd5db}'
            'p,h3{overflow-wrap:anywhere}.case h3{margin-top:0}.case td:first-child{width:18%}.case td:nth-child(2){width:20%}'
            '.scroll:focus-visible{outline:3px solid #355c70;outline-offset:3px}'
            '@media print{table{min-width:0}.case{break-inside:avoid}}</style>'
            '</head><body><main><h1>Reference label review</h1>'
            '<p class="notice">Recorded judgments, not verified truth. A majority does not resolve a disagreement.</p>'
            + f'<p>Declared reference basis: {escape(report["reference_basis"])}</p>'
            + f'<p>Declared raters: {escape(", ".join(report["raters"]))}. '
            + f'Declared adjudicators: {escape(", ".join(report["adjudicators"]))}.</p>'
            + f'<p>Rubric fingerprint: <code>{report["rubric_sha256"]}</code>. Rubric contents are not verified.</p>'
            + '<p>Missing and abstained ratings remain visible. All assigned ratings must be present for adjudication. '
            'A zero-denominator coverage is undefined, not perfect. Groups may overlap; do not add their totals.</p>'
            '<p>On narrow screens, scroll tables sideways. Keyboard users can focus a table region and use arrow keys.</p>'
            + table('Coverage by declared split, criterion, and group',
                     ('Split / Criterion / Group', 'Planned pairs', 'Submitted / assigned ratings',
                      'Original conflicts', 'Adjudicated pairs', 'Exported references'), scopes)
            + '<h2>Every planned item and criterion</h2>'
            + ''.join(sections)
            + f'<h2>Boundaries</h2><p>{escape(report["boundary"])}</p>'
            + f'<p>Plan byte hash: <code>{report["input_sha256"]["plan.json"]}</code></p>'
            + '</main></body></html>')


def reference_payloads(plan_raw, ratings_raw, adjudications_raw, *, plan_sha256):
    plan, template = _plan(plan_raw, plan_sha256)
    ratings = _rows(ratings_raw, plan, adjudication=False)
    adjudications = _rows(adjudications_raw, plan, adjudication=True, ratings_sha256=digest(ratings_raw))
    observations, reference_rows, expanded = [], [], 0
    for item in sorted(plan['items'], key=lambda r: r['item_id']):
        for criterion in sorted(plan['criteria']):
            pair = item['item_id'], criterion
            panel = [{'rater_id': rater, 'verdict': ratings.get((*pair, rater), {}).get('verdict', 'missing'),
                      'rationale': ratings.get((*pair, rater), {}).get('rationale')} for rater in sorted(plan['raters'])]
            counts = Counter(r['verdict'] for r in panel)
            conflict = counts['pass'] > 0 and counts['fail'] > 0
            if conflict:
                original = 'disputed'
            elif counts['pass'] == len(panel):
                original = 'pass'
            elif counts['fail'] == len(panel):
                original = 'fail'
            else:
                original = 'unreviewed'
            decision = adjudications.get(pair)
            if decision is not None and counts['missing']:
                _fail('cannot adjudicate an incomplete panel; submit ratings or recorded abstentions first')
            final = decision['verdict'] if decision is not None else original
            flags = ([s for s, count in (('missing_ratings', counts['missing']), ('abstained_ratings', counts['abstain']),
                                        ('conflicting_ratings', int(conflict))) if count]
                     + (['recorded_adjudication'] if decision is not None else [])
                     + (['panel_reference_changed'] if final != original else []))
            row = {**item, 'criterion': criterion, 'ratings': panel, 'rating_counts': {s: counts[s] for s in STATES},
                   'panel_reference': original, 'adjudication': decision, 'reference': final, 'flags': flags}
            expanded += len(rendered(row))
            if expanded > MAX_JSON_BYTES:
                _fail('expanded review exceeds 2 MB')
            observations.append(row)
            reference_rows.append({'item_id': item['item_id'], 'criterion': criterion,
                                   'evidence_sha256': item['evidence_sha256'], 'verdict': final})
    reference = {'format_version': 'aau-grader-reference/1.0', 'rubric_sha256': plan['rubric_sha256'], 'rows': reference_rows}
    reference_raw = rendered(reference)
    template['reference_sha256'] = digest(reference_raw)
    grader_raw = rendered(template)
    # Validate the export through the existing consumer, including exact reference census.
    from .grader_review import _labels
    validate_grader_plan(grader_raw, digest(grader_raw))
    _labels(reference_raw, template, reference=True)
    groups = [{'group_id': 'overall', 'item_ids': [i['item_id'] for i in plan['items']]}, *plan['groups']]
    report = {'report_version': 'aau-reference-review/1.0', 'status': 'recorded_reference_diagnostic',
              'rubric_sha256': plan['rubric_sha256'], 'reference_basis': plan['reference_basis'],
              'raters': sorted(plan['raters']), 'adjudicators': sorted(plan['adjudicators']),
              'input_sha256': {'plan.json': digest(plan_raw), 'ratings.json': digest(ratings_raw),
                               'adjudications.json': digest(adjudications_raw)},
              'reference_sha256': digest(reference_raw), 'grader_plan_sha256': digest(grader_raw),
              'observations': observations,
              'scopes': [_scope(observations, split, criterion, group, len(plan['raters'])) for split in SPLITS
                         for criterion in sorted(plan['criteria']) for group in groups],
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'reference_review.py', 'grader_review.py', 'agent_bom.py', 'intake_review.py',
                  'inspect_pack.py', 'authority_html.py', 'eval_pack.py')}, 'boundary': BOUNDARY}
    payloads = {'plan.json': plan_raw, 'ratings.json': ratings_raw, 'adjudications.json': adjudications_raw,
                'reference.json': reference_raw, 'grader-plan.json': grader_raw,
                'review.json': rendered(report), 'review.html': render_review(report).encode()}
    payloads['manifest.json'] = rendered({'pack_version': 'aau-reference-review-pack/1.0',
                                        'files': {name: digest(raw) for name, raw in sorted(payloads.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in payloads.values()):
        _fail('generated pack member exceeds 2 MB')
    return report, payloads


def create_reference_pack(plan_raw, ratings_raw, adjudications_raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('refusing to overwrite an existing destination')
    report, payloads = reference_payloads(plan_raw, ratings_raw, adjudications_raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_reference_pack(directory, *, plan_sha256):
    captured, directories = _capture(directory)
    if directories or set(captured) != FILES:
        _fail('pack requires the exact eight-file inventory')
    report, expected = reference_payloads(captured['plan.json'], captured['ratings.json'], captured['adjudications.json'],
                                         plan_sha256=plan_sha256)
    if captured != expected:
        _fail('pack does not recompute byte-for-byte')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau reference-review', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('plan', 'ratings', 'adjudications'):
        create.add_argument(name, type=Path)
    create.add_argument('--plan-sha256', required=True)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--plan-sha256', required=True)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .reference_demo import create_demo
            create_demo(args.out)
            print('Created synthetic panel/adjudication example; no human study or approval claimed.')
            return 0
        if args.command == 'create':
            create_reference_pack(_read_request(args.plan), _read_request(args.ratings), _read_request(args.adjudications),
                                  args.out, plan_sha256=args.plan_sha256)
            report = verify_reference_pack(args.out, plan_sha256=args.plan_sha256)
        else:
            report = verify_reference_pack(args.directory, plan_sha256=args.plan_sha256)
        print(f"Reference packet verified: {len(report['observations'])} planned item/criterion pairs; not verified truth.")
        return 0
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, AgentBomError) else 'reference input or output rejected'
        print(f'error: {reason}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
