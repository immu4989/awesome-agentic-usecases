from copy import deepcopy
from itertools import product
from pathlib import Path
import runpy
import socket
import subprocess

import pytest

from aau_harness import review_queue as module
from aau_harness import eval_routing as routing_module
from aau_harness.agent_bom import digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.inspect_pack import InspectionError


EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/evaluation-review/review_queue.py'


@pytest.fixture
def inputs():
    return runpy.run_path(str(EXAMPLE))['example_inputs']()['one-slot']


def review(inputs):
    plan, routing, source, timing = inputs
    raw = rendered(plan)
    return module.review_queue(raw, routing, source, timing, queue_plan_sha256=digest(raw))


def test_single_slot_exact_waits_deadlines_and_complete_source_failures(inputs):
    result = review(inputs)
    assert result == review(inputs)
    assert result['counts'] == {'deferred_observations': 4, 'scheduled': 4, 'not_scheduled': 0,
                                'declared_deadlines': 4, 'known_deadline_failures': 2, 'deadline_unknown_or_unresolved': 0}
    assert [row['start_s'] for row in result['jobs']] == [0, 3, 6, 9]
    assert [row['finish_s'] for row in result['jobs']] == [3, 6, 9, 12]
    assert result['maximum_scheduled_wait_s'] == 9 and result['maximum_unserved_wait_at_horizon_s'] is None
    assert result['maximum_waiting_after_same_time_events'] == 3
    assert result['timeline'] == [{'time_s': t, 'waiting_after_events': w, 'in_service_after_events': a}
                                 for t, w, a in [(0, 3, 1), (3, 2, 1), (6, 1, 1), (9, 0, 1), (12, 0, 0)]]
    assert result['routing_review']['recorded_joint_failures'] == 4
    assert sum(not row['recorded_jointly_passed'] for row in result['jobs']) == 2
    assert not result['human_resolution_measured']
    assert all(row['human_resolution'] == 'not_measured' for row in result['jobs'])
    assert [row['deferral_reason'] for row in result['jobs']] == ['required_human_review', 'required_human_review', 'unknown_review_requirement', 'missing_score']


def test_parallel_slots_ties_and_no_overlap(inputs):
    inputs[0]['workers'].append({'worker_id': 'review-slot-b', 'windows': [{'start_s': 0, 'end_s': 12}]})
    result = review(inputs)
    assert [r['finish_s'] for r in result['jobs']] == [3, 3, 6, 6]
    assert [r['worker_id'] for r in result['jobs']] == ['review-slot-a', 'review-slot-b', 'review-slot-a', 'review-slot-b']
    assert result['counts']['known_deadline_failures'] == 0
    assert result['maximum_scheduled_wait_s'] == 3
    assert all(w['scheduled_service_s'] == 6 and w['declared_available_s'] == 12 for w in result['workers'])


def test_breaks_require_complete_uninterrupted_slot(inputs):
    inputs[0]['workers'][0]['windows'] = [{'start_s': 0, 'end_s': 4}, {'start_s': 8, 'end_s': 12}]
    result = review(inputs)
    assert [r['start_s'] for r in result['jobs']] == [0, 8, None, None]
    assert result['jobs'][2]['reason'] == 'no_complete_service_slot'
    assert result['jobs'][3]['reason'] == 'blocked_by_earlier_unschedulable_item'
    assert result['maximum_scheduled_wait_s'] == 8 and result['maximum_unserved_wait_at_horizon_s'] == 12
    assert result['timeline'][-1] == {'time_s': 12, 'waiting_after_events': 2, 'in_service_after_events': 0}


def test_later_short_jobs_never_overtake_head_reserved_for_future_window(inputs):
    plan, _, _, timing = inputs
    plan['workers'] = [{'worker_id': 'a', 'windows': [{'start_s': 0, 'end_s': 2}, {'start_s': 8, 'end_s': 12}]},
                       {'worker_id': 'b', 'windows': [{'start_s': 0, 'end_s': 2}]}]
    for row in timing['items'][1:]:
        row['service_s'] = 1
    result = review(inputs)
    assert [r['start_s'] for r in result['jobs']] == [8, 11, None, None]
    assert all(r['worker_id'] != 'b' for r in result['jobs'])


