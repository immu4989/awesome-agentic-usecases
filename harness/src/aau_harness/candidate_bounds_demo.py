"""Construct an offline multiple-candidate uncertainty lesson; not sampled production evidence."""

from copy import deepcopy

from .agent_bom import digest, rendered
from .eval_candidate_bounds import create_candidate_pack, verify_candidate_pack
from .eval_failure_demo import example_inputs as failure_examples
from .eval_import import import_observations
from .evaluation_context import VERSION


def example_inputs():
    fixed, evaluation = failure_examples()['more-scenarios']
    plan = {**fixed, 'plan_version': 'aau-candidate-bound-plan/1.0',
            'candidates': [{'candidate_id': name, 'config_sha256': digest(name.encode())} for name in ('candidate-a', 'candidate-b')],
            'scenario_sha256': {s: digest(s.encode()) for s in fixed['scenario_ids']},
            'scoring_sha256': {'synthetic-scorer': digest(b'synthetic scorer declaration')}}
    sources = {}
    for candidate in plan['candidates']:
        source = deepcopy(evaluation)
        source['evaluation_context'] = {'context_version': VERSION, 'config_sha256': candidate['config_sha256'],
                                        'scenario_sha256': plan['scenario_sha256'], 'scoring_sha256': plan['scoring_sha256']}
        sources[candidate['candidate_id']] = rendered(source)
    return plan, sources


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite candidate-bound demo')
    plan, sources = example_inputs()
    fixed = {**plan, 'sampling_design': 'fixed_benchmark'}
    # Retain a failure in the first repeat; later passing repeats cannot erase it.
    ids = plan['scenario_ids']
    recording = {'format_version': 'aau-recorded-observations/1.0', 'source_label': 'Synthetic candidate-family failure example',
                 'scenario_ids': ids, 'n_repeats': plan['n_repeats'],
                 'observations': [{'scenario_id': s, 'repeat': r, 'metrics': {'completion': 1, 'unauthorized': int(i == 0 and r == 0)}}
                                  for i, s in enumerate(ids) for r in range(plan['n_repeats'])]}
    failed = import_observations(recording)
    failed['evaluation_context'] = {'context_version': VERSION, 'config_sha256': plan['candidates'][1]['config_sha256'],
                                    'scenario_sha256': plan['scenario_sha256'], 'scoring_sha256': plan['scoring_sha256']}
    examples = {'pending': (plan, {'candidate-a': sources['candidate-a']}), 'complete': (plan, sources),
                'fixed-benchmark': (fixed, sources), 'earlier-failure': (plan, {**sources, 'candidate-b': rendered(failed)})}
    directory.mkdir(parents=True, exist_ok=False)
    commands = []
    for name, (approved, submitted) in examples.items():
        raw = rendered(approved)
        pin = digest(raw)
        create_candidate_pack(raw, submitted, directory / name, plan_sha256=pin)
        verify_candidate_pack(directory / name, plan_sha256=pin)
        commands.append(f'aau candidate-bounds verify {name} --plan-sha256 {pin}')
    guide = ['# One uncertainty budget, every planned candidate', '',
             'Synthetic arithmetic only. No real sampling, model execution, or demonstrated public benefit.', '',
             'Two candidates, 60 constructed scenario bundles each, four repeats, and a hypothetical 95% family confidence.',
             'Zero failures gives an upper bound near 4.87% if only one candidate had been planned, but near 5.96%',
             'when both candidates are in this family. The declared 5% limit is therefore not met in this example.',
             'Do not narrow the family after seeing results. These are not estimates of any real system.', '',
             '- pending: candidate-b is missing; candidate-a still uses the complete family allocation.',
             '- complete: both candidates present; the candidate-a bound does not change.',
             '- fixed-benchmark: perfect supplied scores, but population inference is withheld.',
             '- earlier-failure: candidate-b failed one early repeat; the entire scenario bundle remains failed.', '',
             'Open each review.html offline. Missing counts are null, not zero. The packet retains exact input bytes.',
             'From this directory with the matching trusted harness (example-only pins):', '', '```bash', *commands, '```', '',
             'Exit 0 verifies a diagnostic, not a passing policy or acceptable system. Retain independent plan pins for real work.',
             'A predeclared finite family is not permission for adaptive candidate tuning, optional stopping, or extra looks.', '']
    with (directory / 'README.md').open('xb') as stream:
        stream.write('\n'.join(guide).encode())
