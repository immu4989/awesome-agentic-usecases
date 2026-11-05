from copy import deepcopy
from itertools import product
from pathlib import Path
import runpy
import socket
import subprocess

import pytest

from aau_harness import eval_routing as module
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_import import import_observations
from aau_harness.inspect_pack import InspectionError


EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/evaluation-review/routing_workload.py'


@pytest.fixture
def inputs():
    return runpy.run_path(str(EXAMPLE))['example_inputs']()['group-hidden-failure']


def review(plan, source):
    raw = rendered(plan)
    return module.review_routing(raw, source, plan_sha256=digest(raw))


def test_exact_arithmetic_group_failures_and_nonmonotone_risk(inputs):
    plan, source = inputs
    result = review(plan, source)
    assert result == review(plan, source)
    assert result['recorded_joint_failures'] == 4 and len(result['observations']) == 10
    assert result['selected_threshold'] is None and not result['human_resolution_measured']
    low, high, none = result['thresholds']
    first, second = low['scopes']
    assert first['automated_observations'] == 6 and first['deferred_observations'] == 4
    assert first['automated_joint_failures'] == 2 and first['deferred_joint_failures'] == 2
    assert first['automation_fraction'] == .6 and first['automated_failure_fraction'] == 1 / 3
    assert first['status'] == 'recorded_limits_met'
    assert second['automated_observations'] == second['automated_joint_failures'] == 2
    assert second['status'] == low['status'] == 'recorded_limits_not_met'
    assert high['scopes'][0]['automated_failure_fraction'] == .5 > first['automated_failure_fraction']
    assert high['scopes'][0]['deferred_observations'] == 6
    assert none['scopes'][0]['automated_failure_fraction'] is None
    assert none['scopes'][0]['checks'][1]['status'] == 'unverified'
    assert none['scopes'][0]['deferred_joint_failures'] == 4
    assert first['deferral_reasons'] == {'required_human_review': 2, 'unknown_review_requirement': 1, 'missing_score': 1, 'below_threshold': 0}
    assert all(row['human_resolution'] == ('not_measured' if row['deferred_observations'] else 'not_applicable_no_deferrals')
               for threshold in result['thresholds'] for row in threshold['scopes'])
    assert result['source_sha256'] == digest(source) and result['plan_file_sha256'] == digest(rendered(plan))
    assert result['implementation_sha256']['eval_routing.py'] == digest(Path(module.__file__).read_bytes())


def test_all_deferred_is_not_zero_risk_or_successfully_served(inputs):
    plan, source = inputs
    plan.update(groups=[], thresholds=[1])
    plan['limits'].update(minimum_automation_fraction=0, maximum_review_observations=10)
    result = review(plan, source)
    row = result['thresholds'][0]['scopes'][0]
    assert row['automation_fraction'] == 0 and row['automated_failure_fraction'] is None
    assert row['status'] == 'recorded_limits_unverified'
    assert row['human_resolution'] == 'not_measured'
    assert row['recorded_joint_failures'] == row['deferred_joint_failures'] == 4


def test_all_automated_and_zero_failure_is_only_recorded_evidence(inputs):
    plan, source = inputs
    plan['thresholds'] = [0]
    for row in source['results']:
        row['metrics'].update(human_required=0, routing_score=0, unauthorized=0)
    result = review(plan, source)
    row = result['thresholds'][0]['scopes'][0]
    assert row['automation_fraction'] == 1 and row['automated_failure_fraction'] == 0
    assert row['human_resolution'] == 'not_applicable_no_deferrals'
    assert result['source_audit']['status'] == 'inconsistent'  # Never repair or ignore stale summaries.
    assert result['status'] == 'recorded_routing_diagnostic' and result['selected_threshold'] is None


