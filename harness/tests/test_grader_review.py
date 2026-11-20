from copy import deepcopy
from itertools import product
import json
import socket
import subprocess

import pytest

from aau_harness import grader_review as module
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.grader_demo import example_inputs
from aau_harness.inspect_pack import InspectionError


@pytest.fixture
def inputs():
    plan, reference, candidates = example_inputs()
    return plan, reference, candidates['group-blind']


def review(inputs):
    plan, reference, judgments = inputs
    raw = rendered(plan)
    return module.review_grader(raw, rendered(reference), rendered(judgments), plan_sha256=digest(raw))


def scope(report, split='validation', group='overall', criterion='authorization'):
    return next(r for r in report['scopes'] if r['split'] == split and r['group_id'] == group and r['criterion'] == criterion)


def test_group_failures_not_hidden_by_calibration_or_aggregate(inputs):
    result = review(inputs)
    assert result == review(inputs)
    assert scope(result, 'calibration')['agreement_on_paired_decisions'] == {'numerator': 2, 'denominator': 2, 'value': 1}
    assert scope(result)['agreement_on_paired_decisions']['numerator'] == 4
    assert scope(result)['agreement_on_paired_decisions']['denominator'] == 6
    group = scope(result, group='assisted-channel')
    assert group['false_passes'] == 2
    assert group['false_pass_fraction_on_decided_reference_failures']['value'] == 1
    assert group['false_failure_fraction_on_decided_reference_passes']['value'] is None
    assert result['review_item_count'] == 4
    assert len(result['observations']) == 10
    assert len(result['scopes']) == 4  # No combined calibration+validation headline.
    assert result['status'] == 'recorded_grader_diagnostic'


def test_perfect_decided_agreement_retains_sparse_coverage_and_unknown_reference():
    plan, reference, candidates = example_inputs()
    result = review((plan, reference, candidates['sparse']))
    overall = scope(result)
    assert overall['agreement_on_paired_decisions']['value'] == 1
    assert overall['paired_decision_coverage'] == {'numerator': 1, 'denominator': 8, 'value': 0.125}
    assert overall['matrix']['disputed']['missing'] == 1
    assert overall['matrix']['unreviewed']['missing'] == 1
    assert overall['reference_failures_without_grader_decision'] == 2
    assert result['observations'][-1]['review_reasons'] == ['reference_unreviewed', 'grader_missing']


def test_all_abstained_or_missing_is_not_perfect_or_zero_failure_rate(inputs):
    inputs[2]['rows'] = []
    report = review(inputs)
    for row in report['scopes']:
        assert row['agreement_on_paired_decisions']['value'] is None
        assert row['false_pass_fraction_on_decided_reference_failures']['value'] is None
        assert row['false_failure_fraction_on_decided_reference_passes']['value'] is None
    assert scope(report)['reference_failures_without_grader_decision'] == 2


@pytest.mark.parametrize('reference,grader', list(product(module.REFERENCE_STATES, module.GRADER_STATES)))
def test_every_reference_and_grader_state_has_an_exact_denominator(reference, grader):
    plan, refs, candidates = example_inputs()
    plan['items'] = [plan['items'][2]]
    plan['groups'] = []
    refs['rows'] = [{**refs['rows'][2], 'verdict': reference}]
    plan['reference_sha256'] = digest(rendered(refs))
    candidate = candidates['group-blind']
    candidate['rows'] = [] if grader == 'missing' else [{**candidate['rows'][2], 'verdict': grader}]
    result = review((plan, refs, candidate))
    row = scope(result)
    assert row['matrix'][reference][grader] == 1
    assert sum(sum(r.values()) for r in row['matrix'].values()) == 1
    paired = reference in ('pass', 'fail') and grader in ('pass', 'fail')
    assert row['paired_decision_coverage']['numerator'] == int(paired)
    assert row['agreement_on_paired_decisions']['value'] == (int(reference == grader) if paired else None)
    assert row['false_passes'] == int(reference == 'fail' and grader == 'pass')
    assert row['false_failures'] == int(reference == 'pass' and grader == 'fail')
    empty = scope(result, 'calibration')
    assert empty['planned_items'] == 0
    assert empty['reference_coverage']['value'] is None


