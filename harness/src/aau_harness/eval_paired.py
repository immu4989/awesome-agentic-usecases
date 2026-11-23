"""Compare two predeclared systems on complete matched scenario bundles, preserving new failures."""

import argparse
from fractions import Fraction
from html import escape
import math
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .eval_candidate_bounds import _document, validate_plan as validate_candidate_plan
from .eval_repeatability import review_repeatability
from .evaluation_context import VERSION
from .inspect_pack import _capture
from .intake_review import _read_request, _sha
from .report_html import STYLE, table


BOUNDARY = (
    'Paired diagnostic, not an acquisition ranking, release gate, equivalence/noninferiority test, '
    'effect-size confidence interval, causal claim, posterior probability, or safety certification. '
    'One pair is a complete matched scenario bundle for two fixed systems; any joint-criterion failure '
    'in any planned repeat fails that system on that bundle. Repeats never enlarge the paired sample '
    'count. Exact two-sided McNemar inference conditions on discordant pairs and tests equal marginal '
    'bundle-failure probabilities. It requires IID paired bundles within each declared scope, stable '
    'systems/scoring/execution, and a fixed horizon, criteria, memberships, and pair selected before '
    'outcomes. These assumptions, preregistration, reference validity, and authentic pairing are not '
    'verified. Bonferroni reserves the family error level over overall plus every declared group; '
    'overlapping scopes need not be independent for that adjustment. Extra system comparisons, '
    'adaptive selection, tuning, optional stopping, and repeated looks are outside this family. '
    'Fixed benchmarks receive descriptive counts only, never p-values. No detected difference does '
    'not establish equivalence; a detected difference does not establish practical importance or '
    'acceptable absolute failure risk. Every observed new failure remains visible. Shared context '
    'fingerprints must match but do not prove content, execution identity, comparable conditions, '
    'independence, or absence of contamination. Missing scenarios/repeats/criteria are rejected, not '
    'dropped or imputed. Original raw bytes and summary-audit mismatches are retained. Keep the '
    'independently controlled plan byte pin and matching trusted harness; a hash proves neither '
    'authority nor timing. No model calls, network, uploads, or deployment occur. Raw packets may '
    'contain sensitive data; no sanitization or disclosure authorization is provided. Other policy, '
    'cost, accessibility, human-review, and incident obligations remain separate.'
)
FILES = {'plan.json', 'baseline.json', 'candidate.json', 'report.json', 'review.html', 'manifest.json'}


def _fail(reason):
    raise AgentBomError('paired_review_' + reason)


def validate_plan(raw, pin):
    if not isinstance(raw, bytes) or not _sha(pin) or digest(raw) != pin:
        _fail('plan_byte_pin_mismatch')
    plan = _document(raw)
    fields = {'plan_version', 'scenario_ids', 'n_repeats', 'criteria', 'groups', 'sampling_design',
              'sampling_basis', 'family_significance_level', 'baseline', 'candidate',
              'scenario_sha256', 'scoring_sha256'}
    if not isinstance(plan, dict) or set(plan) != fields or plan['plan_version'] != 'aau-paired-candidate-plan/1.0':
        _fail('plan_contract_invalid')
    alpha = plan['family_significance_level']
    if type(alpha) not in (int, float) or not 0.000001 <= alpha <= 0.5:
        _fail('family_significance_level_requires_0_000001_through_0_5')
    if (not isinstance(plan['groups'], list) or any(not isinstance(g, dict)
            or set(g) != {'group_id', 'scenario_ids'} for g in plan['groups'])):
        _fail('group_contract_invalid')
    # Reuse bounded census, criteria, group and fingerprint validation only. The injected
    # failure limits are validation scaffolding, not user thresholds or computed bounds.
    shared = {k: v for k, v in plan.items() if k not in
              ('family_significance_level', 'baseline', 'candidate', 'groups')}
    shared.update(plan_version='aau-candidate-bound-plan/1.0',
                  candidates=[plan['baseline'], plan['candidate']], confidence_level=1 - alpha,
                  maximum_failure_probability=0.5,
                  groups=[{**g, 'maximum_failure_probability': 0.5} for g in plan['groups']])
    encoded = rendered(shared)
    validate_candidate_plan(encoded, digest(encoded))
    return plan


def exact_mcnemar(improvements, regressions):
    """Exact doubled smaller binomial tail under the conditional fair-coin null (no mid-p)."""
    if (type(improvements) is not int or type(regressions) is not int
            or min(improvements, regressions) < 0 or improvements + regressions > 500):
        _fail('discordant_counts_invalid')
    n = improvements + regressions
    return min(Fraction(1), Fraction(2 * sum(math.comb(n, k) for k in range(min(improvements, regressions) + 1)), 2 ** n))


