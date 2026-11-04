from copy import deepcopy
from decimal import Decimal, localcontext
import importlib.util
import json
import math
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest
from aau_harness.catalog_cli import main
from aau_harness.eval_failure_bound import review_failure_bounds, upper_failure_bound, zero_failure_plan
from aau_harness.runner import ScenarioResult, run_eval


def inputs(count=20, repeats=4, failed=(), design='declared_iid_fixed_horizon'):
    ids = [f'synthetic-{i:03d}' for i in range(count)]
    plan = {'plan_version': 'aau-failure-bound-plan/1.0', 'scenario_ids': ids, 'n_repeats': repeats,
            'criteria': [{'metric': 'completion', 'direction': 'higher', 'limit': 1},
                         {'metric': 'unauthorized', 'direction': 'lower', 'limit': 0}],
            'sampling_design': design, 'sampling_basis': 'Synthetic arithmetic example, not collected IID evidence.',
            'confidence_level': .95, 'maximum_failure_probability': .05, 'groups': []}
    source = run_eval(ids, lambda scenario, repeat: ScenarioResult(
        scenario, repeat, {'completion': 1, 'unauthorized': int((scenario, repeat) in failed)},
        0, .1, 0), repeats=repeats).as_dict()
    return plan, source


def test_zero_failures_does_not_mean_zero_risk_or_80_independent_units():
    report = review_failure_bounds(*inputs())
    row = report['scopes'][0]
    assert report['scenario_count'] == 20 and report['observation_count'] == 80
    assert row['failed_scenario_count'] == 0
    assert row['one_sided_upper_failure_bound'] == pytest.approx(.1391083406682652)
    assert row['zero_failure_planning']['minimum_scenarios'] == 59
    assert report['status'] == 'conditional_bounds_exceed_limits'
    many_repeats = review_failure_bounds(*inputs(repeats=100))
    assert many_repeats['observation_count'] == 2000
    assert many_repeats['scopes'] == report['scopes']


def test_more_distinct_scenarios_can_meet_only_a_conditional_limit():
    report = review_failure_bounds(*inputs(count=60))
    assert report['status'] == 'conditional_bounds_within_limits'
    assert report['scopes'][0]['one_sided_upper_failure_bound'] == pytest.approx(.04870291331009749)
    assert 'supplied, not verified' in report['boundary']


def test_fixed_benchmark_withholds_population_bounds_even_for_many_perfect_runs():
    report = review_failure_bounds(*inputs(count=60, design='fixed_benchmark'))
    assert report['status'] == 'population_inference_withheld'
    assert not report['method']['bound_applied']
    assert report['scopes'][0]['one_sided_upper_failure_bound'] is None
    assert report['scopes'][0]['observed_bundle_failure_fraction'] == 0
    assert report['scopes'][0]['zero_failure_planning']['minimum_scenarios'] == 59


def test_one_early_failure_cannot_be_erased_by_later_passing_repeats():
    report = review_failure_bounds(*inputs(count=60, failed={('synthetic-000', 0)}))
    assert report['scopes'][0]['failed_scenario_count'] == 1
    assert report['scopes'][0]['one_sided_upper_failure_bound'] > .05
    assert report['scenario_outcomes'][0] == {'scenario_id': 'synthetic-000', 'bundle_failed': True,
                                            'failed_repeats': [{'repeat': 0, 'failed_criteria': [{'metric': 'unauthorized', 'value': 1}]}]}
    more = review_failure_bounds(*inputs(count=60, failed={('synthetic-000', i) for i in range(4)}))
    assert more['scopes'] == report['scopes']  # Four failures in one bundle are not four IID units.


def test_joint_criteria_cannot_be_combined_across_repeats():
    plan, source = inputs(count=1, repeats=2)
    source['results'][0]['metrics'] = {'completion': 0, 'unauthorized': 0}
    source['results'][1]['metrics'] = {'completion': 1, 'unauthorized': 1}
    report = review_failure_bounds(plan, source)
    assert report['scopes'][0]['one_sided_upper_failure_bound'] == 1
    assert len(report['scenario_outcomes'][0]['failed_repeats']) == 2
    assert report['source_audit']['status'] == 'inconsistent'


def test_groups_use_family_adjustment_and_do_not_hide_behind_overall_results():
    plan, source = inputs(count=100)
    plan['groups'] = [{'group_id': 'assisted-channel', 'scenario_ids': plan['scenario_ids'][:10],
                       'maximum_failure_probability': .05}]
    report = review_failure_bounds(plan, source)
    assert report['method']['family_size'] == 2
    assert report['method']['tail_probability_per_scope'] == pytest.approx(.025)
    overall, group = report['scopes']
    assert overall['status'] == 'conditional_bound_within_limit'
    assert group['status'] == 'conditional_bound_exceeds_limit'
    assert report['status'] == 'conditional_bounds_exceed_limits'
    assert group['zero_failure_planning']['minimum_scenarios'] == 72
    assert overall['one_sided_upper_failure_bound'] > upper_failure_bound(0, 100, .05)