def test_exhaustive_two_item_count_oracle(inputs):
    plan, refs, candidate = inputs
    plan['items'] = plan['items'][2:4]
    plan['groups'] = []
    refs['rows'] = refs['rows'][2:4]
    original = candidate['rows'][2:4]
    states = list(product(module.REFERENCE_STATES, module.GRADER_STATES))
    for pair in product(states, repeat=2):
        for row, (reference, _) in zip(refs['rows'], pair):
            row['verdict'] = reference
        plan['reference_sha256'] = digest(rendered(refs))
        candidate['rows'] = [{**row, 'verdict': grader} for row, (_, grader) in zip(original, pair) if grader != 'missing']
        result = scope(review(inputs))
        paired = [(r, g) for r, g in pair if r in ('pass', 'fail') and g in ('pass', 'fail')]
        agreement = sum(r == g for r, g in paired)
        assert result['agreement_on_paired_decisions'] == {
            'numerator': agreement, 'denominator': len(paired), 'value': agreement / len(paired) if paired else None}
        assert result['paired_decision_coverage']['value'] == len(paired) / 2
        assert sum(sum(row.values()) for row in result['matrix'].values()) == 2


def test_multiple_criteria_and_overlapping_groups_stay_separate(inputs):
    plan, refs, candidate = inputs
    plan['criteria'].append('completion')
    for source in (refs, candidate):
        source['rows'] += [{**row, 'criterion': 'completion', 'verdict': 'pass'} for row in list(source['rows'])]
    plan['groups'].append({'group_id': 'overlapping', 'item_ids': ['case-07', 'case-08']})
    plan['reference_sha256'] = digest(rendered(refs))
    result = review(inputs)
    assert len(result['observations']) == 20
    assert len(result['scopes']) == 12
    assert scope(result, criterion='completion')['false_passes'] == 0
    assert scope(result, group='overlapping')['false_passes'] == 1
    assert scope(result, group='assisted-channel')['false_passes'] == 2


@pytest.mark.parametrize('defect', [
    'extra', 'version', 'empty_items', 'duplicate_id', 'duplicate_hash_same_split', 'duplicate_hash_cross_split',
    'invalid_hash', 'invalid_split', 'invalid_id', 'criteria_empty', 'criteria_duplicate', 'criteria_bool',
    'criteria_too_many', 'items_too_many', 'groups_too_many', 'group_duplicate', 'group_reserved',
    'group_unknown', 'group_empty', 'reference_hash', 'rubric_hash', 'basis_empty', 'basis_large',
])
def test_invalid_or_leaking_plan_rejected(inputs, defect):
    plan = inputs[0]
    if defect == 'extra':
        plan['extra'] = True
    elif defect == 'version':
        plan['plan_version'] = 'future'
    elif defect == 'empty_items':
        plan['items'] = []
    elif defect == 'duplicate_id':
        plan['items'][1]['item_id'] = plan['items'][0]['item_id']
    elif defect.startswith('duplicate_hash'):
        plan['items'][1 if defect.endswith('same_split') else 2]['evidence_sha256'] = plan['items'][0]['evidence_sha256']
    elif defect == 'invalid_hash':
        plan['items'][0]['evidence_sha256'] = 'not-hash'
    elif defect == 'invalid_split':
        plan['items'][0]['split'] = 'test'
    elif defect == 'invalid_id':
        plan['items'][0]['item_id'] = '../escape'
    elif defect.startswith('criteria_'):
        plan['criteria'] = {'criteria_empty': [], 'criteria_duplicate': ['same', 'same'],
                            'criteria_bool': [True], 'criteria_too_many': [f'c{i}' for i in range(11)]}[defect]
    elif defect == 'items_too_many':
        plan['items'] *= 51
    elif defect == 'groups_too_many':
        plan['groups'] *= 20
    elif defect == 'group_duplicate':
        plan['groups'] *= 2
    elif defect == 'group_reserved':
        plan['groups'][0]['group_id'] = 'overall'
    elif defect == 'group_unknown':
        plan['groups'][0]['item_ids'] = ['absent']
    elif defect == 'group_empty':
        plan['groups'][0]['item_ids'] = []
    elif defect == 'reference_hash':
        plan['reference_sha256'] = 'F' * 64
    elif defect == 'rubric_hash':
        plan['rubric_sha256'] = False
    else:
        plan['reference_basis'] = '' if defect == 'basis_empty' else 'x' * 2001
    with pytest.raises(ValueError):
        review(inputs)


@pytest.mark.parametrize('is_reference', [True, False])
@pytest.mark.parametrize('defect', ['duplicate', 'unknown_item', 'unknown_criterion', 'wrong_evidence', 'wrong_rubric',
                                   'wrong_version', 'extra_field', 'numeric_verdict', 'null_verdict', 'invalid_verdict'])
