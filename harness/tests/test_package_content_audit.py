"""Synthetic archive failures plus release-order checks; never install fixture packages."""

import base64
import csv
import gzip
import hashlib
import importlib.util
from io import BytesIO, StringIO
import json
from pathlib import Path
import stat
import tarfile
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('package_audit', ROOT / 'harness/tools/audit_package_contents.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
DIST = 'aau_harness-1.6.0.dist-info'
RECORD = f'{DIST}/RECORD'
METADATA = b'''Metadata-Version: 2.4
Name: aau-harness
Version: 1.6.0
Requires-Python: >=3.10
Requires-Dist: tomli>=2; python_version < "3.11"
Provides-Extra: dev-tools
Requires-Dist: pytest>=7; extra == "dev-tools"
Requires-Dist: ruff>=0.4; python_version >= "3.10" and extra == "dev-tools"

Fixture only.
'''


def wheel_bytes(files):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def with_record(files):
    files = dict(files)
    output = StringIO(newline='')
    writer = csv.writer(output)
    for name, value in sorted(files.items()):
        if name != RECORD:
            digest = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b'=').decode()
            writer.writerow([name, f'sha256={digest}', str(len(value))])
    writer.writerow([RECORD, '', ''])
    files[RECORD] = output.getvalue().encode()
    return files


def source_bytes(files):
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, value in files.items():
            member = tarfile.TarInfo(f'aau_harness-1.6.0/{name}')
            member.size = len(value)
            archive.addfile(member, BytesIO(value))
    return buffer.getvalue()


@pytest.fixture
def package(tmp_path):
    project = tmp_path / 'project'
    (project / 'src/aau_harness').mkdir(parents=True)
    (project / 'pyproject.toml').write_text('''[project]
name = "aau-harness"
version = "1.6.0"
requires-python = ">=3.10"
readme = "README.md"
dependencies = ["tomli>=2; python_version < '3.11'"]
[project.optional-dependencies]
dev_tools = ["pytest>=7", "ruff>=0.4; python_version >= '3.10'"]
[project.scripts]
aau = "aau_harness.cli:main"
''')
    (project / 'README.md').write_text('Synthetic package.\n')
    sources = {'aau_harness/__init__.py': b'"""Synthetic package."""\n',
               'aau_harness/cli.py': b'def main():\n    return 0\n'}
    for name, value in sources.items():
        (project / 'src' / name).write_bytes(value)
    wheel = {**sources, f'{DIST}/METADATA': METADATA,
             f'{DIST}/WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
             f'{DIST}/entry_points.txt': b'[console_scripts]\naau = aau_harness.cli:main\n',
             f'{DIST}/top_level.txt': b'aau_harness\n'}
    sdist = {f'src/{name}': value for name, value in sources.items()}
    sdist.update({name: (project / name).read_bytes() for name in ('pyproject.toml', 'README.md')})
    sdist['PKG-INFO'] = METADATA
    return project, sdist, wheel


def save_archives(package, *, record=True):
    project, source_files, wheel_files = package
    sdist, wheel = project.parent / 'source.tar.gz', project.parent / 'artifact.whl'
    sdist.write_bytes(source_bytes(source_files))
    wheel.write_bytes(wheel_bytes(with_record(wheel_files) if record else wheel_files))
    return project, sdist, wheel


def cli_args(paths):
    project, sdist, wheel = paths
    return [str(sdist), str(wheel), '--project', str(project)]


def test_matching_contents_recompute_and_bind_artifact_bytes(package, capsys):
    paths = save_archives(package)
    project, sdist, wheel = paths
    report = audit.audit(*paths)
    assert report == audit.audit(*paths)
    assert report['status'] == 'contents_match'
    assert report['source_file_count'] == 2 and report['console_script_count'] == 1
    assert all(report['metadata_checks'].values())
    assert report['differences'] == []
    assert report['artifacts'] == {'sdist_sha256': audit.sha(sdist.read_bytes()),
                                   'wheel_sha256': audit.sha(wheel.read_bytes())}
    assert str(project.parent) not in json.dumps(report)
    assert report['wheel_members']['aau_harness/cli.py'] == report['source_files']['aau_harness/cli.py']
    assert report['sdist_members']['src/aau_harness/cli.py'] == report['source_files']['aau_harness/cli.py']
    assert audit.main(cli_args(paths)) == 0
    assert json.loads(capsys.readouterr().out) == report
    output = project.parent / 'audit.json'
    assert audit.main(cli_args(paths) + ['--out', str(output)]) == 0
    assert audit.main(cli_args(paths) + ['--verify', str(output)]) == 0
    original = output.read_bytes()
    assert audit.main(cli_args(paths) + ['--out', str(output)]) == 2
    assert output.read_bytes() == original
    output.write_bytes(original.replace(b'contents_match', b'contents_differ'))
    assert audit.main(cli_args(paths) + ['--verify', str(output)]) == 2