def test_overlapping_scopes_count_each_bundle_once_within_each_scope():
    plan, source = inputs(count=4, failed={('synthetic-001', 0)})
    plan['groups'] = [{'group_id': name, 'scenario_ids': ids, 'maximum_failure_probability': .5}
                      for name, ids in [('a', plan['scenario_ids'][:2]), ('b', plan['scenario_ids'][1:])]]
    report = review_failure_bounds(plan, source)
    assert report['method']['family_size'] == 3
    assert [row['scenario_count'] for row in report['scopes']] == [4, 2, 3]
    assert [row['failed_scenario_count'] for row in report['scopes']] == [1, 1, 1]


def decimal_oracle(k, n, alpha):
    # Independent test implementation: direct polynomial, integer combinations,
    # 70-digit Decimal arithmetic, not the production log-gamma/log-sum algorithm.
    with localcontext() as context:
        context.prec = 70
        if k == n:
            return 1.0
        low, high, target = Decimal(0), Decimal(1), Decimal(str(alpha))
        for _ in range(180):
            p = (low + high) / 2
            cdf = sum(Decimal(math.comb(n, i)) * p**i * (1-p)**(n-i) for i in range(k+1))
            if cdf > target:
                low = p
            else:
                high = p
        return float(high)


@pytest.mark.parametrize('n,k,alpha', [(1, 0, .05), (20, 0, .05), (20, 1, .05), (20, 10, .05),
                                     (20, 19, .05), (20, 20, .05), (50, 3, .0025), (500, 2, 1e-6),
                                     (500, 250, .05), (500, 499, 5e-8)])
def test_bounds_match_independent_high_precision_binomial_oracle(n, k, alpha):
    assert upper_failure_bound(k, n, alpha) == pytest.approx(decimal_oracle(k, n, alpha), abs=2e-13)


def test_small_binomial_coverage_is_conservative_on_probability_grid():
    for n in range(1, 13):
        for alpha in (.05, .025):
            bounds = [upper_failure_bound(k, n, alpha) for k in range(n+1)]
            assert bounds == sorted(bounds)
            for p in (.001, .01, .1, .25, .5, .75, .9, .99, .999):
                coverage = sum(math.comb(n, k) * p**k * (1-p)**(n-k) for k in range(n+1) if p <= bounds[k])
                assert coverage >= 1-alpha-1e-12


@pytest.mark.parametrize('limit,alpha,expected', [(.05, .05, 59), (.01, .05, 299), (.05, .025, 72), (.5, .5, 1)])
def test_zero_failure_fixed_horizon_planning_is_minimal(limit, alpha, expected):
    assert zero_failure_plan(limit, alpha)['minimum_scenarios'] == expected
    assert -math.expm1(math.log(alpha) / expected) <= limit
    if expected > 1:
        assert -math.expm1(math.log(alpha) / (expected-1)) > limit


def test_zero_risk_target_and_extreme_planning_sizes_are_not_fabricated():
    assert zero_failure_plan(0, .05) == {'status': 'no_finite_zero_failure_sample', 'minimum_scenarios': None}
    assert zero_failure_plan(5e-324, .05) == {'status': 'exceeds_planning_range', 'minimum_scenarios': None}
    plan, source = inputs(count=1)
    plan['maximum_failure_probability'] = 0
    report = review_failure_bounds(plan, source)
    assert report['status'] == 'conditional_bounds_exceed_limits'


@pytest.mark.parametrize('field,value', [
    ('plan_version', 'other'), ('scenario_ids', []), ('scenario_ids', ['same', 'same']),
    ('scenario_ids', ['not-observed']), ('n_repeats', True), ('n_repeats', 0), ('n_repeats', 5),
    ('n_repeats', 10001), ('sampling_design', 'inferred'), ('sampling_basis', ''),
    ('sampling_basis', 'x' * 2001), ('confidence_level', True), ('confidence_level', .49),
    ('confidence_level', 1), ('confidence_level', float('nan')), ('maximum_failure_probability', True),
    ('maximum_failure_probability', -1), ('maximum_failure_probability', 1),
    ('maximum_failure_probability', 10**400), ('criteria', []), ('groups', [None]),
])
def test_invalid_and_incomplete_plans_fail_closed(field, value):
    plan, source = inputs(count=2)
    plan[field] = value
    with pytest.raises(AgentBomError):
        review_failure_bounds(plan, source)