def test_invalid_labels_never_silently_drop_or_coerce(inputs, is_reference, defect):
    source = inputs[1 if is_reference else 2]
    row = source['rows'][0]
    if defect == 'duplicate':
        source['rows'][1] = deepcopy(row)
    elif defect == 'unknown_item':
        row['item_id'] = 'other'
    elif defect == 'unknown_criterion':
        row['criterion'] = 'other'
    elif defect == 'wrong_evidence':
        row['evidence_sha256'] = '0' * 64
    elif defect == 'wrong_rubric':
        source['rubric_sha256'] = '0' * 64
    elif defect == 'wrong_version':
        source['format_version'] = 'future'
    elif defect == 'extra_field':
        row['extra'] = True
    else:
        row['verdict'] = {'numeric_verdict': 1, 'null_verdict': None, 'invalid_verdict': 'missing'}[defect]
    inputs[0]['reference_sha256'] = digest(rendered(inputs[1]))
    with pytest.raises(ValueError):
        review(inputs)


def test_reference_cannot_omit_difficult_cases_even_with_updated_pin(inputs):
    inputs[1]['rows'].pop()
    inputs[0]['reference_sha256'] = digest(rendered(inputs[1]))
    with pytest.raises(InspectionError, match='complete_census'):
        review(inputs)


def test_raw_pins_and_exact_report_verification(inputs, tmp_path):
    plan, reference, judgments = inputs
    reference_raw = rendered(reference) + b' \n'
    plan['reference_sha256'] = digest(reference_raw)
    raw = rendered(plan) + b'\n'
    for name, payload in [('plan', raw), ('reference', reference_raw), ('judgments', rendered(judgments))]:
        (tmp_path / f'{name}.json').write_bytes(payload)
    base = ['grader-review', *[str(tmp_path / f'{name}.json') for name in ('plan', 'reference', 'judgments')],
            '--plan-sha256', digest(raw)]
    report = tmp_path / 'report.json'
    assert main([*base, '--out', str(report)]) == 0  # Known false passes remain a diagnostic, not approval.
    original = report.read_bytes()
    assert main([*base, '--out', str(report)]) == 2
    assert report.read_bytes() == original
    assert main([*base, '--verify', str(report)]) == 0
    report.write_bytes(original + b' ')
    assert main([*base, '--verify', str(report)]) == 2
    (tmp_path / 'reference.json').write_bytes(rendered(reference))
    assert main([*base, '--verify', str(report)]) == 2


def test_bad_plan_pin_rejected_before_source_reads(inputs, tmp_path, monkeypatch):
    raw = rendered(inputs[0])
    calls = []
    def read(path):
        calls.append(path.name)
        if path.name != 'plan.json':
            raise AssertionError('read untrusted evidence before rejecting plan')
        return raw
    monkeypatch.setattr(module, '_read_request', read)
    assert main(['grader-review', 'plan.json', 'ref.json', 'judgments.json', '--plan-sha256', '0' * 64,
                 '--out', str(tmp_path / 'report.json')]) == 2
    assert calls == ['plan.json']


def test_substituted_reference_never_parses_judgments(inputs):
    raw = rendered(inputs[0])
    with pytest.raises(InspectionError, match='reference_byte_pin'):
        module.review_grader(raw, rendered(inputs[1]) + b' ', b'not json', plan_sha256=digest(raw))


@pytest.mark.parametrize('payload', [b'{"a":1,"a":2}', b'NaN', b'{}', b'\xff', b'x' * (MAX_JSON_BYTES + 1)])
def test_malformed_or_oversized_judgments_rejected(inputs, payload):
    raw = rendered(inputs[0])
    with pytest.raises(ValueError):
        module.review_grader(raw, rendered(inputs[1]), payload, plan_sha256=digest(raw))


def test_no_network_or_subprocess_and_input_objects_unchanged(inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('offline diagnostic attempted external execution')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    before = deepcopy(inputs)
    review(inputs)
    assert inputs == before


def test_packaged_demo_recomputes_all_outputs_and_refuses_overwrite(tmp_path):
    folder = tmp_path / 'demo'
    assert main(['grader-demo', '--out', str(folder)]) == 0
    assert main(['grader-demo', '--out', str(folder)]) == 2
    assert len(list(folder.iterdir())) == 11
    plan_raw = (folder / 'plan.json').read_bytes()
    reference_raw = (folder / 'reference.json').read_bytes()
    for name in ('exact-on-decided', 'group-blind', 'sparse', 'abstaining'):
        actual = module.review_grader(plan_raw, reference_raw, (folder / f'{name}.json').read_bytes(), plan_sha256=digest(plan_raw))
        assert load_json(folder / f'{name}-report.json') == actual
        assert str(tmp_path) not in json.dumps(actual)
