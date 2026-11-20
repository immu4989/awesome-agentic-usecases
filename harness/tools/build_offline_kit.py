#!/usr/bin/env python3
"""Prepare a no-download Python 3.11+ kit from audited local AAU artifacts."""

import argparse
from pathlib import Path
import sys
import tomllib

from packaging.markers import default_environment

import audit_package_contents as auditor
from verify_offline_kit import MAX_ARTIFACT, MAX_FILE, encoded, expected_names, object_hash, read_regular, sha, verify


BOUNDARY = ('Local preparation from artifacts matching a supplied checkout, not trusted Git identity, '
            'producer authentication, malware scanning, dependency/interpreter validation, reproducible-build '
            'certification, government adoption, FedRAMP authorization, an ATO, or deployment approval. '
            'Python 3.11+ only; Python itself, pip, operating-system dependencies, development extras, and '
            'model providers are not bundled. No package is downloaded, installed, extracted, or executed. '
            'Keep the verifier hash and manifest hash independently through an approved transfer process. '
            'A kit cannot establish trust in its own verifier or its expected hashes.')


def kit_payloads(project, sdist, wheel):
    report = auditor.audit(project, sdist, wheel)
    if report['status'] != 'contents_match':
        raise ValueError('artifacts must match the supplied checkout before preparing an offline kit')
    declaration = tomllib.loads(read_regular(project / 'pyproject.toml').decode())['project']
    if auditor.SpecifierSet(declaration['requires-python']) != auditor.SpecifierSet('>=3.10'):
        raise ValueError('declared Python support changed; offline profile review required')
    # Refuse a no-deps kit if the declared runtime dependency profile has changed.
    environment = default_environment()
    environment.update(python_version='3.11', python_full_version='3.11.0', extra='')
    for requirement in declaration.get('dependencies', []):
        req = auditor.Requirement(requirement)
        if req.marker is None or req.marker.evaluate(environment):
            raise ValueError('the offline profile requires no runtime dependencies on Python 3.11')
    # Only the current compatibility shim is supported; do not infer future marker behavior.
    requirements = [auditor.Requirement(value) for value in declaration.get('dependencies', [])]
    if (len(requirements) != 1 or auditor.canonicalize_name(requirements[0].name) != 'tomli'
            or requirements[0].extras or requirements[0].url is not None
            or requirements[0].specifier != auditor.SpecifierSet('>=2.0')
            or requirements[0].marker != auditor.Marker('python_version < "3.11"')):
        raise ValueError('offline dependency profile changed; explicit review required')
    names = expected_names(report['version'])
    raw_sdist, raw_wheel = read_regular(sdist, MAX_ARTIFACT), read_regular(wheel, MAX_ARTIFACT)
    if report['artifacts'] != {'sdist_sha256': sha(raw_sdist), 'wheel_sha256': sha(raw_wheel)}:
        raise ValueError('artifact changed after content audit')
    sources = {name.removeprefix('aau_harness/'): value for name, value in report['source_files'].items()}
    expected_runtime = {'receipt_version': 'aau-offline-runtime-expectation/1.0', 'distribution_version': report['version'],
                        'source_files': dict(sorted(sources.items())), 'source_tree_sha256': object_hash(sources)}
    files = {names['wheel']: raw_wheel, names['sdist']: raw_sdist,
             'package-audit.json': encoded(report), 'expected-runtime.json': encoded(expected_runtime),
             'LICENSE': read_regular(project.parent / 'LICENSE'),
             'requirements.lock': f'aau-harness=={report["version"]} --hash=sha256:{sha(raw_wheel)}\n'.encode(),
             'verify_offline_kit.py': read_regular(Path(__file__).with_name('verify_offline_kit.py'))}
    files['README.md'] = f'''# AAU offline review installation kit

Prepared from local audited artifacts. This is not a public package release or agency approval.
Requires an independently approved Python 3.11+ environment with pip and venv available.
Python 3.10, development extras, provider SDKs, the Python interpreter, and OS dependencies are not included.
No installer or verifier runs automatically. Do not install software on restricted systems without authorization.

## Establish trust before running code

Obtain the expected SHA-256 values for **both verify_offline_kit.py and manifest.json** independently
from the approved preparer. A hash supplied only inside this kit is not an independent trust anchor.
Before executing this kit's verifier, compare its hash using your already trusted OS hashing tool
(for example `shasum -a 256 verify_offline_kit.py`, `sha256sum verify_offline_kit.py`, or PowerShell
`Get-FileHash verify_offline_kit.py -Algorithm SHA256`). Confirm the manifest hash the same way.
Do not trust instructions in an unverified kit as proof of authenticity. Review the prepared source
and package audit through your organization's approval process; hashes are not malware scanning.

## Verify the transferred kit, then install explicitly

Run from the kit directory, using the separately retained manifest hash:

```bash
python verify_offline_kit.py . --manifest-sha256 APPROVED_MANIFEST_SHA256
```

Exit 0 checks exact kit bytes and receipt consistency; exit 2 means reject. Nothing is installed.
Use a **fresh approved virtual environment outside this kit**. Select/activate its Python interpreter
before running these commands. On some systems the command is python3; Windows and POSIX activation differ.

```bash
python -m pip --isolated install --no-index --no-deps --only-binary=:all: --require-hashes --disable-pip-version-check --find-links wheels -r requirements.lock
python -m pip check
python -m aau_harness.catalog_cli runtime-info --out ../installed-runtime.json
python verify_offline_kit.py . --manifest-sha256 APPROVED_MANIFEST_SHA256 --runtime ../installed-runtime.json
python -m aau_harness.catalog_cli inspect-review demo --out ../offline-review-example
```

All output paths must be new and outside the kit. The kit verifier rejects additional files, including
an in-kit virtual environment or receipts. The pip command uses only the hash-locked local wheel;
it does not resolve dependencies or use an index. Do not remove flags or fetch replacement packages
to bypass a mismatch. A fresh environment avoids silently keeping another build with the same version.
The package metadata version is {report['version']}; matching source hashes, not that version alone,
identify this checkout build. The runtime comparison checks supplied first-party file hashes only,
not interpreter bytes, dependencies, previously loaded code, or trustworthy execution.

## Review a result without agency data

Read ../offline-review-example/README.md. Its unsafe/repaired/unknown-budget examples are synthetic;
expected verification exits are 1/0/1. Open their review/review.html locally. A passing demo is a
mechanism check, not independent reproduction, government adoption, compliance, or public benefit.
The kit's source archive is for authorized review, not an installation fallback; this verifier never
extracts it. Retain all nine kit files, including the repository license, audit evidence, independent pins,
and your local test results. Source project: https://github.com/immu4989/awesome-agentic-usecases

{BOUNDARY}
'''.encode()
    if any(len(raw) > (MAX_ARTIFACT if name in names.values() else MAX_FILE) for name, raw in files.items()):
        raise ValueError('offline kit member exceeds its size limit')
    files['manifest.json'] = encoded({'kit_version': 'aau-offline-installation-kit/1.0',
        'distribution_version': report['version'], 'python_minimum': '3.11',
        'files': {name: sha(raw) for name, raw in sorted(files.items())}, 'boundary': BOUNDARY})
    return files


def create_kit(project, sdist, wheel, directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite an offline kit destination')
    files = kit_payloads(project, sdist, wheel)
    directory.mkdir(parents=True, exist_ok=False)
    for group in ('wheels', 'source'):
        (directory / group).mkdir()
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    manifest_pin = sha(files['manifest.json'])
    verify(directory, manifest_sha256=manifest_pin)
    return {'manifest_sha256': manifest_pin, 'verifier_sha256': sha(files['verify_offline_kit.py'])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdist', type=Path)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(encoded(create_kit(args.project, args.sdist, args.wheel, args.out)).decode(), end='')
        return 0
    except (ValueError, OSError, TypeError, KeyError, RecursionError, RuntimeError, EOFError,
            auditor.tarfile.TarError, auditor.zipfile.BadZipFile, auditor.zlib.error,
            auditor.configparser.Error, auditor.csv.Error) as exc:
        print(f'Offline kit preparation rejected ({type(exc).__name__}); nothing installed or downloaded.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
