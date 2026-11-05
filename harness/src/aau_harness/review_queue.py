"""Replay a declared finite human-review queue without forecasting staffing or claiming resolution."""

import argparse
from pathlib import Path
import sys

from .agent_bom import MAX_JSON_BYTES, _parse_json, digest, load_json, rendered, write_json
from .eval_routing import _bounded, _probability, _route, review_routing, validate_plan as validate_routing_plan
from .inspect_pack import InspectionError
from .intake_review import _read_request, _sha


MAX_TIME = 31_536_000
BOUNDARY = (
    'Deterministic finite-queue what-if replay, not an observed human study, operational scheduler, '
    'staffing recommendation, employee assessment, service forecast, legal deadline calculation, or '
    'deployment approval. All times are supplied integer seconds from a common declared origin, not '
    'wall-clock timestamps inferred from repeat IDs. Timing basis is a declaration, not authentication. '
    'The model starts with an empty queue and idle interchangeable capacity slots at zero; availability '
    'windows must exclude other commitments. Include every hypothetical deferred observation exactly '
    'once. Required and unknown review flags cannot disappear. Strict FIFO orders arrivals, then scenario '
    'ID and repeat; lexical ties do not express urgency, rights, or fairness. Nonpreemptive service must '
    'fit wholly inside one supplied availability window. No overtime, splitting, abandonment, retries, '
    'priority, skill matching, or future arrivals are inferred. If the head cannot fit any remaining '
    'window, later jobs remain blocked even if shorter jobs could fit. Scheduled service completion is '
    'not correct review, a resolved case, a delivered benefit, or recovered harm. All original routing '
    'failures remain visible. Unscheduled waits remain separate from scheduled waits; undeclared '
    'deadlines remain unknown. An unmet declared deadline is a model result, not a legal determination. '
    'No threshold, staffing level, or approval is selected. The independently pinned queue plan binds '
    'the exact routing-plan bytes and one of its declared thresholds; pins are not reviewer authority '
    'or preregistration. Keep both plans, full evaluation, timing inputs, and report with a matching '
    'trusted harness. Capture is not an atomic snapshot. Reports include identifiers, times, scores, '
    'and hashes and are not sanitized or approved for sharing. No models, adapters, human actions, '
    'subprocesses, uploads, or network calls execute.'
)


def _time(value, *, positive=False):
    return type(value) is int and (1 if positive else 0) <= value <= MAX_TIME


def validate_plan(raw, expected_sha256):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise InspectionError('queue_plan_bytes_invalid_or_oversized')
    if not _sha(expected_sha256) or digest(raw) != expected_sha256:
        raise InspectionError('queue_plan_byte_pin_mismatch')
    plan = _parse_json(raw)
    fields = {'plan_version', 'routing_plan_sha256', 'threshold', 'horizon_s', 'timing_basis',
              'timing_scope', 'initial_state', 'workers'}
    if (not isinstance(plan, dict) or set(plan) != fields or plan['plan_version'] != 'aau-human-review-queue-plan/1.0'
            or not _sha(plan['routing_plan_sha256']) or not _probability(plan['threshold'])
            or not _time(plan['horizon_s'], positive=True)
            or plan['timing_basis'] not in ('synthetic', 'supplied_measurements', 'declared_estimates')
            or plan['initial_state'] != 'empty_queue_idle_slots_at_zero'
            or not isinstance(plan['timing_scope'], str) or not plan['timing_scope'].strip() or len(plan['timing_scope']) > 2000):
        raise InspectionError('queue_plan_contract_invalid')
    if not isinstance(plan['workers'], list) or len(plan['workers']) > 20:
        raise InspectionError('queue_worker_census_invalid')
    seen = set()
    for worker in plan['workers']:
        if not isinstance(worker, dict) or set(worker) != {'worker_id', 'windows'}:
            raise InspectionError('queue_worker_fields_invalid')
        name, windows = worker['worker_id'], worker['windows']
        if not isinstance(name, str) or not name.strip() or len(name) > 120 or name in seen:
            raise InspectionError('queue_worker_id_invalid')
        seen.add(name)
        if not isinstance(windows, list) or not 1 <= len(windows) <= 20:
            raise InspectionError('queue_windows_invalid')
        previous = 0
        for window in windows:
            if (not isinstance(window, dict) or set(window) != {'start_s', 'end_s'}
                    or not _time(window['start_s']) or not _time(window['end_s'], positive=True)
                    or not previous <= window['start_s'] < window['end_s'] <= plan['horizon_s']):
                raise InspectionError('queue_windows_must_be_ordered_disjoint_and_bounded')
            previous = window['end_s']
    return plan