@pytest.mark.parametrize('mode', ['no_workers', 'oversized_head'])
def test_zero_capacity_and_unserviceable_head_retain_every_referral(inputs, mode):
    if mode == 'no_workers':
        inputs[0]['workers'] = []
    else:
        inputs[3]['items'][0]['service_s'] = 20
    result = review(inputs)
    assert result['counts']['not_scheduled'] == result['counts']['known_deadline_failures'] == 4
    assert result['maximum_scheduled_wait_s'] is None and result['maximum_unserved_wait_at_horizon_s'] == 12
    assert result['maximum_waiting_after_same_time_events'] == 4


def test_unknown_future_and_already_overdue_deadlines_are_distinct(inputs):
    inputs[0]['workers'] = []
    rows = inputs[3]['items']
    rows[0]['deadline_s'], rows[1]['deadline_s'], rows[2]['deadline_s'] = None, 13, 0
    result = review(inputs)
    assert [r['deadline_status'] for r in result['jobs']] == ['not_declared', 'beyond_horizon_unresolved',
                                                           'not_completed_by_declared_deadline', 'not_completed_by_declared_deadline']
    assert result['counts']['known_deadline_failures'] == result['counts']['deadline_unknown_or_unresolved'] == 2


def _tick_oracle(plan, items):
    """Independent integer-time dispatch simulator, not the production future-slot search."""
    pending = sorted(items, key=lambda row: (row['arrival_s'], row['scenario_id'], row['repeat']))
    busy_until = {w['worker_id']: 0 for w in plan['workers']}
    assigned = {}
    for tick in range(plan['horizon_s'] + 1):
        while pending and pending[0]['arrival_s'] <= tick:
            head = pending[0]
            available = [w['worker_id'] for w in plan['workers'] if busy_until[w['worker_id']] <= tick
                         and any(win['start_s'] <= tick and tick + head['service_s'] <= win['end_s'] for win in w['windows'])]
            if not available:
                break
            worker = min(available)
            assigned[head['scenario_id'], head['repeat']] = tick, worker, tick + head['service_s']
            busy_until[worker] = tick + head['service_s']
            pending.pop(0)
    return assigned


def test_exhaustive_short_queue_matches_independent_time_step_oracle():
    schedules = [[], [{'worker_id': 'a', 'windows': [{'start_s': 0, 'end_s': 5}]}],
                 [{'worker_id': 'a', 'windows': [{'start_s': 0, 'end_s': 2}, {'start_s': 3, 'end_s': 5}]}],
                 [{'worker_id': 'a', 'windows': [{'start_s': 2, 'end_s': 5}]},
                  {'worker_id': 'b', 'windows': [{'start_s': 0, 'end_s': 2}]}]]
    for workers, a0, a1, d0, d1 in product(schedules, range(3), range(3), range(1, 4), range(1, 4)):
        plan = {'workers': workers, 'horizon_s': 5, 'threshold': 0}
        jobs = [{'scenario_id': name, 'repeat': 0, 'arrival_s': arrival, 'service_s': duration, 'deadline_s': 4}
                for name, arrival, duration in [('a', a0, d0), ('b', a1, d1)]]
        deferred = {(row['scenario_id'], 0): {'mandatory_review': 1, 'score': 1, 'jointly_passed': True, 'failed_criteria': []} for row in jobs}
        jobs.sort(key=lambda row: (row['arrival_s'], row['scenario_id'], row['repeat']))
        actual = module._schedule(plan, jobs, deferred)
        expected = _tick_oracle(plan, jobs)
        assert {(r['scenario_id'], r['repeat']): (r['start_s'], r['worker_id'], r['finish_s'])
                for r in actual if r['status'] == 'scheduled'} == expected
        assert len(actual) == 2
        timeline = module._timeline(actual, 5)
        assert all(r['waiting_after_events'] >= 0 and 0 <= r['in_service_after_events'] <= len(workers) for r in timeline)


