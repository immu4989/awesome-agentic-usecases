"""Plan a hypothetical fixed-horizon binomial criterion before observing evaluation outcomes."""

import argparse
from fractions import Fraction
from html import escape
from pathlib import Path
import re
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, _parse_json, digest, rendered
from .inspect_pack import _capture
from .intake_review import _read_request, _sha
from .report_html import STYLE, table


BOUNDARY = (
    'Hypothetical study planning only: no observations, measured effectiveness, acquisition decision, '
    'or deployment approval. Qualification means only that a prespecified binary statistical criterion '
    'would be met. One unit is an IID scenario bundle; any joint-criterion failure in any planned '
    'repeat fails the bundle. Repeats increase attempts, not independent sample size. Assumed failure '
    'probabilities apply to this whole bundle protocol, not individual calls, and are not estimates '
    'from data. Changing repeats requires reconsidering those assumed bundle rates. '
    'IID sampling within each scope, stable scoring/execution, valid rubrics, authentic '
    'group membership, and precommitment are not verified. A Bonferroni allocation reserves the '
    'declared family error probability across every candidate and scope; independence between cells '
    'is not required, but each marginal binomial model is. Qualification probability under the '
    'assumed rate is per cell, not the probability that all cells qualify or a posterior confidence. '
    'Counts alone do not identify actual candidates, sampling frames, case membership, or overlap. '
    'Per-scope designs need not form a jointly realizable dataset; do not sum overlapping counts or '
    'claim a global minimum workload. The search is bounded to 500 bundles per scope and selects '
    'the first qualifying n and largest permitted failure count c at that n. Increasing n without '
    'replanning c need not increase qualification probability. No optional stopping, outcome-driven '
    'sample extension, adaptive selection, multiple looks, finite-population correction, clustering, '
    'or automatic export to an execution/release gate is supported. Fixed benchmarks withhold '
    'population design quantities. Decimal inputs are interpreted exactly; displayed floating-point '
    'probabilities are summaries, not decision arithmetic. Retain the independent plan byte pin and '
    'matching trusted harness. No model, network, collection, spending, or approval action occurs.'
)


def _fail(reason):
    raise AgentBomError('evaluation_design_' + reason)


def _probability(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0(?:\.[0-9]{1,6})?|1(?:\.0{1,6})?)', value):
        _fail('probability_requires_decimal_string_with_at_most_six_places')
    return Fraction(value)


def validate_plan(raw, pin):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_JSON_BYTES or not _sha(pin) or digest(raw) != pin:
        _fail('plan_byte_pin_mismatch_or_size')
    plan = _parse_json(raw)
    fields = {'plan_version', 'purpose', 'sampling_design', 'sampling_basis', 'candidate_count',
              'repeats_per_scenario', 'family_error_probability', 'minimum_qualification_probability',
              'maximum_scenarios_per_scope', 'scopes'}
    if not isinstance(plan, dict) or set(plan) != fields or plan['plan_version'] != 'aau-evaluation-design-plan/1.0':
        _fail('plan_contract_invalid')
    for key in ('purpose', 'sampling_basis'):
        if not isinstance(plan[key], str) or not plan[key].strip() or len(plan[key]) > 2000:
            _fail('reviewable_purpose_and_sampling_basis_required')
    if plan['sampling_design'] not in ('hypothetical_iid_fixed_horizon', 'fixed_benchmark'):
        _fail('sampling_design_invalid')
    for key, maximum in (('candidate_count', 10), ('repeats_per_scenario', 20), ('maximum_scenarios_per_scope', 500)):
        if type(plan[key]) is not int or not 1 <= plan[key] <= maximum:
            _fail('count_out_of_range')
    if not 0 < _probability(plan['family_error_probability']) <= Fraction(1, 2):
        _fail('family_error_probability_out_of_range')
    if not 0 < _probability(plan['minimum_qualification_probability']) <= 1:
        _fail('qualification_probability_out_of_range')
    if not isinstance(plan['scopes'], list) or not 1 <= len(plan['scopes']) <= 20:
        _fail('scope_count_out_of_range')
    seen = set()
    for scope in plan['scopes']:
        if not isinstance(scope, dict) or set(scope) != {'scope_id', 'unacceptable_failure_probability', 'assumed_failure_probability'}:
            _fail('scope_contract_invalid')
        name = scope['scope_id']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name) or name in seen:
            _fail('scope_identity_invalid')
        seen.add(name)
        if not 0 <= _probability(scope['assumed_failure_probability']) < _probability(scope['unacceptable_failure_probability']) < 1:
            _fail('requires_assumed_rate_below_positive_unacceptable_rate_below_one')
    if 'overall' not in seen:
        _fail('overall_scope_required')
    return plan


