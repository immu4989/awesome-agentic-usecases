"""Reserve conditional failure-bound uncertainty across a predeclared candidate family."""

import argparse
from html import escape
from pathlib import Path
import re
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, _parse_json, digest, rendered
from .eval_failure_bound import _bounded, upper_failure_bound, validate_plan as validate_fixed_plan
from .eval_repeatability import review_repeatability
from .evaluation_context import VERSION, validate_context
from .inspect_pack import _capture
from .intake_review import _read_request, _sha
from .report_html import STYLE, table


BOUNDARY = (
    'Conditional simultaneous upper bounds for a finite, predeclared candidate-by-scope family, not '
    'a ranking, pairwise superiority test, posterior probability, release gate, or safety certification. '
    'One unit is a complete scenario bundle; any joint-criterion failure in any planned repeat fails '
    'that bundle. Repeats never enlarge the independent sample count. Each marginal binomial bound '
    'requires IID scenario-bundle outcomes within that candidate/scope and stable scoring and '
    'execution conditions. Shared cases and overlapping groups may correlate bounds; the Bonferroni '
    'union bound does not require independence between those cells. Candidates, sample sizes, criteria, '
    'groups, thresholds, and sampling design must be fixed before outcomes. These assumptions and '
    'preregistration are not verified. Alpha is reserved across ALL planned candidates and scopes, '
    'including missing candidates, without reallocation. Simultaneous coverage concerns this fixed '
    'family; it is not conditional coverage given a selected winner, proof that a chosen candidate '
    'is best, or protection for unplanned candidates, adaptive tuning, benchmark reuse, additional '
    'looks, or optional stopping. Fixed benchmarks receive no population bounds. Missing submissions '
    'stay unobserved; invalid or partial submissions are rejected, not silently dropped. Context '
    'fingerprints must match the approved plan, but do not establish genuine candidate identity, '
    'source execution, distinct tasks, independence, scoring validity, or equivalent deployment '
    'conditions. Original scenario/config/scorer content is not read. Source-summary mismatches '
    'remain visible; numeric observations are not repaired. Floating-point inversion is not an '
    'arbitrary-precision certificate. No models, subprocesses, network, collectors, or deployment '
    'actions run. Preserve the independently controlled plan byte pin and complete packet with a '
    'matching trusted harness. Raw inputs may be sensitive; no sanitization or sharing permission '
    'is provided. Policy, cost, accessibility, human-review, and incident obligations remain separate.'
)


def _fail(reason):
    raise AgentBomError('candidate_bounds_' + reason)


