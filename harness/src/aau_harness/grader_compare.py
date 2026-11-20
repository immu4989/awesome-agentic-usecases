"""Compare recorded graders on the same pinned census without hiding lost decisions."""

import argparse
from collections import Counter
from html import escape
from pathlib import Path
import sys

from .agent_bom import MAX_JSON_BYTES, digest, rendered
from .grader_review import GRADER_STATES, REFERENCE_STATES, _ratio, review_grader
from .inspect_pack import InspectionError, _capture
from .intake_review import _read_request, _sha
from .report_html import STYLE, table


FILES = {'plan.json', 'reference.json', 'baseline.json', 'candidate.json', 'review.json', 'review.html', 'manifest.json'}
CHANGES = ('unchanged', 'wrong_to_right', 'right_to_wrong', 'wrong_to_undecided', 'right_to_undecided',
           'undecided_to_wrong', 'undecided_to_right', 'undecided_changed', 'reference_unresolved')
BOUNDARY = (
    'Descriptive paired grader comparison, not a statistical significance test, population estimate, '
    'winner selection, calibrated probability, release gate, or certification. Correct and wrong mean '
    'agreement or disagreement with the supplied fallible reference, not established truth. An abstention '
    'or missing judgment is not a corrected error. The common decided subset can be selected and '
    'unrepresentative; its agreement must be read beside full-census decision coverage. Calibration '
    'and validation, criteria, and overlapping groups remain separate and must not be pooled. Counts '
    'are item/criterion pairs, not independent samples. No confidence intervals or causal effects are '
    'inferred. The same pinned rubric, reference, and evidence census are required for both sides; '
    'rubric changes need a separately justified study. Hashes and grader IDs do not authenticate sources, '
    'prove execution, independence, reference correctness, or an uncontaminated holdout. Original '
    'transcripts and rubric content are not read. No grader, model, adapter, subprocess, or network '
    'request runs. Preserve the plan and baseline byte pins independently and retain this complete '
    'packet with a matching trusted harness. Raw inputs may contain sensitive labels or identifiers; '
    'no sanitization or permission to publish is provided. A successful command means the diagnostic '
    'was computed, not that the candidate is acceptable or approved for government use.'
)


def _fail(reason):
    raise InspectionError('grader_comparison_' + reason)


def _outcome(reference, verdict):
    if reference not in ('pass', 'fail'):
        return 'reference_unresolved'
    if verdict in ('abstain', 'missing'):
        return verdict
    return 'correct' if verdict == reference else 'false_pass' if verdict == 'pass' else 'false_failure'


def _change(reference, baseline, candidate):
    if reference not in ('pass', 'fail'):
        return 'reference_unresolved'
    if baseline == candidate:
        return 'unchanged'
    def category(verdict):
        return 'undecided' if verdict in ('abstain', 'missing') else 'right' if verdict == reference else 'wrong'
    before, after = category(baseline), category(candidate)
    return 'undecided_changed' if before == after else before + '_to_' + after


def _scope(rows, before, after):
    counts = Counter((r['reference'], r['baseline'], r['candidate']) for r in rows)
    changes = Counter(r['change'] for r in rows)
    common = [r for r in rows if r['reference'] in ('pass', 'fail')
              and r['baseline'] in ('pass', 'fail') and r['candidate'] in ('pass', 'fail')]
    return {'split': before['split'], 'criterion': before['criterion'], 'group_id': before['group_id'],
            'planned_items': len(rows), 'baseline': before, 'candidate': after,
            'changes': {key: changes[key] for key in CHANGES},
            'transition_matrix': {ref: {base: {cand: counts[ref, base, cand] for cand in GRADER_STATES}
                                       for base in GRADER_STATES} for ref in REFERENCE_STATES},
            'common_decided_coverage': _ratio(len(common), len(rows)),
            'baseline_agreement_on_common_decisions': _ratio(sum(r['baseline'] == r['reference'] for r in common), len(common)),
            'candidate_agreement_on_common_decisions': _ratio(sum(r['candidate'] == r['reference'] for r in common), len(common))}


def render_review(report):
    sections = []
    for index, scope in enumerate(report['scopes'], 1):
        name = f"{scope['split']} / {scope['criterion']} / {scope['group_id']}"
        def fraction(value):
            return f"{value['numerator']}/{value['denominator']}" if value['denominator'] else 'Undefined (0 denominator)'
        rows = [(label, fraction(scope['baseline'][key]), fraction(scope['candidate'][key])) for label, key in (
            ('Agreement on each side\'s decided reference pairs', 'agreement_on_paired_decisions'),
            ('Decided reference-pair coverage / planned items', 'paired_decision_coverage'),
            ('Grader decision coverage / planned items', 'grader_decision_coverage'))]
        rows.append(('Agreement on the SAME common decided pairs', fraction(scope['baseline_agreement_on_common_decisions']),
                     fraction(scope['candidate_agreement_on_common_decisions'])))
        sections.append(f'<section><h2>{escape(name)}</h2><p>Planned item/criterion pairs: {scope["planned_items"]}. '
                        f'Common decided coverage: {fraction(scope["common_decided_coverage"])}. '
                        'Different denominators can make an apparent improvement misleading.</p>'
                        + table(f'{index}. Decision coverage and agreement: {name}', ('Measure', 'Baseline', 'Candidate'), rows)
                        + table(f'{index}. Paired changes: {name}', ('Change relative to supplied reference', 'Pairs'),
                                [(k.replace('_', ' '), v) for k, v in scope['changes'].items()]) + '</section>')
    rows = [(r['item_id'], r['split'], r['criterion'], r['reference'], r['baseline'], r['candidate'],
             r['change'].replace('_', ' ')) for r in report['observations']]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Paired grader changes</title>'
            f'<style>{STYLE}</style></head><body><main><h1>What changed when the grader changed?</h1>'
            '<p class="notice">Recorded diagnostic only. No overall winner or deployment decision.</p>'
            f'<p>Baseline: {escape(report["baseline_grader_id"])}. Candidate: {escape(report["candidate_grader_id"])}.</p>'
            '<p>Correct means agreement with a fallible reference. Wrong means disagreement. Missing and abstained '
            'judgments are undecided, not corrected. Disputed and unreviewed references have no accuracy verdict.</p>'
            '<p>Keyboard users: Tab to a table, then use arrow keys to scroll; Tab leaves the table.</p>'
            + ''.join(sections) + '<h2>Every planned item and criterion</h2>'
            + table('Complete paired census, including missing judgments',
                    ('Item', 'Split', 'Criterion', 'Reference', 'Baseline', 'Candidate', 'Change'), rows)
            + '<h2>Interpretation limits</h2><p>' + escape(BOUNDARY) + '</p></main></body></html>')


