from copy import deepcopy
import json
import socket
import subprocess

import pytest

from aau_harness.agent_bom import digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.evidence_index import create_index, index_payloads, validate_request, verify_index
from aau_harness.grader_demo import example_inputs
from aau_harness.grader_pack import FILES, create_grader_pack, grader_payloads, verify_grader_pack
from aau_harness.grader_pack_demo import VARIANTS, build_inputs
from aau_harness.grader_review import review_grader
from aau_harness.inspect_pack import _capture


def inputs(name='group-blind'):
    plan, reference, candidates = example_inputs()
    return tuple(map(rendered, (plan, reference, candidates[name])))


@pytest.mark.parametrize('name', ['exact-on-decided', 'group-blind', 'sparse', 'abstaining'])
def test_packets_preserve_native_diagnostics_and_exact_inputs(tmp_path, name):
    plan, reference, judgments = inputs(name)
    # Noncanonical source whitespace must survive; adjust the independent plan's reference byte pin.
    reference += b'\n'
    changed = json.loads(plan)
    changed['reference_sha256'] = digest(reference)
    plan = rendered(changed) + b'\n'
    judgments += b'\n'
    report = create_grader_pack(plan, reference, judgments, tmp_path / 'pack', plan_sha256=digest(plan))
    assert report == review_grader(plan, reference, judgments, plan_sha256=digest(plan))
    assert report == verify_grader_pack(tmp_path / 'pack', plan_sha256=digest(plan))
    assert report['status'] == 'recorded_grader_diagnostic'
    assert set(p.name for p in (tmp_path / 'pack').iterdir()) == FILES
    for member, raw in zip(('plan.json', 'reference.json', 'judgments.json'), (plan, reference, judgments)):
        assert (tmp_path / 'pack' / member).read_bytes() == raw
    validation = next(s for s in report['scopes'] if s['split'] == 'validation' and s['group_id'] == 'overall')
    if name == 'group-blind':
        assert validation['false_passes'] == 2
    elif name == 'sparse':
        assert sum(r['grader'] == 'missing' for r in report['observations']) == 7
    elif name == 'abstaining':
        assert validation['agreement_on_paired_decisions']['value'] is None


