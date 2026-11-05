"""Describe recorded automation/referral trade-offs without assuming human resolution or safe deployment."""

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

from .agent_bom import MAX_JSON_BYTES, _parse_json, digest, load_json, rendered, write_json
from .eval_audit import audit_evaluation
from .eval_repeatability import _criteria
from .inspect_pack import InspectionError
from .intake_review import _read_request, _sha


BOUNDARY = (
    'Offline hypothetical routing of recorded observations, not an executed router, release gate, optimal '
    'threshold, calibrated probability, statistical risk guarantee, human-performance estimate, or deployment '
    'approval. Higher scores are only a supplied ranking convention. The score and mandatory-review flag '
    'must be available before any consequential action; availability, correctness, independent production, '
    'and absence of outcome leakage are NOT verified. A required or unknown human-review flag always '
    'defers; missing scores also defer. Zero automated observations have undefined automated failure '
    'fraction, not zero risk. All recorded joint failures remain visible, including hypothetically deferred '
    'ones: deferral cannot undo harm already recorded. No human resolution, queue delay, service capacity '
    'over time, staffing, costs, saved work, causal benefit, or future traffic is measured or inferred. '
    'Referral limits count supplied observations only. Repeats are not independent people, arrivals, or '
    'timestamps; groups may overlap and must not be pooled as disjoint populations. No overall winner or '
    'threshold is selected. Selecting a threshold on these outcomes requires separate held-out evaluation; '
    'there are no confidence bounds or population claims here. Plan pins identify bytes, not preregistration '
    'or reviewer authority; protect the expected pin independently. Retain the original plan, full evaluation, '
    'and report with a matching trusted harness. Source summaries are audited but not rewritten. Scoring '
    'validity, representativeness, actual authority, rights, and real outcomes need separate review. Reports '
    'retain IDs, scores, failures, and hashes; they are not sanitized or approved for sharing. No model, '
    'adapter, service action, subprocess, upload, or network request is executed.'
)
DEFER_REASONS = ('required_human_review', 'unknown_review_requirement', 'missing_score', 'below_threshold')
LIMITS = {'minimum_automation_fraction', 'maximum_automated_failure_fraction', 'maximum_review_observations'}


def _bounded(value):
    try:
        json.dumps(value, allow_nan=False, ensure_ascii=False).encode('utf-8')
        if len(rendered(value)) > MAX_JSON_BYTES:
            raise ValueError
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError) as exc:
        raise InspectionError('routing_data_must_be_bounded_finite_utf8_json') from exc


def _probability(value):
    return type(value) in (int, float) and 0 <= value <= 1


def _ids(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= 500
            or any(not isinstance(name, str) or not name.strip() or len(name) > 200 for name in value)
            or len(set(value)) != len(value)):
        raise InspectionError('routing_scenario_census_invalid')
    return set(value)


def _limits(value, count):
    if (not isinstance(value, dict) or set(value) != LIMITS
            or not _probability(value['minimum_automation_fraction'])
            or not _probability(value['maximum_automated_failure_fraction'])
            or type(value['maximum_review_observations']) is not int
            or not 0 <= value['maximum_review_observations'] <= count):
        raise InspectionError('routing_limits_invalid')


