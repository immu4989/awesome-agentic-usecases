"""Five finite-queue what-if contrasts; no actual human review or staffing recommendation."""

import argparse
from copy import deepcopy
from pathlib import Path
import runpy

from aau_harness.agent_bom import digest, rendered, write_json
from aau_harness.eval_routing import _route, review_routing
from aau_harness.review_queue import review_queue
from aau_harness.queue_pack import create_pack, verify_pack


def example_inputs():
    example = runpy.run_path(str(Path(__file__).with_name('routing_workload.py')))
    routing_plan, source = example['example_inputs']()['group-hidden-failure']
    raw = rendered(routing_plan)
    routing = review_routing(raw, source, plan_sha256=digest(raw))
    items = {'format_version': 'aau-human-review-work-items/1.0', 'items': [
        {'scenario_id': row['scenario_id'], 'repeat': row['repeat'], 'arrival_s': 0, 'service_s': 3, 'deadline_s': 6}
        for row in routing['observations'] if _route(row, 0) != 'automated']}
    queue = {'plan_version': 'aau-human-review-queue-plan/1.0', 'routing_plan_sha256': digest(raw),
             'threshold': 0, 'horizon_s': 12, 'timing_basis': 'synthetic',
             'timing_scope': 'Constructed 12-second arithmetic example; not observed arrivals, real human timings, or staffing evidence.',
             'initial_state': 'empty_queue_idle_slots_at_zero',
             'workers': [{'worker_id': 'review-slot-a', 'windows': [{'start_s': 0, 'end_s': 12}]}]}
    examples = {}
    for name in ('one-slot', 'two-slots', 'break-window', 'blocked-head', 'unknown-deadlines'):
        plan, timing = deepcopy(queue), deepcopy(items)
        if name == 'two-slots':
            plan['workers'].append({'worker_id': 'review-slot-b', 'windows': [{'start_s': 0, 'end_s': 12}]})
        elif name == 'break-window':
            plan['workers'][0]['windows'] = [{'start_s': 0, 'end_s': 4}, {'start_s': 8, 'end_s': 12}]
        elif name == 'blocked-head':
            timing['items'][0]['service_s'] = 20
        elif name == 'unknown-deadlines':
            plan['workers'][0]['windows'] = [{'start_s': 0, 'end_s': 3}]
            for row in timing['items']:
                row['deadline_s'] = None
        examples[name] = plan, raw, source, timing
    return examples


def create_example(directory):
    directory.mkdir(parents=True, exist_ok=False)
    expected = {'one-slot': (4, 0, 2), 'two-slots': (4, 0, 0), 'break-window': (2, 2, 3),
                'blocked-head': (0, 4, 4), 'unknown-deadlines': (1, 3, 0)}
    commands, summaries = [], []
    for name, (plan, routing_raw, source, items) in example_inputs().items():
        raw = rendered(plan)
        report = review_queue(raw, routing_raw, source, items, queue_plan_sha256=digest(raw))
        counts = report['counts']
        if tuple(counts[key] for key in ('scheduled', 'not_scheduled', 'known_deadline_failures')) != expected[name]:
            raise RuntimeError('synthetic queue outcome differs from its declared contrast')
        for suffix, value in (('queue-plan', plan), ('routing-plan', report['routing_review']['plan']),
                              ('evaluation', source), ('work-items', items), ('report', report)):
            write_json(value, directory / f'{name}-{suffix}.json')
        pack = directory / f'{name}-pack'
        create_pack(raw, routing_raw, source, items, pack, queue_plan_sha256=digest(raw))
        if verify_pack(pack, queue_plan_sha256=digest(raw)) != report:
            raise RuntimeError('source-retaining queue pack differs from its original replay')
        commands.append(f'aau queue-pack verify {name}-pack --queue-plan-sha256 {digest(raw)}')
        commands.append(f'aau review-queue {name}-queue-plan.json {name}-routing-plan.json {name}-evaluation.json '
                        f'{name}-work-items.json --queue-plan-sha256 {digest(raw)} --verify {name}-report.json')
        summaries.append(f"{name}: scheduled={counts['scheduled']}, unscheduled={counts['not_scheduled']}, "
                         f"declared-deadline failures={counts['known_deadline_failures']}, "
                         f"unknown/unresolved deadlines={counts['deadline_unknown_or_unresolved']}.")
    guide = '''AAU finite human-review queue replay — constructed, not production evidence

The same four hypothetical referrals from a complete routing review are retained in every example.
Each normally needs three synthetic seconds of uninterrupted review; all arrive at zero, with a
declared completion deadline of six seconds. These are arithmetic fixtures, not realistic human
service-time estimates or legal deadlines. No human study or model execution took place.

one-slot finishes at 3, 6, 9, 12, so two declared deadlines are missed.
two-slots finishes at 3, 3, 6, 6 under the changed supplied capacity. This is NOT a staffing recommendation.
break-window forbids work during [4,8), schedules only two items, and retains two unscheduled items.
blocked-head cannot fit its first 20-second item in any available window; later shorter items do NOT bypass it.
unknown-deadlines schedules one and leaves three waiting; no deadline is declared, so no deadline success is inferred.

Start and finish times are simulated service, not correct human review or resolved cases. Every
recorded routing failure remains in the nested report, including the automated-path failures.
The strict FIFO model starts empty; all slots are interchangeable; there is no preemption, skill
matching, urgency, overtime, abandonment, or unreported outside work. Availability must exclude
other commitments. A different production policy requires separate modeling and validation.

All valid diagnostics exit 0 even when work remains or deadlines fail. No deployment gate exists.
Protect the queue-plan hash independently: it binds both the routing-plan bytes and one declared
threshold. Keep both plans, the full evaluation, all timing inputs, and the report. Inspect identifiers,
times, and hashes before sharing. These files are not sanitized or approved for publication.
Each *-pack folder retains the full sources and a readable review.html with timeline and tables.
Verify it first, then open the local page; no external assets or scripts are required.

From this directory with a matching trusted harness:

''' + '\n'.join(commands) + '\n\nExpected constructed outcomes:\n\n' + '\n'.join(summaries) + '\n'
    (directory / 'README.txt').write_text(guide, encoding='utf-8')
    print('Created five finite-queue contrasts with exact referral census and unknown human resolution.')
    return expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
