from copy import deepcopy
import json

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.evidence_index import create_index, index_payloads, validate_request, verify_index
from aau_harness.inspect_pack import _capture
from aau_harness.source_index_demo import EXPORTERS, VARIANTS, build_inputs


def payloads(request, delivery):
    files, dirs = _capture(delivery)
    raw = rendered(request)
    return index_payloads(raw, files, dirs, request_sha256=digest(raw))


@pytest.mark.parametrize('exporter', EXPORTERS)
@pytest.mark.parametrize('variant', VARIANTS)
def test_source_linked_examples_replay_without_promoting_evidence(tmp_path, exporter, variant):
    request, delivery = build_inputs(tmp_path, exporter, variant)
    raw, pin = rendered(request), digest(rendered(request))
    report = create_index(raw, delivery, tmp_path / 'index', request_sha256=pin)
    assert report == verify_index(tmp_path / 'index', request_sha256=pin)
    assert report['exit_code'] == (0 if variant == 'linked-source' else 1)
    assert report['decision_status'] == 'not_assessed' and report['human_review_required']
    by_id = {r['item_id']: r for r in report['items']}
    diagnostic = by_id['diagnostic']
    assert diagnostic['verification_status'] == 'verified'
    assert diagnostic['native_outcome_kind'] == 'source_diagnostic_not_conversion'
    if variant == 'rejected-conversion':
        assert by_id['conversion']['verification_status'] == 'missing'
        assert diagnostic['native_report']['conversion_eligibility']['status'] == 'rejected_by_current_converter'
        assert all(b['status'] == 'not_checked_unverified_item' for b in report['bindings'])
    elif variant == 'substituted-source':
        assert [b['status'] for b in report['bindings']] == ['mismatched', 'matched']
    elif variant == 'policy-context-gap':
        policy = by_id['policy']
        assert policy['verification_status'] == 'receiver_controls_not_matched'
        assert policy['native_report']['declared_context']['status'] == 'unavailable'
        assert 'matching_declared_context' in policy['native_report']['failed_constraints']
        assert policy['native_outcome_status'] == 'constraints_not_met'
        assert report['bindings'][-1]['status'] == 'not_checked_unverified_item'
    else:
        assert all(b['status'] == 'matched' for b in report['bindings'])
        assert by_id['conversion']['native_outcome_kind'] == 'conversion_not_quality'
    for path in delivery.rglob('*'):
        if path.is_file():
            assert (tmp_path / 'index/evidence' / path.relative_to(delivery)).read_bytes() == path.read_bytes()


@pytest.mark.parametrize('exporter', EXPORTERS)
def test_diagnostic_only_request_can_verify_but_never_claim_conversion(tmp_path, exporter):
    request, delivery = build_inputs(tmp_path, exporter, 'rejected-conversion')
    request['items'] = request['items'][1:]
    request['bindings'] = []
    report, generated, _ = payloads(request, delivery)
    assert report['exit_code'] == 0
    assert report['items'][0]['native_report']['conversion_eligibility']['status'] == 'rejected_by_current_converter'
    assert not any(name.endswith('evaluation.json') for name in generated)
    assert report['decision_status'] == 'not_assessed'


@pytest.mark.parametrize('exporter', EXPORTERS)
@pytest.mark.parametrize('role', ['conversion', 'diagnostic'])
def test_wrong_requested_plan_pin_never_falls_back(tmp_path, exporter, role):
    request, delivery = build_inputs(tmp_path, exporter, 'linked-source')
    next(i for i in request['items'] if i['item_id'] == role)['controls']['plan_sha256'] = '0' * 64
    report, _, _ = payloads(request, delivery)
    assert next(i for i in report['items'] if i['item_id'] == role)['verification_status'] == 'verification_failed'
    assert all(b['status'] == 'not_checked_unverified_item' for b in report['bindings'])
    assert report['exit_code'] == 1


@pytest.mark.parametrize('exporter', EXPORTERS)
def test_same_source_does_not_imply_same_mapping(tmp_path, exporter):
    request, delivery = build_inputs(tmp_path, exporter, 'linked-source')
    plan = json.loads((delivery / 'diagnostic/plan.json').read_bytes())
    plan['source_label'] = 'A different independently pinned mapping document'
    plan_raw = rendered(plan)
    source_raw = (delivery / 'diagnostic/source.json').read_bytes()
    if exporter == 'inspect':
        from aau_harness.inspect_diagnostic import diagnostic_payloads
    else:
        from aau_harness.promptfoo_diagnostic import diagnostic_payloads
    _, changed = diagnostic_payloads(plan_raw, source_raw, plan_sha256=digest(plan_raw))
    files, dirs = _capture(delivery)
    files.update({'diagnostic/' + name: raw for name, raw in changed.items()})
    request['items'][1]['controls']['plan_sha256'] = digest(plan_raw)
    raw = rendered(request)
    report, _, _ = index_payloads(raw, files, dirs, request_sha256=digest(raw))
    assert report['verified_count'] == 2
    assert [b['status'] for b in report['bindings']] == ['matched', 'mismatched']
    assert report['exit_code'] == 1


