import json
import os

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest
from aau_harness.catalog_cli import main
from aau_harness.evidence_bag import TAG_NAMES, create_bag, verify_bag
from aau_harness.inspect_pack import _capture


@pytest.fixture
def source(tmp_path):
    source = tmp_path / 'source'
    (source / 'nested' / 'empty').mkdir(parents=True)
    (source / 'nested' / 'binary.bin').write_bytes(bytes(range(256)))
    (source / 'empty.txt').write_bytes(b'')
    (source / 'review.html').write_bytes(b'<script>throw new Error("must not execute")</script>')
    return source


@pytest.fixture
def bag(source, tmp_path):
    directory = tmp_path / 'bag'
    report = create_bag(source, directory)
    return directory, report['tagmanifest_sha256']


def test_deterministic_exact_copy_without_native_claims(source, bag, tmp_path):
    directory, pin = bag
    report = verify_bag(directory, tagmanifest_sha256=pin)
    assert report['status'] == 'transport_fixity_verified'
    assert report['decision_status'] == report['native_evidence_status'] == 'not_assessed'
    assert report['human_review_required'] is True
    assert report['payload_file_count'] == 3
    assert _capture(source) == _capture(directory / 'data')
    assert set(_capture(directory)[0]) == TAG_NAMES | {'data/' + n for n in _capture(source)[0]}
    other = tmp_path / 'other'
    assert create_bag(source, other) == report
    assert _capture(directory) == _capture(other)
    assert (directory / 'data/nested/empty').is_dir()


@pytest.mark.parametrize('member', sorted(TAG_NAMES) + ['data/nested/binary.bin', 'data/empty.txt', 'data/review.html'])
@pytest.mark.parametrize('operation', ['modify', 'remove'])
def test_every_member_is_bound(bag, member, operation):
    directory, pin = bag
    path = directory / member
    if operation == 'modify':
        path.write_bytes(path.read_bytes() + b'x')
    else:
        path.unlink()
    with pytest.raises(AgentBomError):
        verify_bag(directory, tagmanifest_sha256=pin)


@pytest.mark.parametrize('name', ['fetch.txt', 'notes.txt', 'manifest-md5.txt', 'data/extra.txt', 'other/a.txt'])
def test_extra_file_rejected(bag, name):
    directory, pin = bag
    path = directory / name
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b'https://example.invalid/not-fetched')
    with pytest.raises(AgentBomError):
        verify_bag(directory, tagmanifest_sha256=pin)


@pytest.mark.parametrize('operation', ['remove_empty', 'extra_empty', 'extra_tag_directory'])
def test_directory_presence_is_bound_beyond_bagit_checksums(bag, operation):
    directory, pin = bag
    if operation == 'remove_empty':
        (directory / 'data/nested/empty').rmdir()
    else:
        (directory / ('data/new' if operation == 'extra_empty' else 'new')).mkdir()
    with pytest.raises(AgentBomError):
        verify_bag(directory, tagmanifest_sha256=pin)


@pytest.mark.parametrize('pin', [None, 1, '', '0' * 64, 'g' * 64, 'F' * 64, '../manifest'])
def test_independent_pin_required(bag, pin):
    with pytest.raises(AgentBomError):
        verify_bag(bag[0], tagmanifest_sha256=pin)


def test_rebagging_substitution_does_not_match_receiver_pin(source, bag, tmp_path):
    (source / 'empty.txt').write_bytes(b'changed')
    new = tmp_path / 'new'
    report = create_bag(source, new)
    assert report['tagmanifest_sha256'] != bag[1]
    with pytest.raises(AgentBomError):
        verify_bag(new, tagmanifest_sha256=bag[1])


@pytest.mark.parametrize('bad_line', [b'../outside', b'/etc/passwd', b'C:\\secret', b'data/%2e%2e/secret', b'data/./empty.txt'])
def test_manifest_paths_are_never_followed_even_with_replaced_pin(bag, bad_line):
    from aau_harness.evidence_bag import _manifest
    directory, _ = bag
    manifest = directory / 'manifest-sha256.txt'
    manifest.write_bytes(b'0' * 64 + b'  ' + bad_line + b'\n')
    # A matching outer pin cannot make a noncanonical manifest acceptable.
    ordinary = {n: (directory / n).read_bytes() for n in TAG_NAMES if not n.startswith('tagmanifest-')}
    for algorithm in ('sha256', 'sha512'):
        (directory / f'tagmanifest-{algorithm}.txt').write_bytes(_manifest(ordinary, algorithm))
    pin = digest((directory / 'tagmanifest-sha256.txt').read_bytes())
    with pytest.raises(AgentBomError):
        verify_bag(directory, tagmanifest_sha256=pin)


@pytest.mark.parametrize('name', ['CON', 'aux.json', 'LPT1.txt', 'COM9', 'ending.', 'has space', 'p' * 121])
def test_nonportable_names_rejected_before_output(source, tmp_path, name):
    (source / name).write_bytes(b'x')
    out = tmp_path / 'rejected'
    with pytest.raises(AgentBomError):
        create_bag(source, out)
    assert not out.exists()


