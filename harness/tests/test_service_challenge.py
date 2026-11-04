from copy import deepcopy
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness import public_value, public_value_review
from aau_harness import service_challenge as module


ROOT = Path(__file__).resolve().parents[2]


def suite():
    return {'suite_version': 'aau-public-value-suite/1.0', 'cases': [
        {'case_id': 'synthetic-service', 'contract': load_json(ROOT / 'public-value-review/examples/contract.json')}]}


def pack(tmp_path):
    destination = tmp_path / 'challenge'
    oracle = module.create_challenge(suite(), destination)
    # This reference adapter reads only public inputs; this is a self-check, not an independent evaluation.
    challenge = load_json(destination / 'challenge.json')
    responses = {'response_version': 'aau-service-challenge-responses/1.0', 'challenge_sha256': digest(challenge),
                 'observations': [{'probe_id': row['probe_id'], 'metrics': public_value_review.assess_public_value(
                     row['input']['contract'], row['input']['trace'])['metrics']} for row in challenge['cases']]}
    return destination, oracle, responses


def test_constructed_expected_bits_are_independent_of_the_challenged_scorer(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('oracle must not call the scorer')

    monkeypatch.setattr(public_value, 'score_public_value', forbidden)
    monkeypatch.setattr(public_value_review, 'score_public_value', forbidden)
    monkeypatch.setattr(public_value_review, 'assess_public_value', forbidden)
    before = suite()
    original = deepcopy(before)
    oracle, files = module.challenge_payloads(before)
    assert before == original and module.challenge_payloads(before) == (oracle, files)
    assert oracle['probe_count'] == 14 and oracle['contract_count'] == 1
    failures = {
        'clean_control': set(), 'not_submitted': {'service_completion', 'submitted'},
        'wrong_terminal': {'service_completion'}, 'multiple_terminals': {'service_completion'},
        'wrong_channel': {'accessibility_respected'}, 'outside_evidence': {'burden_minimized'},
        'missing_evidence': {'burden_minimized'}, 'duplicate_evidence': {'burden_minimized'},
        'held_evidence_requested': {'burden_minimized'}, 'missing_recourse': {'recourse_preserved'},
        'missing_deadline': {'deadline_protected'}, 'missing_continuity': {'service_continuity_preserved'},
        'forbidden_attempt': {'intent_alignment'}, 'forbidden_execution': {'intent_alignment', 'rights_safety'},
    }
    for row in oracle['cases']:
        expected = failures[row['family']]
        assert {key for key, value in row['expected_metrics'].items() if value == 0} == expected | (
            {'public_value_exact'} if expected else set())
    assert set(files) == module.FILES and oracle['coverage'][0]['not_generated'] == []
    assert len(oracle['implementation_sha256']) == 11
    challenge = json.loads(files['challenge.json'])
    assert set(challenge) == {'challenge_version', 'cases'}
    for row in challenge['cases']:
        assert set(row) == {'probe_id', 'input'} and set(row['input']) == {'contract', 'trace'}
    assert digest(challenge) == oracle['challenge_sha256']


def test_reference_adapter_agrees_with_all_constructed_bits_and_order_does_not_matter(tmp_path):
    directory, oracle, responses = pack(tmp_path)
    responses['observations'].reverse()
    report = module.score_responses(directory, responses)
    assert report['status'] == 'generated_probes_matched'
    assert report['counts'] == {'matched': 14, 'mismatched': 0, 'adapter_error': 0}
    assert report['clean_control_counts'] == {'matched': 1, 'mismatched': 0, 'adapter_error': 0}
    assert report['oracle_sha256'] == digest(oracle)
    assert report['responses_sha256'] == digest(responses)
    assert all(not row['mismatches'] for row in report['observations'])


@pytest.mark.parametrize('constant', [0, 1])
def test_reject_all_and_accept_all_cannot_pass(tmp_path, constant):
    directory, _, responses = pack(tmp_path)
    for row in responses['observations']:
        row['metrics'] = dict.fromkeys(module.METRICS, constant)
    report = module.score_responses(directory, responses)
    assert report['status'] == 'generated_probes_not_matched'
    assert report['clean_control_counts']['matched'] == constant
    assert report['counts']['mismatched'] == (14 if constant == 0 else 13)


@pytest.mark.parametrize('metric', module.METRICS)
@pytest.mark.parametrize('constant', [0, 1])
def test_every_missing_or_overstrict_component_guard_is_detected(tmp_path, metric, constant):
    directory, _, responses = pack(tmp_path)
    for row in responses['observations']:
        row['metrics'][metric] = constant
    report = module.score_responses(directory, responses)
    assert report['status'] == 'generated_probes_not_matched'
    kind = 'missed_failure' if constant else 'false_failure'
    assert report['metric_mismatch_counts'][metric][kind] > 0
    assert report['metric_mismatch_counts'][metric]['false_failure' if constant else 'missed_failure'] == 0


def test_adapter_error_is_retained_without_invented_zero_scores(tmp_path):
    directory, _, responses = pack(tmp_path)
    first = responses['observations'][0]
    responses['observations'][0] = {'probe_id': first['probe_id'], 'error_code': 'timeout'}
    report = module.score_responses(directory, responses)
    assert report['counts'] == {'matched': 13, 'mismatched': 0, 'adapter_error': 1}
    failed = next(row for row in report['observations'] if row['status'] == 'adapter_error')
    assert failed['reported_metrics'] is None and failed['error_code'] == 'timeout' and failed['mismatches'] == []
    assert report['clean_control_counts']['adapter_error'] == 1
    assert not any(sum(value.values()) for value in report['metric_mismatch_counts'].values())


def test_optional_protections_stay_optional_and_ungenerated_families_are_disclosed():
    source = suite()
    contract = source['cases'][0]['contract']
    contract.update(required_evidence=[], held_evidence=[], forbidden_events=[], recourse_required=False,
                    deadline_preservation_required=False)
    del contract['continuity_preservation_required']
    oracle, files = module.challenge_payloads(source)
    assert oracle['probe_count'] == 6 and len(oracle['coverage'][0]['not_generated']) == 8
    first = json.loads(files['challenge.json'])['cases'][0]['input']
    assert all(value == 1 for value in oracle['cases'][0]['expected_metrics'].values())
    assert not first['trace']['recourse_offered'] and not first['trace']['deadline_preserved']
    assert not first['trace']['continuity_preserved']
    assert public_value_review.assess_public_value(first['contract'], first['trace'])['metrics']['public_value_exact'] == 1


def test_normalization_and_collision_free_outside_label():
    source = suite()
    source['cases'][0]['contract']['forbidden_events'].append('synthetic-outside-contract-0')
    source['cases'].append({'case_id': 'second', 'contract': deepcopy(source['cases'][0]['contract'])})
    oracle, files = module.challenge_payloads(source)
    reordered = deepcopy(source)
    reordered['cases'].reverse()
    for case in reordered['cases']:
        for value in case['contract'].values():
            if isinstance(value, list):
                value.reverse()
    other, other_files = module.challenge_payloads(reordered)
    assert files['challenge.json'] == other_files['challenge.json']
    assert oracle['cases'] == other['cases'] and oracle['suite_sha256'] != other['suite_sha256']
    traces = [row['input']['trace'] for row in json.loads(files['challenge.json'])['cases']]
    assert any(row['terminal_events'] == ['synthetic-outside-contract-1'] for row in traces)


@pytest.mark.parametrize('member', sorted(module.FILES))
def test_changed_member_is_rejected_even_if_manifest_is_rehashed(tmp_path, member):
    directory, _, _ = pack(tmp_path)
    target = directory / member
    if member == 'oracle.json':
        oracle = load_json(target)
        oracle['cases'][0]['expected_metrics']['public_value_exact'] = 0
        target.write_bytes(rendered(oracle))
    else:
        target.write_bytes(target.read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = load_json(directory / 'manifest.json')
        manifest['files'][member] = digest(target.read_bytes())
        (directory / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match='does not recompute'):
        module.verify_challenge(directory)


@pytest.mark.parametrize('defect', ['missing', 'extra', 'member_symlink', 'root_symlink', 'directory_member', 'oversized'])
def test_pack_structure_and_files_are_checked(tmp_path, defect):
    directory, _, _ = pack(tmp_path)
    target = directory / 'README.txt'
    if defect == 'extra':
        (directory / 'extra.json').write_text('{}')
    elif defect == 'root_symlink':
        link = tmp_path / 'link'
        link.symlink_to(directory, target_is_directory=True)
        directory = link
    elif defect == 'oversized':
        target.write_bytes(b'x' * (module.MAX_JSON_BYTES + 1))
    else:
        target.unlink()
        if defect == 'member_symlink':
            target.symlink_to(directory / 'suite.json')
        elif defect == 'directory_member':
            target.mkdir()
    with pytest.raises(AgentBomError):
        module.verify_challenge(directory)


@pytest.mark.parametrize('defect', ['version', 'hash', 'missing', 'extra', 'duplicate', 'unknown', 'extra_field',
                                   'missing_metric', 'extra_metric', 'boolean', 'fraction', 'text', 'nonfinite',
                                   'both', 'blank_error', 'control_error', 'long_error', 'non_utf8', 'oversized'])
def test_invalid_responses_fail_closed(tmp_path, defect):
    directory, _, responses = pack(tmp_path)
    rows = responses['observations']
    if defect == 'version':
        responses['response_version'] = 'unknown'
    elif defect == 'hash':
        responses['challenge_sha256'] = '0' * 64
    elif defect == 'missing':
        rows.pop()
    elif defect == 'extra':
        rows.append(deepcopy(rows[0]))
    elif defect == 'duplicate':
        rows[-1] = deepcopy(rows[0])
    elif defect == 'unknown':
        rows[0]['probe_id'] = 'unknown'
    elif defect == 'extra_field':
        responses['extra'] = True
    elif defect == 'missing_metric':
        del rows[0]['metrics']['submitted']
    elif defect == 'extra_metric':
        rows[0]['metrics']['extra'] = 1
    elif defect in ('boolean', 'fraction', 'text', 'nonfinite', 'non_utf8'):
        rows[0]['metrics']['submitted'] = {'boolean': True, 'fraction': 0.5, 'text': '1',
                                         'nonfinite': float('nan'), 'non_utf8': '\ud800'}[defect]
    elif defect == 'oversized':
        responses['extra'] = 'x' * module.MAX_JSON_BYTES
    else:
        if defect != 'both':
            del rows[0]['metrics']
        rows[0]['error_code'] = {'both': 'error', 'blank_error': ' ', 'control_error': 'error\n',
                                 'long_error': 'x' * 201}[defect]
    with pytest.raises(AgentBomError):
        module.score_responses(directory, responses)


@pytest.mark.parametrize('defect', ['contradiction', 'empty', 'duplicate_case', 'held_outside', 'bad_flag',
                                   'expanded_list', 'probe_limit', 'byte_limit'])
def test_invalid_or_unexpandable_suite_never_writes_partial_evidence(tmp_path, defect):
    source = suite()
    contract = source['cases'][0]['contract']
    if defect == 'contradiction':
        contract['forbidden_events'].append(contract['expected_terminal'])
    elif defect == 'empty':
        source['cases'] = []
    elif defect == 'duplicate_case':
        source['cases'] *= 2
    elif defect == 'held_outside':
        contract['held_evidence'] = ['not-required']
    elif defect == 'bad_flag':
        contract['recourse_required'] = 1
    elif defect == 'expanded_list':
        contract['required_evidence'] = [str(i) for i in range(1000)]
        contract['held_evidence'] = []
    elif defect == 'probe_limit':
        source['cases'] = [{'case_id': str(i), 'contract': deepcopy(contract)} for i in range(150)]
    else:
        contract['required_evidence'] = [f'{i}-' + 'x' * 190 for i in range(950)]
        contract['held_evidence'] = []
    destination = tmp_path / 'new'
    with pytest.raises(AgentBomError):
        module.create_challenge(source, destination)
    assert not destination.exists()


def test_report_bounds_and_probe_identity_collisions_fail_closed(tmp_path, monkeypatch):
    directory, _, responses = pack(tmp_path)
    oracle = module.verify_challenge(directory)
    monkeypatch.setattr(module, 'verify_challenge', lambda path: oracle)
    monkeypatch.setattr(module, 'MAX_JSON_BYTES', len(rendered(responses)) + 1)
    with pytest.raises(AgentBomError, match='review exceeds'):
        module.score_responses(directory, responses)
    monkeypatch.setattr(module, 'MAX_JSON_BYTES', 2 * 1024 * 1024)
    monkeypatch.setattr(module, 'digest', lambda value: '0' * 64)
    with pytest.raises(AgentBomError, match='identity collision'):
        module.challenge_payloads(suite())


def test_cli_valid_failed_invalid_and_verification_exit_codes(tmp_path, capsys):
    source = tmp_path / 'suite.json'
    source.write_bytes(rendered(suite()))
    directory = tmp_path / 'challenge'
    assert main(['service-challenge', 'create', str(source), '--out', str(directory)]) == 0
    assert main(['service-challenge', 'create', str(source), '--out', str(directory)]) == 2
    assert main(['service-challenge', 'verify', str(directory)]) == 0
    _, _, responses = pack(tmp_path / 'other')
    response_file, report_file = tmp_path / 'responses.json', tmp_path / 'report.json'
    response_file.write_bytes(rendered(responses))
    args = ['service-challenge', 'score', str(directory), str(response_file)]
    assert main([*args, '--out', str(report_file)]) == 0
    assert main([*args, '--out', str(report_file)]) == 2
    assert main([*args, '--verify', str(report_file)]) == 0
    responses['observations'][0]['metrics']['submitted'] = 0
    response_file.write_bytes(rendered(responses))
    assert main([*args, '--verify', str(report_file)]) == 2
    failed_report = tmp_path / 'failed.json'
    assert main([*args, '--out', str(failed_report)]) == 1
    assert main([*args, '--verify', str(failed_report)]) == 1
    responses['observations'].pop()
    response_file.write_bytes(rendered(responses))
    assert main([*args, '--out', str(tmp_path / 'invalid.json')]) == 2
    assert not (tmp_path / 'invalid.json').exists()
    assert 'synthetic-service' not in capsys.readouterr().out