@pytest.mark.parametrize('exporter', EXPORTERS)
def test_source_binding_is_byte_exact_even_when_json_meaning_is_unchanged(tmp_path, exporter):
    request, delivery = build_inputs(tmp_path, exporter, 'linked-source')
    raw_plan = (delivery / 'diagnostic/plan.json').read_bytes()
    source = (delivery / 'diagnostic/source.json').read_bytes()
    if exporter == 'inspect':
        from aau_harness.inspect_diagnostic import diagnostic_payloads
    else:
        from aau_harness.promptfoo_diagnostic import diagnostic_payloads
    _, changed = diagnostic_payloads(raw_plan, b' ' + source, plan_sha256=digest(raw_plan))
    files, dirs = _capture(delivery)
    files.update({'diagnostic/' + name: raw for name, raw in changed.items()})
    raw = rendered(request)
    report, _, _ = index_payloads(raw, files, dirs, request_sha256=digest(raw))
    assert report['verified_count'] == 2 and report['bindings'][0]['status'] == 'mismatched'
    assert report['bindings'][1]['status'] == 'matched'


@pytest.mark.parametrize('exporter', EXPORTERS)
@pytest.mark.parametrize('role', ['conversion', 'diagnostic'])
def test_bad_child_retained_without_executing_it_or_using_its_bindings(tmp_path, exporter, role):
    request, delivery = build_inputs(tmp_path, exporter, 'linked-source')
    files, dirs = _capture(delivery)
    marker = tmp_path / 'executed'
    files[role + '/untrusted.py'] = f'open({str(marker)!r}, "w").write("bad")'.encode()
    raw = rendered(request)
    report, output, _ = index_payloads(raw, files, dirs, request_sha256=digest(raw))
    assert next(i for i in report['items'] if i['item_id'] == role)['verification_status'] == 'verification_failed'
    assert output[f'evidence/{role}/untrusted.py'] == files[role + '/untrusted.py']
    assert not marker.exists()
    assert all(b['status'] == 'not_checked_unverified_item' for b in report['bindings'])


@pytest.mark.parametrize('exporter', EXPORTERS)
@pytest.mark.parametrize('change', ['evaluation-role', 'custom-path', 'extra-control', 'other-producer'])
def test_no_requested_paths_or_weaker_profile_fallback(tmp_path, exporter, change):
    request, delivery = build_inputs(tmp_path, exporter, 'linked-source')
    if change == 'other-producer':
        other = 'promptfoo' if exporter == 'inspect' else 'inspect'
        request['items'][1]['profile'] = other + '-diagnostic'
        report, _, _ = payloads(request, delivery)
        assert report['items'][1]['verification_status'] == 'verification_failed'
    else:
        if change == 'evaluation-role':
            request['bindings'][0]['right']['role'] = 'evaluation'
        elif change == 'custom-path':
            request['bindings'][0]['right']['role'] = '../evaluation.json'
        else:
            request['items'][1]['controls']['fallback'] = 'promptfoo-conversion'
        raw = rendered(request)
        with pytest.raises(AgentBomError):
            validate_request(raw, digest(raw))


@pytest.mark.parametrize('exporter', EXPORTERS)
def test_outer_replay_rejects_changed_retained_diagnostic_even_after_manifest_rehash(tmp_path, exporter):
    request, delivery = build_inputs(tmp_path, exporter, 'linked-source')
    raw = rendered(request)
    packet = tmp_path / 'index'
    create_index(raw, delivery, packet, request_sha256=digest(raw))
    relative = 'evidence/diagnostic/diagnostic.json'
    (packet / relative).write_bytes((packet / relative).read_bytes() + b' ')
    manifest = json.loads((packet / 'manifest.json').read_bytes())
    manifest['files_sha256'][relative] = digest((packet / relative).read_bytes())
    (packet / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_index(packet, request_sha256=digest(raw))


def test_controls_stay_unchanged_after_indexing(tmp_path):
    request, delivery = build_inputs(tmp_path, 'promptfoo', 'linked-source')
    original = deepcopy(request)
    payloads(request, delivery)
    assert request == original