def comparison_payloads(plan_raw, reference_raw, baseline_raw, candidate_raw, *, plan_sha256, baseline_sha256):
    if not isinstance(baseline_raw, bytes) or not _sha(baseline_sha256) or digest(baseline_raw) != baseline_sha256:
        _fail('baseline_byte_pin_mismatch')
    before = review_grader(plan_raw, reference_raw, baseline_raw, plan_sha256=plan_sha256)
    after = review_grader(plan_raw, reference_raw, candidate_raw, plan_sha256=plan_sha256)
    observations = []
    # Both diagnostics enumerate the exact same validated, sorted census, not just the intersection of supplied rows.
    for base, candidate in zip(before['observations'], after['observations']):
        ref, b, c = base['reference'], base['grader'], candidate['grader']
        observations.append({key: base[key] for key in ('item_id', 'evidence_sha256', 'split', 'criterion', 'reference')}
                            | {'baseline': b, 'candidate': c, 'baseline_outcome': _outcome(ref, b),
                               'candidate_outcome': _outcome(ref, c), 'change': _change(ref, b, c)})
    groups = {g['group_id']: set(g['item_ids']) for g in before['plan']['groups']}
    groups['overall'] = {i['item_id'] for i in before['plan']['items']}
    scopes, size = [], len(rendered(observations))
    for b, c in zip(before['scopes'], after['scopes']):
        rows = [r for r in observations if r['split'] == b['split'] and r['criterion'] == b['criterion']
                and r['item_id'] in groups[b['group_id']]]
        scope = _scope(rows, b, c)
        size += len(rendered(scope))
        if size > MAX_JSON_BYTES:
            _fail('expanded_report_exceeds_limit')
        scopes.append(scope)
    files = {'plan.json': plan_raw, 'reference.json': reference_raw, 'baseline.json': baseline_raw, 'candidate.json': candidate_raw}
    report = {'report_version': 'aau-grader-comparison/1.0', 'status': 'recorded_paired_grader_diagnostic',
              'input_sha256': {name: digest(raw) for name, raw in files.items()},
              'baseline_grader_id': before['grader_id'], 'candidate_grader_id': after['grader_id'],
              'observations': observations, 'scopes': scopes,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'grader_compare.py', 'grader_review.py', 'agent_bom.py', 'intake_review.py', 'inspect_pack.py',
                  'report_html.py', 'authority_html.py')}, 'boundary': BOUNDARY}
    files.update({'review.json': rendered(report), 'review.html': render_review(report).encode()})
    files['manifest.json'] = rendered({'pack_version': 'aau-grader-comparison-pack/1.0',
                                      'files_sha256': {name: digest(raw) for name, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        _fail('pack_member_exceeds_limit')
    return report, files


def create_comparison(plan_raw, reference_raw, baseline_raw, candidate_raw, directory, *, plan_sha256, baseline_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('output_already_exists')
    report, files = comparison_payloads(plan_raw, reference_raw, baseline_raw, candidate_raw,
                                       plan_sha256=plan_sha256, baseline_sha256=baseline_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_comparison(directory, *, plan_sha256, baseline_sha256):
    files, directories = _capture(directory)
    if directories or set(files) != FILES:
        _fail('requires_exact_seven_file_inventory')
    report, expected = comparison_payloads(*(files[name] for name in ('plan.json', 'reference.json', 'baseline.json', 'candidate.json')),
                                          plan_sha256=plan_sha256, baseline_sha256=baseline_sha256)
    if files != expected:
        _fail('pack_does_not_recompute')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau grader-compare', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('plan', 'reference', 'baseline', 'candidate'):
        create.add_argument(name, type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    for command in (create, verify):
        command.add_argument('--plan-sha256', required=True)
        command.add_argument('--baseline-sha256', required=True)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .grader_compare_demo import create_demo
            create_demo(args.out)
        elif args.command == 'create':
            create_comparison(*(_read_request(getattr(args, name)) for name in ('plan', 'reference', 'baseline', 'candidate')),
                              args.out, plan_sha256=args.plan_sha256, baseline_sha256=args.baseline_sha256)
            verify_comparison(args.out, plan_sha256=args.plan_sha256, baseline_sha256=args.baseline_sha256)
        else:
            verify_comparison(args.directory, plan_sha256=args.plan_sha256, baseline_sha256=args.baseline_sha256)
        print('Recorded paired grader diagnostic computed. No winner selection, certification, or deployment approval.')
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'grader_comparison_input_or_output_rejected'
        print(f'error: {reason}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