def _document(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_JSON_BYTES:
        _fail('input_bytes_invalid_or_oversized')
    value = _parse_json(raw)
    _bounded(value)
    return value


def validate_plan(raw, pin):
    if not isinstance(raw, bytes) or not _sha(pin) or digest(raw) != pin:
        _fail('plan_byte_pin_mismatch')
    plan = _document(raw)
    additions = {'candidates', 'scenario_sha256', 'scoring_sha256'}
    if not isinstance(plan, dict) or plan.get('plan_version') != 'aau-candidate-bound-plan/1.0' or not additions <= set(plan):
        _fail('plan_contract_invalid')
    fixed = {k: v for k, v in plan.items() if k not in additions}
    fixed['plan_version'] = 'aau-failure-bound-plan/1.0'
    validate_fixed_plan(fixed)
    candidates = plan['candidates']
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 10:
        _fail('requires_one_to_ten_candidates')
    ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {'candidate_id', 'config_sha256'}:
            _fail('candidate_contract_invalid')
        identity = candidate['candidate_id']
        if (not isinstance(identity, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', identity) is None
                or identity in ids):
            _fail('candidate_id_invalid_or_duplicate')
        ids.add(identity)
        validate_context(_context(plan, candidate), plan['scenario_ids'])
    if len(set(plan['scenario_sha256'].values())) != len(plan['scenario_ids']):
        _fail('duplicate_declared_scenario_fingerprints')
    return plan


def _context(plan, candidate):
    return {'context_version': VERSION, 'config_sha256': candidate['config_sha256'],
            'scenario_sha256': plan['scenario_sha256'], 'scoring_sha256': plan['scoring_sha256']}


def render_review(report):
    rows = [(c['candidate_id'], s['scope_id'], s['scenario_count'], s['failed_scenario_count'],
             s['one_sided_upper_failure_bound'], s['maximum_failure_probability'], s['status'].replace('_', ' ').capitalize())
            for c in report['candidates'] for s in c['scopes']]
    audits = [(c['candidate_id'], c['status'].replace('_', ' ').capitalize(), c['observation_count'],
               c['source_audit']['status'] if c['source_audit'] else 'No submission') for c in report['candidates']]
    failures = [(c['candidate_id'], r['scenario_id'], len(r['failed_repeats']))
                for c in report['candidates'] for r in c['scenario_outcomes'] if r['bundle_failed']]
    method = report['method']
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Planned candidate uncertainty</title>'
            f'<style>{STYLE}</style></head><body><main><h1>One uncertainty budget, every planned candidate</h1>'
            '<p class="notice">Conditional diagnostic only. No ranking, winning system, or deployment approval.</p>'
            f'<p>{escape(report["sampling_basis"])}</p>'
            f'<p>Planned candidates: {method["candidate_count"]}; scopes per candidate: {method["scope_count"]}; '
            f'family cells: {method["family_size"]}; tail allocation per cell: {method["tail_probability_per_cell"]:.6g}. '
            'Missing submissions do not free uncertainty budget. Fixed benchmarks have no population bound.</p>'
            '<p>Keyboard users: Tab to a table, then use arrow keys to scroll; Tab leaves the table. '
            'Unavailable values are not zeros. Displayed decimals use six significant digits; statuses use unrounded values. '
            'Read full precision and failed-repeat details in report.json.</p>'
            + table('Every planned candidate and scope', ('Candidate', 'Scope', 'Observed bundles', 'Failed bundles',
                'Conditional upper failure bound', 'Declared limit', 'Status'), rows, missing_text='Not available', compact_numbers=True)
            + table('Source completeness and summary audit', ('Candidate', 'Submission status', 'Observations', 'Summary audit'),
                    audits, missing_text='Not available')
            + table('Every observed failed bundle; later passing repeats do not erase it',
                    ('Candidate', 'Scenario', 'Failed repeats'), failures)
            + '<h2>Interpretation limits</h2><p>' + escape(BOUNDARY) + '</p></main></body></html>')


def candidate_payloads(plan_raw, sources, *, plan_sha256):
    plan = validate_plan(plan_raw, plan_sha256)
    if not isinstance(sources, dict) or not set(sources) <= {c['candidate_id'] for c in plan['candidates']}:
        _fail('unplanned_source')
    scopes = [{'scope_id': 'overall', 'scenario_ids': plan['scenario_ids'],
               'maximum_failure_probability': plan['maximum_failure_probability']},
              *[{'scope_id': g['group_id'], 'scenario_ids': g['scenario_ids'],
                 'maximum_failure_probability': g['maximum_failure_probability']}
                for g in sorted(plan['groups'], key=lambda g: g['group_id'])]]
    family = len(plan['candidates']) * len(scopes)
    alpha = (1 - plan['confidence_level']) / family
    infer = plan['sampling_design'] == 'declared_iid_fixed_horizon'
    candidates, size = [], 0
    for candidate in plan['candidates']:
        identity = candidate['candidate_id']
        outcomes, repeated = {}, None
        if identity in sources:
            source = _document(sources[identity])
            if not isinstance(source, dict) or source.get('evaluation_context') != _context(plan, candidate):
                _fail('declared_context_mismatch_or_missing')
            repeated = review_repeatability(source, criteria=plan['criteria'], draw_sizes=[1])
            if (repeated['repeat_count'] != plan['n_repeats']
                    or {r['scenario_id'] for r in repeated['scenarios']} != set(plan['scenario_ids'])):
                _fail('source_requires_exact_complete_planned_census')
            outcomes = {r['scenario_id']: {'scenario_id': r['scenario_id'], 'bundle_failed': bool(r['failures']),
                                          'failed_repeats': r['failures']} for r in repeated['scenarios']}
        rows = []
        for scope in scopes:
            failed = sum(outcomes[s]['bundle_failed'] for s in scope['scenario_ids']) if repeated else None
            n = len(scope['scenario_ids']) if repeated else None
            bound = upper_failure_bound(failed, n, alpha) if repeated and infer else None
            rows.append({'scope_id': scope['scope_id'], 'scenario_count': n, 'failed_scenario_count': failed,
                         'observed_bundle_failure_fraction': failed / n if repeated else None,
                         'maximum_failure_probability': scope['maximum_failure_probability'],
                         'one_sided_upper_failure_bound': bound,
                         'status': 'not_observed' if not repeated else 'population_inference_withheld' if not infer else
                         'conditional_bound_within_limit' if bound <= scope['maximum_failure_probability'] else
                         'conditional_bound_exceeds_limit'})
        result = {'candidate_id': identity, 'status': 'observed' if repeated else 'not_observed',
                  'source_file_sha256': digest(sources[identity]) if repeated else None,
                  'observation_count': repeated['observation_count'] if repeated else None,
                  'source_audit': repeated['source_audit'] if repeated else None,
                  'unreviewed_metrics': repeated['unreviewed_metrics'] if repeated else [],
                  'scopes': rows, 'scenario_outcomes': [outcomes[s] for s in plan['scenario_ids']] if repeated else []}
        size += len(rendered(result))
        if size > MAX_JSON_BYTES:
            _fail('expanded_report_exceeds_limit')
        candidates.append(result)
    report = {'report_version': 'aau-candidate-bound-review/1.0',
              'status': 'conditional_candidate_family_diagnostic' if infer else 'population_inference_withheld',
              'plan_file_sha256': plan_sha256, 'sampling_design': plan['sampling_design'],
              'sampling_basis': plan['sampling_basis'], 'criteria': plan['criteria'],
              'scope_definitions': scopes, 'planned_scenario_count': len(plan['scenario_ids']), 'n_repeats': plan['n_repeats'],
              'observed_candidate_count': len(sources), 'missing_candidate_count': len(plan['candidates']) - len(sources),
              'candidates': candidates, 'method': {'unit': 'scenario_bundle', 'confidence_level': plan['confidence_level'],
                  'candidate_count': len(plan['candidates']), 'scope_count': len(scopes), 'family_size': family,
                  'tail_probability_per_cell': alpha, 'missing_budget_reallocated': False,
                  'population_bounds_enabled': infer, 'bound_applied': infer and bool(sources),
                  'multiplicity': 'Bonferroni over all predeclared candidate-by-scope cells',
                  'bound': 'one-sided Clopper-Pearson binomial inversion; floating-point evaluation'},
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'eval_candidate_bounds.py', 'eval_failure_bound.py', 'eval_repeatability.py', 'eval_audit.py',
                  'runner.py', 'evaluation_context.py', 'agent_bom.py', 'intake_review.py', 'inspect_pack.py',
                  'report_html.py', 'authority_html.py')}, 'boundary': BOUNDARY}
    files = {'plan.json': plan_raw, **{f'candidates/{name}.json': raw for name, raw in sorted(sources.items())},
             'report.json': rendered(report), 'review.html': render_review(report).encode()}
    files['manifest.json'] = rendered({'pack_version': 'aau-candidate-bound-pack/1.0',
                                      'files_sha256': {name: digest(raw) for name, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        _fail('pack_member_exceeds_limit')
    return report, files


def create_candidate_pack(plan_raw, sources, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('output_already_exists')
    report, files = candidate_payloads(plan_raw, sources, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    return report


def verify_candidate_pack(directory, *, plan_sha256):
    files, directories = _capture(directory)
    if 'plan.json' not in files:
        _fail('plan_missing')
    plan = validate_plan(files['plan.json'], plan_sha256)
    sources = {c['candidate_id']: files[f'candidates/{c["candidate_id"]}.json'] for c in plan['candidates']
               if f'candidates/{c["candidate_id"]}.json' in files}
    report, expected = candidate_payloads(files['plan.json'], sources, plan_sha256=plan_sha256)
    if files != expected or set(directories) != ({'candidates'} if sources else set()):
        _fail('pack_does_not_recompute')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau candidate-bounds', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('plan', type=Path)
    create.add_argument('sources', type=Path, help='directory containing only CANDIDATE_ID.json submissions')
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    for command in (create, verify):
        command.add_argument('--plan-sha256', required=True)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .candidate_bounds_demo import create_demo
            create_demo(args.out)
        elif args.command == 'create':
            raw = _read_request(args.plan)
            plan = validate_plan(raw, args.plan_sha256)
            if args.out.resolve() == args.sources.resolve() or args.sources.resolve() in args.out.resolve().parents:
                _fail('output_must_be_outside_sources')
            files, directories = _capture(args.sources)
            allowed = {c['candidate_id'] + '.json': c['candidate_id'] for c in plan['candidates']}
            if directories or not set(files) <= set(allowed):
                _fail('source_inventory_invalid')
            create_candidate_pack(raw, {allowed[n]: data for n, data in files.items()}, args.out, plan_sha256=args.plan_sha256)
            verify_candidate_pack(args.out, plan_sha256=args.plan_sha256)
        else:
            verify_candidate_pack(args.directory, plan_sha256=args.plan_sha256)
        print('Candidate-family diagnostic computed; missing evidence and exceeded limits are not approval.')
        return 0
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, AgentBomError) else 'candidate_bound_input_or_output_rejected'
        print(f'error: {reason}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
