"""Synthetic planning examples without data collection or inferred real failure rates."""

from copy import deepcopy

from .agent_bom import digest, rendered
from .eval_design import create_design, verify_design


def demo_plan():
    return {'plan_version': 'aau-evaluation-design-plan/1.0',
            'purpose': 'Synthetic evaluation planning; no actual system or agency study is represented.',
            'sampling_design': 'hypothetical_iid_fixed_horizon',
            'sampling_basis': 'Hypothetical IID scenario bundles under fixed scoring and repeat rules; not verified.',
            'candidate_count': 1, 'repeats_per_scenario': 2, 'family_error_probability': '0.05',
            'minimum_qualification_probability': '0.8', 'maximum_scenarios_per_scope': 500,
            'scopes': [{'scope_id': 'overall', 'unacceptable_failure_probability': '0.05',
                        'assumed_failure_probability': '0.01'}]}


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite evaluation-design demo')
    directory.mkdir(parents=True, exist_ok=False)
    plan = demo_plan()
    limited = deepcopy(plan)
    limited['maximum_scenarios_per_scope'] = 100
    family = deepcopy(plan)
    family['candidate_count'] = 3
    family['scopes'].append({'scope_id': 'assisted_path', 'unacceptable_failure_probability': '0.05',
                             'assumed_failure_probability': '0.01'})
    fixed = deepcopy(plan)
    fixed['sampling_design'] = 'fixed_benchmark'
    commands = []
    for name, current in (('planned', plan), ('limited', limited), ('family', family), ('fixed-benchmark', fixed)):
        raw = rendered(current)
        pin = digest(raw)
        report = create_design(raw, directory / name, plan_sha256=pin)
        if verify_design(directory / name, plan_sha256=pin) != report:
            raise ValueError('design demo replay mismatch')
        commands.append(f'aau evaluation-design verify {name} --plan-sha256 {pin}')
    (directory / 'README.txt').write_text(
        'Synthetic design planning: open each review.html locally. No outcomes were collected.\n'
        'planned: zero failures alone need not deliver the requested qualification probability.\n'
        'limited: a 100-bundle ceiling cannot meet both specified probabilities.\n'
        'family: three candidates and two scopes retain all six error allocations.\n'
        'fixed-benchmark: population planning is withheld.\n'
        'All valid diagnostics exit 0, including incomplete designs; none is approval.\n'
        'Pins below belong only to these generated synthetic examples.\n\n' + '\n'.join(commands) + '\n', encoding='utf-8')
