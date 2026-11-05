"""Construct planned-look arithmetic contrasts; not sampled production evidence or approval."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import digest, rendered, write_json
from aau_harness.eval_failure_bound import upper_failure_bound
from aau_harness.eval_import import import_observations
from aau_harness.eval_planned_bounds import review_planned_bounds


def example_inputs():
    examples = {}
    ids = [f'synthetic-service-{index:03d}' for index in range(100)]
    for name, count, design in [('fixed-benchmark', 60, 'fixed_benchmark'),
                                ('planned-60', 60, 'declared_iid_planned_looks'),
                                ('planned-100', 100, 'declared_iid_planned_looks'),
                                ('early-failure', 100, 'declared_iid_planned_looks'),
                                ('small-group', 100, 'declared_iid_planned_looks')]:
        plan = {'plan_version': 'aau-planned-look-bound-plan/1.0', 'scenario_order': ids, 'look_sizes': [20, 60, 100],
                'n_repeats': 4, 'criteria': [{'metric': 'completion', 'direction': 'higher', 'limit': 1},
                                           {'metric': 'unauthorized', 'direction': 'lower', 'limit': 0}],
                'sampling_design': design, 'sampling_basis': 'Constructed arithmetic lesson, NOT a collected IID sample. '
                'Conditional mode illustrates an assumption only, not real reliability or deployment evidence.',
                'confidence_level': .95, 'maximum_failure_probability': .05, 'groups': []}
        if name == 'small-group':
            plan['groups'] = [{'group_id': 'synthetic-assisted-channel', 'scenario_ids': ids[-10:], 'maximum_failure_probability': .05}]
        source = import_observations({'format_version': 'aau-recorded-observations/1.0',
                                     'source_label': 'Synthetic planned-look fixture; no real service, model, or sampling.',
                                     'scenario_ids': ids[:count], 'n_repeats': 4,
                                     'observations': [{'scenario_id': case, 'repeat': repeat, 'metrics': {
                                         'completion': 1, 'unauthorized': int(name == 'early-failure' and case == ids[0] and repeat == 0)}}
                                         for case in ids[:count] for repeat in range(4)]})
        examples[name] = plan, source
    return examples


def create_example(directory):
    directory.mkdir(parents=True, exist_ok=False)
    commands, summaries, reports = [], [], {}
    expected = {'fixed-benchmark': 'population_inference_withheld', 'planned-60': 'conditional_bounds_exceed_limits',
                'planned-100': 'conditional_bounds_within_limits', 'early-failure': 'conditional_bounds_exceed_limits',
                'small-group': 'conditional_bounds_exceed_limits'}
    for name, (plan, source) in example_inputs().items():
        raw = rendered(plan)
        result = review_planned_bounds(raw, source, plan_sha256=digest(raw))
        if result['latest_completed_look']['status'] != expected[name]:
            raise RuntimeError('synthetic planned-look outcome differs from its contract')
        reports[name] = result
        for suffix, value in (('plan', plan), ('evaluation', source), ('report', result)):
            write_json(value, directory / f'{name}-{suffix}.json')
        commands.append(f'aau planned-look-bounds {name}-plan.json {name}-evaluation.json '
                        f'--plan-sha256 {digest(raw)} --verify {name}-report.json')
        for look in result['looks']:
            for row in look['scopes']:
                bound = row['one_sided_upper_failure_bound']
                value = 'withheld/no observations' if bound is None else f'{bound:.6%} (conditional)'
                summaries.append(f'{name} / look {look["planned_scenario_count"]} / {row["scope_id"]}: '
                                 f'{row["failed_scenario_count"]} failed of {row["scenario_count"]} bundles; upper bound {value}.')
    if reports['planned-60']['looks'][:2] != reports['planned-100']['looks'][:2]:
        raise RuntimeError('later observations changed earlier planned-look arithmetic')
    guide = '''AAU synthetic planned-look diagnostic — not a release gate

All inputs and outcomes are constructed, not independent sampled people or model runs.
The three-look plan has a fixed horizon of 100 bundles and checkpoints at 20, 60, and 100.
At 60 observed bundles, the third look remains pending and its alpha allocation is NOT reused.
Four repeats per scenario do not create four independent sampling units.

''' + f'A hypothetical single fixed look at 60 zero-failure bundles has upper bound {upper_failure_bound(0, 60, .05):.6%}.\n' + '''
That single-look contrast is not permission to replace a multiple-look plan after seeing results.
The planned-60 report exceeds 5% after accounting for all three planned looks. The planned-100
fixture meets the conditional limit, but does not approve deployment. An early failed bundle
stays in every later prefix. The small group's data cannot hide behind the overall result;
its early empty cells are not treated as zero-risk evidence. Fixed benchmarks receive no bound.

''' + '\n'.join(summaries) + '''

From this directory, with the same trusted harness, reverify:

''' + '\n'.join(commands) + '''

Exit 0 means a diagnostic was recomputed, including exceeded limits or withheld inference.
Exit 2 means invalid inputs, mismatching pins, output errors, or a mismatching saved report.
These local fixture hashes are plumbing, not independent approval or proof of preregistration.
For real work, independently review and protect the plan before observing outcomes. Do not
compute expected approval hashes from candidate-controlled plans in the same production job.

Coverage is conditional on valid IID bundle assumptions within each scope and stable candidate,
scorer, and execution conditions. The finite family includes every planned look and scope,
even when a look has not occurred or a group is empty. It is not an unbounded confidence sequence.
Added looks, changed groups, extended horizons, changed candidates, or reset error budgets are
outside this family. No real-time monitor, incident closure, causal effect, or recovery is claimed.
The tool does not compare earlier source exports or authenticate that data actually accumulated.
Keep plans, source evaluations, and reports, and inspect private information before sharing.
This guide is written last after the five expected diagnostic outcomes are checked.
'''
    (directory / 'README.txt').write_text(guide, encoding='utf-8')
    print('Created five synthetic planned-look diagnostics; no production inference or release approval.')
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
