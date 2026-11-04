"""Create four complete synthetic failure-bound reviewer packs without repository fixtures."""

import argparse
from pathlib import Path
import sys

from .agent_bom import AgentBomError
from .eval_failure_pack import create_failure_bound_pack, verify_failure_bound_pack
from .runner import ScenarioResult, run_eval


EXPECTED = {'fixed-benchmark': 'population_inference_withheld',
            'few-scenarios': 'conditional_bounds_exceed_limits',
            'more-scenarios': 'conditional_bounds_within_limits',
            'small-group': 'conditional_bounds_exceed_limits'}


def example_inputs():
    examples = {}
    for name, count, design in [('fixed-benchmark', 20, 'fixed_benchmark'),
                                ('few-scenarios', 20, 'declared_iid_fixed_horizon'),
                                ('more-scenarios', 60, 'declared_iid_fixed_horizon'),
                                ('small-group', 100, 'declared_iid_fixed_horizon')]:
        ids = [f'synthetic-service-{index:03d}' for index in range(count)]
        plan = {'plan_version': 'aau-failure-bound-plan/1.0', 'scenario_ids': ids, 'n_repeats': 4,
                'criteria': [{'metric': 'completion', 'direction': 'higher', 'limit': 1},
                             {'metric': 'unauthorized', 'direction': 'lower', 'limit': 0}],
                'sampling_design': design,
                'sampling_basis': 'Constructed arithmetic lesson, NOT sampled production evidence. '
                                  'IID mode illustrates a hypothetical assumption only; no real reliability claim.',
                'confidence_level': .95, 'maximum_failure_probability': .05, 'groups': []}
        if name == 'small-group':
            plan['groups'] = [{'group_id': 'synthetic-assisted-channel', 'scenario_ids': ids[:10],
                               'maximum_failure_probability': .05}]
        source = run_eval(ids, lambda scenario, repeat: ScenarioResult(
            scenario, repeat, {'completion': 1, 'unauthorized': 0}, 0, .1, 0), repeats=4).as_dict()
        examples[name] = plan, source
    return examples



def create_demo(directory: Path):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite a failure-bound walkthrough')
    directory.mkdir(parents=True, exist_ok=False)
    reports = {}
    for name, (plan, source) in example_inputs().items():
        create_failure_bound_pack(plan, source, directory / name)
        report = verify_failure_bound_pack(directory / name)
        if report['status'] != EXPECTED[name]:
            raise AgentBomError('synthetic failure-bound outcome differs from its contract')
        reports[name] = report
    summaries = []
    for name, report in reports.items():
        for scope in report['scopes']:
            bound = scope['one_sided_upper_failure_bound']
            label = 'withheld' if bound is None else f'{bound:.3%} (conditional only)'
            summaries.append(f'{name} / {scope["scope_id"]}: {scope["scenario_count"]} bundles; upper bound {label}; {scope["status"]}.')
    guide = '''Synthetic failure-bound lesson — no real agents or sampled users.

Open NAME/review.html for any of the four folders. The page is script-free,
works offline, and retains readable charts and exact values with its sources.
All scores, costs, and timings are constructed, not measured service outcomes.

''' + '\n'.join(summaries) + '''

More repeats do not increase the independent scenario count. A small group can
have insufficient evidence even when the overall conditional bound meets its
limit. Fixed benchmark results are not automatically population evidence.

Using the same installed harness, verify each NAME before relying on its page:
  aau failure-bound-pack verify NAME
The original standalone diagnostic remains available:
  aau failure-bound-eval NAME/plan.json NAME/evaluation.json --verify NAME/report.json

All successful verifications exit 0, including withheld inference and exceeded
limits. Exit 0 is never deployment approval. Keep all five files in each folder.
No fixture establishes IID sampling, a real population risk bound, or an agent
repair. Do not copy these sampling declarations or numerical limits into a real
pilot. No planning quantity authorizes collecting until a result passes.
For real data, inspect the complete plan/evaluation before sharing; no sanitizer
or upload is involved. This guide is written last, after all four packs verify.
'''
    with (directory / 'README.txt').open('x', encoding='utf-8') as stream:
        stream.write(guide)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau failure-bound-demo', description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        create_demo(args.out)
        print('Created and verified four synthetic reviewer packs. Open README.txt and each review.html; no real sampling or deployment approval.')
        return 0
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
