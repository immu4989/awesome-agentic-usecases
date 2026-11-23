"""Transfer bounded evidence as a deterministic BagIt directory; never approve its contents."""

import argparse
import hashlib
from pathlib import Path
import re
import sys

from .agent_bom import AgentBomError, digest, rendered
from .inspect_pack import MAX_DIRECTORIES, MAX_FILES, _capture


VERSION = 'aau-evidence-bag/1.0'
DECLARATION = b'BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n'
TAG_NAMES = frozenset({'bagit.txt', 'bag-info.txt', 'aau-transfer.json',
                       'manifest-sha256.txt', 'manifest-sha512.txt',
                       'tagmanifest-sha256.txt', 'tagmanifest-sha512.txt'})
BOUNDARY = (
    'Transport fixity only: native evidence, policy outcomes, and approval are not assessed. '
    'Retain the tag-manifest SHA-256 through an independently trusted channel; a pin supplied '
    'only alongside the bag does not authenticate its sender. Run the appropriate native verifier '
    'on data/ with independently retained request or plan pins before using the evidence. '
    'Files, including HTML and executable content, are opaque and are not opened or executed. '
    'No network retrieval, archive extraction, redaction, encryption, signature, records-retention '
    'assurance, or permission to disclose is provided. The bounded copy is not an atomic snapshot '
    'of a changing source. This verifier accepts only the canonical AAU profile, not arbitrary bags.'
)


def _fail(reason):
    raise AgentBomError('evidence_bag_' + reason)


def _portable_names(names):
    # Fail before writing: case-insensitive filesystems and Windows reserved names must not
    # silently collapse a transferred inventory. Do not normalize or rewrite source names.
    seen = set()
    for name in names:
        if name.casefold() in seen:
            _fail('nonportable_names')
        seen.add(name.casefold())
        for part in name.split('/'):
            stem = part.split('.')[0].upper()
            if (not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', part) or part in {'.', '..'}
                    or part.endswith('.') or stem in {'CON', 'PRN', 'AUX', 'NUL'}
                    or re.fullmatch(r'(COM|LPT)[1-9]', stem)):
                _fail('nonportable_names')


def _tags(payload, directories):
    if (not payload or len(payload) > MAX_FILES - len(TAG_NAMES)
            or len(directories) >= MAX_DIRECTORIES - 1
            or any(len(n.split('/')) > 3 for n in payload)
            or any(len(n.split('/')) > 2 for n in directories)):
        _fail('payload_resource_limit')
    _portable_names([*payload, *directories])
    tags = {
        'bagit.txt': DECLARATION,
        'bag-info.txt': (
            'Bag-Software-Agent: AAU evidence-bag 1.0\n'
            f'Payload-Oxum: {sum(map(len, payload.values()))}.{len(payload)}\n'
            'External-Description: Evidence transport only; not native verification or approval.\n'
        ).encode('utf-8'),
        # BagIt manifests bind files, not empty directories. This additional tag preserves
        # directory presence for native evidence formats where empty and absent differ.
        'aau-transfer.json': rendered({'profile_version': VERSION, 'directories': sorted(directories),
                                       'boundary': BOUNDARY}),
    }
    for algorithm in ('sha256', 'sha512'):
        tags[f'manifest-{algorithm}.txt'] = _manifest(
            {'data/' + name: raw for name, raw in payload.items()}, algorithm)
    ordinary_tags = dict(tags)
    for algorithm in ('sha256', 'sha512'):
        # RFC 8493 forbids a tag manifest from listing itself or another tag manifest.
        tags[f'tagmanifest-{algorithm}.txt'] = _manifest(ordinary_tags, algorithm)
    return tags


def _manifest(files, algorithm):
    return ''.join(f'{hashlib.new(algorithm, files[name]).hexdigest()}  {name}\n'
                   for name in sorted(files)).encode('utf-8')


def _report(payload, directories, tags):
    return {'report_version': VERSION, 'status': 'transport_fixity_verified',
            'native_evidence_status': 'not_assessed', 'decision_status': 'not_assessed',
            'human_review_required': True, 'payload_file_count': len(payload),
            'payload_byte_count': sum(map(len, payload.values())),
            'payload_files_sha256': {n: digest(raw) for n, raw in sorted(payload.items())},
            'payload_directories': sorted(directories),
            'tagmanifest_sha256': digest(tags['tagmanifest-sha256.txt']), 'boundary': BOUNDARY}


def create_bag(source: Path, directory: Path):
    if directory.exists() or directory.is_symlink():
        _fail('refusing_overwrite')
    if directory.resolve().is_relative_to(source.resolve()):
        _fail('output_inside_source')
    payload, directories = _capture(source)
    tags = _tags(payload, directories)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'data').mkdir()
    for name in sorted(directories):
        (directory / 'data' / name).mkdir(parents=True, exist_ok=True)
    for name, raw in {**tags, **{'data/' + n: b for n, b in payload.items()}}.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    # A successful creation checks the completed copy, not only the in-memory inputs.
    return verify_bag(directory, tagmanifest_sha256=digest(tags['tagmanifest-sha256.txt']))


def verify_bag(directory: Path, *, tagmanifest_sha256):
    if not isinstance(tagmanifest_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', tagmanifest_sha256):
        _fail('independent_pin_required')
    files, directories = _capture(directory)
    tags = {n: raw for n, raw in files.items() if not n.startswith('data/')}
    if set(tags) != TAG_NAMES or digest(tags['tagmanifest-sha256.txt']) != tagmanifest_sha256:
        _fail('tag_inventory_or_pin_mismatch')
    if 'data' not in directories or any(n != 'data' and not n.startswith('data/') for n in directories):
        _fail('directory_inventory_mismatch')
    payload = {n.removeprefix('data/'): raw for n, raw in files.items() if n.startswith('data/')}
    payload_dirs = [n.removeprefix('data/') for n in directories if n != 'data']
    # Reconstruct from captured regular files, never follow paths supplied by manifests.
    # Exact bytes also reject duplicate lines, extra algorithms/tags, fetch.txt, altered
    # directory metadata and alternate encodings. Deliberately a profile, not a generic parser.
    if tags != _tags(payload, payload_dirs):
        _fail('canonical_inventory_or_checksums_mismatch')
    return _report(payload, payload_dirs, tags)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau evidence-bag', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create', help='Copy a bounded local directory into a new offline bag')
    create.add_argument('source', type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify', help='Verify against an independently retained tag-manifest pin')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--tagmanifest-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        report = (create_bag(args.source, args.out) if args.command == 'create'
                  else verify_bag(args.directory, tagmanifest_sha256=args.tagmanifest_sha256))
        print(rendered(report).decode('utf-8'), end='')
        return 0
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError):
        print('error: evidence_bag_rejected; no verified transfer reported.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