def _controls(queue_raw, routing_raw, pin):
    plan = validate_plan(queue_raw, pin)
    routing_plan, _ = validate_routing_plan(routing_raw, plan['routing_plan_sha256'])
    if plan['threshold'] not in routing_plan['thresholds']:
        raise InspectionError('queue_threshold_not_declared_in_routing_plan')
    return plan


def _items(source, deferred, horizon):
    _bounded(source)
    if (not isinstance(source, dict) or set(source) != {'format_version', 'items'}
            or source['format_version'] != 'aau-human-review-work-items/1.0'
            or not isinstance(source['items'], list) or len(source['items']) > 10000):
        raise InspectionError('queue_work_items_invalid')
    seen, items = set(), []
    for row in source['items']:
        if (not isinstance(row, dict) or set(row) != {'scenario_id', 'repeat', 'arrival_s', 'service_s', 'deadline_s'}
                or not isinstance(row['scenario_id'], str) or type(row['repeat']) is not int
                or not _time(row['arrival_s']) or row['arrival_s'] >= horizon
                or not _time(row['service_s'], positive=True)
                or (row['deadline_s'] is not None and not _time(row['deadline_s']))):
            raise InspectionError('queue_work_item_fields_invalid')
        key = row['scenario_id'], row['repeat']
        if key in seen or key not in deferred:
            raise InspectionError('queue_work_item_census_mismatch')
        seen.add(key)
        items.append(dict(row))
    if seen != set(deferred):
        raise InspectionError('queue_work_item_census_mismatch')
    return sorted(items, key=lambda row: (row['arrival_s'], row['scenario_id'], row['repeat']))


def _slot(worker, ready, duration, free_at):
    for window in worker['windows']:
        start = max(ready, free_at, window['start_s'])
        if start + duration <= window['end_s']:
            return start, worker['worker_id'], start + duration
    return None


def _deadline(job, end, horizon):
    if job['deadline_s'] is None:
        return 'not_declared'
    if end is not None:
        return 'within_declared_deadline' if end <= job['deadline_s'] else 'after_declared_deadline'
    return 'not_completed_by_declared_deadline' if job['deadline_s'] <= horizon else 'beyond_horizon_unresolved'


def _schedule(plan, items, deferred):
    workers = sorted(plan['workers'], key=lambda row: row['worker_id'])
    free = {worker['worker_id']: 0 for worker in workers}
    jobs, last_start, blocked = [], 0, False
    for row in items:
        ready = max(row['arrival_s'], last_start)  # Later jobs never start before the earlier FIFO head.
        options = [] if blocked else [option for worker in workers
                                      if (option := _slot(worker, ready, row['service_s'], free[worker['worker_id']])) is not None]
        start = end = worker_id = reason = None
        if options:
            start, worker_id, end = min(options)
            free[worker_id], last_start = end, start
        else:
            reason = 'blocked_by_earlier_unschedulable_item' if blocked else 'no_complete_service_slot'
            blocked = True
        observation = deferred[row['scenario_id'], row['repeat']]
        jobs.append({**row, 'status': 'scheduled' if options else 'not_scheduled', 'reason': reason,
                     'worker_id': worker_id, 'start_s': start, 'finish_s': end,
                     'scheduled_wait_s': start - row['arrival_s'] if start is not None else None,
                     'unserved_wait_at_horizon_s': plan['horizon_s'] - row['arrival_s'] if start is None else None,
                     'deadline_status': _deadline(row, end, plan['horizon_s']),
                     'deferral_reason': _route(observation, plan['threshold']),
                     'recorded_jointly_passed': observation['jointly_passed'],
                     'recorded_failed_criteria': observation['failed_criteria'], 'human_resolution': 'not_measured'})
    return jobs