@pytest.mark.parametrize('defect', ['missing', 'extra', 'duplicate', 'automated_item', 'unknown_requirement_dropped',
                                   'missing_service', 'zero_service', 'float_service', 'boolean_arrival', 'arrival_after_horizon', 'bad_deadline'])
def test_exact_referral_census_and_valid_timings_are_required(inputs, defect):
    rows = inputs[3]['items']
    if defect in ('missing', 'unknown_requirement_dropped'):
        rows.pop(2 if defect == 'unknown_requirement_dropped' else 0)
    elif defect == 'extra':
        rows.append({**rows[0], 'scenario_id': 'outside'})
    elif defect == 'duplicate':
        rows.append(deepcopy(rows[0]))
    elif defect == 'automated_item':
        rows[0]['scenario_id'] = 'ordinary-a'
    elif defect == 'missing_service':
        rows[0]['service_s'] = None
    elif defect == 'zero_service':
        rows[0]['service_s'] = 0
    elif defect == 'float_service':
        rows[0]['service_s'] = 3.0
    elif defect == 'boolean_arrival':
        rows[0]['arrival_s'] = False
    elif defect == 'arrival_after_horizon':
        rows[0]['arrival_s'] = 12
    else:
        rows[0]['deadline_s'] = -1
    with pytest.raises(InspectionError):
        review(inputs)


@pytest.mark.parametrize('defect', ['version', 'extra', 'threshold', 'routing_pin', 'initial_state', 'timing_basis',
                                   'empty_basis', 'horizon_bool', 'horizon_zero', 'duplicate_worker', 'empty_windows',
                                   'overlap', 'reversed_windows', 'outside_horizon', 'bool_window'])
def test_closed_queue_controls(inputs, defect):
    plan = inputs[0]
    if defect == 'version':
        plan['plan_version'] = 'new'
    elif defect == 'extra':
        plan['allow_overtime'] = True
    elif defect == 'threshold':
        plan['threshold'] = .2
    elif defect == 'routing_pin':
        plan['routing_plan_sha256'] = '0' * 64
    elif defect == 'initial_state':
        plan['initial_state'] = 'assumed_unknown'
    elif defect == 'timing_basis':
        plan['timing_basis'] = 'predicted_by_tool'
    elif defect == 'empty_basis':
        plan['timing_scope'] = ''
    elif defect == 'horizon_bool':
        plan['horizon_s'] = True
    elif defect == 'horizon_zero':
        plan['horizon_s'] = 0
    elif defect == 'duplicate_worker':
        plan['workers'].append(deepcopy(plan['workers'][0]))
    elif defect == 'empty_windows':
        plan['workers'][0]['windows'] = []
    elif defect == 'overlap':
        plan['workers'][0]['windows'].append({'start_s': 6, 'end_s': 10})
    elif defect == 'reversed_windows':
        plan['workers'][0]['windows'] = [{'start_s': 8, 'end_s': 12}, {'start_s': 0, 'end_s': 4}]
    elif defect == 'outside_horizon':
        plan['workers'][0]['windows'][0]['end_s'] = 13
    else:
        plan['workers'][0]['windows'][0]['start_s'] = False
    with pytest.raises(ValueError):
        review(inputs)


def test_control_pins_before_source_reads(inputs, tmp_path, monkeypatch):
    plan, routing, _, _ = inputs
    raw = rendered(plan)
    (tmp_path / 'queue.json').write_bytes(raw)
    (tmp_path / 'routing.json').write_bytes(routing)
    def forbidden(*args, **kwargs):
        pytest.fail('evaluation/timing read before valid controls')
    monkeypatch.setattr(module, 'load_json', forbidden)
    command = ['review-queue', str(tmp_path / 'queue.json'), str(tmp_path / 'routing.json'), 'absent-eval', 'absent-timings',
               '--out', str(tmp_path / 'report.json')]
    assert main([*command, '--queue-plan-sha256', '0' * 64]) == 2
    (tmp_path / 'routing.json').write_bytes(routing + b' ')
    assert main([*command, '--queue-plan-sha256', digest(raw)]) == 2
    assert not (tmp_path / 'report.json').exists()