@pytest.mark.parametrize('target,member,change', [
    ('wheel', 'aau_harness/cli.py', b'raise RuntimeError("not the approved source")\n'),
    ('wheel', 'aau_harness/cli.py', None),
    ('wheel', 'aau_harness/new.py', b'# unexpected module'),
    ('wheel', 'unexpected.pth', b'import unexpected'),
    ('wheel', 'aau_harness-1.6.0.data/scripts/extra', b'#!/bin/sh\n'),
    ('wheel', 'foreign/__init__.py', b'# foreign package'),
    ('sdist', 'src/aau_harness/cli.py', b'# changed source'),
    ('sdist', 'src/aau_harness/cli.py', None),
    ('sdist', 'src/aau_harness/resource.bin', b'extra package resource'),
    ('sdist', 'pyproject.toml', b'# different build inputs'),
    ('sdist', 'README.md', b'# different description'),
    ('sdist', 'README.md', None),
])
def test_missing_altered_and_extra_payloads_fail_even_with_valid_record(package, target, member, change):
    files = package[2 if target == 'wheel' else 1]
    if change is None:
        del files[member]
    else:
        files[member] = change
    paths = save_archives(package)
    report = audit.audit(*paths)
    assert report['status'] == 'contents_differ'
    assert any(diff['member'] == member for diff in report['differences'])
    output = paths[0].parent / 'failed.json'
    assert audit.main(cli_args(paths) + ['--out', str(output)]) == 1
    assert audit.main(cli_args(paths) + ['--verify', str(output)]) == 1


@pytest.mark.parametrize('target', ['wheel', 'sdist'])
@pytest.mark.parametrize('before,after', [
    (b'Name: aau-harness', b'Name: another-project'),
    (b'Version: 1.6.0', b'Version: 9.9.9'),
    (b'Requires-Python: >=3.10', b'Requires-Python: >=3.12'),
    (b'Requires-Dist: tomli>=2;', b'Requires-Dist: tomli>=3;'),
    (b'Provides-Extra: dev-tools', b'Provides-Extra: surprise'),
    (b'\n\nFixture', b'\nRequires-Dist: unexpected-install-dependency>=1\n\nFixture'),
])
def test_package_identity_python_and_dependency_metadata_must_match(package, target, before, after):
    files, name = (package[2], f'{DIST}/METADATA') if target == 'wheel' else (package[1], 'PKG-INFO')
    files[name] = files[name].replace(before, after)
    report = audit.audit(*save_archives(package))
    assert report['status'] == 'contents_differ'
    assert report['metadata_checks'][f'{target}_metadata'] is False


@pytest.mark.parametrize('name,value,check', [
    ('entry_points.txt', b'[console_scripts]\naau = unexpected:main\n', 'console_scripts'),
    ('entry_points.txt', b'[console_scripts]\naau = aau_harness.cli:main\nextra = aau_harness.cli:main\n', 'console_scripts'),
    ('top_level.txt', b'foreign\n', 'top_level_package'),
])
def test_changed_commands_and_top_level_declaration_fail(package, name, value, check):
    package[2][f'{DIST}/{name}'] = value
    report = audit.audit(*save_archives(package))
    assert report['status'] == 'contents_differ' and not report['metadata_checks'][check]


@pytest.mark.parametrize('replacement', [
    b'[plugin]\nx = arbitrary:code\n',
    b'[DEFAULT]\naau = arbitrary:code\n[console_scripts]\n',
    b'[console_scripts]\naau = first:main\naau = second:main\n',
])
def test_unsupported_or_ambiguous_entrypoints_are_invalid(package, replacement):
    package[2][f'{DIST}/entry_points.txt'] = replacement
    assert audit.main(cli_args(save_archives(package))) == 2


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'hash', 'size', 'self', 'foreign', 'short', 'weak'])
def test_record_integrity_cannot_be_bypassed(package, mutation):
    files = with_record(package[2])
    rows = list(csv.reader(StringIO(files[RECORD].decode())))
    if mutation == 'missing':
        rows.pop(0)
    elif mutation == 'duplicate':
        rows.append(rows[0])
    elif mutation == 'hash':
        rows[0][1] = 'sha256=' + 'a' * 43
    elif mutation == 'size':
        rows[0][2] = '9999'
    elif mutation == 'self':
        rows[-1][1] = 'sha256=' + 'a' * 43
    elif mutation == 'foreign':
        rows.append(['not-in-wheel', '', ''])
    elif mutation == 'short':
        rows[0] = rows[0][:2]
    else:
        rows[0][1] = 'md5=not-a-supported-digest'
    output = StringIO(newline='')
    csv.writer(output).writerows(rows)
    files[RECORD] = output.getvalue().encode()
    assert audit.main(cli_args(save_archives((package[0], package[1], files), record=False))) == 2


