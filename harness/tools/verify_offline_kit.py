#!/usr/bin/env python3
"""Standard-library-only verification of an independently pinned offline kit; never install it."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


MAX_FILE = 2_000_000
MAX_ARTIFACT = 20_000_000


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def object_hash(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode())


def read_regular(path, limit=MAX_FILE):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError('kit inputs must be bounded regular non-symlink files')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError('kit input changed during capture')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('kit input exceeds limit')
    return raw


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs)
    json.dumps(value, allow_nan=False)
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def expected_names(version):
    if not isinstance(version, str) or re.fullmatch(r'[0-9][0-9A-Za-z.!+]*', version) is None:
        raise ValueError('unsupported distribution version')
    return {'wheel': f'wheels/aau_harness-{version}-py3-none-any.whl',
            'sdist': f'source/aau_harness-{version}.tar.gz'}


def verify(directory, *, manifest_sha256, runtime_path=None):
    if sys.version_info < (3, 11):
        raise ValueError('this offline kit requires Python 3.11 or newer; Python 3.10 dependencies are not bundled')
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('kit must be a real directory')
    raw = read_regular(directory / 'manifest.json')
    if not valid_hash(manifest_sha256) or sha(raw) != manifest_sha256:
        raise ValueError('offline kit manifest pin mismatch')
    manifest = parse(raw)
    if (set(manifest) != {'kit_version', 'distribution_version', 'python_minimum', 'files', 'boundary'}
            or manifest['kit_version'] != 'aau-offline-installation-kit/1.0' or manifest['python_minimum'] != '3.11'):
        raise ValueError('unsupported kit manifest')
    names = expected_names(manifest['distribution_version'])
    expected = {'package-audit.json', 'expected-runtime.json', 'requirements.lock', 'verify_offline_kit.py', 'README.md', 'LICENSE', *names.values()}
    pins = manifest['files']
    if not isinstance(pins, dict) or set(pins) != expected or not all(valid_hash(v) for v in pins.values()):
        raise ValueError('kit manifest must pin its exact member inventory')
    root_names = {name.split('/')[0] for name in expected} | {'manifest.json'}
    if {p.name for p in directory.iterdir()} != root_names:
        raise ValueError('unexpected or missing root member')
    for group in ('wheels', 'source'):
        folder = directory / group
        if folder.is_symlink() or not folder.is_dir() or {p.name for p in folder.iterdir()} != {n.split('/')[1] for n in names.values() if n.startswith(group + '/')}:
            raise ValueError('unexpected or unsafe artifact directory')
    captured = {name: read_regular(directory / name, MAX_ARTIFACT if name in names.values() else MAX_FILE) for name in sorted(expected)}
    if any(sha(data) != pins[name] for name, data in captured.items()):
        raise ValueError('kit member differs from the independently pinned manifest')
    version = manifest['distribution_version']
    lock = f'aau-harness=={version} --hash=sha256:{sha(captured[names["wheel"]])}\n'.encode()
    if captured['requirements.lock'] != lock:
        raise ValueError('requirements lock does not bind the exact wheel')
    audit = parse(captured['package-audit.json'])
    if (audit.get('status') != 'contents_match' or audit.get('version') != version
            or audit.get('distribution') != 'aau-harness'
            or audit.get('artifacts') != {'sdist_sha256': sha(captured[names['sdist']]), 'wheel_sha256': sha(captured[names['wheel']])}):
        raise ValueError('package audit receipt does not bind these artifacts')
    expected_runtime = parse(captured['expected-runtime.json'])
    source_files = audit.get('source_files')
    if (not isinstance(source_files, dict) or not source_files or len(source_files) > 500
            or any(not n.startswith('aau_harness/') or not valid_hash(v) for n, v in source_files.items())):
        raise ValueError('package audit source inventory is invalid')
    sources = {name.removeprefix('aau_harness/'): value for name, value in source_files.items()}
    target = {'receipt_version': 'aau-offline-runtime-expectation/1.0', 'distribution_version': version,
              'source_files': dict(sorted(sources.items())), 'source_tree_sha256': object_hash(sources)}
    if expected_runtime != target:
        raise ValueError('expected runtime differs from the package audit source inventory')
    if runtime_path is not None:
        actual = parse(read_regular(runtime_path))
        if (actual.get('report_version') != 'aau-runtime-source-receipt/1.0'
                or any(actual.get(name) != target[name] for name in ('distribution_version', 'source_files', 'source_tree_sha256'))):
            raise ValueError('installed first-party runtime receipt does not match the kit')
    return {'status': 'kit_bytes_verified', 'manifest_sha256': manifest_sha256,
            'distribution_version': version, 'member_count': len(captured) + 1,
            'runtime_sources': 'matched_supplied_receipt' if runtime_path is not None else 'not_supplied',
            'boundary': 'Byte integrity and receipt consistency only. This verifier does not independently rerun the source/archive audit, install or execute the wheel, authenticate the producer, approve software, validate dependencies/interpreter bytes, or attest actual execution. A runtime receipt is supplied data, not an authenticated observation. Trust this verifier and the expected manifest hash independently before running it.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--runtime', type=Path, help='optionally compare a separately collected aau runtime-info receipt')
    args = parser.parse_args(argv)
    try:
        print(encoded(verify(args.directory, manifest_sha256=args.manifest_sha256, runtime_path=args.runtime)).decode(), end='')
        return 0
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as exc:
        print(f'Offline kit rejected ({type(exc).__name__}); nothing installed or executed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
