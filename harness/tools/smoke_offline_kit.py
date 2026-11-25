#!/usr/bin/env python3
"""Explicitly install locally audited artifacts in a fresh no-index venv and test the offline path."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

from build_offline_kit import create_kit
from verify_offline_kit import verify


def smoke(project, sdist, wheel):
    if sys.version_info < (3, 11):
        raise ValueError('offline kit smoke requires Python 3.11+')
    with tempfile.TemporaryDirectory(prefix='aau-offline-install-') as temporary:
        root = Path(temporary)
        kit = root / 'kit'
        pins = create_kit(project, sdist, wheel, kit)
        verify(kit, manifest_sha256=pins['manifest_sha256'])
        environment = root / 'venv'
        venv.EnvBuilder(with_pip=True).create(environment)
        binary = environment / ('Scripts' if os.name == 'nt' else 'bin')
        python = binary / ('python.exe' if os.name == 'nt' else 'python')
        env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME')}
        env['PYTHONNOUSERSITE'] = '1'

        def run(args, expected=0):
            result = subprocess.run([str(x) for x in args], cwd=kit, env=env, capture_output=True, text=True, timeout=60)
            if result.returncode != expected:
                raise RuntimeError(f'offline kit smoke returned {result.returncode}, expected {expected}: '
                                   + result.stdout + result.stderr)
            return result.stdout

        run([python, '-I', '-m', 'pip', '--isolated', 'install', '--no-index', '--no-deps', '--only-binary=:all:',
             '--require-hashes', '--disable-pip-version-check', '--find-links', 'wheels', '-r', 'requirements.lock'])
        run([python, '-I', '-m', 'pip', '--isolated', 'check', '--disable-pip-version-check'])
        location = Path(run([python, '-I', '-c', 'import aau_harness; print(aau_harness.__file__)']).strip()).resolve()
        if environment.resolve() not in location.parents:
            raise RuntimeError('offline import resolved outside the fresh installation')
        receipt = root / 'runtime.json'
        cli = [python, '-I', '-m', 'aau_harness.catalog_cli']
        run([*cli, 'runtime-info', '--out', receipt])
        report = verify(kit, manifest_sha256=pins['manifest_sha256'], runtime_path=receipt)
        run([python, kit / 'verify_offline_kit.py', kit, '--manifest-sha256', pins['manifest_sha256'], '--runtime', receipt])
        run([python, kit / 'verify_offline_kit.py', kit, '--manifest-sha256', '0' * 64], expected=2)
        self_check = root / 'self-check'
        run([*cli, 'self-check', 'run', '--out', self_check])
        run([*cli, 'self-check', 'verify', self_check])
        run([*cli, 'self-check', 'run', '--out', self_check], expected=2)
        checked = json.loads((self_check / 'checks.json').read_bytes())
        if len(checked['checks']) != 9 or any(c['status'] != 'matched_expected' for c in checked['checks']):
            raise RuntimeError('offline installed self-check lost a fixed expectation')
        if (self_check / 'runtime.json').read_bytes() != receipt.read_bytes():
            raise RuntimeError('offline self-check did not bind the audited installed runtime')
        changed_check = self_check / 'checks.json'
        changed_check.write_bytes(changed_check.read_bytes() + b' ')
        run([*cli, 'self-check', 'verify', self_check], expected=2)
        demo = root / 'demo'
        run([*cli, 'inspect-review', 'demo', '--out', demo])
        for name, expected in (('unsafe', 1), ('repaired', 0), ('unknown-budget', 1)):
            import hashlib
            pin = hashlib.sha256((demo / name / 'request.json').read_bytes()).hexdigest()
            run([*cli, 'inspect-review', 'verify', demo / name, '--request-sha256', pin], expected=expected)
        # A receipt with a changed source inventory must not be accepted as this kit's runtime.
        changed = json.loads(receipt.read_bytes())
        changed['source_files']['catalog_cli.py'] = '0' * 64
        receipt.write_text(json.dumps(changed))
        run([python, kit / 'verify_offline_kit.py', kit, '--manifest-sha256', pins['manifest_sha256'], '--runtime', receipt], expected=2)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdist', type=Path)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    report = smoke(args.project, args.sdist, args.wheel)
    print(f'Offline kit smoke passed: {report["member_count"]} pinned files, hash-locked no-index install, '
          'matching first-party runtime receipt, nine fixed self-checks, synthetic outcomes 1/0/1, '
          'and rejected changed pin/runtime/self-check. '
          'Not an air-gap attestation or deployment approval.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