def _timeline(jobs, horizon):
    events = {0: [0, 0], horizon: [0, 0]}
    for row in jobs:
        events.setdefault(row['arrival_s'], [0, 0])[0] += 1
        if row['start_s'] is not None:
            event = events.setdefault(row['start_s'], [0, 0])
            event[0] -= 1
            event[1] += 1
            events.setdefault(row['finish_s'], [0, 0])[1] -= 1
    timeline, waiting, active = [], 0, 0
    for time, (waiting_change, active_change) in sorted(events.items()):
        waiting += waiting_change
        active += active_change
        timeline.append({'time_s': time, 'waiting_after_events': waiting, 'in_service_after_events': active})
    return timeline


def review_queue(queue_raw, routing_raw, evaluation, work_items, *, queue_plan_sha256):
    plan = _controls(queue_raw, routing_raw, queue_plan_sha256)
    routing = review_routing(routing_raw, evaluation, plan_sha256=plan['routing_plan_sha256'])
    deferred = {(row['scenario_id'], row['repeat']): row for row in routing['observations'] if _route(row, plan['threshold']) != 'automated'}
    items = _items(work_items, deferred, plan['horizon_s'])
    jobs = _schedule(plan, items, deferred)
    timeline = _timeline(jobs, plan['horizon_s'])
    scheduled = [row for row in jobs if row['status'] == 'scheduled']
    unscheduled = [row for row in jobs if row['status'] == 'not_scheduled']
    workers = []
    for worker in sorted(plan['workers'], key=lambda row: row['worker_id']):
        assigned = [row for row in scheduled if row['worker_id'] == worker['worker_id']]
        workers.append({'worker_id': worker['worker_id'], 'declared_available_s': sum(w['end_s'] - w['start_s'] for w in worker['windows']),
                        'scheduled_service_s': sum(row['service_s'] for row in assigned), 'scheduled_job_count': len(assigned)})
    report = {'report_version': 'aau-human-review-queue-replay/1.0', 'status': 'finite_queue_diagnostic',
              'queue_plan_file_sha256': queue_plan_sha256, 'work_items_sha256': digest(work_items), 'plan': plan,
              'routing_review': routing, 'jobs': jobs, 'workers': workers, 'timeline': timeline,
              'counts': {'deferred_observations': len(jobs), 'scheduled': len(scheduled), 'not_scheduled': len(unscheduled),
                         'declared_deadlines': sum(row['deadline_s'] is not None for row in jobs),
                         'known_deadline_failures': sum(row['deadline_status'] in ('after_declared_deadline', 'not_completed_by_declared_deadline') for row in jobs),
                         'deadline_unknown_or_unresolved': sum(row['deadline_status'] in ('not_declared', 'beyond_horizon_unresolved') for row in jobs)},
              'maximum_scheduled_wait_s': max((row['scheduled_wait_s'] for row in scheduled), default=None),
              'maximum_unserved_wait_at_horizon_s': max((row['unserved_wait_at_horizon_s'] for row in unscheduled), default=None),
              'maximum_waiting_after_same_time_events': max(row['waiting_after_events'] for row in timeline),
              'human_resolution_measured': False,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
                                        ('review_queue.py', 'eval_routing.py', 'agent_bom.py')}, 'boundary': BOUNDARY}
    _bounded(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau review-queue', description=__doc__)
    parser.add_argument('queue_plan', type=Path)
    parser.add_argument('routing_plan', type=Path)
    parser.add_argument('evaluation', type=Path)
    parser.add_argument('work_items', type=Path)
    parser.add_argument('--queue-plan-sha256', required=True, help='independently controlled queue-plan byte hash')
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        queue_raw, routing_raw = _read_request(args.queue_plan), _read_request(args.routing_plan)
        _controls(queue_raw, routing_raw, args.queue_plan_sha256)  # Both control pins before evaluation/timing reads.
        report = review_queue(queue_raw, routing_raw, load_json(args.evaluation), load_json(args.work_items),
                              queue_plan_sha256=args.queue_plan_sha256)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise InspectionError('queue_report_does_not_recompute')
        else:
            write_json(report, args.out)
        print(f"Finite queue replay: {report['counts']['scheduled']} scheduled; {report['counts']['not_scheduled']} unscheduled; "
              f"{report['counts']['known_deadline_failures']} declared-deadline failures. Human resolution not measured.")
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'queue_input_or_output_rejected'
        print(f'error: {reason}; no verified queue diagnostic produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
