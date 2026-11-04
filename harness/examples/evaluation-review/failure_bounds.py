"""Synthetic failure-bound lesson: repeated success, distinct scenarios, and a small group."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import write_json
from aau_harness.eval_failure_bound import review_failure_bounds
from aau_harness.runner import ScenarioResult, run_eval


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


def create_examples(directory):
    directory.mkdir(parents=True, exist_ok=False)
    expected = {'fixed-benchmark': 'population_inference_withheld',
                'few-scenarios': 'conditional_bounds_exceed_limits',
                'more-scenarios': 'conditional_bounds_within_limits',
                'small-group': 'conditional_bounds_exceed_limits'}
    for name, (plan, source) in example_inputs().items():
        report = review_failure_bounds(plan, source)
        if report['status'] != expected[name]:
            raise RuntimeError('synthetic failure-bound outcome changed')
        for label, value in [('plan', plan), ('evaluation', source), ('report', report)]:
            write_json(value, directory / name / f'{label}.json')
    (directory / 'README.txt').write_text('''Synthetic failure-bound lesson — no real agents or sampled users.

Every example records perfect completion and authorization across four repeats.
fixed-benchmark: population inference is withheld, regardless of those scores.
few-scenarios: 20 distinct scenarios imply about a 13.9% upper bound only under
the hypothetical IID fixed-horizon assumptions; 80 repeated observations are
not 80 independent scenario units.
more-scenarios: 60 distinct scenarios lower that hypothetical bound below 5%.
small-group: 100 overall scenarios meet the conditional 5% target, but the ten
assisted-channel scenarios do not. Both scopes use the family correction.

From this directory, verify each NAME with the current installed harness:
  aau failure-bound-eval NAME/plan.json NAME/evaluation.json --verify NAME/report.json

Exit 0 means the diagnostic recomputes, not that a target passes or deployment
is approved. Keep plan, evaluation, and report together. These fixtures do not
establish IID sampling, production reliability, or an effective agent repair.
Do not copy their sampling declarations or numerical limits into a real pilot.
No zero-failure planning quantity authorizes collecting until a test passes.
''', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_examples(parser.parse_args().out)
