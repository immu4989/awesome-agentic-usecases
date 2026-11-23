"""Cross-check synthetic AAU bags with pinned Library of Congress bagit-python, not agency approval."""

import argparse
from importlib.metadata import version
from pathlib import Path
import shutil

from aau_harness.agent_bom import AgentBomError, digest, write_json
from aau_harness.evidence_bag import create_bag, verify_bag


def run_probe(out):
    import bagit

    if version('bagit') != '1.9.0':
        raise RuntimeError('this interoperability probe requires bagit==1.9.0')
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'source'
    (source / 'nested/empty').mkdir(parents=True)
    (source / 'nested/binary.bin').write_bytes(bytes(range(256)))
    (source / 'empty.txt').write_bytes(b'')
    original = out / 'original'
    receipt = create_bag(source, original)
    pin = receipt['tagmanifest_sha256']
    results = []

    def check(name, directory, *, expected_library, expected_pinned):
        # Full checksum validation, never fast/oxum-only validation or a fetch operation.
        try:
            valid = bagit.Bag(str(directory)).validate(processes=1, fast=False)
        except bagit.BagValidationError:
            valid = False
        try:
            verify_bag(directory, tagmanifest_sha256=pin)
            pinned = True
        except AgentBomError:
            pinned = False
        if valid is not expected_library or pinned is not expected_pinned:
            raise RuntimeError(f'{name}: unexpected interoperability result: library={valid}, pinned={pinned}')
        results.append({'case': name, 'library_full_validation': valid, 'aau_pinned_validation': pinned})

    check('original', original, expected_library=True, expected_pinned=True)
    for name in ('same-size-corruption', 'missing-file', 'extra-file', 'changed-tag', 'missing-empty-directory'):
        directory = out / name
        shutil.copytree(original, directory)
        if name == 'same-size-corruption':
            (directory / 'data/nested/binary.bin').write_bytes(bytes(reversed(range(256))))
        elif name == 'missing-file':
            (directory / 'data/empty.txt').unlink()
        elif name == 'extra-file':
            (directory / 'data/extra.txt').write_bytes(b'')
        elif name == 'changed-tag':
            with (directory / 'bag-info.txt').open('ab') as stream:
                stream.write(b'Contact-Name: Synthetic replacement\n')
        else:
            (directory / 'data/nested/empty').rmdir()
        check(name, directory, expected_library=name == 'missing-empty-directory', expected_pinned=False)
    # Recomputed checksums can describe a different, valid bag. The receiver's old pin still rejects it.
    (source / 'empty.txt').write_bytes(b'substituted')
    replacement = out / 'replacement'
    create_bag(source, replacement)
    check('recomputed-substitution', replacement, expected_library=True, expected_pinned=False)
    report = {'probe_version': 'aau-bagit-compatibility/1.0', 'bagit_version': version('bagit'),
              'aau_harness_version': version('aau-harness'), 'bagit_module_sha256': digest(Path(bagit.__file__).read_bytes()),
              'original_receipt': receipt, 'checks': results,
              'boundary': 'Seven synthetic directory cases against one pinned library, not full BagIt conformance, '
                          'independent reproduction, provenance, native evidence validation, or agency acceptance.'}
    write_json(report, out / 'compatibility.json')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.out)
    print(f'{len(report["checks"])} BagIt interoperability checks passed (full checksums; not approval).')


if __name__ == '__main__':
    main()
