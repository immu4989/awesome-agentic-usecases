from copy import deepcopy
import json
import socket
import subprocess

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
import aau_harness.self_check as module


def test_all_fixed_cases_are_reproducible_without_a_checkout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first, files = module.check_payloads()
    second, again = module.check_payloads()
    assert first == second and files == again
    assert first['status'] == 'expected_behavior_observed'
    assert len(first['checks']) == 9
    assert all(c['status'] == 'matched_expected' and c['error_code'] is None for c in first['checks'])
    assert set(files) == module.FILES
    assert digest(files['runtime.json']) == first['runtime_receipt_sha256']


@pytest.mark.parametrize('case', module.CASES)
def test_each_expected_negative_or_positive_is_actually_exercised(tmp_path, case):
    assert module._execute(case, tmp_path) is True


@pytest.mark.parametrize('value', [False, None, 1, 'true', {}])
def test_non_boolean_success_is_never_accepted(monkeypatch, value):
    monkeypatch.setattr(module, '_execute', lambda case, root: value)
    report, _ = module.check_payloads()
    assert report['status'] == 'self_check_failed'
    assert all(c['error_code'] == 'expected_behavior_not_observed' for c in report['checks'])


@pytest.mark.parametrize('exc,code', [
    (ImportError('secret /private/local/path'), 'required_module_unavailable'),
    (PermissionError('credential=not-for-export'), 'filesystem_operation_failed'),
    (ValueError('hostname=private-host'), 'fixture_or_behavior_contract_failed'),
    (RuntimeError('sensitive exception body'), 'unexpected_exception'),
])
def test_failures_retained_with_closed_codes_without_exception_details(monkeypatch, exc, code):
    called = []
    def failing(case, root):
        called.append(case)
        raise exc
    monkeypatch.setattr(module, '_execute', failing)
    report, files = module.check_payloads()
    assert called == list(module.CASES)
    assert report['status'] == 'self_check_failed'
    assert all(c['error_code'] == code for c in report['checks'])
    assert str(exc).encode() not in b''.join(files.values())


def test_one_failed_check_does_not_hide_later_checks(monkeypatch):
    original = module._execute
    def changed(case, root):
        return False if case == 'policy-unmet' else original(case, root)
    monkeypatch.setattr(module, '_execute', changed)
    report, _ = module.check_payloads()
    assert [c['case_id'] for c in report['checks'] if c['status'] == 'failed'] == ['policy-unmet']
    assert report['checks'][-1]['status'] == 'matched_expected'


def test_negative_controls_do_not_count_unrelated_exceptions_as_rejection():
    def unrelated():
        raise AgentBomError('a different failure')
    assert not module._rejected(unrelated, 'expected refusal')
    assert not module._rejected(lambda: None, 'expected refusal')
    with pytest.raises(OSError):
        module._rejected(lambda: (_ for _ in ()).throw(OSError('not the intended refusal')), 'refusal')


def test_interrupt_is_not_swallowed_and_temporary_files_are_removed(tmp_path, monkeypatch):
    observed = []
    def interrupted(case, root):
        observed.append(root)
        (root / 'partial.txt').write_text('synthetic')
        raise KeyboardInterrupt
    monkeypatch.setattr(module, '_execute', interrupted)
    with pytest.raises(KeyboardInterrupt):
        module.create_check(tmp_path / 'result')
    assert observed and all(not p.exists() for p in observed)
    assert not (tmp_path / 'result').exists()


def test_fixed_workflows_use_no_network_or_subprocess(monkeypatch):
    calls = []
    def denied(*args, **kwargs):
        calls.append(True)
        raise RuntimeError('unexpected network or subprocess request')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(socket, 'getaddrinfo', denied)
    monkeypatch.setattr(subprocess, 'Popen', denied)
    report, _ = module.check_payloads()
    assert report['status'] == 'expected_behavior_observed' and calls == []