def validate_plan(raw, expected_sha256):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise InspectionError('routing_plan_bytes_invalid_or_oversized')
    if not _sha(expected_sha256) or digest(raw) != expected_sha256:
        raise InspectionError('routing_plan_byte_pin_mismatch')
    plan = _parse_json(raw)
    fields = {'plan_version', 'scenario_ids', 'n_repeats', 'criteria', 'score_metric', 'score_basis',
              'mandatory_review_metric', 'thresholds', 'limits', 'groups'}
    if not isinstance(plan, dict) or set(plan) != fields or plan['plan_version'] != 'aau-recorded-routing-plan/1.0':
        raise InspectionError('routing_plan_fields_invalid')
    ids = _ids(plan['scenario_ids'])
    repeats = plan['n_repeats']
    if type(repeats) is not int or repeats < 1 or len(ids) * repeats > 10000:
        raise InspectionError('routing_repeat_count_invalid')
    criteria = _criteria(plan['criteria'])
    names = [rule['metric'] for rule in criteria]
    for field in ('score_metric', 'mandatory_review_metric'):
        name = plan[field]
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in names:
            raise InspectionError('routing_metrics_must_be_distinct_from_outcomes')
        names.append(name)
    if not isinstance(plan['score_basis'], str) or not plan['score_basis'].strip() or len(plan['score_basis']) > 2000:
        raise InspectionError('routing_score_basis_required')
    thresholds = plan['thresholds']
    if (not isinstance(thresholds, list) or not 1 <= len(thresholds) <= 20
            or not all(_probability(value) for value in thresholds) or len(set(thresholds)) != len(thresholds)):
        raise InspectionError('routing_thresholds_invalid')
    _limits(plan['limits'], len(ids) * repeats)
    if not isinstance(plan['groups'], list) or len(plan['groups']) > 19:
        raise InspectionError('routing_groups_invalid')
    seen = {'overall'}
    for group in plan['groups']:
        if not isinstance(group, dict) or set(group) != {'group_id', 'scenario_ids', 'limits'}:
            raise InspectionError('routing_group_fields_invalid')
        name = group['group_id']
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in seen:
            raise InspectionError('routing_group_id_invalid')
        seen.add(name)
        members = _ids(group['scenario_ids'])
        if not members <= ids:
            raise InspectionError('routing_group_outside_census')
        _limits(group['limits'], len(members) * repeats)
    return plan, criteria


def _route(row, threshold):
    if row['mandatory_review'] == 1:
        return 'required_human_review'
    if row['mandatory_review'] is None:
        return 'unknown_review_requirement'
    if row['score'] is None:
        return 'missing_score'
    return 'automated' if row['score'] >= threshold else 'below_threshold'


def _check(name, numerator, denominator, limit, direction):
    observed = numerator / denominator if denominator else None
    # Compare rational counts with the parsed limit's decimal spelling, not rounded display fractions.
    passed = None if denominator == 0 else (Fraction(numerator, denominator) >= Fraction(str(limit)) if direction == 'higher'
                                           else Fraction(numerator, denominator) <= Fraction(str(limit)))
    return {'constraint': name, 'numerator': numerator, 'denominator': denominator, 'observed': observed,
            'limit': limit, 'status': 'unverified' if passed is None else 'met' if passed else 'not_met'}


def _status(checks):
    states = {row['status'] for row in checks}
    return ('recorded_limits_not_met' if 'not_met' in states else 'recorded_limits_unverified' if 'unverified' in states
            else 'recorded_limits_met')


def _scope(scope, rows, threshold):
    selected = set(scope['scenario_ids'])
    members = [row for row in rows if row['scenario_id'] in selected]
    routes = [(row, _route(row, threshold)) for row in members]
    automatic = [row for row, route in routes if route == 'automated']
    auto_failed = sum(not row['jointly_passed'] for row in automatic)
    failed = sum(not row['jointly_passed'] for row in members)
    total, count = len(members), len(automatic)
    limits = scope['limits']
    checks = [_check('minimum_automation_fraction', count, total, limits['minimum_automation_fraction'], 'higher'),
              _check('maximum_automated_failure_fraction', auto_failed, count, limits['maximum_automated_failure_fraction'], 'lower'),
              _check('maximum_review_observations', total - count, 1, limits['maximum_review_observations'], 'lower')]
    return {'scope_id': scope['group_id'], 'observation_count': total, 'automated_observations': count,
            'deferred_observations': total - count, 'recorded_joint_failures': failed,
            'automated_joint_failures': auto_failed, 'deferred_joint_failures': failed - auto_failed,
            'automation_fraction': count / total, 'automated_failure_fraction': auto_failed / count if count else None,
            'deferral_reasons': {reason: sum(route == reason for _, route in routes) for reason in DEFER_REASONS},
            'human_resolution': 'not_measured' if total != count else 'not_applicable_no_deferrals',
            'checks': checks, 'status': _status(checks)}


