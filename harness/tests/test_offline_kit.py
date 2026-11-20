import importlib
import json
import os
from pathlib import Path
import sys

import pytest

from test_package_content_audit import package as package, save_archives


TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
try:
    builder = importlib.import_module('build_offline_kit')
    verifier = importlib.import_module('verify_offline_kit')
finally:
    sys.path.pop(0)


def create(package, tmp_path):
    (package[0].parent / 'LICENSE').write_text('Synthetic license fixture, not a real distribution.\n')
    paths = save_archives(package)
    folder = tmp_path / 'kit'
    pins = builder.create_kit(*paths, folder)
    return folder, pins


def test_kit_is_deterministic_source_bound_and_never_installs_or_executes(package, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution attempted')
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)
    paths = save_archives(package)
    before = [p.read_bytes() for p in paths[1:]]
    (paths[0].parent / 'LICENSE').write_text('Synthetic license fixture, not a real distribution.\n')
    files = builder.kit_payloads(*paths)
    assert files == builder.kit_payloads(*paths)
    folder = tmp_path / 'kit'
    pins = builder.create_kit(*paths, folder)
    report = verifier.verify(folder, manifest_sha256=pins['manifest_sha256'])
    assert report['member_count'] == 9 and report['runtime_sources'] == 'not_supplied'
    assert [p.read_bytes() for p in paths[1:]] == before
    assert files['wheels/aau_harness-1.6.0-py3-none-any.whl'] == before[1]
    assert files['source/aau_harness-1.6.0.tar.gz'] == before[0]
    assert pins['verifier_sha256'] == verifier.sha((TOOLS / 'verify_offline_kit.py').read_bytes())
    assert b'--hash=sha256:' in files['requirements.lock']
    assert str(tmp_path).encode() not in b''.join(raw for name, raw in files.items() if name.endswith(('.json', '.md')))
    with pytest.raises(ValueError, match='overwrite'):
        builder.create_kit(*paths, folder)


@pytest.mark.parametrize('member', ['manifest.json', 'requirements.lock', 'verify_offline_kit.py', 'README.md', 'LICENSE',
    'package-audit.json', 'expected-runtime.json', 'wheels/aau_harness-1.6.0-py3-none-any.whl', 'source/aau_harness-1.6.0.tar.gz'])
def test_every_member_tamper_is_rejected_under_the_independent_pin(package, tmp_path, member):
    folder, pins = create(package, tmp_path)
    with (folder / member).open('ab') as stream:
        stream.write(b' ')
    with pytest.raises(ValueError):
        verifier.verify(folder, manifest_sha256=pins['manifest_sha256'])
    manifest = json.loads((folder / 'manifest.json').read_bytes())
    if member != 'manifest.json':
        manifest['files'][member] = verifier.sha((folder / member).read_bytes())
        (folder / 'manifest.json').write_bytes(verifier.encoded(manifest))
    with pytest.raises(ValueError, match='manifest pin'):
        verifier.verify(folder, manifest_sha256=pins['manifest_sha256'])


def test_runtime_receipt_compares_first_party_sources_not_host_metadata(package, tmp_path):
    folder, pins = create(package, tmp_path)
    expected = json.loads((folder / 'expected-runtime.json').read_bytes())
    runtime = {k: v for k, v in expected.items() if k != 'receipt_version'}
    runtime.update(report_version='aau-runtime-source-receipt/1.0', python={'version': '3.12.0'}, boundary='supplied receipt')
    receipt = tmp_path / 'runtime.json'
    receipt.write_bytes(verifier.encoded(runtime))
    assert verifier.verify(folder, manifest_sha256=pins['manifest_sha256'], runtime_path=receipt)['runtime_sources'] == 'matched_supplied_receipt'
    for field in ('distribution_version', 'source_tree_sha256', 'source_files', 'report_version'):
        changed = dict(runtime)
        changed[field] = {} if field == 'source_files' else 'wrong'
        receipt.write_bytes(verifier.encoded(changed))
        with pytest.raises(ValueError, match='runtime receipt'):
            verifier.verify(folder, manifest_sha256=pins['manifest_sha256'], runtime_path=receipt)


@pytest.mark.parametrize('defect', ['extra-root', 'extra-wheel', 'missing', 'root-link', 'group-link', 'member-link', 'fifo', 'oversized'])
def test_closed_inventory_and_nonregular_files(package, tmp_path, defect):
    folder, pins = create(package, tmp_path)
    if defect == 'extra-root':
        (folder / 'runtime.json').write_text('{}')
    elif defect == 'extra-wheel':
        (folder / 'wheels/unapproved.whl').write_bytes(b'x')
    elif defect == 'missing':
        (folder / 'requirements.lock').unlink()
    elif defect == 'oversized':
        (folder / 'README.md').write_bytes(b'x' * (verifier.MAX_FILE + 1))
    elif defect == 'fifo':
        if not hasattr(os, 'mkfifo'):
            pytest.skip('FIFO unavailable')
        (folder / 'requirements.lock').unlink()
        os.mkfifo(folder / 'requirements.lock')
    else:
        target = folder if defect == 'root-link' else folder / ('wheels' if defect == 'group-link' else 'requirements.lock')
        moved = tmp_path / 'moved'
        target.rename(moved)
        target.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises((ValueError, OSError)):
        verifier.verify(folder, manifest_sha256=pins['manifest_sha256'])


