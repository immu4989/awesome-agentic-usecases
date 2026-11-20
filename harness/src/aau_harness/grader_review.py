"""Audit recorded binary grader judgments against pinned, fallible reference labels."""

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

from .agent_bom import MAX_JSON_BYTES, _parse_json, digest, rendered
from .inspect_pack import InspectionError
from .intake_review import _read_request, _sha


REFERENCE_STATES = ('pass', 'fail', 'disputed', 'unreviewed')
GRADER_STATES = ('pass', 'fail', 'abstain', 'missing')
SPLITS = ('calibration', 'validation')
BOUNDARY = (
    'Descriptive comparison of supplied judgments with fallible reference labels, not a grader certification, '
    'release gate, calibrated probability, human study, population estimate, or deployment approval. '
    'Reference correctness, reviewer expertise and independence, blinding, and absence of training/test '
    'contamination are not verified. Calibration and validation are declared partitions, never pooled. '
    'Duplicate declared evidence fingerprints are rejected, but distinct hashes do not prove distinct or '
    'independent tasks, and validation labels are not kept secret by this tool. Rubric and evidence hashes '
    'are checked for agreement, not against original transcripts or rubric content. No transcript is read, '
    'no grader is run, and no network, model, adapter, or subprocess is invoked. Binary judgments only: '
    'no implicit conversion of numeric scores or free text. Missing and abstained judgments and disputed '
    'or unreviewed references remain explicit; undefined ratios are null, never perfect agreement. '
    'Groups can overlap and must not be pooled. No confidence intervals or overall winner are inferred. '
    'Protect the expected plan hash independently; pins bind bytes, not authority or preregistration. '
    'Retain all three input files and the report with a matching trusted harness. IDs, labels, and hashes '
    'may be sensitive; this is not sanitization or permission to share.'
)


def _reject(reason):
    raise InspectionError('grader_' + reason)


def _object(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        _reject('fields_invalid')


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}', value) is not None


def _ids(value, maximum):
    if (not isinstance(value, list) or not 1 <= len(value) <= maximum
            or not all(_id(v) for v in value) or len(set(value)) != len(value)):
        _reject('ids_invalid')
    return set(value)