def review_routing(plan_raw, source, *, plan_sha256):
    plan, criteria = validate_plan(plan_raw, plan_sha256)
    _bounded(source)
    audit = audit_evaluation(source)
    if source['n_repeats'] != plan['n_repeats'] or {row['scenario_id'] for row in source['results']} != set(plan['scenario_ids']):
        raise InspectionError('routing_evidence_must_match_complete_planned_census')
    observations = []
    for row in sorted(source['results'], key=lambda item: (item['scenario_id'], item['repeat'])):
        metrics = row['metrics']
        if any(rule['metric'] not in metrics for rule in criteria):
            raise InspectionError('routing_outcome_criteria_must_cover_every_observation')
        score, mandatory = metrics.get(plan['score_metric']), metrics.get(plan['mandatory_review_metric'])
        if plan['score_metric'] in metrics and not _probability(score):
            raise InspectionError('routing_score_must_be_numeric_zero_through_one')
        if plan['mandatory_review_metric'] in metrics and (type(mandatory) not in (int, float) or mandatory not in (0, 1)):
            raise InspectionError('routing_mandatory_flag_must_be_numeric_binary')
        failed = [{'metric': rule['metric'], 'value': metrics[rule['metric']]} for rule in criteria
                  if (metrics[rule['metric']] < rule['limit'] if rule['direction'] == 'higher' else metrics[rule['metric']] > rule['limit'])]
        observations.append({'scenario_id': row['scenario_id'], 'repeat': row['repeat'], 'score': score,
                             'mandatory_review': mandatory, 'jointly_passed': not failed, 'failed_criteria': failed})
    scopes = [{'group_id': 'overall', 'scenario_ids': plan['scenario_ids'], 'limits': plan['limits']}, *plan['groups']]
    thresholds = []
    for threshold in sorted(plan['thresholds']):
        rows = [_scope(scope, observations, threshold) for scope in scopes]
        thresholds.append({'threshold': threshold, 'scopes': rows,
                           'status': _status([check for row in rows for check in row['checks']])})
    report = {'report_version': 'aau-recorded-routing-review/1.0', 'status': 'recorded_routing_diagnostic',
              'plan_file_sha256': plan_sha256, 'source_sha256': digest(source), 'plan': plan,
              'observation_count': len(observations), 'recorded_joint_failures': sum(not row['jointly_passed'] for row in observations),
              'observations': observations, 'thresholds': thresholds, 'source_audit': audit,
              'unreviewed_metrics': sorted({name for row in source['results'] for name in row['metrics']}
                                          - {rule['metric'] for rule in criteria} - {plan['score_metric'], plan['mandatory_review_metric']}),
              'selected_threshold': None, 'human_resolution_measured': False,
              'method': {'unit': 'recorded scenario-repeat observation, not independent traffic',
                         'automatic_when': 'mandatory_review == 0 AND score present AND score >= threshold',
                         'missing_routing_measurements': 'defer, never impute zero or silently drop',
                         'limits': 'exact count ratios versus decimal spelling of parsed limits; displays are floating point',
                         'population_inference': 'withheld; no sampling or calibration guarantee'},
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
                                        ('eval_routing.py', 'eval_audit.py', 'eval_repeatability.py', 'runner.py', 'agent_bom.py')},
              'boundary': BOUNDARY}
    _bounded(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau routing-eval', description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('evaluation', type=Path)
    parser.add_argument('--plan-sha256', required=True, help='independently controlled hash of exact routing-plan bytes')
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        raw = _read_request(args.plan)
        validate_plan(raw, args.plan_sha256)  # Reject a substituted plan before reading evaluation evidence.
        report = review_routing(raw, load_json(args.evaluation), plan_sha256=args.plan_sha256)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise InspectionError('routing_report_does_not_recompute')
        else:
            write_json(report, args.out)
        print(f"Recorded routing diagnostic: {len(report['thresholds'])} thresholds; "
              f"{report['recorded_joint_failures']} retained joint failures. No chosen threshold or deployment approval.")
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'routing_input_or_output_rejected'
        print(f'error: {reason}; no verified routing diagnostic produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
