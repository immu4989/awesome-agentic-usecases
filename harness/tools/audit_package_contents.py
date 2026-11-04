#!/usr/bin/env python3
"""Read-only AAU source/sdist/wheel content audit; never extract, install, or execute artifacts."""

import argparse
import base64
import configparser
import csv
from email.parser import BytesParser
import gzip
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile
import tomllib
import zipfile
import zlib

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version


MAX_FILE = 2_000_000
MAX_ARCHIVE = 20_000_000
MAX_EXPANDED = 40_000_000
MAX_MEMBERS = 2000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_file(path, limit=MAX_FILE):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("inputs must be bounded regular files, not symlinks")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("input exceeds size limit")
    return data


def safe_name(name):
    if (not isinstance(name, str) or not name or len(name) > 500 or "\\" in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("invalid archive member name")
    path = PurePosixPath(name)
    if (not path.parts or path.is_absolute() or any(p in ("..", ".") or ":" in p for p in path.parts)
            or str(path) != name):
        raise ValueError("noncanonical or unsafe archive path")
    return name


def _add_member(files, seen, name, data, is_directory=False):
    safe_name(name)
    if name in seen or len(seen) >= MAX_MEMBERS:
        raise ValueError("duplicate or excessive archive member inventory")
    seen.add(name)
    if not is_directory:
        if len(data) > MAX_FILE:
            raise ValueError("archive member exceeds size limit")
        files[name] = data


def zip_members(raw):
    if len(raw) > MAX_ARCHIVE:
        raise ValueError("wheel exceeds archive size limit")
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        if len(archive.infolist()) > MAX_MEMBERS:
            raise ValueError("too many wheel members")
        for item in archive.infolist():
            if item.orig_filename != item.filename:
                raise ValueError("wheel member name was normalized")
            kind = stat.S_IFMT(item.external_attr >> 16)
            if (item.flag_bits & 1 or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError("encrypted, linked, special, or unsupported wheel member")
            if ((kind == stat.S_IFDIR and not item.is_dir())
                    or (item.is_dir() and (kind == stat.S_IFREG or item.file_size))):
                raise ValueError("inconsistent wheel directory entry")
            total += item.file_size
            if item.file_size > MAX_FILE or total > MAX_EXPANDED:
                raise ValueError("expanded wheel exceeds size limits")
            _add_member(files, seen, item.filename.rstrip('/') if item.is_dir() else item.filename,
                        b'' if item.is_dir() else archive.read(item), item.is_dir())
    return files


def tar_members(raw):
    if len(raw) > MAX_ARCHIVE:
        raise ValueError("source archive exceeds size limit")
    with gzip.GzipFile(fileobj=BytesIO(raw)) as stream:
        expanded = stream.read(MAX_EXPANDED + 1)
    if len(expanded) > MAX_EXPANDED:
        raise ValueError("expanded source archive exceeds size limit")
    files, seen = {}, set()
    with tarfile.open(fileobj=BytesIO(expanded), mode="r:") as archive:
        for item in archive:
            if (not item.isfile() and not item.isdir()) or item.issparse():
                raise ValueError("source archive links and special files are refused")
            if item.size < 0 or item.size > MAX_FILE or (item.isdir() and item.size):
                raise ValueError("source archive member exceeds size limit")
            data = archive.extractfile(item).read(MAX_FILE + 1) if item.isfile() else b''
            _add_member(files, seen, item.name.rstrip('/') if item.isdir() else item.name, data, item.isdir())
    roots = {PurePosixPath(name).parts[0] for name in seen}
    if len(roots) != 1 or not files:
        raise ValueError("source archive requires one nonempty top-level project directory")
    prefix = roots.pop() + '/'
    if any(not name.startswith(prefix) for name in files):
        raise ValueError("source archive files must be inside its project directory")
    return {name[len(prefix):]: value for name, value in files.items()}


def source_inventory(project):
    package = project / "src/aau_harness"
    if (project.is_symlink() or not project.is_dir() or (project / 'src').is_symlink()
            or package.is_symlink() or not package.is_dir()):
        raise ValueError("project and package must be real directories")
    files, total = {}, 0

    def onerror(error):
        raise ValueError("source tree is unreadable") from error

    for folder, directories, names in os.walk(package, followlinks=False, onerror=onerror):
        directories[:] = sorted(name for name in directories if name != "__pycache__")
        if any((Path(folder) / name).is_symlink() for name in directories):
            raise ValueError("source package directories cannot be symlinks")
        for name in sorted(names):
            if not name.endswith('.py'):
                continue
            path = Path(folder) / name
            data = read_file(path)
            total += len(data)
            if len(files) >= 500 or total > MAX_ARCHIVE:
                raise ValueError("first-party source inventory exceeds limits")
            key = path.relative_to(project / "src").as_posix()
            safe_name(key)
            files[key] = data
    if "aau_harness/__init__.py" not in files:
        raise ValueError("missing package initializer")
    return dict(sorted(files.items()))


def entry_points(raw):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(raw.decode('utf-8'))
    if parser.defaults() or parser.sections() != ['console_scripts']:
        raise ValueError("only explicit console_scripts entry points are supported")
    return dict(parser['console_scripts'])


def requirements(project):
    result = {Requirement(value) for value in project.get('dependencies', [])}
    extras = project.get('optional-dependencies', {})
    for extra, values in extras.items():
        for value in values:
            requirement = Requirement(value)
            condition = f'extra == "{canonicalize_name(extra)}"'
            requirement.marker = Marker(f'({requirement.marker}) and {condition}' if requirement.marker else condition)
            result.add(requirement)
    return result, {canonicalize_name(extra) for extra in extras}


def metadata_matches(raw, project):
    metadata = BytesParser().parsebytes(raw)
    for field in ('Name', 'Version', 'Requires-Python'):
        if len(metadata.get_all(field, [])) != 1:
            raise ValueError("package metadata requires one identity/version/Python requirement")
    expected_requirements, extras = requirements(project)
    return (canonicalize_name(metadata['Name']) == canonicalize_name(project['name'])
            and Version(metadata['Version']) == Version(project['version'])
            and SpecifierSet(metadata['Requires-Python']) == SpecifierSet(project['requires-python'])
            and {Requirement(value) for value in metadata.get_all('Requires-Dist', [])} == expected_requirements
            and {canonicalize_name(value) for value in metadata.get_all('Provides-Extra', [])} == extras)


def verify_record(files, dist_info):
    record = f'{dist_info}/RECORD'
    rows = list(csv.reader(StringIO(files[record].decode('utf-8'), newline=''), strict=True))
    indexed = {}
    for row in rows:
        if len(row) != 3 or row[0] in indexed or row[0] not in files:
            raise ValueError("wheel RECORD contains missing, duplicate, or unexpected entries")
        indexed[row[0]] = row[1:]
    if set(indexed) != set(files) or indexed[record] != ['', '']:
        raise ValueError("wheel RECORD must cover every member and leave its own digest/size empty")
    for name, data in files.items():
        if name != record:
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            if indexed[name] != [f'sha256={expected}', str(len(data))]:
                raise ValueError("wheel RECORD SHA-256 or size does not match member bytes")


def audit(project: Path, sdist: Path, wheel: Path):
    inputs = {name: read_file(project / name) for name in ('pyproject.toml', 'README.md')}
    declaration = tomllib.loads(inputs['pyproject.toml'].decode())['project']
    if declaration['name'] != 'aau-harness' or declaration.get('readme') != 'README.md' or declaration.get('dynamic'):
        raise ValueError("audit supports the static AAU harness package declaration only")
    version = str(Version(declaration['version']))
    expected_scripts = declaration['scripts']
    if not isinstance(expected_scripts, dict) or not expected_scripts:
        raise ValueError("explicit console entry points are required")
    sources = source_inventory(project)
    source_raw, wheel_raw = read_file(sdist, MAX_ARCHIVE), read_file(wheel, MAX_ARCHIVE)
    source_files, wheel_files = tar_members(source_raw), zip_members(wheel_raw)
    dist_info = f'aau_harness-{version}.dist-info'
    metadata_files = {f'{dist_info}/{name}' for name in ('METADATA', 'WHEEL', 'RECORD', 'entry_points.txt', 'top_level.txt')}
    if not metadata_files <= set(wheel_files):
        raise ValueError("wheel is missing required AAU metadata members")
    verify_record(wheel_files, dist_info)
    wheel_header = BytesParser().parsebytes(wheel_files[f'{dist_info}/WHEEL'])
    if (wheel_header.get_all('Wheel-Version') != ['1.0'] or wheel_header.get_all('Root-Is-Purelib') != ['true']
            or wheel_header.get_all('Tag') != ['py3-none-any']):
        raise ValueError("audit requires the AAU pure-Python wheel profile")
    if 'PKG-INFO' not in source_files:
        raise ValueError("source archive is missing PKG-INFO")
    differences = []

    def compare(scope, expected, actual):
        for name in sorted(set(expected) | set(actual)):
            if expected.get(name) != actual.get(name):
                differences.append({'scope': scope, 'member': name,
                                    'expected_sha256': sha(expected[name]) if name in expected else None,
                                    'actual_sha256': sha(actual[name]) if name in actual else None})

    compare('wheel_payload', sources, {name: value for name, value in wheel_files.items() if name not in metadata_files})
    compare('sdist_python', {f'src/{name}': value for name, value in sources.items()},
            {name: value for name, value in source_files.items() if name.startswith('src/aau_harness/')})
    compare('sdist_build_inputs', inputs, {name: source_files[name] for name in inputs if name in source_files})
    checks = {'wheel_metadata': metadata_matches(wheel_files[f'{dist_info}/METADATA'], declaration),
              'sdist_metadata': metadata_matches(source_files['PKG-INFO'], declaration),
              'console_scripts': entry_points(wheel_files[f'{dist_info}/entry_points.txt']) == expected_scripts,
              'top_level_package': wheel_files[f'{dist_info}/top_level.txt'].strip() == b'aau_harness'}
    status = 'contents_match' if not differences and all(checks.values()) else 'contents_differ'
    return {'report_version': 'aau-package-content-audit/1.0', 'status': status,
            'distribution': declaration['name'], 'version': version,
            'source_files': {name: sha(value) for name, value in sources.items()},
            'build_inputs': {name: sha(value) for name, value in inputs.items()},
            'artifacts': {'sdist_sha256': sha(source_raw), 'wheel_sha256': sha(wheel_raw)},
            'wheel_members': {name: sha(value) for name, value in sorted(wheel_files.items())},
            'sdist_members': {name: sha(value) for name, value in sorted(source_files.items())},
            'metadata_checks': checks, 'differences': differences,
            'source_file_count': len(sources), 'console_script_count': len(expected_scripts),
            'boundary': 'Read-only content comparison against the supplied checkout, not trusted Git identity, signatures, '
                        'execution safety, reproducible-build certification, interpreter/dependency bytes, or release approval. '
                        'Every installed payload member must match the declared first-party Python files; only the five '
                        'specified metadata files are allowed. Sdist package sources, pyproject.toml, README.md, and declared '
                        'dependency metadata are checked; other sdist members are inventoried but not approved as build inputs. '
                        'No artifact is extracted, installed, imported, or executed. Archive bytes and inventories are bound, '
                        'not authenticated. ZIP timestamps/compression are not compared against a second build. Requires a '
                        'trusted checkout and this auditor. No local absolute paths or environment values are recorded.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdist', type=Path)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(args.project, args.sdist, args.wheel)
        encoded = (json.dumps(report, indent=2) + '\n').encode('utf-8')
        if len(encoded) > MAX_FILE:
            raise ValueError("audit report exceeds size limit")
        if args.verify:
            if read_file(args.verify) != encoded:
                raise ValueError("package content audit does not recompute")
        elif args.out:
            with args.out.open('xb') as stream:
                stream.write(encoded)
        else:
            print(encoded.decode('utf-8'), end='')
        if args.out or args.verify:
            print(f"Package audit: {report['status']}; {report['source_file_count']} sources and {report['console_script_count']} commands.")
        return int(report['status'] != 'contents_match')
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, configparser.Error, csv.Error,
            tarfile.TarError, zipfile.BadZipFile, zlib.error, RuntimeError, EOFError) as exc:
        # Do not echo untrusted archive contents or absolute local paths.
        print(f'Package audit rejected input ({type(exc).__name__}); no artifact executed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
