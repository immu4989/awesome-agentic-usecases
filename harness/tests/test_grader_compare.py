from copy import deepcopy
from itertools import product
import json
import socket
import subprocess

import pytest

from aau_harness import grader_compare as module
from aau_harness.agent_bom import digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.grader_compare_demo import comparison_inputs, create_demo
from aau_harness.grader_review import GRADER_STATES, REFERENCE_STATES
from aau_harness.inspect_pack import InspectionError


def inputs(name='corrected'):
    plan, reference, baseline, candidates = comparison_inputs()
    return [plan, reference, baseline, candidates[name]]


def payloads(values):
    raw = [rendered(v) for v in values]
    return module.comparison_payloads(*raw, plan_sha256=digest(raw[0]), baseline_sha256=digest(raw[2]))


def scope(report, split='validation', group='overall', criterion='authorization'):
    return next(s for s in report['scopes'] if (s['split'], s['group_id'], s['criterion']) == (split, group, criterion))


@pytest.mark.parametrize('name,corrected,undecided,regressed', [
    ('corrected', 2, 0, 0), ('abstention-trap', 0, 2, 0), ('omission-trap', 0, 2, 0),
    ('net-gain-with-regression', 2, 0, 1),
])
def test_apparent_gains_preserve_corrections_missingness_and_new_errors(name, corrected, undecided, regressed):
    report, files = payloads(inputs(name))
    assert (report, files) == payloads(inputs(name))
    row = scope(report)
    assert row['changes']['wrong_to_right'] == corrected
    assert row['changes']['wrong_to_undecided'] == undecided
    assert row['changes']['right_to_wrong'] == regressed
    assert row['changes']['reference_unresolved'] == 2
    assert row['baseline']['agreement_on_paired_decisions']['value'] == 4 / 6
    assert row['candidate']['agreement_on_paired_decisions']['value'] > 4 / 6
    assert row['common_decided_coverage']['numerator'] == 6 - undecided
    if undecided:
        assert row['baseline_agreement_on_common_decisions']['value'] == 1
        assert row['candidate_agreement_on_common_decisions']['value'] == 1
    assert scope(report, group='assisted-channel')['planned_items'] == 2
    assert scope(report, split='calibration')['changes']['unchanged'] == 2
    assert report['status'] == 'recorded_paired_grader_diagnostic'
    assert len(report['observations']) == 10
    assert set(files) == module.FILES


@pytest.mark.parametrize('ref,before,after', list(product(REFERENCE_STATES, GRADER_STATES, GRADER_STATES)))
def test_exhaustive_single_pair_oracle(ref, before, after):
    values = inputs()
    plan, reference, baseline, candidate = values
    plan['items'] = plan['items'][2:3]
    plan['groups'] = []
    reference['rows'] = [{**reference['rows'][2], 'verdict': ref}]
    plan['reference_sha256'] = digest(rendered(reference))
    for source, state in ((baseline, before), (candidate, after)):
        source['rows'] = [] if state == 'missing' else [{**source['rows'][2], 'verdict': state}]
    report, _ = payloads(values)
    row = scope(report)
    assert row['transition_matrix'][ref][before][after] == 1
    assert sum(v for matrix in row['transition_matrix'].values() for r in matrix.values() for v in r.values()) == 1
    assert sum(row['changes'].values()) == 1
    common = ref in ('pass', 'fail') and before in ('pass', 'fail') and after in ('pass', 'fail')
    assert row['common_decided_coverage']['value'] == int(common)
    for side, state in (('baseline', before), ('candidate', after)):
        ratio = row[side + '_agreement_on_common_decisions']
        assert ratio == {'numerator': int(common and state == ref), 'denominator': int(common),
                         'value': int(state == ref) if common else None}
    if ref in ('disputed', 'unreviewed'):
        expected = 'reference_unresolved'
    elif before == after:
        expected = 'unchanged'
    elif before in ('abstain', 'missing') and after in ('abstain', 'missing'):
        expected = 'undecided_changed'
    else:
        b = 'undecided' if before in ('abstain', 'missing') else 'right' if before == ref else 'wrong'
        a = 'undecided' if after in ('abstain', 'missing') else 'right' if after == ref else 'wrong'
        expected = b + '_to_' + a
    assert row['changes'][expected] == 1
    empty = scope(report, split='calibration')
    assert empty['common_decided_coverage']['value'] is None
    assert empty['candidate_agreement_on_common_decisions']['value'] is None


def test_multiple_criteria_overlapping_groups_and_reordered_rows_do_not_pool():
    values = inputs()
    plan, reference, baseline, candidate = values
    plan['criteria'].append('completion')
    plan['groups'].append({'group_id': 'overlap', 'item_ids': ['case-07', 'case-08']})
    for source in (reference, baseline, candidate):
        source['rows'] += [{**r, 'criterion': 'completion', 'verdict': 'pass'} for r in list(source['rows'])]
        source['rows'].reverse()
    plan['reference_sha256'] = digest(rendered(reference))
    report, _ = payloads(values)
    assert len(report['scopes']) == 12
    assert len(report['observations']) == 20
    assert scope(report, group='overlap')['changes']['wrong_to_right'] == 1
    assert scope(report, criterion='completion')['changes']['wrong_to_right'] == 0