@pytest.mark.parametrize('member', ['METADATA', 'WHEEL', 'RECORD', 'entry_points.txt', 'top_level.txt'])
def test_required_wheel_members_cannot_be_omitted(package, member):
    files = with_record(package[2])
    del files[f'{DIST}/{member}']
    assert audit.main(cli_args(save_archives((package[0], package[1], files), record=False))) == 2


@pytest.mark.parametrize('header', [
    b'Wheel-Version: 2.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    b'Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: py3-none-any\n',
    b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: cp312-linux-x86_64\n',
    b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\nTag: other\n',
])
def test_non_aau_wheel_profiles_are_invalid(package, header):
    package[2][f'{DIST}/WHEEL'] = header
    assert audit.main(cli_args(save_archives(package))) == 2


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a/../b', 'a/./b', 'a//b', 'a\\b', 'C:/file', 'a\nb', '.'])
@pytest.mark.parametrize('archive', ['zip', 'tar'])
def test_unsafe_or_noncanonical_member_names_are_rejected(name, archive):
    raw = wheel_bytes({name: b'x'}) if archive == 'zip' else source_bytes({name: b'x'})
    with pytest.raises(ValueError):
        (audit.zip_members if archive == 'zip' else audit.tar_members)(raw)


@pytest.mark.parametrize('archive', ['zip', 'tar'])
def test_duplicate_member_paths_are_rejected(archive):
    buffer = BytesIO()
    if archive == 'zip':
        with zipfile.ZipFile(buffer, 'w') as stream, pytest.warns(UserWarning):
            stream.writestr('duplicate', b'first')
            stream.writestr('duplicate', b'second')
    else:
        with tarfile.open(fileobj=buffer, mode='w:gz') as stream:
            for value in [b'first', b'second']:
                member = tarfile.TarInfo('root/duplicate')
                member.size = len(value)
                stream.addfile(member, BytesIO(value))
    with pytest.raises(ValueError, match='duplicate'):
        (audit.zip_members if archive == 'zip' else audit.tar_members)(buffer.getvalue())


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE])
def test_tar_links_and_special_members_are_not_extracted(kind, tmp_path):
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        member = tarfile.TarInfo('root/link')
        member.type, member.linkname = kind, str(tmp_path / 'outside')
        archive.addfile(member)
    with pytest.raises(ValueError):
        audit.tar_members(buffer.getvalue())
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('kind', [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR])
def test_zip_special_members_are_not_extracted(kind):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        member = zipfile.ZipInfo('link')
        member.create_system, member.external_attr = 3, (kind | 0o644) << 16
        archive.writestr(member, b'outside')
    with pytest.raises(ValueError):
        audit.zip_members(buffer.getvalue())


@pytest.mark.parametrize('archive', ['zip', 'tar'])
@pytest.mark.parametrize('limit', ['MAX_FILE', 'MAX_ARCHIVE', 'MAX_EXPANDED', 'MAX_MEMBERS'])
def test_archive_resource_limits_fail_closed(monkeypatch, archive, limit):
    raw = wheel_bytes({'a': b'x' * 128, 'b': b'y'}) if archive == 'zip' else source_bytes({'a': b'x' * 128, 'b': b'y'})
    monkeypatch.setattr(audit, limit, 1 if limit == 'MAX_MEMBERS' else 64)
    with pytest.raises(ValueError):
        (audit.zip_members if archive == 'zip' else audit.tar_members)(raw)


def test_gzip_expansion_is_bounded_before_tar_parsing(monkeypatch):
    monkeypatch.setattr(audit, 'MAX_EXPANDED', 1024)
    with pytest.raises(ValueError, match='expanded'):
        audit.tar_members(gzip.compress(b'x' * 20000))


@pytest.mark.parametrize('target', ['project', 'src', 'package', 'module', 'nested', 'sdist', 'wheel'])
def test_symlink_inputs_are_refused(package, target):
    paths = list(save_archives(package))
    project = paths[0]
    if target == 'nested':
        (project / 'src/aau_harness/nested').symlink_to(project / 'src', target_is_directory=True)
    else:
        path = {'project': project, 'src': project / 'src', 'package': project / 'src/aau_harness',
                'module': project / 'src/aau_harness/cli.py', 'sdist': paths[1], 'wheel': paths[2]}[target]
        moved = path.with_name(path.name + '.original')
        path.rename(moved)
        path.symlink_to(moved, target_is_directory=moved.is_dir())
    assert audit.main(cli_args(paths)) == 2


