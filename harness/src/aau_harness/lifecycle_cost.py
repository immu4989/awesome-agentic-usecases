"""Exact, assumption-bound lifecycle cost scenarios; not a government cost estimate or award decision."""

import argparse
from pathlib import Path
import re
import sys

from .agent_bom import MAX_JSON_BYTES, _parse_json, digest, rendered
from .inspect_pack import InspectionError
from .intake_review import _read_request, _sha


CATEGORIES = ('implementation', 'model_usage', 'infrastructure', 'human_review', 'monitoring',
              'security_privacy_accessibility', 'transition_exit')
DRIVERS = {'one_time': None, 'per_month': 'months', 'per_case': 'cases', 'per_review': 'reviews'}
BOUNDARY = (
    'Offline arithmetic for declared constant-USD scenarios, not a validated lifecycle cost estimate, '
    'invoice, price forecast, value-for-money assessment, funding recommendation, vendor ranking, '
    'procurement decision, GAO conformity finding, or evidence of public savings. Quantities and rates '
    'are supplied assumptions, not inferred from evaluation repeats or production traffic. Human reviews '
    'are declared review events, not unique people, correct resolutions, or measured staffing capacity. '
    'The required categories prompt disclosure but do not prove that all costs are included or disjoint. '
    'Taxes, minimum commitments, tiered prices, discounts, failed attempts, overhead, maintenance, '
    'training, inflation, financing, and transition obligations are included only when explicitly modeled. '
    'Every row is linear in one driver. Nonlinear contracts require a separate model, not an invented '
    'average rate. A zero driver means zero variable charge under this model, not a verified waiver '
    'of contract minimums. Unknown active rates make the total unknown; known subtotals are not full costs. '
    'Exact micro-dollar arithmetic does not establish source precision or reliable forecasts. Scenario '
    'differences are conditional arithmetic, not causal benefit, probabilities, uncertainty intervals, '
    'or a complete sensitivity/risk study. No model calls, provider prices, exchange rates, subprocesses, '
    'uploads, or network requests occur. Protect the expected plan hash independently; pins bind bytes '
    'rather than approval authority or source authenticity. Rate bases and source references are declarations '
    'and are not verified or fetched. Retain plan, rates, report, and the matching trusted implementation. '
    'Commercial assumptions may be procurement-sensitive; this is not sanitization or permission to publish.'
)


def _fail(reason):
    raise InspectionError('lifecycle_cost_' + reason)


def _exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        _fail('fields_invalid')


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value) is not None


def _text(value, maximum=2000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _parse(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        _fail('bytes_invalid_or_oversized')
    return _parse_json(raw)


def _micros(value):
    # Accept decimal strings only: never binary floats, exponent notation, negatives, or hidden rounding.
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]{0,11})(\.[0-9]{1,6})?', value):
        _fail('rate_must_be_nonnegative_decimal_string')
    whole, _, fraction = value.partition('.')
    return int(whole) * 1_000_000 + int(fraction.ljust(6, '0'))


def _usd(micros):
    sign = '-' if micros < 0 else ''
    whole, fraction = divmod(abs(micros), 1_000_000)
    return f'{sign}{whole}.{fraction:06d}'


def validate_plan(raw, expected_sha256):
    if not isinstance(raw, bytes) or not _sha(expected_sha256) or digest(raw) != expected_sha256:
        _fail('plan_byte_pin_mismatch')
    plan = _parse(raw)
    _exact(plan, ('plan_version', 'currency', 'assumptions', 'cost_items', 'scenarios'))
    if plan['plan_version'] != 'aau-lifecycle-cost-plan/1.0' or plan['currency'] != 'USD' or not _text(plan['assumptions']):
        _fail('plan_version_currency_or_assumptions_invalid')
    if not isinstance(plan['cost_items'], list) or not 1 <= len(plan['cost_items']) <= 100:
        _fail('cost_item_count_invalid')
    seen, categories = set(), set()
    for item in plan['cost_items']:
        _exact(item, ('cost_id', 'category', 'driver', 'description'))
        if not _id(item['cost_id']) or item['cost_id'] in seen:
            _fail('cost_id_invalid_or_duplicate')
        if item['category'] not in (*CATEGORIES, 'other') or not isinstance(item['driver'], str) or item['driver'] not in DRIVERS:
            _fail('category_or_driver_invalid')
        if not _text(item['description'], 500):
            _fail('cost_description_required')
        seen.add(item['cost_id'])
        categories.add(item['category'])
    if not set(CATEGORIES) <= categories:
        _fail('required_cost_categories_missing')
    scenarios = plan['scenarios']
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 20:
        _fail('scenario_count_invalid')
    seen = set()
    for scenario in scenarios:
        _exact(scenario, ('scenario_id', 'months', 'cases', 'reviews', 'assumptions'))
        if not _id(scenario['scenario_id']) or scenario['scenario_id'] in seen or not _text(scenario['assumptions']):
            _fail('scenario_identity_or_assumptions_invalid')
        seen.add(scenario['scenario_id'])
        for field, low, high in (('months', 1, 120), ('cases', 0, 10**9), ('reviews', 0, 10**9)):
            if type(scenario[field]) is not int or not low <= scenario[field] <= high:
                _fail('scenario_quantity_invalid')
    return plan


