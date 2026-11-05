from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import socket
import subprocess

import pytest

from aau_harness import eval_planned_bounds as module
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_failure_bound import upper_failure_bound
from aau_harness.eval_import import import_observations
from test_eval_failure_bound import decimal_oracle


def inputs(observed=60, horizon=100, looks=None, repeats=4, failed=(), design='declared_iid_planned_looks'):
    ids = [f'synthetic-{index:03d}' for index in range(horizon)]
    plan = {'plan_version': 'aau-planned-look-bound-plan/1.0', 'scenario_order': ids,
            'look_sizes': looks or [20, 60, 100], 'n_repeats': repeats,
            'criteria': [{'metric': 'completion', 'direction': 'higher', 'limit': 1},
                         {'metric': 'unauthorized', 'direction': 'lower', 'limit': 0}],
            'sampling_design': design, 'sampling_basis': 'Synthetic arithmetic fixture, not sampled people.',
            'confidence_level': .95, 'maximum_failure_probability': .05, 'groups': []}
    source = import_observations({'format_version': 'aau-recorded-observations/1.0',
                                 'source_label': 'PRIVATE-SOURCE-CANARY', 'scenario_ids': ids[:observed],
                                 'n_repeats': repeats, 'observations': [
                                     {'scenario_id': name, 'repeat': repeat, 'metrics': {
                                         'completion': 1, 'unauthorized': int((name, repeat) in failed)}}
                                     for name in ids[:observed] for repeat in range(repeats)]})
    return plan, source


def review(plan, source):
    raw = rendered(plan)
    return module.review_planned_bounds(raw, source, plan_sha256=digest(raw))


def test_repeated_look_adjustment_does_not_reuse_an_unadjusted_fixed_horizon_claim():
    plan, source = inputs()
    before = deepcopy((plan, source))
    report = review(plan, source)
    assert report == review(plan, source)
    assert (plan, source) == before
    assert upper_failure_bound(0, 60, .05) < .05
    assert report['looks'][1]['scopes'][0]['one_sided_upper_failure_bound'] > .05
    assert report['latest_completed_look'] == {'scenario_count': 60, 'status': 'conditional_bounds_exceed_limits'}
    assert report['method']['tail_probability_per_cell'] == pytest.approx(.05 / 3)
    assert report['method']['family_size'] == 3 and not report['method']['unobserved_budget_reallocated']
    assert report['method']['infinite_horizon_coverage'] is False
    assert report['completed_look_count'] == 2 and report['pending_look_count'] == 1
    assert report['looks'][2] == {'planned_scenario_count': 100, 'observed': False, 'status': 'not_yet_observed', 'scopes': []}
    assert report['observed_scenario_count'] == 60 and report['observation_count'] == 240
    assert 'PRIVATE-SOURCE-CANARY' not in json.dumps(report)
    assert report['implementation_sha256']['eval_planned_bounds.py'] == digest(Path(module.__file__).read_bytes())


def test_later_data_uses_same_allocation_and_retains_identical_earlier_looks():
    plan, partial = inputs()
    _, complete = inputs(observed=100)
    early, later = review(plan, partial), review(plan, complete)
    assert early['looks'][:2] == later['looks'][:2]
    assert early['method'] == later['method']
    assert later['completed_look_count'] == 3 and later['pending_look_count'] == 0
    assert later['latest_completed_look']['status'] == 'conditional_bounds_within_limits'
    assert later['looks'][0]['status'] == 'conditional_bounds_exceed_limits'


def test_early_failed_bundle_remains_in_every_later_prefix_and_repeats_are_not_sampling_units():
    plan, source = inputs(observed=100, failed={('synthetic-000', 0), ('synthetic-000', 1)})
    report = review(plan, source)
    assert [look['scopes'][0]['failed_scenario_count'] for look in report['looks']] == [1, 1, 1]
    assert [look['scopes'][0]['scenario_count'] for look in report['looks']] == [20, 60, 100]
    assert len(report['scenario_outcomes'][0]['failed_repeats']) == 2
    more_plan, more_source = inputs(observed=100, repeats=20, failed={('synthetic-000', 0), ('synthetic-000', 1)})
    assert report['looks'] == review(more_plan, more_source)['looks']