def test_archive_input_is_never_imported_or_run(package):
    project, sources, wheel = package
    marker = project.parent / 'code-was-executed'
    payload = f'from pathlib import Path\nPath({str(marker)!r}).touch()\n'.encode()
    (project / 'src/aau_harness/__init__.py').write_bytes(payload)
    sources['src/aau_harness/__init__.py'] = wheel['aau_harness/__init__.py'] = payload
    assert audit.audit(*save_archives(package))['status'] == 'contents_match'
    assert not marker.exists()  # Matching code is not certified safe, and the auditor does not execute it.


def test_other_sdist_build_inputs_are_bound_but_not_approved(package):
    package[1]['setup.py'] = b'raise RuntimeError("not executed by this auditor")\n'
    report = audit.audit(*save_archives(package))
    assert report['status'] == 'contents_match'
    assert 'setup.py' in report['sdist_members']
    assert 'other sdist members are inventoried but not approved' in report['boundary']


def test_invalid_inputs_do_not_echo_content_or_local_paths(package, capsys):
    package[2][f'{DIST}/METADATA'] = METADATA.replace(b'Name: aau-harness', b'Name: aau-harness\nName: PRIVATE_VALUE')
    assert audit.main(cli_args(save_archives(package))) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert 'PRIVATE_VALUE' not in captured.err and str(package[0]) not in captured.err
    assert 'no artifact executed' in captured.err


def test_report_size_limit_and_byte_exact_verification(package, monkeypatch):
    paths = save_archives(package)
    report = paths[0].parent / 'audit.json'
    assert audit.main(cli_args(paths) + ['--out', str(report)]) == 0
    report.write_bytes(report.read_bytes() + b' ')
    assert audit.main(cli_args(paths) + ['--verify', str(report)]) == 2
    computed = audit.audit(*paths)
    monkeypatch.setattr(audit, 'audit', lambda *args: computed)
    monkeypatch.setattr(audit, 'MAX_FILE', 1)
    assert audit.main(cli_args(paths) + ['--out', str(paths[0].parent / 'oversized.json')]) == 2
    assert not (paths[0].parent / 'oversized.json').exists()


@pytest.mark.parametrize('target,raw', [('sdist', b'not gzip'), ('sdist', b'\x1f\x8b'),
                                      ('sdist', gzip.compress(b'not tar')), ('wheel', b'not zip')])
def test_malformed_archives_are_invalid(package, target, raw):
    paths = save_archives(package)
    paths[1 if target == 'sdist' else 2].write_bytes(raw)
    assert audit.main(cli_args(paths)) == 2


def test_source_archive_requires_metadata(package):
    del package[1]['PKG-INFO']
    assert audit.main(cli_args(save_archives(package))) == 2


@pytest.mark.parametrize('before,after', [
    ('name = "aau-harness"', 'name = "another-package"'),
    ('readme = "README.md"', 'readme = "other.md"'),
    ('[project]', '[project]\ndynamic = ["description"]'),
])
def test_other_project_profiles_are_not_silently_accepted(package, before, after):
    path = package[0] / 'pyproject.toml'
    path.write_text(path.read_text().replace(before, after))
    assert audit.main(cli_args(save_archives(package))) == 2


def test_matching_report_cannot_be_reused_for_repacked_artifact(package):
    paths = save_archives(package)
    report = paths[0].parent / 'audit.json'
    assert audit.main(cli_args(paths) + ['--out', str(report)]) == 0
    with zipfile.ZipFile(paths[2], 'a') as archive:
        archive.comment = b'Same member contents; different artifact bytes.'
    assert audit.audit(*paths)['status'] == 'contents_match'
    assert audit.main(cli_args(paths) + ['--verify', str(report)]) == 2


def test_release_audits_before_executing_installing_uploading_or_attesting_wheel():
    workflow = (ROOT / '.github/workflows/harness-release.yml').read_text()
    assert workflow.index('python -m build harness') < workflow.index('audit_package_contents.py')
    assert workflow.index('audit_package_contents.py') < workflow.index('smoke_installed_wheel.py')
    assert workflow.index('audit_package_contents.py') < workflow.index('Upload package distributions')
    assert workflow.index('audit_package_contents.py') < workflow.index('Attest package provenance')
    assert 'needs: build' in workflow.split('publish-pypi:', 1)[1]
    assert 'needs: build' in workflow.split('publish-github:', 1)[1]