def _p_value(value):
    return {'value': float(value), 'numerator': str(value.numerator), 'denominator': str(value.denominator)}


def render_review(report):
    counts = [(s['scope_id'], s['scenario_count'], s['both_pass'], s['improved'], s['regressed'], s['both_fail'],
               s['observed_candidate_minus_baseline_failure_fraction']) for s in report['scopes']]
    inference = [(s['scope_id'], s['two_sided_exact_p']['value'] if s['two_sided_exact_p'] else None,
                  s['bonferroni_adjusted_p']['value'] if s['bonferroni_adjusted_p'] else None,
                  s['inference_status'].replace('_', ' ')) for s in report['scopes']]
    cases = [(r['scenario_id'], r['transition'].replace('_', ' '),
              len(r['baseline_failed_repeats']), len(r['candidate_failed_repeats'])) for r in report['scenario_outcomes']]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Paired candidate review</title>'
            f'<style>{STYLE}</style></head><body><main><h1>What improved—and what newly failed?</h1>'
            '<p class="notice">Diagnostic only. A net gain never erases a new failure or grants approval.</p>'
            f'<p>Baseline: {escape(report["baseline_id"])}. Candidate: {escape(report["candidate_id"])}.</p>'
            f'<p>{escape(report["sampling_basis"])}</p>'
            '<p>Each scenario includes every planned repeat. Negative failure-rate differences favor the candidate '
            'on these supplied cases; they are not causal effects or confidence intervals. '
            'Tab to a table and use arrow keys to scroll; Tab leaves the table.</p>'
            + table('Matched scenario bundles; all transitions retained',
                    ('Scope', 'Pairs', 'Both pass', 'Improved', 'Regressed', 'Both fail', 'Candidate minus baseline failure rate'),
                    counts, compact_numbers=True)
            + table('Conditional inference; not a deployment decision',
                    ('Scope', 'Exact two-sided p', 'Family-adjusted p', 'Inference status'), inference,
                    missing_text='Withheld', compact_numbers=True)
            + f'<p>Declared family significance level: {report["family_significance_level"]}; '
              f'{report["scope_count"]} predeclared scopes. Exact rational p-values are retained in report.json. '
              'Failure to detect a difference is not equivalence; fixed benchmarks receive no p-values.</p>'
            + table('Every paired scenario; earlier failed repeats remain failures',
                    ('Scenario', 'Transition', 'Baseline failed repeats', 'Candidate failed repeats'), cases)
            + table('Summary audit; source observations are not repaired', ('Source', 'Status'),
                    [(role, report['source_audits'][role]['status']) for role in ('baseline', 'candidate')])
            + '<h2>Interpretation limits</h2><p>' + escape(BOUNDARY) + '</p></main></body></html>')


