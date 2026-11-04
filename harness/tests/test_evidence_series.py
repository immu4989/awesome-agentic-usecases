from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess

import pytest

from aau_harness import evidence_series as module
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_pack import create_pack
from aau_harness.inspect_pack import InspectionError

# Native format fixtures, including deliberately context-free legacy CSV examples.
from test_inspect_pack import packs as packs
from test_intake_review import fixture_request


@pytest.fixture(scope='module')
def fixtures(tmp_path_factory):
    root = tmp_path_factory.mktemp('evidence-series-fixtures')
    policy, baseline, candidate, diagnostics = demo_inputs()
    baseline['source_label'] = candidate['source_label'] = 'PRIVATE-SOURCE-CANARY'
    budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': policy['scenario_ids'], 'minimum_repeats': 4,
              'criteria': diagnostics['criteria'], 'cost_basis': 'synthetic', 'groups': [], 'limits': {'total_cost_usd': 2}}
    unknown = deepcopy(candidate)
    del unknown['observations'][0]['cost_usd']
    expensive = deepcopy(candidate)
    expensive['observations'][0]['cost_usd'] = 3
    relaxed_policy = deepcopy(policy)
    relaxed_policy['metrics'][1]['candidate_observation_limit'] = 1
    changed_baseline = deepcopy(baseline)
    changed_baseline['source_label'] = 'Substituted baseline'
    for name, p, b, c, gate in [('passed', policy, baseline, candidate, budget),
                              ('failed', policy, baseline, baseline, budget),
                              ('unknown', policy, baseline, unknown, budget),
                              ('expensive', policy, baseline, expensive, budget),
                              ('changed-policy', relaxed_policy, baseline, baseline, budget),
                              ('changed-baseline', policy, changed_baseline, candidate, budget),
                              ('downgraded', policy, baseline, candidate, None)]:
        create_pack(p, b, c, root / name, recordings=True, diagnostics=diagnostics, operating_budget=gate)
    # Controlled fixture inputs, not a claim of independent production approval.
    request = {'request_version': 'aau-evidence-intake-request/1.0', 'profile': 'evaluation-review',
               'pack_version': 'aau-evaluation-review-pack/3.0', 'input_format': 'recordings',
               'pinned_inputs': {role: digest(rendered(value)) for role, value in (
                   ('policy', policy), ('baseline', baseline), ('diagnostics', diagnostics), ('operating_budget', budget))}}
    return root, rendered(request)


