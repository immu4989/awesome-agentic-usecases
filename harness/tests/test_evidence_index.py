from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.evidence_index import create_index, index_payloads, validate_request, verify_index
from aau_harness.evidence_index_demo import build_inputs, create_demo
from aau_harness.inspect_pack import _capture


@pytest.fixture
def inputs(tmp_path):
    request, delivery, *_ = build_inputs(tmp_path)
    files, directories = _capture(delivery)
    return request, delivery, files, directories


def payloads(request, files, directories):
    raw = rendered(request)
    return index_payloads(raw, files, directories, request_sha256=digest(raw))


def test_complete_byte_linked_delivery_does_not_cancel_failed_policy(inputs):
    request, _, files, directories = inputs
    originals = deepcopy((request, files, directories))
    report, generated, dirs = payloads(request, files, directories)
    assert (request, files, directories) == originals
    assert report['exit_code'] == 0 and report['verified_count'] == 3
    assert report['decision_status'] == 'not_assessed' and report['human_review_required'] is True
    assert report['items'][0]['verification_status'] == 'verified'
    assert report['items'][0]['native_outcome_status'] == 'constraints_not_met'
    assert report['items'][1]['native_report']['scopes'][0]['regressed'] == 1
    assert report['items'][2]['native_outcome_status'] == 'coverage_met'
    assert all(b['status'] == 'matched' for b in report['bindings'])
    assert len(generated) == len(files) + 4 and 'evidence' in dirs
    for name, raw in files.items():
        assert generated['evidence/' + name] == raw


def test_missing_empty_and_invalid_are_not_conflated(inputs):
    request, _, files, directories = inputs
    remaining = {n: raw for n, raw in files.items() if not n.startswith('coverage/')}
    missing, _, _ = payloads(request, remaining, [n for n in directories if n != 'coverage'])
    empty, _, dirs = payloads(request, remaining, directories)
    assert missing['items'][2]['verification_status'] == 'missing'
    assert missing['items'][2]['captured_files_sha256'] is None
    assert empty['items'][2]['verification_status'] == 'verification_failed'
    assert empty['items'][2]['captured_files_sha256'] == {}
    assert 'evidence/coverage' in dirs
    for report in (missing, empty):
        assert report['exit_code'] == 1
        assert report['bindings'][1]['status'] == 'not_checked_unverified_item'
        assert report['bindings'][1]['right_file_sha256'] is None


def test_all_missing_is_an_explicit_replayable_report(inputs, tmp_path):
    request, _, _, _ = inputs
    empty = tmp_path / 'empty'
    empty.mkdir()
    raw = rendered(request)
    packet = tmp_path / 'packet'
    report = create_index(raw, empty, packet, request_sha256=digest(raw))
    assert report == verify_index(packet, request_sha256=digest(raw))
    assert report['verified_count'] == 0 and report['missing_count'] == 3
    assert report['exit_code'] == 1


def test_modified_derived_child_is_retained_but_never_used_in_binding(inputs):
    request, _, files, directories = inputs
    files['comparison/report.json'] += b' '
    report, generated, _ = payloads(request, files, directories)
    assert report['items'][1]['verification_status'] == 'verification_failed'
    assert report['items'][1]['native_report'] is None
    assert report['bindings'][0]['status'] == 'not_checked_unverified_item'
    assert generated['evidence/comparison/report.json'] == files['comparison/report.json']


def test_control_changes_fail_even_when_native_packet_is_valid(inputs):
    request, _, files, directories = inputs
    request['items'][0]['controls']['intake_request']['pinned_inputs']['baseline'] = '0' * 64
    report, _, _ = payloads(request, files, directories)
    item = report['items'][0]
    assert item['verification_status'] == 'receiver_controls_not_matched'
    assert item['native_report']['unmatched_input_roles'] == ['baseline']
    assert report['exit_code'] == 1 and report['bindings'][0]['status'] == 'not_checked_unverified_item'


