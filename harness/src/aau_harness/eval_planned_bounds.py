"""Conditional binomial upper bounds across a fixed, predeclared family of cumulative looks."""

import argparse
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, _parse_json, digest, load_json, rendered, write_json
from .eval_failure_bound import _bounded, upper_failure_bound, validate_plan as validate_fixed_plan
from .eval_repeatability import review_repeatability
from .intake_review import _read_request, _sha


class PlannedBoundError(AgentBomError):
    """Closed public reason codes; raw parser errors and source paths stay private."""


BOUNDARY = (
    'Conditional finite-family diagnostic, not a release gate, posterior probability, unrestricted anytime-valid '
    'confidence sequence, or safety/recovery certification. One sampling unit is a complete scenario bundle: '
    'any joint-criterion failure in any planned repeat fails that bundle. Repeats never increase the independent '
    'unit count. The estimand is bundle failure under this exact repeat protocol, not per-call failure. '
    'Clopper-Pearson marginal bounds require IID scenario-bundle outcomes within every declared scope and '
    'stable candidate/scorer/execution conditions. The order, scope memberships, thresholds, finite look sizes, '
    'and maximum horizon must be selected before outcomes. These assumptions, membership, actual acquisition '
    'order, independence, source authenticity, scoring correctness, and preregistration are not verified. '
    'The plan byte pin must be independently reviewed and controlled, not computed from candidate-controlled '
    'input in the same production job; a hash does not establish identity, authority, or timing. Bonferroni '
    'allocates alpha across ALL planned look-by-scope cells, including pending looks and empty groups, without '
    'reallocation. Dependence between cumulative looks or overlapping scopes does not require an additional '
    'independence assumption for the union bound, but each marginal binomial assumption must hold. Conditional '
    'simultaneous coverage permits selecting among these declared looks, not unplanned peeking, added looks, '
    'extending the horizon, changing candidates/criteria/groups, resetting the error budget, or winner selection '
    'across multiple candidate systems. Those actions are outside this family. Fixed benchmarks receive no '
    'population bounds. Unobserved looks remain pending; empty groups have no bound. Earlier failed bundles '
    'within the supplied dataset remain in every later applicable prefix. Previous exports are not compared, '
    'so authenticity of accumulated history is not established. Bounds may decrease as more sampled bundles arrive; this does '
    'not erase harms, close incidents, or establish effectiveness. No source data is repaired or silently '
    'filtered. Floating-point inversion is not an arbitrary-precision certificate. Source hashes bind supplied '
    'JSON values, not original bytes or trusted provenance. The report has no clock, authenticated history, '
    'data collector, model calls, uploads, or deployment action. Other policy and operating-budget obligations '
    'remain independent. Inspect all IDs, sampling notes, and scores before sharing; no sanitization is performed.'
)


def validate_plan(raw, expected_sha256):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise PlannedBoundError('planned_bound_plan_bytes_invalid_or_oversized')
    if not _sha(expected_sha256) or digest(raw) != expected_sha256:
        raise PlannedBoundError('planned_bound_plan_byte_pin_mismatch')
    plan = _parse_json(raw)
    fields = {'plan_version', 'scenario_order', 'look_sizes', 'n_repeats', 'criteria', 'sampling_design',
              'sampling_basis', 'confidence_level', 'maximum_failure_probability', 'groups'}
    if (not isinstance(plan, dict) or set(plan) != fields
            or plan['plan_version'] != 'aau-planned-look-bound-plan/1.0'):
        raise PlannedBoundError('invalid_planned_bound_plan')
    if plan['sampling_design'] not in ('fixed_benchmark', 'declared_iid_planned_looks'):
        raise PlannedBoundError('unsupported_planned_bound_sampling_design')
    # Share the existing strict scenario/repeat/criterion/group/probability validation,
    # without treating the supplied planned-look declaration as a verified sampling design.
    fixed = {key: value for key, value in plan.items() if key not in ('scenario_order', 'look_sizes')}
    fixed.update(plan_version='aau-failure-bound-plan/1.0', scenario_ids=plan['scenario_order'],
                 sampling_design='fixed_benchmark' if plan['sampling_design'] == 'fixed_benchmark' else 'declared_iid_fixed_horizon')
    validate_fixed_plan(fixed)
    looks = plan['look_sizes']
    if (not isinstance(looks, list) or not 1 <= len(looks) <= 20
            or any(type(size) is not int or not 1 <= size <= len(plan['scenario_order']) for size in looks)
            or looks != sorted(set(looks)) or looks[-1] != len(plan['scenario_order'])):
        raise PlannedBoundError('look_sizes_require_increasing_counts_ending_at_horizon')
    return plan


def _scope_row(scope, prefix, outcomes, alpha, infer):
    ids = prefix.intersection(scope['scenario_ids'])
    failures = sum(outcomes[name]['bundle_failed'] for name in ids)
    bound = upper_failure_bound(failures, len(ids), alpha) if infer and ids else None
    status = ('no_observed_bundles' if not ids else 'population_inference_withheld' if not infer
              else 'conditional_bound_within_limit' if bound <= scope['maximum_failure_probability']
              else 'conditional_bound_exceeds_limit')
    return {'scope_id': scope['scope_id'], 'scenario_count': len(ids), 'failed_scenario_count': failures,
            'observed_bundle_failure_fraction': failures / len(ids) if ids else None,
            'maximum_failure_probability': scope['maximum_failure_probability'],
            'one_sided_upper_failure_bound': bound, 'status': status}


