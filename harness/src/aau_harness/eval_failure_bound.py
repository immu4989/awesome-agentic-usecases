"""Separate observed benchmark failures from conditional fixed-horizon binomial bounds."""

import argparse
import json
import math
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_repeatability import _criteria, review_repeatability


BOUNDARY = (
    "Conditional statistical diagnostic, not a release gate, probability that a hypothesis is true, or safety certification. "
    "One unit is a scenario bundle containing every planned repeat; any joint-criterion failure in any repeat fails that "
    "bundle. Repeats never increase the sampling-unit count. The estimand is bundle failure under this exact repeat "
    "protocol, not per-call failure or an arbitrary production workload. Binomial coverage requires independently and "
    "identically sampled scenario bundles within each declared scope, stable scoring/execution conditions, and a fixed "
    "horizon and plan chosen before outcomes. These assumptions, sampling basis, group membership, preregistration, "
    "scoring correctness, and source authenticity are supplied, not verified. Fixed benchmarks receive no population "
    "bound. Bonferroni covers only this declared family, including overlapping groups; it does not correct adaptive "
    "group selection, repeated peeking, optional stopping, benchmark reuse, or choosing among many candidate agents. "
    "Zero-failure sample sizes are hypothetical new fixed-horizon planning quantities, not permission to keep testing "
    "until a result passes or to erase existing failures. Source hashes bind JSON values, not original bytes or trusted "
    "provenance. Other policy obligations and operating budgets remain independent. No network or model calls, "
    "data collection, human approval, or deployment action occurs. Inspect identifiers, sampling notes, and failed "
    "scores before sharing; no sanitization is performed."
)
MAX_PLANNING_SCENARIOS = 1_000_000_000


def _bounded(value):
    try:
        json.dumps(value, allow_nan=False, ensure_ascii=False).encode('utf-8')
        if len(rendered(value)) > MAX_JSON_BYTES:
            raise AgentBomError("failure-bound input or report exceeds 2 MB")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise AgentBomError("failure-bound data must be bounded finite UTF-8 JSON") from exc


def _probability(value, *, confidence=False):
    if (type(value) not in (int, float)
            or not (0.5 <= value <= 0.999999 if confidence else 0 <= value < 1)):
        raise AgentBomError("confidence must be 0.5 through 0.999999; failure limits must be 0 through less than 1")


def _ids(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= 500
            or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in value)
            or len(set(value)) != len(value)):
        raise AgentBomError("scenario IDs must be 1 to 500 distinct nonblank names")
    return set(value)


def validate_plan(plan):
    fields = {'plan_version', 'scenario_ids', 'n_repeats', 'criteria', 'sampling_design',
              'sampling_basis', 'confidence_level', 'maximum_failure_probability', 'groups'}
    if not isinstance(plan, dict) or set(plan) != fields or plan['plan_version'] != 'aau-failure-bound-plan/1.0':
        raise AgentBomError("failure-bound plan requires exactly the version 1.0 fields")
    ids = _ids(plan['scenario_ids'])
    if type(plan['n_repeats']) is not int or not 1 <= plan['n_repeats'] or len(ids) * plan['n_repeats'] > 10000:
        raise AgentBomError("planned repeats must be positive and fit 10000 observations")
    _criteria(plan['criteria'])
    if plan['sampling_design'] not in ('fixed_benchmark', 'declared_iid_fixed_horizon'):
        raise AgentBomError("declare fixed_benchmark or declared_iid_fixed_horizon; design is not inferred")
    basis = plan['sampling_basis']
    if not isinstance(basis, str) or not basis.strip() or len(basis) > 2000:
        raise AgentBomError("sampling_basis requires a nonblank reviewable explanation of at most 2000 characters")
    _probability(plan['confidence_level'], confidence=True)
    _probability(plan['maximum_failure_probability'])
    if not isinstance(plan['groups'], list) or len(plan['groups']) > 19:
        raise AgentBomError("at most 19 groups plus the mandatory overall scope are supported")
    seen = {'overall'}
    for group in plan['groups']:
        if not isinstance(group, dict) or set(group) != {'group_id', 'scenario_ids', 'maximum_failure_probability'}:
            raise AgentBomError("group requires identity, complete membership, and a failure limit")
        name = group['group_id']
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in seen:
            raise AgentBomError("group IDs must be unique and cannot use reserved overall")
        seen.add(name)
        if not _ids(group['scenario_ids']) <= ids:
            raise AgentBomError("group contains an unplanned scenario")
        _probability(group['maximum_failure_probability'])


def upper_failure_bound(failures: int, scenarios: int, alpha: float) -> float:
    """One-sided Clopper-Pearson upper limit, computed in floating point.

    Invert P(Binomial(n, p) <= failures) = alpha. Log-sum-exp prevents
    underflow in the tails. The returned endpoint is the upper bisection
    endpoint; this is not an arbitrary-precision interval certificate.
    """
    if (type(scenarios) is not int or not 1 <= scenarios <= 500 or type(failures) is not int
            or not 0 <= failures <= scenarios or type(alpha) not in (float, int) or not 0 < alpha < 1):
        raise AgentBomError("invalid binomial counts or tail probability")
    if failures == scenarios:
        return 1.0
    if failures == 0:
        return -math.expm1(math.log(alpha) / scenarios)
    coefficients = [math.lgamma(scenarios + 1) - math.lgamma(i + 1) - math.lgamma(scenarios - i + 1)
                    for i in range(failures + 1)]
    log_alpha, low, high = math.log(alpha), 0.0, 1.0
    for _ in range(64):
        p = (low + high) / 2
        if p == low or p == high:
            break
        lp, lq = math.log(p), math.log1p(-p)
        terms = [coefficient + i * lp + (scenarios - i) * lq for i, coefficient in enumerate(coefficients)]
        peak = max(terms)
        cdf = peak + math.log(math.fsum(math.exp(term - peak) for term in terms))
        if cdf > log_alpha:
            low = p
        else:
            high = p
    return high