def test_binding_is_strict_bytes_not_semantic_json_and_no_binding_is_no_claim(inputs):
    request, _, files, directories = inputs
    # Create a valid new coverage packet with a different original serialization.
    from aau_harness.coverage_review import coverage_payloads
    raw = files['coverage/plan.json']
    _, changed = coverage_payloads(raw, files['coverage/inventory.json'], b' ' + files['coverage/evaluation.json'],
                                   plan_sha256=digest(raw))
    files.update({'coverage/' + n: v for n, v in changed.items()})
    report, _, _ = payloads(request, files, directories)
    assert report['verified_count'] == 3 and report['exit_code'] == 1
    assert report['bindings'][1]['status'] == 'mismatched'
    request['bindings'] = []
    unbound, _, _ = payloads(request, files, directories)
    assert unbound['bindings'] == [] and unbound['exit_code'] == 0
    assert unbound['decision_status'] == 'not_assessed'


def test_native_coverage_gap_remains_a_distinct_finding_not_a_corrupt_packet(inputs):
    from aau_harness.coverage_review import coverage_payloads
    request, _, files, directories = inputs
    plan = json.loads(files['coverage/plan.json'])
    plan['dimensions']['channel'].append('unobserved-path')
    raw = rendered(plan)
    request['items'][2]['controls']['plan_sha256'] = digest(raw)
    _, changed = coverage_payloads(raw, files['coverage/inventory.json'], files['coverage/evaluation.json'], plan_sha256=digest(raw))
    files.update({'coverage/' + n: v for n, v in changed.items()})
    report, _, _ = payloads(request, files, directories)
    assert report['exit_code'] == 0 and report['items'][2]['verification_status'] == 'verified'
    assert report['items'][2]['native_outcome_status'] != 'coverage_met'
    assert report['decision_status'] == 'not_assessed'


@pytest.mark.parametrize('recordings', [False, True])
def test_policy_budget_and_diagnostic_controls_are_not_lost(tmp_path, recordings):
    from aau_harness.eval_demo import demo_inputs
    from aau_harness.eval_import import import_observations
    from aau_harness.eval_pack import create_pack
    policy, baseline, candidate, diagnostics = demo_inputs()
    budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': policy['scenario_ids'], 'minimum_repeats': 4,
              'criteria': diagnostics['criteria'], 'cost_basis': 'synthetic', 'groups': [], 'limits': {'total_cost_usd': 2}}
    if not recordings:
        baseline, candidate = import_observations(baseline), import_observations(candidate)
    delivery = tmp_path / 'delivery'
    create_pack(policy, baseline, candidate, delivery / 'policy', recordings=recordings,
                diagnostics=diagnostics, operating_budget=budget)
    controls = {'request_version': 'aau-evidence-intake-request/1.0', 'profile': 'evaluation-review',
                'pack_version': 'aau-evaluation-review-pack/3.0', 'input_format': 'recordings' if recordings else 'evaluations',
                'pinned_inputs': {role: digest(rendered(value)) for role, value in (
                    ('policy', policy), ('baseline', baseline), ('diagnostics', diagnostics), ('operating_budget', budget))}}
    request = {'request_version': 'aau-evidence-index-request/1.0', 'purpose': 'Synthetic budget handoff test',
               'items': [{'item_id': 'policy', 'profile': 'policy-review', 'purpose': 'Preserve budget controls',
                          'controls': {'intake_request': controls}}], 'bindings': []}
    files, dirs = _capture(delivery)
    report, _, _ = payloads(request, files, dirs)
    assert report['exit_code'] == 0
    assert report['items'][0]['native_report']['pack_inspection']['assessment']['candidate_budget_status'] == 'constraints_met'
    controls['pinned_inputs']['operating_budget'] = '0' * 64
    changed, _, _ = payloads(request, files, dirs)
    assert changed['exit_code'] == 1
    assert changed['items'][0]['verification_status'] == 'receiver_controls_not_matched'


@pytest.mark.parametrize('defect', ['request-extra', 'version', 'purpose', 'empty-items', 'too-many-items',
    'duplicate-id', 'path-id', 'unknown-profile', 'item-extra', 'item-purpose', 'missing-controls', 'bad-plan-pin',
    'policy-missing-baseline', 'policy-source-profile', 'binding-extra', 'unknown-item', 'unknown-role', 'path-role',
    'self-binding', 'duplicate-binding', 'reversed-duplicate', 'too-many-bindings', 'endpoint-extra'])