def test_case_collisions_rejected_without_filesystem_dependency():
    from aau_harness.evidence_bag import _portable_names
    with pytest.raises(AgentBomError):
        _portable_names(['Folder', 'folder'])


@pytest.mark.parametrize('kind', ['file', 'directory', 'root', 'fifo'])
def test_special_source_members_rejected(source, tmp_path, kind):
    if kind == 'fifo':
        os.mkfifo(source / 'fifo')
    elif kind == 'root':
        alias = tmp_path / 'alias'
        alias.symlink_to(source, target_is_directory=True)
        source = alias
    else:
        (source / 'alias').symlink_to(source if kind == 'directory' else source / 'empty.txt')
    with pytest.raises(AgentBomError):
        create_bag(source, tmp_path / 'rejected')


def test_bag_member_symlink_rejected(bag, source):
    directory, pin = bag
    (directory / 'data/empty.txt').unlink()
    (directory / 'data/empty.txt').symlink_to(source / 'empty.txt')
    with pytest.raises(AgentBomError):
        verify_bag(directory, tagmanifest_sha256=pin)


@pytest.mark.parametrize('limit', ['files', 'directories', 'depth', 'bytes', 'empty'])
def test_limits_apply_before_output(tmp_path, limit):
    source = tmp_path / 'source'
    source.mkdir()
    if limit == 'files':
        for i in range(58):
            (source / f'f{i}').write_bytes(b'')
    elif limit == 'directories':
        for i in range(15):
            (source / f'd{i}').mkdir()
        (source / 'f').write_bytes(b'')
    elif limit == 'depth':
        (source / 'a/b/c').mkdir(parents=True)
        (source / 'a/b/c/f').write_bytes(b'')
    elif limit == 'bytes':
        (source / 'f').write_bytes(b'x' * (MAX_JSON_BYTES + 1))
    with pytest.raises(AgentBomError):
        create_bag(source, tmp_path / 'rejected')
    assert not (tmp_path / 'rejected').exists()


def test_maximum_supported_inventory_round_trips(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    for i in range(14):
        (source / f'd{i}').mkdir()
    for i in range(57):
        (source / f'd{i % 14}' / f'f{i}').write_bytes(b'x')
    report = create_bag(source, tmp_path / 'bag')
    assert report['payload_file_count'] == 57
    assert len(report['payload_directories']) == 14


def test_overwrite_and_nested_outputs_refused(source, bag, tmp_path):
    before = _capture(source)
    for out in (source, source / 'child', bag[0]):
        with pytest.raises(AgentBomError):
            create_bag(source, out)
    dangling = tmp_path / 'dangling'
    dangling.symlink_to(tmp_path / 'absent')
    with pytest.raises(AgentBomError):
        create_bag(source, dangling)
    assert _capture(source) == before


def test_native_failed_policy_is_preserved_and_replayable(tmp_path):
    from aau_harness.evidence_index import verify_index
    from aau_harness.evidence_index_demo import create_demo
    demo = tmp_path / 'demo'
    create_demo(demo)
    source = demo / 'complete-with-failed-policy'
    request_pin = digest((source / 'request.json').read_bytes())
    original = verify_index(source, request_sha256=request_pin)
    report = create_bag(source, tmp_path / 'bag')
    assert report['status'] == 'transport_fixity_verified'
    replay = verify_index(tmp_path / 'bag/data', request_sha256=request_pin)
    assert replay == original
    assert replay['items'][0]['native_outcome_status'] == 'constraints_not_met'


def test_cli_and_closed_errors(source, tmp_path, capsys):
    directory = tmp_path / 'bag'
    assert main(['evidence-bag', 'create', str(source), '--out', str(directory)]) == 0
    report = json.loads(capsys.readouterr().out)
    command = ['evidence-bag', 'verify', str(directory), '--tagmanifest-sha256', report['tagmanifest_sha256']]
    assert main(command) == 0
    assert json.loads(capsys.readouterr().out) == report
    assert main(['evidence-bag', 'create', str(source), '--out', str(directory)]) == 2
    assert str(source) not in capsys.readouterr().err
    (directory / 'data/empty.txt').write_bytes(b'x')
    assert main(command) == 2
    captured = capsys.readouterr()
    assert captured.out == '' and 'rejected' in captured.err


def test_canonical_profile_rejects_duplicate_and_reformatted_manifests(bag):
    directory, pin = bag
    manifest = directory / 'manifest-sha256.txt'
    original = manifest.read_bytes()
    for changed in (original + original.splitlines(keepends=True)[0], original.replace(b'  ', b'\t'),
                    original.replace(b'\n', b'\r\n'), b'\xef\xbb\xbf' + original):
        manifest.write_bytes(changed)
        with pytest.raises(AgentBomError):
            verify_bag(directory, tagmanifest_sha256=pin)
