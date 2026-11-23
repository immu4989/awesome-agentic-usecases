"""Fixed synthetic paired-comparison examples; no live models or sampled population evidence."""

from copy import deepcopy

from .agent_bom import digest, rendered
from .eval_import import import_observations
from .eval_paired import create_paired_pack, verify_paired_pack
from .evaluation_context import VERSION


def example_inputs():
    ids = [f'case-{i:02}' for i in range(12)]
    plan = {'plan_version': 'aau-paired-candidate-plan/1.0', 'scenario_ids': ids, 'n_repeats': 2,
            'criteria': [{'metric': 'completion', 'direction': 'higher', 'limit': 1},
                         {'metric': 'unauthorized', 'direction': 'lower', 'limit': 0}],
            'groups': [{'group_id': 'assisted-path', 'scenario_ids': ids[10:]}],
            'sampling_design': 'declared_iid_fixed_horizon',
            'sampling_basis': 'Constructed arithmetic lesson, not sampled population evidence. IID is hypothetical here.',
            'family_significance_level': 0.05,
            'baseline': {'candidate_id': 'baseline-system', 'config_sha256': digest(b'baseline configuration')},
            'candidate': {'candidate_id': 'candidate-system', 'config_sha256': digest(b'candidate configuration')},
            'scenario_sha256': {s: digest(s.encode()) for s in ids},
            'scoring_sha256': {'synthetic-scorer': digest(b'constructed scorer')}}
    sources = {}
    for role in ('baseline', 'candidate'):
        recording = {'format_version': 'aau-recorded-observations/1.0', 'source_label': 'Constructed paired-review demo',
                     'scenario_ids': ids, 'n_repeats': 2,
                     'observations': [{'scenario_id': s, 'repeat': repeat,
                         'metrics': {'completion': 1, 'unauthorized': int(repeat == 0 and
                                     (i < 10 if role == 'baseline' else i == 10))}}
                         for i, s in enumerate(ids) for repeat in range(2)]}
        source = import_observations(recording)
        source['evaluation_context'] = {'context_version': VERSION, 'config_sha256': plan[role]['config_sha256'],
                                        'scenario_sha256': plan['scenario_sha256'], 'scoring_sha256': plan['scoring_sha256']}
        sources[role] = source
    return plan, sources['baseline'], sources['candidate']


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite paired-review demo')
    plan, baseline, candidate = example_inputs()
    same = deepcopy(baseline)
    same['evaluation_context']['config_sha256'] = plan['candidate']['config_sha256']
    reversed_plan = {**plan, 'baseline': plan['candidate'], 'candidate': plan['baseline']}
    examples = {'net-gain-with-regression': (plan, baseline, candidate),
                'fixed-benchmark': ({**plan, 'sampling_design': 'fixed_benchmark'}, baseline, candidate),
                'same-recorded-outcomes': (plan, baseline, same),
                'reversed-comparison': (reversed_plan, candidate, baseline)}
    directory.mkdir(parents=True, exist_ok=False)
    commands = []
    for name, (approved, old, new) in examples.items():
        raw = rendered(approved)
        pin = digest(raw)
        create_paired_pack(raw, rendered(old), rendered(new), directory / name, plan_sha256=pin)
        verify_paired_pack(directory / name, plan_sha256=pin)
        commands.append(f'aau paired-review verify {name} --plan-sha256 {pin}')
    guide = ['# Better overall does not erase a newly failed case', '',
             'Synthetic mechanism checks only: no live model, true sampling, or demonstrated public benefit.', '',
             'Each of 12 paired scenario bundles includes two repeats. The candidate corrects ten baseline failures',
             'but newly fails one assisted-path case. Both systems pass the last case. All later repeats pass:',
             'earlier failures still count, and 24 repeats never become 24 independent pairs.', '',
             '- net-gain-with-regression: 10 improvements, one regression; raw exact p = 0.01171875.',
             '  Two predeclared scopes give adjusted p = 0.0234375 overall. The assisted-path regression stays visible.',
             '- fixed-benchmark: identical counts; population inference and all p-values are withheld.',
             '- same-recorded-outcomes: zero discordance gives p = 1, not proof of equivalence or safety.',
             '- reversed-comparison: improvements and regressions swap; the two-sided p-value does not.', '',
             'Open each review.html offline. report.json retains exact rational p-values and failed repeats.',
             'From this directory, with the matching trusted harness (example-only pins):', '', '```bash',
             *commands, '```', '',
             'Exit 0 means the diagnostic recomputes, not that a system should be purchased or deployed.',
             'Real use needs independently controlled plan pins, appropriate matched sampling, valid scoring,',
             'absolute risk and practical-importance assessment, and separate authorized human decisions.', '']
    with (directory / 'README.md').open('xb') as stream:
        stream.write('\n'.join(guide).encode())