def test_request_contract_is_closed_before_delivery_read(inputs, tmp_path, defect):
    request, _, _, _ = inputs
    if defect == 'request-extra':
        request['command'] = 'do not execute'
    elif defect == 'version':
        request['request_version'] = 'future'
    elif defect == 'purpose':
        request['purpose'] = ''
    elif defect == 'empty-items':
        request['items'] = []
    elif defect == 'too-many-items':
        request['items'] *= 3
    elif defect == 'duplicate-id':
        request['items'][1]['item_id'] = 'policy'
    elif defect == 'path-id':
        request['items'][0]['item_id'] = '../outside'
    elif defect == 'unknown-profile':
        request['items'][0]['profile'] = 'untrusted.module'
    elif defect == 'item-extra':
        request['items'][0]['path'] = '/tmp/untrusted'
    elif defect == 'item-purpose':
        request['items'][0]['purpose'] = 'x' * 1001
    elif defect == 'missing-controls':
        request['items'][0]['controls'] = {}
    elif defect == 'bad-plan-pin':
        request['items'][1]['controls']['plan_sha256'] = 'bad'
    elif defect == 'policy-missing-baseline':
        del request['items'][0]['controls']['intake_request']['pinned_inputs']['baseline']
    elif defect == 'policy-source-profile':
        request['items'][0]['controls']['intake_request']['profile'] = 'csv-source'
    elif defect == 'binding-extra':
        request['bindings'][0]['url'] = 'https://invalid.example'
    elif defect in ('unknown-item', 'unknown-role', 'path-role', 'endpoint-extra'):
        point = request['bindings'][0]['left']
        if defect == 'unknown-item':
            point['item_id'] = 'unknown'
        elif defect == 'endpoint-extra':
            point['path'] = '/tmp/extra'
        else:
            point['role'] = 'unknown' if defect == 'unknown-role' else '../plan.json'
    elif defect == 'self-binding':
        request['bindings'][0]['right'] = {'item_id': 'policy', 'role': 'baseline'}
    elif defect in ('duplicate-binding', 'reversed-duplicate'):
        binding = deepcopy(request['bindings'][0])
        if defect == 'reversed-duplicate':
            binding = {'left': binding['right'], 'right': binding['left']}
        request['bindings'].append(binding)
    elif defect == 'too-many-bindings':
        request['bindings'] *= 11
    raw = rendered(request)
    with pytest.raises(AgentBomError):
        create_index(raw, tmp_path / 'unread-missing-delivery', tmp_path / 'no-output', request_sha256=digest(raw))
    assert not (tmp_path / 'no-output').exists()


@pytest.mark.parametrize('defect', ['root-file', 'undeclared-directory', 'nested-directory', 'traversal',
                                  'backslash', 'too-many-files', 'oversized', 'non-bytes', 'duplicate-directory'])
def test_delivery_inventory_cannot_hide_extra_scope_or_write_paths(inputs, defect):
    request, _, files, directories = inputs
    if defect == 'root-file':
        files['extra.json'] = b'{}'
    elif defect == 'undeclared-directory':
        directories.append('unrequested')
    elif defect == 'nested-directory':
        directories.append('policy/extra')
    elif defect == 'traversal':
        files['policy/..'] = b'bad'
    elif defect == 'backslash':
        files['policy/bad\\name.json'] = b'bad'
    elif defect == 'too-many-files':
        files.update({f'policy/extra-{i}.json': b'{}' for i in range(61)})
    elif defect == 'oversized':
        files['policy/extra.json'] = b' ' * (MAX_JSON_BYTES + 1)
    elif defect == 'non-bytes':
        files['policy/extra.json'] = {}
    elif defect == 'duplicate-directory':
        directories.append(directories[0])
    with pytest.raises(AgentBomError):
        payloads(request, files, directories)


def test_bad_control_pin_does_not_fallback_to_weaker_child_or_other_profile(inputs):
    request, _, files, directories = inputs
    request['items'][1]['controls']['plan_sha256'] = '0' * 64
    report, _, _ = payloads(request, files, directories)
    assert report['items'][1]['verification_status'] == 'verification_failed'
    assert report['exit_code'] == 1