def test_exhaustive_small_routing_grid_and_count_conservation(inputs):
    plan, _ = inputs
    plan.update(groups=[], n_repeats=1, thresholds=[0, .5, 1])
    cases = list(product([None, 0, .5, 1], [None, 0, 1], [0, 1]))
    ids = [f'case-{i}' for i in range(len(cases))]
    plan['scenario_ids'] = ids
    plan['limits']['maximum_review_observations'] = len(ids)
    observations = []
    for identity, (score, mandatory, failure) in zip(ids, cases):
        metrics = {'completion': 1, 'unauthorized': failure}
        if score is not None:
            metrics['routing_score'] = score
        if mandatory is not None:
            metrics['human_required'] = mandatory
        observations.append({'scenario_id': identity, 'repeat': 0, 'metrics': metrics})
    source = import_observations({'format_version': 'aau-recorded-observations/1.0', 'source_label': 'Synthetic grid',
                                  'scenario_ids': ids, 'n_repeats': 1, 'observations': observations})
    result = review(plan, source)
    previous = len(cases)
    for threshold in result['thresholds']:
        row = threshold['scopes'][0]
        expected_auto = [(s, m, f) for s, m, f in cases if m == 0 and s is not None and s >= threshold['threshold']]
        assert row['automated_observations'] == len(expected_auto) <= previous
        previous = row['automated_observations']
        assert row['automated_joint_failures'] == sum(f for _, _, f in expected_auto)
        assert row['automated_observations'] + row['deferred_observations'] == len(cases)
        assert sum(row['deferral_reasons'].values()) == row['deferred_observations']
        assert row['automated_joint_failures'] + row['deferred_joint_failures'] == row['recorded_joint_failures'] == 12


def test_overlapping_groups_are_separate_not_added_into_global_counts(inputs):
    plan, source = inputs
    plan['groups'].append({'group_id': 'overlap', 'scenario_ids': ['assisted-channel', 'human-only'],
                           'limits': {'minimum_automation_fraction': 0, 'maximum_automated_failure_fraction': 1, 'maximum_review_observations': 4}})
    result = review(plan, source)
    assert result['observation_count'] == 10
    assert [r['observation_count'] for r in result['thresholds'][0]['scopes']] == [10, 2, 4]
    assert [r['recorded_joint_failures'] for r in result['thresholds'][0]['scopes']] == [4, 2, 3]


def test_joint_outcomes_not_marginal_success_and_limits_not_rounded(inputs):
    plan, source = inputs
    source['results'][0]['metrics']['completion'] = 0
    source['results'][0]['metrics']['unauthorized'] = 0
    row = review(plan, source)['observations'][0]
    assert row['failed_criteria'] == [{'metric': 'completion', 'value': 0}] and not row['jointly_passed']
    assert module._check('test', 1, 3, .3333, 'lower')['status'] == 'not_met'
    assert module._check('test', 1, 10, .1, 'lower')['status'] == 'met'
    assert module._check('test', 1, 10, .1, 'higher')['status'] == 'met'


@pytest.mark.parametrize('field,value', [('thresholds', []), ('thresholds', [0, 0.0]), ('thresholds', [True]),
                                       ('thresholds', [-.1]), ('thresholds', [1.1]), ('thresholds', [None]),
                                       ('thresholds', [i / 20 for i in range(21)]), ('n_repeats', True),
                                       ('n_repeats', 0), ('n_repeats', 10001), ('score_basis', ''),
                                       ('score_metric', 'completion'), ('mandatory_review_metric', 'routing_score'),
                                       ('score_metric', []), ('scenario_ids', []), ('scenario_ids', ['a', 'a']),
                                       ('scenario_ids', [{}]), ('groups', [{}]), ('plan_version', 'unsupported')])
def test_invalid_plans_fail_closed(inputs, field, value):
    plan, source = inputs
    plan[field] = value
    with pytest.raises(ValueError):
        review(plan, source)


@pytest.mark.parametrize('defect', ['extra_field', 'missing_field', 'outside_group', 'duplicate_group', 'reserved_group',
                                   'extra_limit', 'negative_limit', 'boolean_limit', 'oversized_count', 'wrong_count_type'])
