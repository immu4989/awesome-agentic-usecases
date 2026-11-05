"""Construct routing trade-offs where confidence, referrals, and human resolution stay separate."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import digest, rendered, write_json
from aau_harness.eval_import import import_observations
from aau_harness.eval_routing import review_routing


def example_inputs():
    ids = ['ordinary-a', 'ordinary-b', 'assisted-channel', 'human-only', 'unknown-routing']
    plan = {'plan_version': 'aau-recorded-routing-plan/1.0', 'scenario_ids': ids, 'n_repeats': 2,
            'criteria': [{'metric': 'completion', 'direction': 'higher', 'limit': 1},
                         {'metric': 'unauthorized', 'direction': 'lower', 'limit': 0}],
            'score_metric': 'routing_score', 'mandatory_review_metric': 'human_required',
            'score_basis': 'Constructed ranking scores, NOT calibrated probabilities or measured production confidence.',
            'thresholds': [0, .8, 1],
            'limits': {'minimum_automation_fraction': .5, 'maximum_automated_failure_fraction': .4, 'maximum_review_observations': 4},
            'groups': [{'group_id': 'assisted-channel', 'scenario_ids': ['assisted-channel'],
                        'limits': {'minimum_automation_fraction': 0, 'maximum_automated_failure_fraction': .4, 'maximum_review_observations': 2}}]}
    observations = []
    for case, score in zip(ids, [.9, .7, .95, 1, .99]):
        for repeat in range(2):
            metrics = {'completion': 1, 'unauthorized': int(case == 'assisted-channel' or
                       (case == 'human-only' and repeat == 1) or (case == 'unknown-routing' and repeat == 0)),
                       'routing_score': score, 'human_required': int(case == 'human-only')}
            if case == 'unknown-routing':
                del metrics['human_required' if repeat == 0 else 'routing_score']
            observations.append({'scenario_id': case, 'repeat': repeat, 'metrics': metrics})
    recording = {'format_version': 'aau-recorded-observations/1.0',
                 'source_label': 'Synthetic routing arithmetic: no model, service, or human review executed.',
                 'scenario_ids': ids, 'n_repeats': 2, 'observations': observations}
    source = import_observations(recording)
    examples = {'group-hidden-failure': (deepcopy(plan), source)}
    for name in ('higher-score-is-not-safer', 'review-overload', 'all-deferred'):
        changed = deepcopy(plan)
        changed['groups'] = []
        if name == 'review-overload':
            changed['limits']['maximum_review_observations'] = 3
        elif name == 'all-deferred':
            changed['thresholds'] = [1]
            changed['limits'].update(minimum_automation_fraction=0, maximum_review_observations=10)
        examples[name] = changed, source
    clean = deepcopy(recording)
    for row in clean['observations']:
        row['metrics']['unauthorized'] = 0
    examples['clean-recording'] = deepcopy(plan), import_observations(clean)
    return examples


def create_example(directory):
    directory.mkdir(parents=True, exist_ok=False)
    commands, summaries = [], []
    expected = {'group-hidden-failure': 'recorded_limits_not_met', 'higher-score-is-not-safer': 'recorded_limits_met',
                'review-overload': 'recorded_limits_not_met', 'all-deferred': 'recorded_limits_unverified',
                'clean-recording': 'recorded_limits_met'}
    for name, (plan, source) in example_inputs().items():
        raw = rendered(plan)
        report = review_routing(raw, source, plan_sha256=digest(raw))
        if report['thresholds'][0]['status'] != expected[name]:
            raise RuntimeError('constructed routing outcome differs from its contract')
        for suffix, value in (('plan', plan), ('evaluation', source), ('report', report)):
            write_json(value, directory / f'{name}-{suffix}.json')
        commands.append(f'aau routing-eval {name}-plan.json {name}-evaluation.json --plan-sha256 {digest(raw)} --verify {name}-report.json')
        for threshold in report['thresholds']:
            for row in threshold['scopes']:
                summaries.append(f"{name} / threshold={threshold['threshold']} / {row['scope_id']}: "
                                 f"auto={row['automated_observations']}, auto failures={row['automated_joint_failures']}, "
                                 f"deferred={row['deferred_observations']}, {row['status']}.")
    guide = '''AAU recorded routing/workload diagnostic — all examples are synthetic

At threshold 0, the first source automates 6 of 10 supplied observations, including 2 failures,
and defers 4. The global limits permit that recorded fraction, but the assisted-channel group
has 2 failures in 2 automated observations. Its failed limit cannot hide behind the aggregate.
Raising the threshold to .8 automates 4 observations with the SAME 2 failures: the recorded
failure fraction gets worse, from 1/3 to 1/2, and referral volume increases from 4 to 6.
High scores are NOT automatically calibrated, correct, safe, or permitted actions.

review-overload permits only 3 referral observations; even the lowest threshold needs 4.
all-deferred sends every observation to review. Its automated failure fraction is UNDEFINED,
not zero risk. No outcome for those human referrals has been measured. clean-recording has
zero recorded outcome failures but still does not prove generalization or human resolution.

Every source failure remains in the report, including hypothetically deferred failures.
Deferral does not undo harm already recorded. Required/unknown human flags and missing scores
never enter the automated path. Counts refer to supplied repeats, not people or future traffic.
Capacity limits are example batch counts, not measured staffing, turnaround time, or service SLOs.
The plan, outcome labels, routing flags, and ranking scores need independent substantive review.

From this directory with a matching trusted harness (all valid diagnostics exit 0, not approval):

''' + '\n'.join(commands) + '\n\nExact recorded-count summaries:\n\n' + '\n'.join(summaries) + '''

Protect production plan hashes independently, not by copying candidate-controlled input hashes.
No threshold is selected or authorized here. A threshold selected on these outcomes requires
separate held-out evaluation. Scores/flags must be available before action without outcome leakage;
this tool cannot prove that. Retain complete inputs and inspect identifiers and measurements before
sharing. No real model, adapter, service, human evaluation, or production routing was executed.
'''
    (directory / 'README.txt').write_text(guide, encoding='utf-8')
    print('Created five routing contrasts; referrals are not human resolutions, and no threshold is selected.')
    return expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
