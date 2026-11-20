from copy import deepcopy
from decimal import Decimal
from itertools import product
import socket
import subprocess

import pytest

from aau_harness import lifecycle_cost as module
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.lifecycle_demo import example_inputs


@pytest.fixture
def inputs():
    plan, variants = example_inputs()
    return plan, variants['complete']


def review(inputs):
    plan, rates = inputs
    raw = rendered(plan)
    return module.review_costs(raw, rendered(rates), plan_sha256=digest(raw))


def test_complete_example_retains_full_cost_and_exact_differences(inputs):
    result = review(inputs)
    assert result == review(inputs)
    assert [row['declared_total_usd'] for row in result['scenarios']] == [
        '368000.000000', '638000.000000', '914000.000000', '353000.000000']
    expected = result['scenarios'][0]
    assert next(r for r in expected['categories'] if r['category'] == 'model_usage')['declared_total_usd'] == '3000.000000'
    assert next(r for r in expected['categories'] if r['category'] == 'human_review')['declared_total_usd'] == '270000.000000'
    assert [row['declared_total_difference_usd'] for row in result['comparisons_to_first_scenario']] == [
        '270000.000000', '546000.000000', '-15000.000000']
    assert [row['comparison_kind'] for row in result['comparisons_to_first_scenario']] == [
        'one_quantity_changed', 'multiple_quantities_changed', 'one_quantity_changed']
    assert result['comparisons_to_first_scenario'][0]['changed_quantity_drivers'] == ['reviews']


def test_missing_exit_does_not_become_a_complete_total():
    plan, variants = example_inputs()
    result = review((plan, variants['unknown-exit']))
    expected = result['scenarios'][0]
    assert expected['known_subtotal_usd'] == '353000.000000'
    assert expected['declared_total_usd'] is None
    assert expected['unknown_active_cost_ids'] == ['exit']
    assert all(row['declared_total_difference_usd'] is None for row in result['comparisons_to_first_scenario'])
    assert next(row for row in expected['cost_items'] if row['cost_id'] == 'exit')['rate_status'] == 'unknown'


def test_no_rates_keeps_all_active_unknowns():
    plan, variants = example_inputs()
    result = review((plan, variants['no-rates']))
    for scenario in result['scenarios']:
        assert scenario['known_subtotal_usd'] == '0.000000'
        assert scenario['declared_total_usd'] is None
        assert len(scenario['unknown_active_cost_ids']) == 7
        assert all(row['rate_status'] == 'missing' for row in scenario['cost_items'])


def test_zero_driver_is_zero_extended_charge_but_never_a_known_rate(inputs):
    plan, rates = inputs
    plan['scenarios'] = [{**plan['scenarios'][0], 'cases': 0, 'reviews': 0}]
    rates['rates'] = [row for row in rates['rates'] if row['cost_id'] not in ('model', 'review')]
    result = review(inputs)['scenarios'][0]
    assert result['declared_total_usd'] == '95000.000000'
    for row in result['cost_items']:
        if row['cost_id'] in ('model', 'review'):
            assert row['unit_cost_usd'] is None
            assert row['extended_cost_usd'] == '0.000000'
            assert row['zero_quantity_assumption'] and row['rate_status'] == 'missing'
    plan['scenarios'][0]['reviews'] = 1
    assert review(inputs)['scenarios'][0]['unknown_active_cost_ids'] == ['review']


def test_decimal_arithmetic_matches_independent_oracle(inputs):
    plan, rates = inputs
    plan['scenarios'] = [plan['scenarios'][0]]
    for row, rate in zip(rates['rates'], ('0.1', '0.000001', '1.234567', '0.2', '0', '99.999999', '9.01')):
        row['unit_cost_usd'] = rate
    mapping = {row['cost_id']: Decimal(row['unit_cost_usd']) for row in rates['rates']}
    for months, cases, reviews in product((1, 12, 120), (0, 1, 999), (0, 2, 117)):
        scenario = plan['scenarios'][0]
        scenario.update(months=months, cases=cases, reviews=reviews)
        quantities = {'one_time': 1, 'per_month': months, 'per_case': cases, 'per_review': reviews}
        expected = sum(mapping[row['cost_id']] * quantities[row['driver']] for row in plan['cost_items'])
        actual = review(inputs)['scenarios'][0]
        assert Decimal(actual['declared_total_usd']) == expected
        assert sum(Decimal(row['declared_total_usd']) for row in actual['categories']) == expected


@pytest.mark.parametrize('rate', ['0', '0.000001', '999999999999.999999'])
def test_extreme_valid_rates_do_not_overflow_or_round(inputs, rate):
    for row in inputs[1]['rates']:
        row['unit_cost_usd'] = rate
    inputs[0]['scenarios'][0].update(months=120, cases=10**9, reviews=10**9)
    total = review(inputs)['scenarios'][0]['declared_total_usd']
    assert Decimal(total) == Decimal(rate) * (2 + 3 * 120 + 2 * 10**9)