def history(tmp_path, fixtures, names):
    source, request = fixtures
    root = tmp_path / 'history'
    root.mkdir()
    ids = [f'checkpoint-{index}' for index in range(len(names))]
    for name, identity in zip(names, ids):
        if name == 'missing':
            continue
        shutil.copytree(source / ('passed' if name == 'invalid' else name), root / identity)
        if name == 'invalid':
            (root / identity / 'review.json').write_bytes(b'{}')
    plan = rendered({'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ids})
    return plan, request, root


def review(inputs):
    plan, request, root = inputs
    return module.review_series(plan, request, root, plan_sha256=digest(plan), request_sha256=digest(request))


@pytest.mark.parametrize('profile', ['evaluation-review', 'csv-review', 'retry-review', 'otlp-review', 'service-review'])
def test_all_five_review_families_use_full_intake_including_legacy_context_failures(tmp_path, packs, profile):
    root = tmp_path / 'history'
    for name in ('first', 'second'):
        shutil.copytree(packs[profile], root / name)
    plan = rendered({'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ['first', 'second']})
    request = rendered(fixture_request(packs[profile]))  # Synthetic plumbing, not independent approval.
    result = review((plan, request, root))
    assert result['exit_code'] == (1 if profile == 'csv-review' else 0)
    assert all(row['intake']['pack_inspection']['profile'] == profile for row in result['checkpoints'])
    assert result['distinct_verified_pack_inventory_count'] == 1
    if profile == 'csv-review':
        assert all(row['intake']['failed_constraints'] == ['matching_declared_context'] for row in result['checkpoints'])


@pytest.mark.parametrize('middle,status,code', [
    ('passed', 'series_constraints_met', 0), ('failed', 'series_constraints_not_met', 1),
    ('unknown', 'series_constraints_not_met', 1), ('expensive', 'series_constraints_not_met', 1),
    ('changed-policy', 'series_constraints_not_met', 1), ('changed-baseline', 'series_constraints_not_met', 1),
    ('downgraded', 'series_constraints_not_met', 1), ('missing', 'series_evidence_missing', 1),
    ('invalid', 'series_not_fully_verified', 2),
])
def test_later_passing_checkpoint_never_erases_history(tmp_path, fixtures, middle, status, code):
    inputs = history(tmp_path, fixtures, ['passed', middle, 'passed'])
    report = review(inputs)
    assert report == review(inputs)
    assert report['status'] == status and report['exit_code'] == code
    assert report['latest_checkpoint']['status'] == 'request_constraints_met'
    assert report['historical_issue_checkpoint_ids'] == ([] if code == 0 else ['checkpoint-1'])
    assert sum(report['counts'].values()) == report['checkpoint_count'] == 3
    assert len(report['checkpoints']) == 3 and len(report['transitions']) == 2
    if middle in ('missing', 'invalid'):
        assert all(row['relationship'] == 'not_comparable_missing_or_invalid' for row in report['transitions'])
        assert report['checkpoints'][1]['intake'] is None
    elif middle != 'passed':
        assert [row['relationship'] for row in report['transitions']] == [
            'requirements_started_failing', 'requirements_met_after_failure']
    else:
        assert all(row['relationship'] == 'unchanged_requirement_outcome' for row in report['transitions'])
    assert 'PRIVATE-SOURCE-CANARY' not in json.dumps(report)
    assert str(inputs[2]) not in json.dumps(report)
    assert report['implementation_sha256']['evidence_series.py'] == digest(Path(module.__file__).read_bytes())


@pytest.mark.parametrize('last', ['missing', 'invalid', 'failed', 'unknown'])
def test_latest_checkpoint_does_not_fall_back_to_earlier_green_evidence(tmp_path, fixtures, last):
    report = review(history(tmp_path, fixtures, ['passed', last]))
    expected = last if last in ('missing', 'invalid') else 'request_constraints_not_met'
    assert report['latest_checkpoint'] == {'checkpoint_id': 'checkpoint-1', 'position': 2, 'status': expected}
    assert report['exit_code'] != 0


def test_all_unavailable_and_mixed_failure_precedence_preserve_every_checkpoint(tmp_path, fixtures):
    inputs = history(tmp_path, fixtures, ['failed', 'missing', 'invalid', 'unknown', 'passed'])
    report = review(inputs)
    assert report['status'] == 'series_not_fully_verified' and report['exit_code'] == 2
    assert report['counts'] == {'request_constraints_met': 1, 'request_constraints_not_met': 2, 'missing': 1, 'invalid': 1}
    assert report['checkpoints'][3]['intake']['pack_inspection']['assessment']['candidate_budget_status'] == 'constraints_not_verified'
    assert report['checkpoints'][0]['intake']['pack_inspection']['assessment']['policy_status'] == 'constraints_not_met'
    for path in inputs[2].iterdir():
        shutil.rmtree(path)
    result = review(inputs)
    assert result['status'] == 'series_evidence_missing' and result['counts']['missing'] == 5
    assert result['distinct_verified_pack_inventory_count'] == 0


def test_order_is_pinned_plan_order_not_alphabetic_or_modification_time(tmp_path, fixtures):
    plan, request, root = history(tmp_path, fixtures, ['passed', 'failed', 'unknown'])
    value = json.loads(plan)
    value['checkpoint_ids'] = ['checkpoint-2', 'checkpoint-0', 'checkpoint-1']
    for index, path in enumerate(root.iterdir()):
        os.utime(path, (100 + index, 100 + index))
    changed = rendered(value)
    report = review((changed, request, root))
    assert [row['checkpoint_id'] for row in report['checkpoints']] == value['checkpoint_ids']
    assert report['latest_checkpoint']['checkpoint_id'] == 'checkpoint-1'
    assert report['plan_file_sha256'] == digest(changed)
    with pytest.raises(InspectionError, match='series_plan_byte_pin_mismatch'):
        module.review_series(changed, request, root, plan_sha256=digest(plan), request_sha256=digest(request))


def test_identical_retained_inventories_are_disclosed_not_claimed_as_fresh_executions(tmp_path, fixtures):
    report = review(history(tmp_path, fixtures, ['passed', 'failed', 'passed', 'failed']))
    assert report['distinct_verified_pack_inventory_count'] == 2
    groups = {tuple(row['checkpoint_ids']) for row in report['repeated_pack_inventories']}
    assert groups == {('checkpoint-0', 'checkpoint-2'), ('checkpoint-1', 'checkpoint-3')}
    assert 'not fresh executions' in report['boundary']
    assert report['counts']['request_constraints_not_met'] == 2


@pytest.mark.parametrize('defect', ['policy', 'baseline'])
def test_full_verification_success_is_not_control_input_approval(tmp_path, fixtures, defect):
    report = review(history(tmp_path, fixtures, ['passed', f'changed-{defect}', 'passed']))
    changed = report['checkpoints'][1]['intake']
    assert changed['pack_inspection']['exit_code'] == 0
    assert changed['unmatched_input_roles'] == [defect]
    assert report['status'] == 'series_constraints_not_met'


@pytest.mark.parametrize('defect', ['file', 'symlink', 'dangling_symlink', 'fifo'])
def test_non_directory_checkpoints_are_invalid_not_missing_and_do_not_stop_other_reviews(tmp_path, fixtures, defect):
    inputs = history(tmp_path, fixtures, ['missing', 'passed'])
    path = inputs[2] / 'checkpoint-0'
    if defect == 'file':
        path.write_bytes(b'not a pack')
    elif defect == 'symlink':
        path.symlink_to(fixtures[0] / 'passed', target_is_directory=True)
    elif defect == 'dangling_symlink':
        path.symlink_to(tmp_path / 'absent')
    else:
        if not hasattr(os, 'mkfifo'):
            pytest.skip('FIFO unavailable')
        os.mkfifo(path)
    report = review(inputs)
    assert report['counts']['invalid'] == 1 and report['counts']['missing'] == 0
    assert report['checkpoints'][1]['status'] == 'request_constraints_met'
    assert report['checkpoints'][0]['reason'] == 'checkpoint_verification_failed'


@pytest.mark.parametrize('defect', ['extra_directory', 'extra_file', 'extra_symlink', 'root_symlink', 'no_root'])
def test_root_scope_errors_are_rejected_not_silently_filtered(tmp_path, fixtures, defect):
    plan, request, root = history(tmp_path, fixtures, ['passed', 'failed'])
    if defect == 'extra_directory':
        (root / 'hidden-failure').mkdir()
    elif defect == 'extra_file':
        (root / 'report.json').write_bytes(b'{}')
    elif defect == 'extra_symlink':
        (root / 'unlisted').symlink_to(tmp_path / 'absent')
    elif defect == 'root_symlink':
        link = tmp_path / 'link'
        link.symlink_to(root, target_is_directory=True)
        root = link
    else:
        root = tmp_path / 'absent'
    with pytest.raises(InspectionError):
        review((plan, request, root))


@pytest.mark.parametrize('ids', [[], ['one'], ['one', 'one'], ['a', '../outside'], ['a', 'a/b'], ['a', 'a\\b'],
                                ['a', 'A'], ['a', 'con'], ['a', 'lpt1'], ['a', '-option'], ['a', 'a' * 65],
                                ['a', True], ['a', {}], 'ab', [f'c{i}' for i in range(11)]])
def test_invalid_checkpoint_census_or_unsafe_ids_fail_closed(ids, tmp_path, fixtures):
    plan = rendered({'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ids})
    with pytest.raises(InspectionError, match='invalid_series_checkpoint_ids'):
        review((plan, fixtures[1], tmp_path))


@pytest.mark.parametrize('raw', [b'', b'[]', b'{"private":1,"private":2}', b'{"x":NaN}', b'\xff', b'x' * (MAX_JSON_BYTES + 1)],
                         ids=['empty', 'array', 'duplicate', 'nonfinite', 'utf8', 'oversized'])
def test_invalid_plans_are_rejected_before_any_checkpoint_access(tmp_path, fixtures, monkeypatch, raw):
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid plan must not read evidence')
    monkeypatch.setattr(module, '_entries', forbidden)
    with pytest.raises(InspectionError):
        review((raw, fixtures[1], tmp_path))


@pytest.mark.parametrize('which', ['plan', 'request'])
def test_both_byte_pins_are_validated_before_pack_access(tmp_path, fixtures, monkeypatch, which):
    plan = rendered({'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ['first', 'last']})
    request = fixtures[1]
    def forbidden(*args, **kwargs):
        raise AssertionError('bad pin must not access evidence')
    monkeypatch.setattr(module, '_entries', forbidden)
    with pytest.raises(InspectionError, match='byte_pin_mismatch'):
        module.review_series(plan, request, tmp_path, plan_sha256='0' * 64 if which == 'plan' else digest(plan),
                             request_sha256='0' * 64 if which == 'request' else digest(request))


@pytest.mark.parametrize('change', ['version', 'extra', 'missing', 'wrong_request_schema'])
def test_invalid_control_contracts_do_not_produce_an_all_invalid_history(tmp_path, fixtures, monkeypatch, change):
    plan = {'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ['first', 'last']}
    request = fixtures[1]
    if change == 'version':
        plan['plan_version'] = 'aau-evidence-series-plan/99.0'
    elif change == 'extra':
        plan['allow_missing'] = True
    elif change == 'missing':
        del plan['checkpoint_ids']
    else:
        request = b'{}'
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid controls must abort before checkpoint access')
    monkeypatch.setattr(module, '_entries', forbidden)
    with pytest.raises(InspectionError):
        review((rendered(plan), request, tmp_path))


@pytest.mark.parametrize('mutation', ['add_missing', 'remove', 'replace'])
def test_root_membership_changes_during_review_are_rejected(tmp_path, fixtures, monkeypatch, mutation):
    inputs = history(tmp_path, fixtures, ['passed', 'missing' if mutation == 'add_missing' else 'failed'])
    original = module.review_intake
    changed = False
    def mutate(*args, **kwargs):
        nonlocal changed
        result = original(*args, **kwargs)
        if not changed:
            changed = True
            target = inputs[2] / 'checkpoint-1'
            if mutation == 'add_missing':
                shutil.copytree(fixtures[0] / 'passed', target)
            elif mutation == 'remove':
                shutil.rmtree(target)
            else:
                target.rename(tmp_path / 'previous')
                shutil.copytree(fixtures[0] / 'passed', target)
        return result
    monkeypatch.setattr(module, 'review_intake', mutate)
    with pytest.raises(InspectionError, match='series_membership_changed_during_review'):
        review(inputs)


def test_maximum_census_and_report_limit_without_execution(tmp_path, fixtures, monkeypatch):
    inputs = history(tmp_path, fixtures, ['passed'] * module.MAX_CHECKPOINTS)
    def forbidden(*args, **kwargs):
        raise AssertionError('no command or network execution permitted')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    assert review(inputs)['counts']['request_constraints_met'] == module.MAX_CHECKPOINTS
    # Keep plan size valid but constrain the composed report separately.
    monkeypatch.setattr(module, 'MAX_JSON_BYTES', len(inputs[0]))
    with pytest.raises(InspectionError, match='series_report_exceeds_limit'):
        review(inputs)


@pytest.mark.parametrize('middle,code', [('passed', 0), ('failed', 1), ('missing', 1), ('invalid', 2)])
def test_cli_preserves_all_outcomes_and_recomputes_reports(tmp_path, fixtures, middle, code):
    plan, request, root = history(tmp_path, fixtures, ['passed', middle, 'passed'])
    plan_file, request_file, output = (tmp_path / name for name in ('plan.json', 'request.json', 'report.json'))
    plan_file.write_bytes(plan)
    request_file.write_bytes(request)
    args = ['review-series', str(plan_file), str(request_file), str(root), '--plan-sha256', digest(plan),
            '--request-sha256', digest(request)]
    assert main([*args, '--out', str(output)]) == code
    assert main([*args, '--verify', str(output)]) == code
    assert load_json(output)['exit_code'] == code
    assert main([*args, '--out', str(output)]) == 2
    assert main([*args, '--out', str(root / 'report.json')]) == 2
    saved = output.read_bytes()
    changed = load_json(output)
    changed['historical_issue_checkpoint_ids'] = ['fabricated']
    output.write_bytes(rendered(changed))
    assert main([*args, '--verify', str(output)]) == 2
    output.write_bytes(saved)
    plan_file.write_bytes(plan + b' ')
    assert main([*args, '--out', str(tmp_path / 'invalid.json')]) == 2
    assert not (tmp_path / 'invalid.json').exists()


def test_closed_cli_errors_do_not_echo_private_keys_or_paths(tmp_path, fixtures, capsys):
    plan_file, request_file = (tmp_path / name for name in ('plan.json', 'request.json'))
    raw = b'{"PRIVATE-KEY":1,"PRIVATE-KEY":2}'
    plan_file.write_bytes(raw)
    request_file.write_bytes(fixtures[1])
    assert main(['review-series', str(plan_file), str(request_file), str(tmp_path / 'PRIVATE-PATH'),
                 '--plan-sha256', digest(raw), '--request-sha256', digest(fixtures[1]),
                 '--out', str(tmp_path / 'report.json')]) == 2
    captured = capsys.readouterr()
    assert 'PRIVATE-KEY' not in captured.out + captured.err
    assert 'PRIVATE-PATH' not in captured.out + captured.err


def test_filling_a_gap_changes_the_report_instead_of_verifying_old_history(tmp_path, fixtures):
    plan, request, root = history(tmp_path, fixtures, ['passed', 'missing', 'passed'])
    plan_file, request_file = tmp_path / 'plan.json', tmp_path / 'request.json'
    plan_file.write_bytes(plan)
    request_file.write_bytes(request)
    args = ['review-series', str(plan_file), str(request_file), str(root), '--plan-sha256', digest(plan),
            '--request-sha256', digest(request)]
    report = tmp_path / 'report.json'
    assert main([*args, '--out', str(report)]) == 1
    shutil.copytree(fixtures[0] / 'passed', root / 'checkpoint-1')
    assert main([*args, '--verify', str(report)]) == 2
    assert main([*args, '--out', str(tmp_path / 'updated-report.json')]) == 0
    assert load_json(report)['status'] == 'series_evidence_missing'  # Original receipt is never overwritten.