def review_planned_bounds(plan_raw, source, *, plan_sha256):
    try:
        plan = validate_plan(plan_raw, plan_sha256)
        _bounded(source)
        repeated = review_repeatability(source, criteria=plan['criteria'], draw_sizes=[1])
        count = repeated['scenario_count']
        if (count not in plan['look_sizes'] or repeated['repeat_count'] != plan['n_repeats']
                or {row['scenario_id'] for row in repeated['scenarios']} != set(plan['scenario_order'][:count])):
            raise PlannedBoundError('source_requires_exact_complete_prefix_at_a_planned_look')
        outcomes = {row['scenario_id']: {'scenario_id': row['scenario_id'], 'bundle_failed': bool(row['failures']),
                                        'failed_repeats': row['failures']} for row in repeated['scenarios']}
        scopes = [{'scope_id': 'overall', 'scenario_ids': plan['scenario_order'],
                   'maximum_failure_probability': plan['maximum_failure_probability']},
                  *[{'scope_id': group['group_id'], 'scenario_ids': group['scenario_ids'],
                     'maximum_failure_probability': group['maximum_failure_probability']}
                    for group in sorted(plan['groups'], key=lambda value: value['group_id'])]]
        family_size = len(scopes) * len(plan['look_sizes'])
        alpha = (1 - plan['confidence_level']) / family_size
        infer = plan['sampling_design'] == 'declared_iid_planned_looks'
        looks = []
        for size in plan['look_sizes']:
            if size > count:
                looks.append({'planned_scenario_count': size, 'observed': False, 'status': 'not_yet_observed', 'scopes': []})
                continue
            prefix = set(plan['scenario_order'][:size])
            rows = [_scope_row(scope, prefix, outcomes, alpha, infer) for scope in scopes]
            status = ('population_inference_withheld' if not infer
                      else 'insufficient_group_observations' if any(row['status'] == 'no_observed_bundles' for row in rows)
                      else 'conditional_bounds_within_limits' if all(row['status'] == 'conditional_bound_within_limit' for row in rows)
                      else 'conditional_bounds_exceed_limits')
            looks.append({'planned_scenario_count': size, 'observed': True, 'status': status, 'scopes': rows})
        observed_looks = [look for look in looks if look['observed']]
        report = {'report_version': 'aau-planned-look-bound-review/1.0',
                  'status': 'conditional_planned_look_diagnostic' if infer else 'population_inference_withheld',
                  'plan_file_sha256': plan_sha256, 'plan_byte_pin_matched': True, 'source_sha256': digest(source),
                  'sampling_design': plan['sampling_design'], 'sampling_basis': plan['sampling_basis'],
                  'planned_scenario_count': len(plan['scenario_order']), 'observed_scenario_count': count,
                  'observation_count': repeated['observation_count'], 'repeats_per_scenario': plan['n_repeats'],
                  'completed_look_count': len(observed_looks), 'pending_look_count': len(looks) - len(observed_looks),
                  'latest_completed_look': {'scenario_count': count, 'status': observed_looks[-1]['status']},
                  'criteria': repeated['criteria'], 'scope_definitions': scopes, 'looks': looks,
                  'scenario_outcomes': [outcomes[name] for name in plan['scenario_order'][:count]],
                  'source_audit': repeated['source_audit'], 'unreviewed_metrics': repeated['unreviewed_metrics'],
                  'method': {'unit': 'scenario_bundle', 'confidence_level': plan['confidence_level'],
                             'planned_look_count': len(looks), 'scope_count': len(scopes), 'family_size': family_size,
                             'tail_probability_per_cell': alpha,
                             'multiplicity': 'Bonferroni over all planned look-by-scope cells, including unobserved cells',
                             'bound': 'one-sided Clopper-Pearson binomial inversion; floating-point evaluation',
                             'bound_applied': infer, 'unobserved_budget_reallocated': False,
                             'infinite_horizon_coverage': False},
                  'warnings': ['Conditional diagnostic only: no policy verdict, observed deployment, or independent approval.',
                               'Only the declared finite look family is covered; do not add looks or reset the error budget.',
                               'The plan pin does not prove it was chosen before outcomes or that scenario order was actually followed.',
                               *(['Fixed benchmark: population bounds are withheld.'] if not infer else []),
                               *(['Stored metric summaries differ; observations are used without repairing the source.']
                                 if repeated['source_audit']['status'] != 'consistent' else [])],
                  'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                      'eval_planned_bounds.py', 'eval_failure_bound.py', 'eval_repeatability.py', 'eval_audit.py',
                      'runner.py', 'agent_bom.py')}, 'boundary': BOUNDARY}
        _bounded(report)
        return report
    except PlannedBoundError:
        raise
    except (ValueError, OSError, KeyError, TypeError, OverflowError, RecursionError) as exc:
        raise PlannedBoundError('planned_bound_inputs_invalid') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau planned-look-bounds', description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('evaluation', type=Path)
    parser.add_argument('--plan-sha256', required=True, help='independently controlled SHA-256 of exact plan bytes')
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        raw = _read_request(args.plan)
        validate_plan(raw, args.plan_sha256)  # Reject an invalid plan before reading the evaluation.
        report = review_planned_bounds(raw, load_json(args.evaluation), plan_sha256=args.plan_sha256)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise PlannedBoundError('planned_bound_report_does_not_recompute')
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {report['completed_look_count']} observed looks; "
              f"{report['pending_look_count']} pending. Diagnostic only, not a release decision.")
        return 0
    except (ValueError, OSError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, PlannedBoundError) else 'planned_bound_input_or_output_rejected'
        print(f'error: {reason}; no new planned-look report produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