@pytest.mark.parametrize('rate', [0, 0.1, True, '-1', 'NaN', 'Infinity', '1e3', '.1', '01', '1.', ' 1',
                                 '1.0000001', '1000000000000', [], {}])
def test_ambiguous_or_invalid_money_is_rejected(inputs, rate):
    inputs[1]['rates'][0]['unit_cost_usd'] = rate
    with pytest.raises(ValueError):
        review(inputs)


@pytest.mark.parametrize('defect', ['version', 'currency', 'assumptions', 'empty_items', 'missing_category', 'duplicate_item',
                                   'unknown_category', 'unknown_driver', 'bad_id', 'description', 'duplicate_scenario',
                                   'empty_scenarios', 'extra_field', 'scenario_extra', 'too_many_items', 'too_many_scenarios'])
def test_plan_defects_rejected(inputs, defect):
    plan = inputs[0]
    if defect == 'version':
        plan['plan_version'] = 'future'
    elif defect == 'currency':
        plan['currency'] = 'EUR'
    elif defect == 'assumptions':
        plan['assumptions'] = ''
    elif defect == 'empty_items':
        plan['cost_items'] = []
    elif defect == 'missing_category':
        plan['cost_items'].pop()
    elif defect == 'duplicate_item':
        plan['cost_items'].append(deepcopy(plan['cost_items'][0]))
    elif defect == 'unknown_category':
        plan['cost_items'][0]['category'] = 'unclassified'
    elif defect == 'unknown_driver':
        plan['cost_items'][0]['driver'] = 'per_year'
    elif defect == 'bad_id':
        plan['cost_items'][0]['cost_id'] = '../escape'
    elif defect == 'description':
        plan['cost_items'][0]['description'] = ' '
    elif defect == 'duplicate_scenario':
        plan['scenarios'][1]['scenario_id'] = plan['scenarios'][0]['scenario_id']
    elif defect == 'empty_scenarios':
        plan['scenarios'] = []
    elif defect == 'extra_field':
        plan['approval'] = True
    elif defect == 'scenario_extra':
        plan['scenarios'][0]['approved'] = True
    elif defect == 'too_many_items':
        plan['cost_items'] *= 15
    else:
        plan['scenarios'] *= 6
    with pytest.raises(ValueError):
        review(inputs)


@pytest.mark.parametrize('field,value', [('months', 0), ('months', 121), ('months', True), ('months', 1.5),
                                       ('cases', -1), ('reviews', -1), ('cases', 10**9 + 1),
                                       ('reviews', '10'), ('cases', None), ('reviews', 1.0)])
def test_quantities_are_explicit_bounded_integers(inputs, field, value):
    inputs[0]['scenarios'][0][field] = value
    with pytest.raises(ValueError):
        review(inputs)


@pytest.mark.parametrize('defect', ['version', 'currency', 'duplicate', 'unplanned', 'extra', 'basis', 'unknown_basis', 'source', 'assumptions'])
def test_rate_evidence_defects_rejected(inputs, defect):
    rates = inputs[1]
    row = rates['rates'][0]
    if defect == 'version':
        rates['format_version'] = 'future'
    elif defect == 'currency':
        rates['currency'] = 'EUR'
    elif defect == 'duplicate':
        rates['rates'][1] = deepcopy(row)
    elif defect == 'unplanned':
        row['cost_id'] = 'unknown'
    elif defect == 'extra':
        row['approved'] = True
    elif defect == 'basis':
        row['basis'] = 'verified'
    elif defect == 'unknown_basis':
        row['basis'] = 'unknown'
    elif defect == 'source':
        row['source_ref'] = ''
    else:
        row['assumptions'] = ''
    with pytest.raises(ValueError):
        review(inputs)


def test_multiple_items_in_category_and_same_quantities_are_retained(inputs):
    plan, rates = inputs
    plan['cost_items'].append({'cost_id': 'training', 'category': 'implementation', 'driver': 'one_time', 'description': 'Training'})
    rates['rates'].append({'cost_id': 'training', 'unit_cost_usd': '7.12', 'basis': 'estimate',
                           'source_ref': 'declared-assumption', 'assumptions': 'Synthetic test value, not a validated estimate.'})
    plan['scenarios'] = [plan['scenarios'][0], {**plan['scenarios'][0], 'scenario_id': 'same'}]
    result = review(inputs)
    assert result['scenarios'][0]['declared_total_usd'] == '368007.120000'
    assert result['scenarios'][0]['categories'][0]['declared_total_usd'] == '50007.120000'
    assert result['comparisons_to_first_scenario'][0]['comparison_kind'] == 'same_quantities'
    assert result['comparisons_to_first_scenario'][0]['declared_total_difference_usd'] == '0.000000'