def _rates(raw, plan):
    document = _parse(raw)
    _exact(document, ('format_version', 'currency', 'rates'))
    if document['format_version'] != 'aau-lifecycle-cost-rates/1.0' or document['currency'] != 'USD':
        _fail('rates_version_or_currency_invalid')
    items = {item['cost_id'] for item in plan['cost_items']}
    if not isinstance(document['rates'], list) or len(document['rates']) > len(items):
        _fail('rate_count_invalid')
    result = {}
    for row in document['rates']:
        _exact(row, ('cost_id', 'unit_cost_usd', 'basis', 'source_ref', 'assumptions'))
        if not _id(row['cost_id']) or row['cost_id'] not in items or row['cost_id'] in result:
            _fail('rate_identity_invalid_or_duplicate')
        if not _text(row['source_ref'], 500) or not _text(row['assumptions']):
            _fail('rate_source_and_assumptions_required')
        micros = None if row['unit_cost_usd'] is None else _micros(row['unit_cost_usd'])
        if row['basis'] not in ('estimate', 'quote', 'synthetic', 'unknown') or (micros is not None and row['basis'] == 'unknown'):
            _fail('rate_basis_invalid')
        result[row['cost_id']] = {**row, 'unit_cost_micros': micros}
    return result


def _totals(rows):
    unknown = [row['cost_id'] for row in rows if row['extended_cost_micros'] is None]
    known = sum(row['extended_cost_micros'] for row in rows if row['extended_cost_micros'] is not None)
    return {'known_subtotal_usd': _usd(known), 'declared_total_usd': None if unknown else _usd(known),
            'unknown_active_cost_ids': unknown, 'status': 'declared_costs_incomplete' if unknown else 'declared_costs_computed'}


def review_costs(plan_raw, rates_raw, *, plan_sha256):
    plan = validate_plan(plan_raw, plan_sha256)
    rates = _rates(rates_raw, plan)
    scenarios = []
    for scenario in plan['scenarios']:
        rows = []
        for item in sorted(plan['cost_items'], key=lambda row: row['cost_id']):
            supplied = rates.get(item['cost_id'])
            rate = supplied['unit_cost_micros'] if supplied else None
            driver = DRIVERS[item['driver']]
            quantity = scenario[driver] if driver else 1
            cost = 0 if quantity == 0 else None if rate is None else rate * quantity
            rows.append({**item, 'quantity': quantity, 'unit_cost_usd': _usd(rate) if rate is not None else None,
                         'rate_status': 'missing' if supplied is None else 'unknown' if rate is None else 'supplied',
                         'rate_basis': supplied['basis'] if supplied else 'unknown',
                         'rate_source_ref': supplied['source_ref'] if supplied else None,
                         'rate_assumptions': supplied['assumptions'] if supplied else None,
                         'extended_cost_micros': cost, 'extended_cost_usd': _usd(cost) if cost is not None else None,
                         'zero_quantity_assumption': quantity == 0})
        totals = _totals(rows)
        categories = [{'category': category, **_totals([row for row in rows if row['category'] == category])}
                      for category in (*CATEGORIES, 'other') if any(row['category'] == category for row in rows)]
        scenarios.append({**scenario, **totals, 'categories': categories,
                          'cost_items': [{k: v for k, v in row.items() if k != 'extended_cost_micros'} for row in rows]})
    comparisons = []
    baseline = scenarios[0]
    for candidate in scenarios[1:]:
        changed = [field for field in ('months', 'cases', 'reviews') if candidate[field] != baseline[field]]
        before, after = baseline['declared_total_usd'], candidate['declared_total_usd']
        # Totals can exceed the per-unit rate bound, so parse their already-computed fixed-point spelling directly.
        difference = None if before is None or after is None else _usd(int(after.replace('.', '')) - int(before.replace('.', '')))
        comparisons.append({'baseline_scenario_id': baseline['scenario_id'], 'scenario_id': candidate['scenario_id'],
                            'changed_quantity_drivers': changed,
                            'comparison_kind': 'one_quantity_changed' if len(changed) == 1 else
                                               'multiple_quantities_changed' if changed else 'same_quantities',
                            'declared_total_difference_usd': difference})
    report = {'report_version': 'aau-lifecycle-cost-review/1.0', 'status': 'declared_cost_scenario_diagnostic',
              'plan_file_sha256': plan_sha256, 'rates_file_sha256': digest(rates_raw), 'plan': plan,
              'currency': 'USD', 'arithmetic': 'integer micro-dollars, no rounding; constant supplied rates',
              'scenarios': scenarios, 'comparisons_to_first_scenario': comparisons,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                                        for name in ('lifecycle_cost.py', 'agent_bom.py', 'intake_review.py')},
              'boundary': BOUNDARY}
    if len(rendered(report)) > MAX_JSON_BYTES:
        _fail('report_exceeds_limit')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau lifecycle-cost', description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('rates', type=Path)
    parser.add_argument('--plan-sha256', required=True)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        raw = _read_request(args.plan)
        validate_plan(raw, args.plan_sha256)
        report = review_costs(raw, _read_request(args.rates), plan_sha256=args.plan_sha256)
        if args.verify:
            if _read_request(args.verify) != rendered(report):
                _fail('report_does_not_recompute')
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('xb') as stream:
                stream.write(rendered(report))
        unknown = sum(row['declared_total_usd'] is None for row in report['scenarios'])
        print(f"Lifecycle cost diagnostic: {unknown}/{len(report['scenarios'])} scenario totals unknown. Not budget or award approval.")
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'lifecycle_cost_input_or_output_rejected'
        print(f'error: {reason}; no verified lifecycle cost diagnostic.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