def _document(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        _reject('input_bytes_invalid_or_oversized')
    return _parse_json(raw)


def validate_plan(raw, expected_sha256):
    if not isinstance(raw, bytes) or not _sha(expected_sha256) or digest(raw) != expected_sha256:
        _reject('plan_byte_pin_mismatch')
    plan = _document(raw)
    _object(plan, ('plan_version', 'rubric_sha256', 'reference_sha256', 'reference_basis', 'criteria', 'items', 'groups'))
    if plan['plan_version'] != 'aau-grader-review-plan/1.0':
        _reject('plan_version_invalid')
    if not _sha(plan['rubric_sha256']) or not _sha(plan['reference_sha256']):
        _reject('control_hash_invalid')
    basis = plan['reference_basis']
    if not isinstance(basis, str) or not basis.strip() or len(basis) > 2000:
        _reject('reference_basis_required')
    _ids(plan['criteria'], 10)
    items = plan['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        _reject('item_census_invalid')
    ids, fingerprints = set(), set()
    for item in items:
        _object(item, ('item_id', 'evidence_sha256', 'split'))
        if not _id(item['item_id']) or item['item_id'] in ids or item['split'] not in SPLITS:
            _reject('item_identity_or_split_invalid')
        if not _sha(item['evidence_sha256']) or item['evidence_sha256'] in fingerprints:
            _reject('duplicate_or_invalid_evidence_fingerprint')
        ids.add(item['item_id'])
        fingerprints.add(item['evidence_sha256'])
    if not isinstance(plan['groups'], list) or len(plan['groups']) > 19:
        _reject('groups_invalid')
    seen = {'overall'}
    for group in plan['groups']:
        _object(group, ('group_id', 'item_ids'))
        if not _id(group['group_id']) or group['group_id'] in seen:
            _reject('group_id_invalid')
        seen.add(group['group_id'])
        if not _ids(group['item_ids'], 500) <= ids:
            _reject('group_outside_census')
    return plan


def _labels(raw, plan, *, reference):
    value = _document(raw)
    _object(value, ('format_version', 'rubric_sha256', 'rows') if reference
            else ('format_version', 'rubric_sha256', 'grader_id', 'rows'))
    version = 'aau-grader-reference/1.0' if reference else 'aau-grader-judgments/1.0'
    if value['format_version'] != version or value['rubric_sha256'] != plan['rubric_sha256']:
        _reject('label_version_or_rubric_mismatch')
    if not reference and not _id(value['grader_id']):
        _reject('identity_invalid')
    items = {item['item_id']: item for item in plan['items']}
    census = {(item, criterion) for item in items for criterion in plan['criteria']}
    rows = value['rows']
    if not isinstance(rows, list) or len(rows) > len(census):
        _reject('label_count_invalid')
    labels = {}
    for row in rows:
        _object(row, ('item_id', 'criterion', 'evidence_sha256', 'verdict'))
        if not _id(row['item_id']) or not _id(row['criterion']):
            _reject('label_identity_invalid')
        key = row['item_id'], row['criterion']
        if key not in census or key in labels:
            _reject('duplicate_or_unplanned_label')
        if row['evidence_sha256'] != items[row['item_id']]['evidence_sha256']:
            _reject('evidence_fingerprint_mismatch')
        states = REFERENCE_STATES if reference else GRADER_STATES[:-1]
        if row['verdict'] not in states:
            _reject('verdict_invalid')
        labels[key] = row['verdict']
    if reference and set(labels) != census:
        _reject('reference_requires_complete_census')
    return value, labels


def _ratio(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'value': numerator / denominator if denominator else None}


def _scope(rows, split, criterion, group):
    selected = set(group['item_ids'])
    rows = [r for r in rows if r['split'] == split and r['criterion'] == criterion and r['item_id'] in selected]
    counts = Counter((r['reference'], r['grader']) for r in rows)
    matrix = {ref: {grader: counts[ref, grader] for grader in GRADER_STATES} for ref in REFERENCE_STATES}
    paired = sum(counts[r, g] for r in ('pass', 'fail') for g in ('pass', 'fail'))
    reference_decided = sum(sum(matrix[r].values()) for r in ('pass', 'fail'))
    grader_decided = sum(counts[r, g] for r in REFERENCE_STATES for g in ('pass', 'fail'))
    return {'split': split, 'criterion': criterion, 'group_id': group['group_id'], 'planned_items': len(rows),
            'matrix': matrix, 'false_passes': counts['fail', 'pass'], 'false_failures': counts['pass', 'fail'],
            'reference_failures_without_grader_decision': counts['fail', 'abstain'] + counts['fail', 'missing'],
            'reference_passes_without_grader_decision': counts['pass', 'abstain'] + counts['pass', 'missing'],
            'reference_coverage': _ratio(reference_decided, len(rows)),
            'grader_decision_coverage': _ratio(grader_decided, len(rows)),
            'paired_decision_coverage': _ratio(paired, len(rows)),
            'agreement_on_paired_decisions': _ratio(counts['pass', 'pass'] + counts['fail', 'fail'], paired),
            'false_pass_fraction_on_decided_reference_failures': _ratio(counts['fail', 'pass'], counts['fail', 'pass'] + counts['fail', 'fail']),
            'false_failure_fraction_on_decided_reference_passes': _ratio(counts['pass', 'fail'], counts['pass', 'fail'] + counts['pass', 'pass'])}


def review_grader(plan_raw, reference_raw, judgments_raw, *, plan_sha256):
    plan = validate_plan(plan_raw, plan_sha256)
    if not isinstance(reference_raw, bytes) or digest(reference_raw) != plan['reference_sha256']:
        _reject('reference_byte_pin_mismatch')
    _, reference = _labels(reference_raw, plan, reference=True)
    judgments, grades = _labels(judgments_raw, plan, reference=False)
    observations = []
    for item in sorted(plan['items'], key=lambda row: row['item_id']):
        for criterion in sorted(plan['criteria']):
            key = item['item_id'], criterion
            ref, grader = reference[key], grades.get(key, 'missing')
            reasons = []
            if ref in ('disputed', 'unreviewed'):
                reasons.append('reference_' + ref)
            if grader in ('abstain', 'missing'):
                reasons.append('grader_' + grader)
            if ref in ('pass', 'fail') and grader in ('pass', 'fail') and ref != grader:
                reasons.append('false_pass' if grader == 'pass' else 'false_failure')
            observations.append({**item, 'criterion': criterion, 'reference': ref, 'grader': grader,
                                 'review_reasons': reasons})
    groups = [{'group_id': 'overall', 'item_ids': [item['item_id'] for item in plan['items']]}, *plan['groups']]
    report = {'report_version': 'aau-grader-review/1.0', 'status': 'recorded_grader_diagnostic',
              'plan_file_sha256': plan_sha256, 'reference_file_sha256': digest(reference_raw),
              'judgments_file_sha256': digest(judgments_raw), 'plan': plan, 'grader_id': judgments['grader_id'],
              'observations': observations, 'review_item_count': sum(bool(row['review_reasons']) for row in observations),
              'scopes': [_scope(observations, split, criterion, group) for split in SPLITS
                         for criterion in sorted(plan['criteria']) for group in groups],
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                                        for name in ('grader_review.py', 'agent_bom.py', 'intake_review.py')},
              'boundary': BOUNDARY}
    if len(rendered(report)) > MAX_JSON_BYTES:
        _reject('report_exceeds_limit')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau grader-review', description=__doc__)
    for name in ('plan', 'reference', 'judgments'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--plan-sha256', required=True)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        raw = _read_request(args.plan)
        validate_plan(raw, args.plan_sha256)
        report = review_grader(raw, _read_request(args.reference), _read_request(args.judgments), plan_sha256=args.plan_sha256)
        if args.verify:
            if _read_request(args.verify) != rendered(report):
                _reject('report_does_not_recompute')
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('xb') as stream:
                stream.write(rendered(report))
        print(f"Grader diagnostic: {report['review_item_count']} item/criterion pairs need review. Not grader certification.")
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'grader_input_or_output_rejected'
        print(f'error: {reason}; no verified grader diagnostic.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