def binomial_weights(n, probability):
    """Exact integer binomial weights over one shared denominator; bounded by callers."""
    if type(n) is not int or not 1 <= n <= 500 or not isinstance(probability, Fraction) or not 0 <= probability < 1:
        _fail('invalid_binomial_arguments')
    a, d = probability.numerator, probability.denominator
    b = d - a
    weight, weights = b ** n, []
    for k in range(n + 1):
        weights.append(weight)
        if k < n:
            weight = weight * (n - k) * a // ((k + 1) * b)
    return weights, d ** n


def _ratio(value):
    return {'numerator': str(value.numerator), 'denominator': str(value.denominator), 'decimal': float(value)}


def search_design(bad, assumed, alpha, minimum, maximum):
    """Enumerate n: discrete critical values make a binary search on power invalid."""
    zero = selected = None
    for n in range(1, maximum + 1):
        weights, denominator = binomial_weights(n, bad)
        total, cutoff, accepted_total = 0, -1, 0
        for c, weight in enumerate(weights):
            total += weight
            if total * alpha.denominator > alpha.numerator * denominator:
                break
            cutoff, accepted_total = c, total
        if cutoff < 0:
            continue
        good, good_denominator = binomial_weights(n, assumed)
        probability_numerator = sum(good[:cutoff + 1])
        if zero is None:
            zero_probability = Fraction(good[0], good_denominator)
            zero = {'scenario_count': n, 'maximum_failed_bundles': 0,
                    'qualification_probability_at_assumed_rate': _ratio(zero_probability),
                    'meets_requested_probability': zero_probability >= minimum}
        if probability_numerator * minimum.denominator >= minimum.numerator * good_denominator:
            selected = {'scenario_count': n, 'maximum_failed_bundles': cutoff,
                        'qualification_probability_at_unacceptable_rate': _ratio(Fraction(accepted_total, denominator)),
                        'qualification_probability_at_assumed_rate': _ratio(Fraction(probability_numerator, good_denominator))}
            break
    return selected, zero


def render_review(report):
    rows, zero_rows = [], []
    for scope in report['scopes']:
        selected, zero = scope['design'], scope['zero_failure_reference']
        rows.append((scope['scope_id'], scope['unacceptable_failure_probability'], scope['assumed_failure_probability'],
                     selected['scenario_count'] if selected else None, selected['maximum_failed_bundles'] if selected else None,
                     selected['attempts_per_candidate'] if selected else None, scope['status'].replace('_', ' ')))
        zero_rows.append((scope['scope_id'], zero['scenario_count'] if zero else None,
                          zero['qualification_probability_at_assumed_rate']['decimal'] if zero else None,
                          report['minimum_qualification_probability'],
                          'Yes' if zero and zero['meets_requested_probability'] else 'No' if zero else 'Not available'))
    probabilities = [(s['scope_id'], s['design']['qualification_probability_at_unacceptable_rate']['decimal'],
                      s['design']['qualification_probability_at_assumed_rate']['decimal']) for s in report['scopes'] if s['design']]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Evaluation design planning</title>'
            f'<style>{STYLE}</style></head><body><main><h1>Plan the study before observing outcomes</h1>'
            '<p class="notice">Hypothetical planning, not observed performance, a study approval, or a release gate.</p>'
            f'<p>{escape(report["purpose"])}</p><p>{escape(report["sampling_basis"])}</p>'
            f'<p>Candidate-by-scope family size: {report["family_size"]}. Error allocation per cell: '
            f'{escape(report["cell_error_probability"]["numerator"])}/{escape(report["cell_error_probability"]["denominator"])}. '
            f'Search ceiling: {report["maximum_scenarios_per_scope"]} scenario bundles per scope. '
            'Counts can overlap; they are not a total workload or a guarantee of joint dataset feasibility.</p>'
            '<p>One failed repeat fails a bundle. Repeats do not enlarge the independent sample. '
            'Qualification means only meeting the planned statistical criterion, not approving a system. '
            'Tab to a table and use arrow keys to scroll; Tab leaves it. Displayed decimals are rounded; '
            'report.json retains exact probability fractions and all decision arithmetic uses integers.</p>'
            + table('Smallest per-scope design within the bounded search',
                    ('Scope', 'Unacceptable bundle failure rate', 'Assumed bundle failure rate', 'Bundles',
                     'Maximum failed bundles', 'Attempts per candidate', 'Planning status'), rows, missing_text='Not available')
            + table('Probability of meeting the criterion, not measured outcomes',
                    ('Scope', 'At unacceptable rate', 'At assumed rate'), probabilities, compact_numbers=True)
            + table('Why planning on zero failures alone can be underpowered',
                    ('Scope', 'Zero-failure reference bundles', 'Probability at assumed rate', 'Requested probability', 'Meets request'),
                    zero_rows, missing_text='Not available', compact_numbers=True)
            + '<h2>Assumptions and limits</h2><p>' + escape(BOUNDARY) + '</p></main></body></html>')