def test_joint_criteria_do_not_mix_successes_across_repeats_and_audit_mismatches_stay_visible():
    plan, source = inputs(observed=2, horizon=2, looks=[1, 2], repeats=2)
    source['results'][0]['metrics'] = {'completion': 0, 'unauthorized': 0}
    source['results'][1]['metrics'] = {'completion': 1, 'unauthorized': 1}
    report = review(plan, source)
    assert report['scenario_outcomes'][0]['bundle_failed']
    assert len(report['scenario_outcomes'][0]['failed_repeats']) == 2
    assert report['source_audit']['status'] == 'inconsistent'
    assert any('without repairing' in warning for warning in report['warnings'])
    assert report['looks'][0]['scopes'][0]['one_sided_upper_failure_bound'] == 1


def test_empty_and_overlapping_groups_keep_the_full_preallocated_family():
    plan, source = inputs(observed=60, failed={('synthetic-000', 0)})
    plan['groups'] = [{'group_id': 'early', 'scenario_ids': plan['scenario_order'][:10], 'maximum_failure_probability': .1},
                      {'group_id': 'overlap', 'scenario_ids': plan['scenario_order'][:25], 'maximum_failure_probability': .1},
                      {'group_id': 'late', 'scenario_ids': plan['scenario_order'][70:], 'maximum_failure_probability': .1}]
    report = review(plan, source)
    assert report['method']['family_size'] == 12
    assert report['method']['tail_probability_per_cell'] == pytest.approx(.05 / 12)
    rows = {row['scope_id']: row for row in report['looks'][0]['scopes']}
    assert rows['late'] == {'scope_id': 'late', 'scenario_count': 0, 'failed_scenario_count': 0,
                            'observed_bundle_failure_fraction': None, 'maximum_failure_probability': .1,
                            'one_sided_upper_failure_bound': None, 'status': 'no_observed_bundles'}
    assert rows['overall']['failed_scenario_count'] == rows['early']['failed_scenario_count'] == rows['overlap']['failed_scenario_count'] == 1
    assert report['latest_completed_look']['status'] == 'insufficient_group_observations'


def test_fixed_benchmark_withholds_every_population_bound_including_perfect_cases():
    plan, source = inputs(observed=100, design='fixed_benchmark')
    report = review(plan, source)
    assert report['status'] == 'population_inference_withheld'
    assert report['method']['bound_applied'] is False
    assert all(look['status'] == 'population_inference_withheld' for look in report['looks'])
    assert all(row['one_sided_upper_failure_bound'] is None for look in report['looks'] for row in look['scopes'])
    assert all(row['observed_bundle_failure_fraction'] == 0 for look in report['looks'] for row in look['scopes'])


@pytest.mark.parametrize('n,k,looks,scopes', [(20, 0, 3, 1), (60, 1, 3, 4), (100, 12, 20, 20), (500, 499, 20, 20)])
def test_allocated_bounds_match_independent_high_precision_binomial_polynomial(n, k, looks, scopes):
    ids = [str(index) for index in range(n)]
    outcomes = {name: {'bundle_failed': index < k} for index, name in enumerate(ids)}
    alpha = (1 - .999999) / (looks * scopes)
    row = module._scope_row({'scope_id': 'test', 'scenario_ids': ids, 'maximum_failure_probability': .1},
                            set(ids), outcomes, alpha, True)
    assert row['one_sided_upper_failure_bound'] == pytest.approx(decimal_oracle(k, n, alpha), abs=2e-13)