@pytest.mark.parametrize('defect', ['bad-lock', 'bad-audit', 'bad-runtime', 'extra-manifest', 'unsafe-version', 'wrong-members'])
def test_internally_inconsistent_kits_are_rejected_even_with_a_new_pin(package, tmp_path, defect):
    folder, _ = create(package, tmp_path)
    manifest = json.loads((folder / 'manifest.json').read_bytes())
    if defect == 'bad-lock':
        (folder / 'requirements.lock').write_text('https://do-not-fetch.invalid/package.whl\n')
    elif defect == 'bad-audit':
        audit = json.loads((folder / 'package-audit.json').read_bytes())
        audit['artifacts']['wheel_sha256'] = '0' * 64
        (folder / 'package-audit.json').write_bytes(verifier.encoded(audit))
    elif defect == 'bad-runtime':
        target = json.loads((folder / 'expected-runtime.json').read_bytes())
        target['source_tree_sha256'] = '0' * 64
        (folder / 'expected-runtime.json').write_bytes(verifier.encoded(target))
    elif defect == 'extra-manifest':
        manifest['extra'] = True
    elif defect == 'unsafe-version':
        manifest['distribution_version'] = '../escape'
    else:
        manifest['files']['../escape'] = '0' * 64
    if defect != 'wrong-members':
        manifest['files'] = {name: verifier.sha((folder / name).read_bytes()) for name in manifest['files']}
    raw = verifier.encoded(manifest)
    (folder / 'manifest.json').write_bytes(raw)
    with pytest.raises(ValueError):
        verifier.verify(folder, manifest_sha256=verifier.sha(raw))


def test_source_mismatch_and_new_dependency_profile_are_rejected_before_output(package, tmp_path):
    paths = save_archives(package)
    (paths[0] / 'src/aau_harness/cli.py').write_text('raise RuntimeError("different source")\n')
    with pytest.raises(ValueError, match='artifacts must match'):
        builder.create_kit(*paths, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('requirement', ['requests>=2', 'tomli>=2', 'tomli>=3; python_version < "3.11"',
    'tomli>=2; python_version < "3.12"', 'new-dep; python_version >= "3.13"'])
def test_no_deps_profile_requires_explicit_review_after_dependency_change(package, tmp_path, monkeypatch, requirement):
    paths = save_archives(package)
    audit = builder.auditor.audit(*paths)
    declaration = (paths[0] / 'pyproject.toml').read_text()
    import tomllib
    parsed = tomllib.loads(declaration)
    parsed['project']['dependencies'] = [requirement]
    monkeypatch.setattr(builder.auditor, 'audit', lambda *args: audit)
    monkeypatch.setattr(builder.tomllib, 'loads', lambda *args: parsed)
    with pytest.raises(ValueError, match='dependenc'):
        builder.create_kit(*paths, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


def test_cli_failures_and_unsupported_python_are_explicit(package, tmp_path, monkeypatch):
    folder, pins = create(package, tmp_path)
    assert verifier.main([str(folder), '--manifest-sha256', pins['manifest_sha256']]) == 0
    assert verifier.main([str(folder), '--manifest-sha256', '0' * 64]) == 2
    monkeypatch.setattr(verifier.sys, 'version_info', (3, 10, 0))
    assert verifier.main([str(folder), '--manifest-sha256', pins['manifest_sha256']]) == 2


@pytest.mark.parametrize('requirement', ['>=3.12', '>=3.10,<3.12', '>=3.10,!=3.11.*'])
def test_changed_python_support_cannot_be_advertised_as_the_existing_offline_profile(package, tmp_path, monkeypatch, requirement):
    paths = save_archives(package)
    audit = builder.auditor.audit(*paths)
    declaration = builder.tomllib.loads((paths[0] / 'pyproject.toml').read_text())
    declaration['project']['requires-python'] = requirement
    monkeypatch.setattr(builder.auditor, 'audit', lambda *args: audit)
    monkeypatch.setattr(builder.tomllib, 'loads', lambda *args: declaration)
    with pytest.raises(ValueError, match='Python support changed'):
        builder.create_kit(*paths, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('raw', [b'[]', b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":1e999}', b'\xff', b'[' * 2000])
def test_untrusted_manifest_json_does_not_execute_or_normalize_invalid_data(package, tmp_path, raw):
    folder, _ = create(package, tmp_path)
    (folder / 'manifest.json').write_bytes(raw)
    assert verifier.main([str(folder), '--manifest-sha256', verifier.sha(raw)]) == 2