def zero_failure_plan(limit: float, alpha: float) -> dict:
    _probability(limit)
    if type(alpha) not in (int, float) or not 0 < alpha < 1:
        raise AgentBomError("planning tail probability must be between zero and one")
    if limit == 0:
        return {'status': 'no_finite_zero_failure_sample', 'minimum_scenarios': None}
    ratio = math.log(alpha) / math.log1p(-limit)
    if not math.isfinite(ratio) or ratio > MAX_PLANNING_SCENARIOS:
        return {'status': 'exceeds_planning_range', 'minimum_scenarios': None}
    count = max(1, math.ceil(ratio))
    # Check neighboring integers rather than rounding a near-integer log ratio.
    def bound(n):
        return -math.expm1(math.log(alpha) / n)
    while count > 1 and bound(count - 1) <= limit:
        count -= 1
    while bound(count) > limit:
        count += 1
    if count > MAX_PLANNING_SCENARIOS:
        return {'status': 'exceeds_planning_range', 'minimum_scenarios': None}
    return {'status': 'hypothetical_fixed_horizon', 'minimum_scenarios': count}


def review_failure_bounds(plan: dict, source: dict) -> dict:
    _bounded(plan)
    _bounded(source)
    validate_plan(plan)
    repeated = review_repeatability(source, criteria=plan['criteria'], draw_sizes=[1])
    scenarios = repeated['scenarios']
    if ({row['scenario_id'] for row in scenarios} != set(plan['scenario_ids'])
            or repeated['repeat_count'] != plan['n_repeats']):
        raise AgentBomError("evaluation must match the exact planned scenarios and repeats")
    outcomes = {row['scenario_id']: {'scenario_id': row['scenario_id'], 'bundle_failed': bool(row['failures']),
                                    'failed_repeats': row['failures']} for row in scenarios}
    scopes = [{'group_id': 'overall', 'scenario_ids': sorted(outcomes),
               'maximum_failure_probability': plan['maximum_failure_probability']},
              *sorted(plan['groups'], key=lambda group: group['group_id'])]
    alpha = (1 - plan['confidence_level']) / len(scopes)
    infer = plan['sampling_design'] == 'declared_iid_fixed_horizon'
    rows = []
    for scope in scopes:
        ids = sorted(scope['scenario_ids'])
        failed_ids = [name for name in ids if outcomes[name]['bundle_failed']]
        limit = scope['maximum_failure_probability']
        bound = upper_failure_bound(len(failed_ids), len(ids), alpha) if infer else None
        rows.append({'scope_id': scope['group_id'], 'scenario_ids': ids, 'scenario_count': len(ids),
                     'failed_scenario_ids': failed_ids, 'failed_scenario_count': len(failed_ids),
                     'observed_bundle_failure_fraction': len(failed_ids) / len(ids),
                     'maximum_failure_probability': limit, 'one_sided_upper_failure_bound': bound,
                     'status': 'population_inference_withheld' if not infer else
                               'conditional_bound_within_limit' if bound <= limit else 'conditional_bound_exceeds_limit',
                     'zero_failure_planning': zero_failure_plan(limit, alpha)})
    report = {'report_version': 'aau-failure-bound-review/1.0', 'plan_sha256': digest(plan),
              'source_sha256': digest(source), 'sampling_design': plan['sampling_design'],
              'sampling_basis': plan['sampling_basis'], 'criteria': repeated['criteria'],
              'status': 'population_inference_withheld' if not infer else
                        'conditional_bounds_within_limits' if all(row['status'] == 'conditional_bound_within_limit' for row in rows)
                        else 'conditional_bounds_exceed_limits',
              'scenario_count': len(scenarios), 'repeats_per_scenario': plan['n_repeats'],
              'observation_count': repeated['observation_count'], 'scopes': rows,
              'scenario_outcomes': [outcomes[name] for name in sorted(outcomes)],
              'source_audit': repeated['source_audit'], 'unreviewed_metrics': repeated['unreviewed_metrics'],
              'method': {'unit': 'scenario_bundle', 'bundle_failure': 'any joint-criterion failure in any planned repeat',
                         'confidence_level': plan['confidence_level'], 'family_size': len(scopes),
                         'tail_probability_per_scope': alpha, 'multiplicity': 'Bonferroni across overall and every declared group',
                         'bound': 'one-sided Clopper-Pearson binomial inversion; floating-point evaluation',
                         'bound_applied': infer, 'zero_failure_planning_limit': MAX_PLANNING_SCENARIOS},
              'warnings': ['Sampling assumptions are declared, not verified; this is not a policy or release verdict.',
                           'Do not add repeats to the independent scenario count or read zero observed failures as zero risk.',
                           'Choosing this plan after looking at outcomes, optional stopping, or selecting a winner invalidates the stated coverage.',
                           *(['Fixed benchmark: no population confidence bound is reported; planning values are hypothetical.'] if not infer else []),
                           *(['Stored metric summaries differ; this diagnostic uses observations and does not repair the source.']
                             if repeated['source_audit']['status'] != 'consistent' else [])],
              'boundary': BOUNDARY}
    _bounded(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau failure-bound-eval', description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('evaluation', type=Path)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        report = review_failure_bounds(load_json(args.plan), load_json(args.evaluation))
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError("failure-bound report does not recompute")
        else:
            write_json(report, args.out)
        print(f"Failure-bound diagnostic: {report['status']}; {report['scenario_count']} scenario bundles. Not deployment approval.")
        return 0  # Producing a diagnostic is never a release decision.
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
