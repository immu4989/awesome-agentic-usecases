"""Probe-contract tests need no Inspect installation, model, or network access."""

import importlib.util
from pathlib import Path
import socket

import pytest

from aau_harness.agent_bom import AgentBomError, rendered


spec = importlib.util.spec_from_file_location(
    'inspect_exporter_probe', Path(__file__).parents[1] / 'tools/check_inspect_exporter.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def source():
    return {'version': 2, 'status': 'success',
            'eval': {'config': {'epochs': 2}, 'dataset': {'sample_ids': [1, 2]},
                     'packages': {'inspect_ai': probe.INSPECT_VERSION}},
            'results': {'total_samples': 4, 'completed_samples': 4},
            'samples': [{'id': identity, 'epoch': epoch,
                         'scores': {'match': {'value': 'C' if identity == 1 else 'I'},
                                    'numeric_match': {'value': int(identity == 1)}}}
                        for identity in (1, 2) for epoch in (1, 2)]}


def test_projection_contract_not_sample_order():
    raw = source()
    for samples in (raw['samples'], list(reversed(raw['samples']))):
        raw['samples'] = samples
        report = probe.check_projection(rendered(probe.mapping()), rendered(raw))
        assert report['observation_count'] == 4
        assert report['declared_inspect_version'] == '0.3.291'


@pytest.mark.parametrize('defect', ['numeric', 'label', 'missing', 'duplicate', 'version', 'error', 'epoch'])
def test_projection_rejects_changes(defect):
    raw = source()
    if defect == 'numeric':
        raw['samples'][0]['scores']['numeric_match']['value'] = 0
    elif defect == 'label':
        raw['samples'][0]['scores']['match']['value'] = 'I'
    elif defect == 'missing':
        raw['samples'].pop()
    elif defect == 'duplicate':
        raw['samples'][-1] = raw['samples'][0]
    elif defect == 'version':
        raw['eval']['packages']['inspect_ai'] = '0.3.100'
    elif defect == 'error':
        raw['samples'][0]['error'] = {'message': 'constructed interruption'}
    elif defect == 'epoch':
        raw['samples'][0]['epoch'] = 3
    with pytest.raises((ValueError, AgentBomError)):
        probe.check_projection(rendered(probe.mapping()), rendered(raw))


@pytest.mark.parametrize('method', ['connect', 'connect_ex', 'sendto'])
@pytest.mark.parametrize('family', [socket.AF_INET, socket.AF_INET6])
def test_tripwire_blocks_before_any_socket_operation_and_restores(method, family):
    original = getattr(socket.socket, method)
    # No real socket is needed: the wrapper must reject before delegating to the OS.
    class PretendSocket:
        pass
    sock = PretendSocket()
    sock.family = family
    with probe.deny_ip_connections() as attempted:
        with pytest.raises(RuntimeError, match='forbids IP'):
            getattr(socket.socket, method)(sock, 'unused destination')
        assert attempted == [method]
    assert getattr(socket.socket, method) is original


def test_tripwire_restores_after_exception():
    originals = {name: getattr(socket.socket, name) for name in ('connect', 'connect_ex', 'sendto')}
    with pytest.raises(ValueError):
        with probe.deny_ip_connections():
            raise ValueError('synthetic failure')
    assert all(getattr(socket.socket, name) is method for name, method in originals.items())


def test_existing_output_rejected_before_inspect_import(tmp_path):
    (tmp_path / 'keep.txt').write_text('user data')
    with pytest.raises(ValueError, match='overwrite'):
        probe.exercise(tmp_path)
    assert (tmp_path / 'keep.txt').read_text() == 'user data'


def test_wrong_installed_version_rejected_before_output_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, 'version', lambda name: 'different-version')
    with pytest.raises(ValueError, match='exact documented'):
        probe.exercise(tmp_path / 'new')
    assert not (tmp_path / 'new').exists()


@pytest.mark.parametrize('defect', [None, 'missing', 'duplicate', 'unrelated-error', 'no-error'])
def test_negative_control_requires_the_intended_failure(defect):
    raw = source()
    for row in raw['samples']:
        row['error'] = {'message': "RuntimeError('intentional synthetic solver interruption')"}
    if defect == 'missing':
        raw['samples'].pop()
    elif defect == 'duplicate':
        raw['samples'][-1] = raw['samples'][0]
    elif defect == 'unrelated-error':
        raw['samples'][0]['error']['message'] = 'unrelated setup failure'
    elif defect == 'no-error':
        del raw['samples'][0]['error']
    if defect:
        with pytest.raises(ValueError, match='intended solver interruptions'):
            probe.check_interruption(rendered(raw))
    else:
        probe.check_interruption(rendered(raw))