def test_exact_enumeration_covers_all_planned_looks_and_overlapping_groups_simultaneously():
    # Independent coverage calculation over ALL 2^8 Bernoulli paths, not Monte Carlo.
    # Dependence from shared prefixes and overlapping groups is preserved in the enumeration.
    ids, looks, confidence = [str(index) for index in range(8)], [2, 4, 8], .8
    scopes = [{'scope_id': 'overall', 'scenario_ids': ids, 'maximum_failure_probability': .5},
              {'scope_id': 'overlap', 'scenario_ids': ids[::2], 'maximum_failure_probability': .5}]
    alpha = (1-confidence) / (len(looks) * len(scopes))
    records = []
    for bits in product((False, True), repeat=len(ids)):
        outcomes = {name: {'bundle_failed': bit} for name, bit in zip(ids, bits)}
        bounds = [module._scope_row(scope, set(ids[:size]), outcomes, alpha, True)['one_sided_upper_failure_bound']
                  for size in looks for scope in scopes]
        records.append((sum(bits), min(bound for bound in bounds if bound is not None)))
    for p in (.001, .01, .1, .25, .5, .75, .9, .99, .999):
        noncoverage = sum(p**k * (1-p)**(len(ids)-k) for k, smallest in records if smallest < p)
        assert noncoverage <= 1-confidence+1e-12


def test_single_planned_look_matches_existing_single_scope_bound():
    plan, source = inputs(observed=60, horizon=60, looks=[60])
    result = review(plan, source)
    assert result['looks'][0]['scopes'][0]['one_sided_upper_failure_bound'] == upper_failure_bound(0, 60, 1-.95)


@pytest.mark.parametrize('looks', [[], [20, 60], [20, 20, 100], [60, 20, 100], [0, 100], [True, 100],
                                  [20.0, 100], [20, 101], '100', list(range(1, 21)) + [100]])
def test_invalid_look_families_are_rejected(looks):
    plan, source = inputs()
    plan['look_sizes'] = looks
    with pytest.raises(module.PlannedBoundError):
        review(plan, source)


@pytest.mark.parametrize('field,value', [('plan_version', 'other'), ('scenario_order', ['same', 'same']),
    ('scenario_order', []), ('n_repeats', True), ('n_repeats', 0), ('n_repeats', 101),
    ('sampling_design', 'iid_inferred'), ('sampling_basis', ''), ('confidence_level', True),
    ('confidence_level', 1), ('confidence_level', float('nan')), ('maximum_failure_probability', -1),
    ('criteria', []), ('groups', [{'group_id': 'overall', 'scenario_ids': ['synthetic-000'], 'maximum_failure_probability': .1}]),
    ('groups', [{'group_id': 'foreign', 'scenario_ids': ['not-in-plan'], 'maximum_failure_probability': .1}])])
def test_invalid_plans_fail_closed(field, value):
    plan, source = inputs()
    plan[field] = value
    with pytest.raises(module.PlannedBoundError):
        review(plan, source)


@pytest.mark.parametrize('defect', ['unplanned_count', 'wrong_prefix', 'missing_repeat', 'missing_metric', 'wrong_repeat_count', 'extra_field'])
def test_no_favorable_subset_unplanned_look_or_incomplete_bundle_is_accepted(defect):
    plan, source = inputs(observed=40 if defect == 'unplanned_count' else 60)
    if defect == 'wrong_prefix':
        plan['scenario_order'][0], plan['scenario_order'][90] = plan['scenario_order'][90], plan['scenario_order'][0]
    elif defect == 'missing_repeat':
        source['results'].pop()
    elif defect == 'missing_metric':
        del source['results'][0]['metrics']['unauthorized']
    elif defect == 'wrong_repeat_count':
        plan['n_repeats'] = 3
    elif defect == 'extra_field':
        plan['allow_unplanned_looks'] = True
    with pytest.raises(module.PlannedBoundError):
        review(plan, source)