def test_cli_pin_output_refusal_and_exact_replay(inputs, tmp_path):
    plan, rates = inputs
    raw = rendered(plan) + b' \n'
    (tmp_path / 'plan.json').write_bytes(raw)
    (tmp_path / 'rates.json').write_bytes(rendered(rates))
    base = ['lifecycle-cost', str(tmp_path / 'plan.json'), str(tmp_path / 'rates.json'), '--plan-sha256', digest(raw)]
    output = tmp_path / 'report.json'
    assert main([*base, '--out', str(output)]) == 0
    original = output.read_bytes()
    assert main([*base, '--out', str(output)]) == 2
    assert output.read_bytes() == original
    assert main([*base, '--verify', str(output)]) == 0
    output.write_bytes(original + b' ')
    assert main([*base, '--verify', str(output)]) == 2
    assert main([*base[:-1], '0' * 64, '--verify', str(output)]) == 2
    output.write_bytes(original)
    rates['rates'].pop()
    (tmp_path / 'rates.json').write_bytes(rendered(rates))
    assert main([*base, '--verify', str(output)]) == 2
    assert main([*base, '--out', str(tmp_path / 'incomplete.json')]) == 0
    assert load_json(tmp_path / 'incomplete.json')['scenarios'][0]['declared_total_usd'] is None


def test_plan_pin_checked_before_rate_read(inputs, monkeypatch, tmp_path):
    calls = []
    def read(path):
        calls.append(path.name)
        assert path.name == 'plan.json'
        return rendered(inputs[0])
    monkeypatch.setattr(module, '_read_request', read)
    assert main(['lifecycle-cost', 'plan.json', 'rates.json', '--plan-sha256', '0' * 64,
                 '--out', str(tmp_path / 'report.json')]) == 2
    assert calls == ['plan.json']


@pytest.mark.parametrize('raw', [b'NaN', b'{"a":1,"a":2}', b'\xff', b'{}', b' ' * (MAX_JSON_BYTES + 1)])
def test_malformed_and_oversized_rates_rejected(inputs, raw):
    plan_raw = rendered(inputs[0])
    with pytest.raises(ValueError):
        module.review_costs(plan_raw, raw, plan_sha256=digest(plan_raw))


def test_offline_execution_and_inputs_unchanged(inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution from offline diagnostic')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    original = deepcopy(inputs)
    review(inputs)
    assert inputs == original


def test_composed_report_size_is_bounded_before_output(inputs, tmp_path):
    plan, rates = inputs
    for index in range(93):
        plan['cost_items'].append({'cost_id': f'other-{index}', 'category': 'other', 'driver': 'one_time', 'description': 'Explicit extra line'})
        rates['rates'].append({'cost_id': f'other-{index}', 'unit_cost_usd': '1', 'basis': 'synthetic',
                              'source_ref': 'constructed', 'assumptions': 'x' * 2000})
    plan['scenarios'] = [{**plan['scenarios'][0], 'scenario_id': f'scenario-{i}'} for i in range(20)]
    raw = rendered(plan)
    assert len(raw) < MAX_JSON_BYTES and len(rendered(rates)) < MAX_JSON_BYTES
    (tmp_path / 'plan.json').write_bytes(raw)
    (tmp_path / 'rates.json').write_bytes(rendered(rates))
    output = tmp_path / 'report.json'
    assert main(['lifecycle-cost', str(tmp_path / 'plan.json'), str(tmp_path / 'rates.json'),
                 '--plan-sha256', digest(raw), '--out', str(output)]) == 2
    assert not output.exists()


def test_source_and_output_symlinks_are_not_followed(inputs, tmp_path):
    raw = rendered(inputs[0])
    plan = tmp_path / 'plan.json'
    rates = tmp_path / 'rates.json'
    plan.write_bytes(raw)
    rates.write_bytes(rendered(inputs[1]))
    link = tmp_path / 'linked.json'
    link.symlink_to(rates)
    output = tmp_path / 'report.json'
    assert main(['lifecycle-cost', str(plan), str(link), '--plan-sha256', digest(raw), '--out', str(output)]) == 2
    assert not output.exists()
    original = rates.read_bytes()
    assert main(['lifecycle-cost', str(plan), str(rates), '--plan-sha256', digest(raw), '--out', str(link)]) == 2
    assert rates.read_bytes() == original


def test_packaged_demo_replays_every_variant(tmp_path):
    folder = tmp_path / 'demo'
    assert main(['lifecycle-cost-demo', '--out', str(folder)]) == 0
    assert main(['lifecycle-cost-demo', '--out', str(folder)]) == 2
    assert len(list(folder.iterdir())) == 8
    raw = (folder / 'plan.json').read_bytes()
    for name in ('complete', 'unknown-exit', 'no-rates'):
        report = module.review_costs(raw, (folder / f'{name}-rates.json').read_bytes(), plan_sha256=digest(raw))
        assert load_json(folder / f'{name}-report.json') == report
        assert str(tmp_path) not in rendered(report).decode()