@pytest.mark.parametrize('side', [2, 3])
@pytest.mark.parametrize('defect', ['rubric', 'fingerprint', 'duplicate', 'outside', 'numeric', 'extra'])
def test_each_side_must_obey_the_same_strict_contract(side, defect):
    values = inputs()
    source = values[side]
    if defect == 'rubric':
        source['rubric_sha256'] = '0' * 64
    elif defect == 'fingerprint':
        source['rows'][0]['evidence_sha256'] = '0' * 64
    elif defect == 'duplicate':
        source['rows'].append(deepcopy(source['rows'][0]))
    elif defect == 'outside':
        source['rows'][0]['item_id'] = 'outside'
    elif defect == 'numeric':
        source['rows'][0]['verdict'] = 1
    else:
        source['extra'] = True
    with pytest.raises(InspectionError):
        payloads(values)


@pytest.mark.parametrize('pin', ['plan_sha256', 'baseline_sha256'])
def test_independently_held_pins_reject_changed_control_bytes(pin):
    raw = [rendered(v) for v in inputs()]
    pins = {'plan_sha256': digest(raw[0]), 'baseline_sha256': digest(raw[2])}
    pins[pin] = '0' * 64
    with pytest.raises(InspectionError, match='pin_mismatch'):
        module.comparison_payloads(*raw, **pins)
    pins[pin] = digest(raw[0 if pin == 'plan_sha256' else 2])
    raw[0 if pin == 'plan_sha256' else 2] += b' '
    with pytest.raises(InspectionError, match='pin_mismatch'):
        module.comparison_payloads(*raw, **pins)


def make_pack(path):
    raw = [rendered(v) for v in inputs()]
    pins = {'plan_sha256': digest(raw[0]), 'baseline_sha256': digest(raw[2])}
    report = module.create_comparison(*raw, path, **pins)
    assert module.verify_comparison(path, **pins) == report
    return pins


@pytest.mark.parametrize('member', sorted(module.FILES))
def test_every_retained_byte_is_verified_even_if_manifest_is_rehashed(tmp_path, member):
    packet = tmp_path / 'packet'
    pins = make_pack(packet)
    (packet / member).write_bytes((packet / member).read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = json.loads((packet / 'manifest.json').read_bytes())
        manifest['files_sha256'][member] = digest((packet / member).read_bytes())
        (packet / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(InspectionError):
        module.verify_comparison(packet, **pins)


@pytest.mark.parametrize('defect', ['extra', 'directory', 'symlink', 'missing'])
def test_incomplete_or_unexpected_inventory_is_rejected(tmp_path, defect):
    packet = tmp_path / 'packet'
    pins = make_pack(packet)
    if defect == 'directory':
        (packet / 'extra').mkdir()
    elif defect == 'symlink':
        (packet / 'extra').symlink_to(packet / 'review.json')
    elif defect == 'missing':
        (packet / 'candidate.json').unlink()
    else:
        (packet / 'extra').write_text('unexpected')
    with pytest.raises(InspectionError):
        module.verify_comparison(packet, **pins)


def test_same_grader_id_is_not_identity_proof_and_empty_judgments_are_not_a_win():
    values = inputs()
    values[3]['grader_id'] = values[2]['grader_id']
    values[2]['rows'] = []
    values[3]['rows'] = []
    report, _ = payloads(values)
    assert report['baseline_grader_id'] == report['candidate_grader_id']
    row = scope(report)
    assert row['candidate']['agreement_on_paired_decisions']['value'] is None
    assert row['common_decided_coverage']['value'] == 0
    assert row['changes']['unchanged'] == 6  # Known reference, both missing; not six correct decisions.


def test_offline_and_expansion_bounds(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected execution')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    report, files = payloads(inputs())
    assert b'<script' not in files['review.html']
    assert b'scope="row"' in files['review.html']
    assert report['boundary'] == module.BOUNDARY
    monkeypatch.setattr(module, 'MAX_JSON_BYTES', 100)
    with pytest.raises(InspectionError, match='exceeds_limit'):
        payloads(inputs())


def test_cli_demo_creation_verification_and_overwrite_refusal(tmp_path):
    root = tmp_path / 'demo'
    assert main(['grader-compare', 'demo', '--out', str(root)]) == 0
    assert main(['grader-compare', 'demo', '--out', str(root)]) == 2
    for name in comparison_inputs()[3]:
        packet = root / name
        pin = digest((packet / 'plan.json').read_bytes())
        base_pin = digest((packet / 'baseline.json').read_bytes())
        args = ['--plan-sha256', pin, '--baseline-sha256', base_pin]
        assert main(['grader-compare', 'verify', str(packet), *args]) == 0
        out = tmp_path / name
        create = ['grader-compare', 'create', *(str(packet / f'{n}.json') for n in ('plan', 'reference', 'baseline', 'candidate')),
                  *args, '--out', str(out)]
        assert main(create) == 0
        assert main(create) == 2
        assert main(['grader-compare', 'verify', str(packet), '--plan-sha256', pin, '--baseline-sha256', '0' * 64]) == 2
    assert '5/6' in (root / 'README.md').read_text()
    with pytest.raises(ValueError):
        create_demo(root)