def test_cli_full_replay_source_change_tamper_and_overwrite(inputs, tmp_path):
    plan, routing, source, timing = inputs
    raw = rendered(plan)
    for name, payload in [('queue', raw), ('routing', routing), ('evaluation', rendered(source)), ('timing', rendered(timing))]:
        (tmp_path / f'{name}.json').write_bytes(payload)
    command = ['review-queue', *[str(tmp_path / f'{name}.json') for name in ('queue', 'routing', 'evaluation', 'timing')],
               '--queue-plan-sha256', digest(raw)]
    target = tmp_path / 'report.json'
    assert main([*command, '--out', str(target)]) == 0  # Diagnostic with missed deadlines, not approval.
    assert main([*command, '--verify', str(target)]) == 0
    original = target.read_bytes()
    assert main([*command, '--out', str(target)]) == 2 and target.read_bytes() == original
    report = load_json(target)
    report['counts']['known_deadline_failures'] = 0
    target.write_bytes(rendered(report))
    assert main([*command, '--verify', str(target)]) == 2
    target.write_bytes(original)
    timing['items'][0]['service_s'] = 4
    (tmp_path / 'timing.json').write_bytes(rendered(timing))
    assert main([*command, '--verify', str(target)]) == 2


def test_no_external_execution(inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('queue replay must remain offline')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    assert review(inputs)['status'] == 'finite_queue_diagnostic'


def test_no_referrals_is_not_a_claim_of_safe_automation(inputs):
    plan, routing, source, timing = inputs
    for row in source['results']:
        row['metrics'].update(routing_score=1, human_required=0)
    timing['items'] = []
    result = review((plan, routing, source, timing))
    assert result['jobs'] == [] and result['counts']['deferred_observations'] == 0
    assert result['maximum_scheduled_wait_s'] is None and result['maximum_unserved_wait_at_horizon_s'] is None
    assert result['routing_review']['recorded_joint_failures'] == 4
    assert result['maximum_waiting_after_same_time_events'] == 0


def test_queue_report_bound_covers_nested_routing_and_timeline(inputs, monkeypatch):
    result = review(inputs)
    bound = len(rendered(result)) - 1
    assert len(rendered(result['routing_review'])) < bound
    monkeypatch.setattr(routing_module, 'MAX_JSON_BYTES', bound)
    with pytest.raises(InspectionError, match='bounded'):
        review(inputs)


def test_input_list_order_cannot_change_declared_fifo_or_worker_ties(inputs):
    inputs[0]['workers'].append({'worker_id': 'z', 'windows': [{'start_s': 0, 'end_s': 12}]})
    original = review(inputs)
    inputs[0]['workers'].reverse()
    inputs[3]['items'].reverse()
    reordered = review(inputs)
    assert reordered['jobs'] == original['jobs'] and reordered['timeline'] == original['timeline']
    assert reordered['queue_plan_file_sha256'] != original['queue_plan_file_sha256']
    assert reordered['work_items_sha256'] != original['work_items_sha256']


def test_all_five_examples_replay(tmp_path):
    root = tmp_path / 'examples'
    expected = runpy.run_path(str(EXAMPLE))['create_example'](root)
    assert len(expected) == 5 and (root / 'README.txt').is_file()
    for name in expected:
        raw = (root / f'{name}-queue-plan.json').read_bytes()
        report = module.review_queue(raw, (root / f'{name}-routing-plan.json').read_bytes(),
                                     load_json(root / f'{name}-evaluation.json'), load_json(root / f'{name}-work-items.json'),
                                     queue_plan_sha256=digest(raw))
        assert report == load_json(root / f'{name}-report.json')