def test_invalid_scope_and_limit_contracts(inputs, defect):
    plan, source = inputs
    if defect == 'extra_field':
        plan['selected_threshold'] = .8
    elif defect == 'missing_field':
        del plan['mandatory_review_metric']
    elif defect == 'outside_group':
        plan['groups'][0]['scenario_ids'] = ['absent']
    elif defect == 'duplicate_group':
        plan['groups'].append(deepcopy(plan['groups'][0]))
    elif defect == 'reserved_group':
        plan['groups'][0]['group_id'] = 'overall'
    elif defect == 'extra_limit':
        plan['limits']['allow_unknown_risk'] = True
    elif defect == 'negative_limit':
        plan['limits']['minimum_automation_fraction'] = -.1
    elif defect == 'boolean_limit':
        plan['limits']['maximum_automated_failure_fraction'] = False
    elif defect == 'oversized_count':
        plan['groups'][0]['limits']['maximum_review_observations'] = 3
    else:
        plan['limits']['maximum_review_observations'] = 4.0
    with pytest.raises(ValueError):
        review(plan, source)


@pytest.mark.parametrize('defect', ['missing_row', 'duplicate_row', 'subset_census', 'repeats', 'missing_outcome',
                                   'bad_score', 'bad_flag', 'boolean_score', 'boolean_flag', 'null_score', 'nonfinite'])
def test_source_coverage_and_metric_validity_are_enforced(inputs, defect):
    plan, source = inputs
    metrics = source['results'][0]['metrics']
    if defect == 'missing_row':
        source['results'].pop()
    elif defect == 'duplicate_row':
        source['results'][-1] = deepcopy(source['results'][0])
    elif defect == 'subset_census':
        plan['scenario_ids'].remove('ordinary-a')
    elif defect == 'repeats':
        plan['n_repeats'] = 3
    elif defect == 'missing_outcome':
        del metrics['unauthorized']
    elif defect == 'bad_score':
        metrics['routing_score'] = 1.01
    elif defect == 'bad_flag':
        metrics['human_required'] = .5
    elif defect == 'boolean_score':
        metrics['routing_score'] = True
    elif defect == 'boolean_flag':
        metrics['human_required'] = False
    elif defect == 'null_score':
        metrics['routing_score'] = None
    else:
        metrics['routing_score'] = float('inf')
    with pytest.raises(ValueError):
        review(plan, source)


def test_plan_pin_is_checked_before_reading_or_auditing_source(inputs, monkeypatch, tmp_path):
    plan, source = inputs
    raw = rendered(plan)
    def forbidden(*args, **kwargs):
        pytest.fail('source must not be read before the plan pin is checked')
    monkeypatch.setattr(module, 'audit_evaluation', forbidden)
    with pytest.raises(InspectionError, match='byte_pin_mismatch'):
        module.review_routing(raw, source, plan_sha256='0' * 64)
    (tmp_path / 'plan.json').write_bytes(raw)
    monkeypatch.setattr(module, 'load_json', forbidden)
    assert main(['routing-eval', str(tmp_path / 'plan.json'), str(tmp_path / 'missing'), '--plan-sha256', '0' * 64,
                 '--out', str(tmp_path / 'report.json')]) == 2
    assert not (tmp_path / 'report.json').exists()


def test_report_bound_and_unreviewed_metrics(inputs):
    plan, source = inputs
    source['results'][0]['metrics']['other'] = 42
    assert review(plan, source)['unreviewed_metrics'] == ['other']
    source['private_extra'] = 'x' * MAX_JSON_BYTES
    with pytest.raises(InspectionError, match='bounded'):
        review(plan, source)


def test_composed_report_limit_is_enforced_not_only_source_size(inputs, monkeypatch):
    plan, source = inputs
    report_size = len(rendered(review(plan, source)))
    assert len(rendered(source)) < report_size - 1
    monkeypatch.setattr(module, 'MAX_JSON_BYTES', report_size - 1)
    with pytest.raises(InspectionError, match='bounded'):
        review(plan, source)