def paired_payloads(plan_raw, baseline_raw, candidate_raw, *, plan_sha256):
    plan = validate_plan(plan_raw, plan_sha256)
    reviews = {}
    for role, raw in (('baseline', baseline_raw), ('candidate', candidate_raw)):
        source = _document(raw)
        context = {'context_version': VERSION, 'config_sha256': plan[role]['config_sha256'],
                   'scenario_sha256': plan['scenario_sha256'], 'scoring_sha256': plan['scoring_sha256']}
        if not isinstance(source, dict) or source.get('evaluation_context') != context:
            _fail('declared_context_mismatch_or_missing')
        review = review_repeatability(source, criteria=plan['criteria'], draw_sizes=[1])
        if (review['repeat_count'] != plan['n_repeats']
                or {r['scenario_id'] for r in review['scenarios']} != set(plan['scenario_ids'])):
            _fail('requires_complete_matched_planned_census')
        reviews[role] = review
    by_role = {role: {r['scenario_id']: r['failures'] for r in review['scenarios']}
               for role, review in reviews.items()}
    outcomes = []
    for identity in plan['scenario_ids']:
        b, c = by_role['baseline'][identity], by_role['candidate'][identity]
        transition = 'both_fail' if b and c else 'improved' if b else 'regressed' if c else 'both_pass'
        outcomes.append({'scenario_id': identity, 'transition': transition,
                         'baseline_failed_repeats': b, 'candidate_failed_repeats': c})
    definitions = [{'group_id': 'overall', 'scenario_ids': plan['scenario_ids']},
                   *sorted(plan['groups'], key=lambda g: g['group_id'])]
    infer = plan['sampling_design'] == 'declared_iid_fixed_horizon'
    alpha = Fraction(str(plan['family_significance_level']))
    scopes = []
    for group in definitions:
        rows = [r for r in outcomes if r['scenario_id'] in group['scenario_ids']]
        counts = {name: sum(r['transition'] == name for r in rows)
                  for name in ('both_pass', 'improved', 'regressed', 'both_fail')}
        p = exact_mcnemar(counts['improved'], counts['regressed']) if infer else None
        adjusted = min(Fraction(1), p * len(definitions)) if infer else None
        scopes.append({'scope_id': group['group_id'], 'scenario_count': len(rows), **counts,
                       'discordant_pair_count': counts['improved'] + counts['regressed'],
                       'observed_candidate_minus_baseline_failure_fraction': (counts['regressed'] - counts['improved']) / len(rows),
                       'two_sided_exact_p': _p_value(p) if infer else None,
                       'bonferroni_adjusted_p': _p_value(adjusted) if infer else None,
                       'inference_status': 'population_inference_withheld' if not infer else
                       'difference_detected' if adjusted <= alpha else 'difference_not_detected'})
    report = {'report_version': 'aau-paired-candidate-review/1.0',
              'status': 'conditional_paired_diagnostic' if infer else 'population_inference_withheld',
              'plan_file_sha256': plan_sha256, 'baseline_file_sha256': digest(baseline_raw),
              'candidate_file_sha256': digest(candidate_raw), 'baseline_id': plan['baseline']['candidate_id'],
              'candidate_id': plan['candidate']['candidate_id'], 'sampling_design': plan['sampling_design'],
              'sampling_basis': plan['sampling_basis'], 'criteria': plan['criteria'], 'n_repeats': plan['n_repeats'],
              'scenario_count': len(outcomes), 'scope_count': len(definitions), 'scope_definitions': definitions,
              'family_significance_level': plan['family_significance_level'], 'scopes': scopes,
              'scenario_outcomes': outcomes, 'source_audits': {r: v['source_audit'] for r, v in reviews.items()},
              'unreviewed_metrics': {r: v['unreviewed_metrics'] for r, v in reviews.items()},
              'method': {'unit': 'paired_scenario_bundle', 'test': 'exact two-sided conditional McNemar; no mid-p',
                         'multiplicity': 'Bonferroni over overall and every declared group',
                         'arithmetic': 'integer binomial sums and rational comparisons; floats for display only',
                         'decision_rule': 'adjusted p <= declared family significance level',
                         'equivalence_test': False, 'effect_confidence_interval': False},
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'eval_paired.py', 'eval_candidate_bounds.py', 'eval_failure_bound.py', 'eval_repeatability.py',
                  'eval_audit.py', 'runner.py', 'evaluation_context.py', 'agent_bom.py', 'intake_review.py',
                  'inspect_pack.py', 'report_html.py', 'authority_html.py')}, 'boundary': BOUNDARY}
    files = {'plan.json': plan_raw, 'baseline.json': baseline_raw, 'candidate.json': candidate_raw,
             'report.json': rendered(report), 'review.html': render_review(report).encode()}
    files['manifest.json'] = rendered({'pack_version': 'aau-paired-candidate-pack/1.0',
                                      'files_sha256': {n: digest(v) for n, v in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        _fail('pack_member_exceeds_limit')
    return report, files


def create_paired_pack(plan_raw, baseline_raw, candidate_raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('output_already_exists')
    report, files = paired_payloads(plan_raw, baseline_raw, candidate_raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_paired_pack(directory, *, plan_sha256):
    files, directories = _capture(directory)
    if set(files) != FILES or directories:
        _fail('pack_inventory_invalid')
    report, expected = paired_payloads(files['plan.json'], files['baseline.json'], files['candidate.json'],
                                      plan_sha256=plan_sha256)
    if files != expected:
        _fail('pack_does_not_recompute')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau paired-review', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('plan', 'baseline', 'candidate'):
        create.add_argument(name, type=Path)
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
            from .paired_demo import create_demo
            create_demo(args.out)
        elif args.command == 'create':
            raw = _read_request(args.plan)
            validate_plan(raw, args.plan_sha256)
            create_paired_pack(raw, _read_request(args.baseline), _read_request(args.candidate), args.out,
                               plan_sha256=args.plan_sha256)
            verify_paired_pack(args.out, plan_sha256=args.plan_sha256)
        else:
            verify_paired_pack(args.directory, plan_sha256=args.plan_sha256)
        print('Paired diagnostic verified; new failures remain visible. Not equivalence or deployment approval.')
        return 0
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        print('error: ' + (str(exc) if isinstance(exc, AgentBomError) else 'paired_review_input_or_output_rejected'), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