def test_html_and_code_in_invalid_packet_are_never_executed_or_reflected(inputs, tmp_path):
    request, _, files, directories = inputs
    request['purpose'] = '<script>injected</script>'
    marker = tmp_path / 'executed'
    files['comparison/run.py'] = f'open({str(marker)!r}, "w").write("executed")'.encode()
    files['comparison/review.html'] = b'<script>injected</script>'
    report, generated, _ = payloads(request, files, directories)
    assert not marker.exists()
    assert report['items'][1]['verification_status'] == 'verification_failed'
    assert b'<script>' not in generated['review.html']
    assert b'&lt;script&gt;' in generated['review.html']
    assert b'role="group"' in generated['review.html']


@pytest.mark.parametrize('member', ['request.json', 'report.json', 'review.html', 'manifest.json',
                                  'evidence/policy/candidate.json', 'extra.json', 'empty-directory', 'symlink'])
def test_source_retention_exact_external_pin_and_tamper_rejection(inputs, tmp_path, member):
    request, delivery, files, _ = inputs
    raw = b' ' + rendered(request)
    packet = tmp_path / 'index'
    original = create_index(raw, delivery, packet, request_sha256=digest(raw))
    assert original == verify_index(packet, request_sha256=digest(raw))
    for name, data in files.items():
        assert (packet / 'evidence' / name).read_bytes() == data
    with pytest.raises(AgentBomError):
        verify_index(packet, request_sha256=digest(rendered(request)))
    with pytest.raises(AgentBomError):
        create_index(raw, delivery, packet, request_sha256=digest(raw))
    if member == 'empty-directory':
        (packet / member).mkdir()
    elif member == 'symlink':
        (packet / member).symlink_to(packet / 'request.json')
    else:
        with (packet / member).open('ab') as stream:
            stream.write(b' ')
    with pytest.raises(AgentBomError):
        verify_index(packet, request_sha256=digest(raw))


def test_symlink_delivery_and_nested_output_refused(inputs, tmp_path):
    request, delivery, _, _ = inputs
    raw = rendered(request)
    link = tmp_path / 'linked'
    link.symlink_to(delivery, target_is_directory=True)
    with pytest.raises(AgentBomError):
        create_index(raw, link, tmp_path / 'index', request_sha256=digest(raw))
    with pytest.raises(AgentBomError):
        create_index(raw, delivery, delivery / 'index', request_sha256=digest(raw))


def test_wrong_outer_pin_rejects_before_untrusted_data(inputs):
    request, _, _, _ = inputs
    raw = rendered(request)
    with pytest.raises(AgentBomError):
        validate_request(raw, '0' * 64)


def test_cli_five_synthetic_outcomes_and_replay(tmp_path, capsys):
    directory = tmp_path / 'demo'
    assert main(['evidence-index', 'demo', '--out', str(directory)]) == 0
    assert main(['evidence-index', 'demo', '--out', str(directory)]) == 2
    for packet in sorted(p for p in directory.iterdir() if p.is_dir()):
        pin = digest((packet / 'request.json').read_bytes())
        expected = 0 if packet.name == 'complete-with-failed-policy' else 1
        assert main(['evidence-index', 'verify', str(packet), '--request-sha256', pin]) == expected
        report = json.loads((packet / 'report.json').read_bytes())
        assert report['decision_status'] == 'not_assessed'
    assert main(['evidence-index', 'create', str(packet / 'request.json'), str(packet / 'evidence'),
                 '--request-sha256', pin, '--out', str(tmp_path / 'copy')]) == expected
    assert main(['evidence-index', 'verify', str(packet), '--request-sha256', '0' * 64]) == 2
    assert str(tmp_path) not in capsys.readouterr().err


def test_demo_deterministic(tmp_path):
    create_demo(tmp_path / 'first')
    create_demo(tmp_path / 'second')
    def captured(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob('*') if p.is_file()}
    assert captured(tmp_path / 'first') == captured(tmp_path / 'second')