def test_thresholds_and_observations_are_deterministic_without_hiding_input_changes(inputs):
    plan, source = inputs
    original = review(plan, source)
    plan['thresholds'].reverse()
    source['results'].reverse()
    reordered = review(plan, source)
    assert reordered['thresholds'] == original['thresholds']
    assert reordered['observations'] == original['observations']
    assert reordered['plan_file_sha256'] != original['plan_file_sha256']
    assert reordered['source_sha256'] != original['source_sha256']


def test_budget_exceedance_keeps_unknown_empty_denominator_visible(inputs):
    plan, source = inputs
    plan['thresholds'] = [1]
    overall = review(plan, source)['thresholds'][0]['scopes'][0]
    assert overall['status'] == 'recorded_limits_not_met'
    assert [row['status'] for row in overall['checks']] == ['not_met', 'unverified', 'not_met']


@pytest.mark.parametrize('defect', ['duplicate_json', 'changed_bytes', 'symlink'])
def test_cli_closed_control_errors_do_not_echo_private_content(inputs, tmp_path, capsys, defect):
    plan, source = inputs
    raw = rendered(plan)
    target = tmp_path / 'plan.json'
    if defect == 'duplicate_json':
        raw = b'{"PRIVATE-KEY":1,"PRIVATE-KEY":2}'
        target.write_bytes(raw)
    elif defect == 'changed_bytes':
        target.write_bytes(raw + b' ')
    else:
        (tmp_path / 'source.json').write_bytes(raw)
        target.symlink_to(tmp_path / 'source.json')
    assert main(['routing-eval', str(target), str(tmp_path / 'PRIVATE-PATH'), '--plan-sha256', digest(raw),
                 '--out', str(tmp_path / 'report.json')]) == 2
    captured = capsys.readouterr()
    assert 'PRIVATE-KEY' not in captured.err + captured.out and 'PRIVATE-PATH' not in captured.err + captured.out
    assert not (tmp_path / 'report.json').exists()


def test_cli_replay_tampering_and_non_overwrite(inputs, tmp_path):
    plan, source = inputs
    raw = rendered(plan)
    (tmp_path / 'plan.json').write_bytes(raw)
    (tmp_path / 'evaluation.json').write_bytes(rendered(source))
    target = tmp_path / 'report.json'
    command = ['routing-eval', str(tmp_path / 'plan.json'), str(tmp_path / 'evaluation.json'), '--plan-sha256', digest(raw)]
    assert main([*command, '--out', str(target)]) == 0  # Valid diagnostic, NOT a passed routing policy.
    assert main([*command, '--verify', str(target)]) == 0
    original = target.read_bytes()
    assert main([*command, '--out', str(target)]) == 2 and target.read_bytes() == original
    result = load_json(target)
    result['recorded_joint_failures'] = 0
    target.write_bytes(rendered(result))
    assert main([*command, '--verify', str(target)]) == 2
    target.write_bytes(original)
    source['results'][0]['metrics']['routing_score'] = .2
    (tmp_path / 'evaluation.json').write_bytes(rendered(source))
    assert main([*command, '--verify', str(target)]) == 2


def test_five_synthetic_examples_have_explicit_contrasts(tmp_path):
    expected = runpy.run_path(str(EXAMPLE))['create_example'](tmp_path / 'examples')
    assert len(expected) == 5
    assert (tmp_path / 'examples/README.txt').is_file()
    for name, status in expected.items():
        root = tmp_path / 'examples'
        plan = (root / f'{name}-plan.json').read_bytes()
        report = module.review_routing(plan, load_json(root / f'{name}-evaluation.json'), plan_sha256=digest(plan))
        assert report == load_json(root / f'{name}-report.json')
        assert report['thresholds'][0]['status'] == status
    with pytest.raises(FileExistsError):
        runpy.run_path(str(EXAMPLE))['create_example'](tmp_path / 'examples')


def test_no_network_or_adapter_execution(inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('recorded routing must not execute external work')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    assert review(*inputs)['status'] == 'recorded_routing_diagnostic'