def test_no_environment_or_working_directory_metadata_is_collected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('AAU_PRIVATE_EXAMPLE', 'PRIVATE_MUST_NOT_APPEAR')
    _, files = module.check_payloads()
    text = b''.join(files.values()).decode()
    assert str(tmp_path) not in text and 'PRIVATE_MUST_NOT_APPEAR' not in text
    assert 'AAU_PRIVATE_EXAMPLE' not in text


def test_runtime_drift_prevents_output(tmp_path, monkeypatch):
    original = module.runtime_info()
    changed = deepcopy(original)
    changed['source_tree_sha256'] = '0' * 64
    values = iter((original, changed))
    monkeypatch.setattr(module, 'runtime_info', lambda: next(values))
    with pytest.raises(AgentBomError, match='changed during collection'):
        module.create_check(tmp_path / 'unstable')
    assert not (tmp_path / 'unstable').exists()


@pytest.mark.parametrize('member', sorted(module.FILES))
def test_modified_receipt_is_rejected_even_after_manifest_rehash(tmp_path, member):
    directory = tmp_path / 'receipt'
    module.create_check(directory)
    path = directory / member
    path.write_bytes(path.read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = json.loads((directory / 'manifest.json').read_bytes())
        manifest['files'][member] = digest(path.read_bytes())
        (directory / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match='differs from current runtime'):
        module.verify_check(directory)


def test_changed_runtime_or_rerun_results_cannot_validate_old_receipt(tmp_path, monkeypatch):
    packet = tmp_path / 'packet'
    module.create_check(packet)
    original = module.runtime_info()
    changed = deepcopy(original)
    changed['python']['version'] = 'different'
    monkeypatch.setattr(module, 'runtime_info', lambda: changed)
    with pytest.raises(AgentBomError):
        module.verify_check(packet)
    monkeypatch.setattr(module, 'runtime_info', lambda: original)
    monkeypatch.setattr(module, '_execute', lambda case, root: False)
    with pytest.raises(AgentBomError):
        module.verify_check(packet)


@pytest.mark.parametrize('defect', ['extra', 'missing', 'nested', 'symlink', 'executable'])
def test_inventory_rejected_before_fixed_checks_run(tmp_path, monkeypatch, defect):
    packet = tmp_path / 'packet'
    module.create_check(packet)
    if defect == 'extra':
        (packet / 'extra.json').write_text('{}')
    elif defect == 'missing':
        (packet / 'checks.json').unlink()
    elif defect == 'nested':
        (packet / 'nested').mkdir()
    elif defect == 'symlink':
        target = packet / 'runtime.json'
        moved = tmp_path / 'runtime-copy.json'
        target.rename(moved)
        target.symlink_to(moved)
    else:
        (packet / 'run.py').write_text('raise RuntimeError("must not execute")')
    monkeypatch.setattr(module, 'check_payloads', lambda: pytest.fail('unexpected execution before inventory rejection'))
    with pytest.raises(ValueError):
        module.verify_check(packet)


def test_cli_complete_failed_and_invalid_states(tmp_path, monkeypatch, capsys):
    packet = tmp_path / 'good'
    assert main(['self-check', 'run', '--out', str(packet)]) == 0
    assert main(['self-check', 'verify', str(packet)]) == 0
    assert main(['self-check', 'run', '--out', str(packet)]) == 2
    monkeypatch.setattr(module, '_execute', lambda case, root: False)
    failed = tmp_path / 'failed'
    assert main(['self-check', 'run', '--out', str(failed)]) == 1
    assert main(['self-check', 'verify', str(failed)]) == 1
    assert main(['self-check', 'verify', str(packet)]) == 2
    assert str(tmp_path) not in capsys.readouterr().err


def test_existing_output_refused_before_running_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'check_payloads', lambda: pytest.fail('must refuse before execution'))
    with pytest.raises(AgentBomError):
        module.create_check(tmp_path)
    link = tmp_path / 'link'
    link.symlink_to(tmp_path / 'nonexistent')
    with pytest.raises(AgentBomError):
        module.create_check(link)