@pytest.mark.parametrize('member', sorted(FILES))
def test_derived_tampering_and_manifest_rehash_never_validate(tmp_path, member):
    plan, reference, judgments = inputs()
    packet = tmp_path / 'pack'
    create_grader_pack(plan, reference, judgments, packet, plan_sha256=digest(plan))
    target = packet / member
    target.write_bytes(target.read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = json.loads((packet / 'manifest.json').read_bytes())
        manifest['files'][member] = digest(target.read_bytes())
        (packet / 'manifest.json').write_bytes(rendered(manifest))
    # A judgment whitespace change is a legitimate new input only if the derived report is recomputed;
    # its old report must still be rejected, even if the manifest hashes are updated.
    with pytest.raises(ValueError):
        verify_grader_pack(packet, plan_sha256=digest(plan))


@pytest.mark.parametrize('defect', ['extra', 'missing', 'nested', 'symlink'])
def test_exact_bounded_inventory_required(tmp_path, defect):
    plan, reference, judgments = inputs()
    packet = tmp_path / 'pack'
    create_grader_pack(plan, reference, judgments, packet, plan_sha256=digest(plan))
    if defect == 'extra':
        (packet / 'script.py').write_text('raise RuntimeError("never execute")')
    elif defect == 'missing':
        (packet / 'README.txt').unlink()
    elif defect == 'nested':
        (packet / 'nested').mkdir()
    else:
        (packet / 'README.txt').rename(tmp_path / 'guide.txt')
        (packet / 'README.txt').symlink_to(tmp_path / 'guide.txt')
    with pytest.raises(ValueError):
        verify_grader_pack(packet, plan_sha256=digest(plan))


@pytest.mark.parametrize('defect', ['wrong-pin', 'reference-change', 'duplicate-judgment', 'unknown-verdict'])
def test_invalid_inputs_do_not_create_output(tmp_path, defect):
    plan, reference, judgments = inputs()
    pin = digest(plan)
    if defect == 'wrong-pin':
        pin = '0' * 64
    elif defect == 'reference-change':
        reference += b' '
    else:
        changed = json.loads(judgments)
        if defect == 'duplicate-judgment':
            changed['rows'].append(deepcopy(changed['rows'][0]))
        else:
            changed['rows'][0]['verdict'] = 'approved'
        judgments = rendered(changed)
    with pytest.raises(ValueError):
        create_grader_pack(plan, reference, judgments, tmp_path / 'rejected', plan_sha256=pin)
    assert not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('variant', VARIANTS)
def test_reference_chain_preserves_native_findings_and_rejects_substitution(tmp_path, variant):
    request, delivery = build_inputs(tmp_path, variant)
    raw = rendered(request)
    report = create_index(raw, delivery, tmp_path / 'index', request_sha256=digest(raw))
    assert report == verify_index(tmp_path / 'index', request_sha256=digest(raw))
    assert report['exit_code'] == (0 if variant == 'linked-false-passes' else 1)
    assert report['decision_status'] == 'not_assessed' and report['human_review_required']
    grader = report['items'][1]
    assert grader['verification_status'] == 'verified'
    assert grader['native_outcome_kind'] == 'grader_diagnostic_not_certification'
    native = grader['native_report']
    validation = next(s for s in native['scopes'] if s['split'] == 'validation' and s['group_id'] == 'overall')
    if variant == 'linked-false-passes':
        assert validation['false_passes'] == 2
        assert validation['reference_coverage']['numerator'] == 2
        assert validation['reference_coverage']['denominator'] == 5
        assert [b['status'] for b in report['bindings']] == ['matched', 'matched']
        assert report['items'][0]['native_outcome_kind'] == 'reference_diagnostic_not_truth'
    elif variant == 'missing-provenance':
        assert report['items'][0]['verification_status'] == 'missing'
        assert all(b['status'] == 'not_checked_unverified_item' for b in report['bindings'])
    elif variant == 'substituted-reference':
        assert validation['false_passes'] == 0
        assert report['verified_count'] == 2
        assert all(b['status'] == 'mismatched' for b in report['bindings'])
    else:
        assert report['verified_count'] == 2
        assert [b['status'] for b in report['bindings']] == ['matched', 'mismatched']


@pytest.mark.parametrize('identity', ['panel', 'grader'])
@pytest.mark.parametrize('defect', ['wrong-pin', 'modified-report'])
def test_index_never_binds_failed_packet(tmp_path, identity, defect):
    request, delivery = build_inputs(tmp_path, 'linked-false-passes')
    files, dirs = _capture(delivery)
    if defect == 'wrong-pin':
        next(i for i in request['items'] if i['item_id'] == identity)['controls']['plan_sha256'] = '0' * 64
    else:
        files[identity + ('/review.json' if identity == 'panel' else '/report.json')] += b' '
    raw = rendered(request)
    report, _, _ = index_payloads(raw, files, dirs, request_sha256=digest(raw))
    assert next(i for i in report['items'] if i['item_id'] == identity)['verification_status'] == 'verification_failed'
    assert report['exit_code'] == 1
    assert all(b['status'] == 'not_checked_unverified_item' for b in report['bindings'])


def test_unbound_packets_do_not_claim_label_provenance(tmp_path):
    request, delivery = build_inputs(tmp_path, 'substituted-reference')
    request['bindings'] = []
    raw = rendered(request)
    report = create_index(raw, delivery, tmp_path / 'index', request_sha256=digest(raw))
    assert report['exit_code'] == 0 and report['bindings'] == []
    assert report['decision_status'] == 'not_assessed'


def test_closed_roles_do_not_allow_arbitrary_paths(tmp_path):
    request, _ = build_inputs(tmp_path, 'linked-false-passes')
    request['bindings'][0]['left']['role'] = '../reference.json'
    raw = rendered(request)
    with pytest.raises(ValueError):
        validate_request(raw, digest(raw))


def test_cli_and_no_network_or_process_execution(tmp_path, monkeypatch):
    calls = []
    def deny(*args, **kwargs):
        calls.append(True)
        raise RuntimeError('unexpected network or subprocess')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(subprocess, 'Popen', deny)
    plan, reference, judgments = inputs()
    for name, raw in zip(('plan', 'reference', 'judgments'), (plan, reference, judgments)):
        (tmp_path / (name + '.json')).write_bytes(raw)
    args = ['grader-pack', 'create', *(str(tmp_path / (n + '.json')) for n in ('plan', 'reference', 'judgments')),
            '--plan-sha256', digest(plan), '--out', str(tmp_path / 'packet')]
    assert main(args) == 0
    assert main(args) == 2
    assert main(['grader-pack', 'verify', str(tmp_path / 'packet'), '--plan-sha256', digest(plan)]) == 0
    assert main(['grader-pack', 'verify', str(tmp_path / 'packet'), '--plan-sha256', '0' * 64]) == 2
    assert main(['grader-pack', 'demo', '--out', str(tmp_path / 'demo')]) == 0
    assert main(['grader-pack', 'demo', '--out', str(tmp_path / 'demo')]) == 2
    assert not calls


def test_payload_generation_is_deterministic():
    plan, reference, judgments = inputs()
    first = grader_payloads(plan, reference, judgments, plan_sha256=digest(plan))
    assert first == grader_payloads(plan, reference, judgments, plan_sha256=digest(plan))