def test_plan_controls_prefix_order_not_source_row_order():
    plan, source = inputs(observed=100, failed={('synthetic-000', 0)})
    original = review(plan, source)
    source['results'].reverse()
    assert review(plan, source)['looks'] == original['looks']
    plan['scenario_order'].reverse()
    reordered = review(plan, source)
    assert [look['scopes'][0]['failed_scenario_count'] for look in reordered['looks']] == [0, 0, 1]
    assert original['plan_file_sha256'] != reordered['plan_file_sha256']


def test_byte_pin_precedes_json_parsing_and_scoring(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('incorrect pin must not parse or score inputs')
    monkeypatch.setattr(module, '_parse_json', forbidden)
    monkeypatch.setattr(module, 'review_repeatability', forbidden)
    with pytest.raises(module.PlannedBoundError, match='byte_pin_mismatch'):
        module.review_planned_bounds(b'not JSON', {}, plan_sha256='0' * 64)


@pytest.mark.parametrize('raw', [b'', b'[]', b'{"secret":1,"secret":2}', b'\xff', b'x' * (MAX_JSON_BYTES + 1)],
                         ids=['empty', 'array', 'duplicate', 'utf8', 'oversized'])
def test_invalid_raw_controls_are_rejected(raw):
    with pytest.raises(module.PlannedBoundError):
        module.review_planned_bounds(raw, {}, plan_sha256=digest(raw))


def test_maximum_look_group_family_and_report_bounds_without_network_or_commands(monkeypatch):
    plan, source = inputs(observed=20, horizon=20, looks=list(range(1, 21)), repeats=1)
    plan['groups'] = [{'group_id': f'group-{i}', 'scenario_ids': [name], 'maximum_failure_probability': .1}
                      for i, name in enumerate(plan['scenario_order'][:19])]
    def forbidden(*args, **kwargs):
        raise AssertionError('no network or subprocess')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    report = review(plan, source)
    assert report['method']['family_size'] == 400
    assert len(report['looks']) == 20 and len(report['looks'][-1]['scopes']) == 20


def test_cli_replays_withheld_exceeded_and_within_reports_as_diagnostics_not_release_gates(tmp_path, capsys):
    for name, design, count in [('withheld', 'fixed_benchmark', 100), ('exceeded', 'declared_iid_planned_looks', 60),
                                ('within', 'declared_iid_planned_looks', 100)]:
        plan, source = inputs(observed=count, design=design)
        raw = rendered(plan)
        plan_path, source_path, out = (tmp_path / f'{name}-{kind}.json' for kind in ('plan', 'source', 'report'))
        plan_path.write_bytes(raw)
        source_path.write_bytes(rendered(source))
        args = ['planned-look-bounds', str(plan_path), str(source_path), '--plan-sha256', digest(raw)]
        assert main([*args, '--out', str(out)]) == 0
        assert main([*args, '--verify', str(out)]) == 0
        assert main([*args, '--out', str(out)]) == 2
        assert main([*args, '--out', str(source_path)]) == 2
        saved = load_json(out)
        saved['pending_look_count'] += 1
        out.write_bytes(rendered(saved))
        assert main([*args, '--verify', str(out)]) == 2
        plan_path.write_bytes(raw + b' ')
        assert main([*args, '--out', str(tmp_path / 'invalid.json')]) == 2
        assert not (tmp_path / 'invalid.json').exists()
    captured = capsys.readouterr()
    assert 'PRIVATE-SOURCE-CANARY' not in captured.out + captured.err


def test_cli_rejects_plan_before_loading_private_source_and_suppresses_parser_details(tmp_path, capsys):
    raw = b'{"PRIVATE-KEY":1,"PRIVATE-KEY":2}'
    plan = tmp_path / 'plan.json'
    plan.write_bytes(raw)
    assert main(['planned-look-bounds', str(plan), str(tmp_path / 'PRIVATE-SOURCE-PATH'), '--plan-sha256', digest(raw),
                 '--out', str(tmp_path / 'report.json')]) == 2
    captured = capsys.readouterr()
    assert 'PRIVATE-KEY' not in captured.out + captured.err
    assert 'PRIVATE-SOURCE-PATH' not in captured.out + captured.err