@pytest.mark.parametrize('mutation', ['reserved', 'duplicate', 'foreign', 'empty', 'unknown', 'many'])
def test_invalid_scope_families_are_rejected(mutation):
    plan, source = inputs(count=2)
    group = {'group_id': 'group', 'scenario_ids': plan['scenario_ids'][:1], 'maximum_failure_probability': .1}
    plan['groups'] = [group]
    if mutation == 'reserved':
        group['group_id'] = 'overall'
    elif mutation == 'duplicate':
        plan['groups'].append(deepcopy(group))
    elif mutation == 'foreign':
        group['scenario_ids'] = ['outside']
    elif mutation == 'empty':
        group['scenario_ids'] = []
    elif mutation == 'unknown':
        group['extra'] = True
    else:
        plan['groups'] = [{**group, 'group_id': str(i)} for i in range(20)]
    with pytest.raises(AgentBomError):
        review_failure_bounds(plan, source)


@pytest.mark.parametrize('mutation', ['missing_metric', 'duplicate_repeat', 'missing_row', 'nan', 'bool', 'incomplete_scenario'])
def test_observations_are_not_dropped_imputed_or_coerced(mutation):
    plan, source = inputs(count=2)
    if mutation == 'missing_metric':
        del source['results'][0]['metrics']['completion']
    elif mutation == 'duplicate_repeat':
        source['results'][1] = deepcopy(source['results'][0])
    elif mutation == 'missing_row':
        source['results'].pop()
    elif mutation == 'nan':
        source['results'][0]['metrics']['completion'] = float('nan')
    elif mutation == 'bool':
        source['results'][0]['metrics']['completion'] = True
    else:
        source['results'][0]['scenario_id'] = 'outside'
    with pytest.raises(AgentBomError):
        review_failure_bounds(plan, source)


def test_order_invariance_and_source_binding():
    plan, source = inputs(count=3, failed={('synthetic-000', 0)})
    report = review_failure_bounds(plan, source)
    source['results'].reverse()
    plan['scenario_ids'].reverse()
    plan['criteria'].reverse()
    reordered = review_failure_bounds(plan, source)
    assert report['scopes'] == reordered['scopes'] and report['scenario_outcomes'] == reordered['scenario_outcomes']
    assert reordered['source_sha256'] == digest(source) != report['source_sha256']
    assert reordered['plan_sha256'] == digest(plan) != report['plan_sha256']


def test_cli_verifies_failure_diagnostics_without_treating_exit_zero_as_approval(tmp_path, capsys):
    plan, source = inputs(count=2)
    plan_path, source_path, out = [tmp_path / name for name in ('plan.json', 'source.json', 'report.json')]
    plan_path.write_text(json.dumps(plan))
    source_path.write_text(json.dumps(source))
    args = ['failure-bound-eval', str(plan_path), str(source_path)]
    assert main(args + ['--out', str(out)]) == 0
    assert main(args + ['--verify', str(out)]) == 0
    assert 'conditional_bounds_exceed_limits' in capsys.readouterr().out
    original = out.read_bytes()
    assert main(args + ['--out', str(out)]) == 2
    assert out.read_bytes() == original
    changed = json.loads(original)
    changed['scopes'][0]['one_sided_upper_failure_bound'] = 0
    out.write_text(json.dumps(changed))
    assert main(args + ['--verify', str(out)]) == 2
    out.write_bytes(original)
    plan['maximum_failure_probability'] = .9
    plan_path.write_text(json.dumps(plan))
    assert main(args + ['--verify', str(out)]) == 2


def test_example_emits_recomputable_synthetic_contrasts(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'examples/evaluation-review/failure_bounds.py'
    spec = importlib.util.spec_from_file_location('failure_bound_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / 'demo'
    module.create_examples(root)
    assert len([p for p in root.rglob('*') if p.is_file()]) == 21
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        assert main(['failure-bound-eval', str(directory / 'plan.json'), str(directory / 'evaluation.json'),
                     '--verify', str(directory / 'report.json')]) == 0
    with pytest.raises(AgentBomError):
        module.create_examples(root)
    assert 'no real agents' in (root / 'README.txt').read_text()


@pytest.mark.parametrize('failures,count,alpha', [(True, 2, .05), (1, 0, .05), (1, 501, .05),
                                                (-1, 10, .05), (11, 10, .05), (1, 2, True), (1, 2, float('nan'))])
def test_invalid_binomial_arguments_are_rejected(failures, count, alpha):
    with pytest.raises(AgentBomError):
        upper_failure_bound(failures, count, alpha)


def test_oversized_input_and_unknown_plan_fields_are_rejected():
    plan, source = inputs(count=1)
    source['extra'] = 'x' * 2_000_000
    with pytest.raises(AgentBomError):
        review_failure_bounds(plan, source)
    del source['extra']
    plan['extra'] = 'do not ignore'
    with pytest.raises(AgentBomError):
        review_failure_bounds(plan, source)