def design_payloads(raw, *, plan_sha256):
    plan = validate_plan(raw, plan_sha256)
    family = plan['candidate_count'] * len(plan['scopes'])
    alpha = _probability(plan['family_error_probability']) / family
    minimum = _probability(plan['minimum_qualification_probability'])
    infer = plan['sampling_design'] == 'hypothetical_iid_fixed_horizon'
    rows = []
    for scope in sorted(plan['scopes'], key=lambda s: s['scope_id']):
        selected, zero = search_design(_probability(scope['unacceptable_failure_probability']),
                                      _probability(scope['assumed_failure_probability']), alpha, minimum,
                                      plan['maximum_scenarios_per_scope']) if infer else (None, None)
        if selected:
            selected['attempts_per_candidate'] = selected['scenario_count'] * plan['repeats_per_scenario']
        rows.append({**scope, 'design': selected, 'zero_failure_reference': zero,
                     'status': 'population_design_withheld' if not infer else 'per_scope_design_found' if selected
                               else 'no_design_within_search_limit'})
    report = {'report_version': 'aau-evaluation-design/1.0', 'plan_file_sha256': plan_sha256,
              **{k: plan[k] for k in ('purpose', 'sampling_design', 'sampling_basis', 'candidate_count',
                 'repeats_per_scenario', 'family_error_probability', 'minimum_qualification_probability', 'maximum_scenarios_per_scope')},
              'family_size': family, 'cell_error_probability': _ratio(alpha), 'scopes': rows,
              'status': 'population_design_withheld' if not infer else
                        'per_scope_designs_found' if all(r['design'] for r in rows) else 'design_search_incomplete',
              'decision_status': 'not_assessed', 'boundary': BOUNDARY,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                                       for name in ('eval_design.py', 'agent_bom.py', 'inspect_pack.py', 'intake_review.py',
                                                    'report_html.py', 'authority_html.py')}}
    files = {'plan.json': raw, 'report.json': rendered(report), 'review.html': render_review(report).encode('utf-8')}
    files['manifest.json'] = rendered({'pack_version': 'aau-evaluation-design-pack/1.0',
                                      'files_sha256': {n: digest(b) for n, b in sorted(files.items())}})
    if any(len(b) > MAX_JSON_BYTES for b in files.values()):
        _fail('pack_size_exceeded')
    return report, files


def create_design(raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('refusing_overwrite')
    report, files = design_payloads(raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, contents in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(contents)
    return report


def verify_design(directory, *, plan_sha256):
    files, directories = _capture(directory)
    if 'plan.json' not in files:
        _fail('plan_missing')
    report, expected = design_payloads(files['plan.json'], plan_sha256=plan_sha256)
    if files != expected or directories:
        _fail('pack_does_not_recompute')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau evaluation-design', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('plan', type=Path)
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
            from .eval_design_demo import create_demo
            create_demo(args.out)
            print('Created synthetic study-design examples; assumptions are not measured performance.')
        else:
            report = (create_design(_read_request(args.plan), args.out, plan_sha256=args.plan_sha256)
                      if args.command == 'create' else verify_design(args.directory, plan_sha256=args.plan_sha256))
            print(report['status'] + '; planning diagnostic only, not approval.')
        return 0
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError):
        print('error: evaluation_design_input_or_replay_rejected.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
