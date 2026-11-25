from copy import deepcopy
from itertools import product
import json
import os
import shutil

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_pack import verify_pack
from aau_harness.eval_promptfoo import verify_promptfoo_pack
from aau_harness.promptfoo_review import create_handoff, handoff_payloads, verify_handoff
from aau_harness.promptfoo_review_demo import example_inputs


def inputs(variant='repaired'):
    raws = tuple(map(rendered, example_inputs()[variant]))
    return raws, digest(raws[0])


@pytest.mark.parametrize('variant,status,count', [('unsafe', 'constraints_not_met', 29),
    ('repaired', 'constraints_met', 29), ('unknown-budget', 'constraints_not_verified', 32)])
def test_full_chain_replays_without_inventing_context_or_operating_data(tmp_path, variant, status, count):
    raws, pin = inputs(variant)
    directory = tmp_path / variant
    report = create_handoff(*raws, directory, request_sha256=pin)
    assert verify_handoff(directory, request_sha256=pin) == report
    assert report['status'] == status
    assert report['declared_context']['status'] == 'unavailable'
    assert len([p for p in directory.rglob('*') if p.is_file()]) == count
    for side, selected in (('baseline', 0), ('candidate', 1)):
        assert report['sources'][side]['selected_column']['prompt_index'] == selected
        assert report['sources'][side]['validated_row_count'] == 6
        assert report['sources'][side]['projected_row_count'] == 3
        nested = directory / side
        verify_promptfoo_pack(nested, plan_sha256=digest((nested / 'plan.json').read_bytes()),
                              evaluation_path=directory / f'review/{side}.json')
        evaluation = json.loads((directory / f'review/{side}.json').read_bytes())
        assert 'evaluation_context' not in evaluation
        assert all(not {'cost_usd', 'latency_s', 'n_api_calls'} & set(row) for row in evaluation['results'])
    assert verify_pack(directory / 'review', require_recordings=True, require_diagnostics=True)['status'] == status
    if variant == 'unknown-budget':
        assert report['policy_status'] == 'constraints_met'
        assert report['candidate_budget_status'] == 'constraints_not_verified'


def test_pins_bind_original_bytes_and_all_controls_but_candidate_is_assessed(tmp_path):
    request, baseline, candidate = example_inputs()['repaired']
    baseline_raw = b'\xef\xbb\xbf' + rendered(baseline).replace(b'\n', b'\r\n')
    request['baseline_source_sha256'] = digest(baseline_raw)
    request_raw, candidate_raw = b' ' + rendered(request), b' ' + rendered(candidate)
    pin = digest(request_raw)
    create_handoff(request_raw, baseline_raw, candidate_raw, tmp_path / 'pack', request_sha256=pin)
    for name, raw in [('request.json', request_raw), ('baseline/source.json', baseline_raw), ('candidate/source.json', candidate_raw)]:
        assert (tmp_path / 'pack' / name).read_bytes() == raw
    assert (tmp_path / 'pack/candidate/plan.json').read_bytes() == rendered(request['candidate_plan'])
    with pytest.raises(AgentBomError, match='baseline bytes'):
        handoff_payloads(request_raw, baseline_raw + b' ', candidate_raw, request_sha256=pin)
    with pytest.raises(AgentBomError, match='request byte pin'):
        handoff_payloads(request_raw + b' ', baseline_raw, candidate_raw, request_sha256=pin)
    candidate['results']['results'][1]['namedScores']['authorization'] = 0
    report, _ = handoff_payloads(request_raw, baseline_raw, rendered(candidate), request_sha256=pin)
    assert report['status'] == 'constraints_not_met'


def test_selected_column_authorization_oracle_cannot_be_rescued_by_other_column():
    request, baseline, candidate = example_inputs()['repaired']
    for values in product((0, 1), repeat=3):
        changed = deepcopy(candidate)
        for row, value in zip(changed['results']['results'][1::2], values):
            row['namedScores']['authorization'] = value
        report, _ = handoff_payloads(*map(rendered, (request, baseline, changed)), request_sha256=digest(rendered(request)))
        assert (report['status'] == 'constraints_met') == all(values)
    assert all(r['namedScores']['authorization'] == 1 for r in candidate['results']['results'])


@pytest.mark.parametrize('member', sorted(handoff_payloads(*inputs('unknown-budget')[0], request_sha256=inputs('unknown-budget')[1])[1]))
def test_every_member_recomputed_even_with_rehashed_manifest(tmp_path, member):
    raws, pin = inputs('unknown-budget')
    directory = tmp_path / 'pack'
    create_handoff(*raws, directory, request_sha256=pin)
    path = directory / member
    with path.open('ab') as stream:
        stream.write(b' ')
    if member != 'manifest.json':
        manifest = json.loads((directory / 'manifest.json').read_bytes())
        manifest['files'][member] = digest(path.read_bytes())
        (directory / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_handoff(directory, request_sha256=pin)


@pytest.mark.parametrize('side', ['baseline', 'candidate', 'review'])
def test_valid_unrelated_nested_packs_cannot_replace_full_chain(tmp_path, side):
    raws, pin = inputs()
    original, alternate = tmp_path / 'original', tmp_path / 'alternate'
    create_handoff(*raws, original, request_sha256=pin)
    request, baseline, candidate = example_inputs()['repaired']
    for key in ('baseline_plan', 'candidate_plan'):
        request[key]['source_label'] = 'An independently valid but unrelated nested source label'
    changed = tuple(map(rendered, (request, baseline, candidate)))
    create_handoff(*changed, alternate, request_sha256=digest(changed[0]))
    for path in (alternate / side).iterdir():
        shutil.copyfile(path, original / side / path.name)
    if side == 'review':
        verify_pack(original / side, require_recordings=True, require_diagnostics=True)
    else:
        verify_promptfoo_pack(original / side, plan_sha256=digest((original / side / 'plan.json').read_bytes()))
    manifest = json.loads((original / 'manifest.json').read_bytes())
    for name in manifest['files']:
        manifest['files'][name] = digest((original / name).read_bytes())
    (original / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match='does not recompute'):
        verify_handoff(original, request_sha256=pin)


@pytest.mark.parametrize('control', ['column', 'mapping', 'policy', 'diagnostics', 'budget'])
def test_receiver_controls_cannot_be_changed_under_original_pin(tmp_path, control):
    request, baseline, candidate = example_inputs()['unknown-budget']
    pin = digest(rendered(request))
    if control == 'column':
        request['candidate_plan']['selected_prompt_index'] = 0
    elif control == 'mapping':
        request['candidate_plan']['metrics']['authorization']['name'] = 'different'
    elif control == 'policy':
        request['policy']['metrics'][1]['candidate_observation_limit'] = 0
    elif control == 'diagnostics':
        request['diagnostics']['criteria'][1]['limit'] = 0
    else:
        request['operating_budget'] = None
    with pytest.raises(AgentBomError, match='request byte pin'):
        create_handoff(*map(rendered, (request, baseline, candidate)), tmp_path / 'bad', request_sha256=pin)
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('defect', ['version', 'extra', 'diagnostics', 'budget', 'policy', 'mapping', 'baseline',
    'unselected-error', 'hole', 'duplicate', 'repeat', 'missing-metric', 'identity'])
def test_invalid_requests_and_rejected_sources_never_write_handoff(tmp_path, defect):
    request, baseline, candidate = example_inputs()['repaired']
    if defect == 'version':
        request['request_version'] = 'unknown'
    elif defect == 'extra':
        request['override'] = True
    elif defect in ('diagnostics', 'budget', 'policy'):
        request['operating_budget' if defect == 'budget' else defect] = False
    elif defect == 'mapping':
        request['candidate_plan']['metrics'] = {}
    elif defect == 'baseline':
        baseline['results']['results'][0]['score'] = 0
    elif defect == 'unselected-error':
        candidate['results']['results'][0].update(failureReason=2, success=False, error='synthetic')
    elif defect == 'hole':
        candidate['results']['results'].pop()
    elif defect == 'duplicate':
        candidate['results']['results'][-1] = deepcopy(candidate['results']['results'][0])
    elif defect == 'repeat':
        candidate['config']['evaluateOptions']['repeat'] = 2
    elif defect == 'missing-metric':
        candidate['results']['results'][1]['namedScores']['authorization'] = None
    else:
        candidate['results']['results'][0]['provider']['id'] = 'wrong'
    with pytest.raises(AgentBomError):
        create_handoff(*map(rendered, (request, baseline, candidate)), tmp_path / 'bad', request_sha256=digest(rendered(request)))
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('defect', ['extra', 'missing', 'extra-directory', 'member-link', 'root-link', 'fifo', 'oversized'])
def test_unsafe_or_incomplete_capture_rejected(tmp_path, defect):
    raws, pin = inputs()
    directory = tmp_path / 'pack'
    create_handoff(*raws, directory, request_sha256=pin)
    if defect == 'extra':
        (directory / 'review/extra').write_text('x')
    elif defect == 'missing':
        (directory / 'handoff.json').unlink()
    elif defect == 'extra-directory':
        (directory / 'review/empty').mkdir()
    elif defect == 'oversized':
        (directory / 'handoff.json').write_bytes(b'x' * (MAX_JSON_BYTES + 1))
    elif defect == 'fifo':
        if not hasattr(os, 'mkfifo'):
            pytest.skip('FIFO unavailable')
        (directory / 'handoff.json').unlink()
        os.mkfifo(directory / 'handoff.json')
    else:
        target = directory if defect == 'root-link' else directory / 'candidate/source.json'
        moved = tmp_path / 'moved'
        target.rename(moved)
        target.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises(AgentBomError):
        verify_handoff(directory, request_sha256=pin)


@pytest.mark.parametrize('raw', [b'{}', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'[' * 2000,
                               b'\xff', b'x' * (MAX_JSON_BYTES + 1)])
def test_invalid_request_bytes_rejected(raw):
    raws, _ = inputs()
    with pytest.raises(AgentBomError):
        handoff_payloads(raw, *raws[1:], request_sha256=digest(raw))


def test_cli_demo_and_copy_with_expected_exits(tmp_path):
    directory = tmp_path / 'demo'
    assert main(['promptfoo-review', 'demo', '--out', str(directory)]) == 0
    assert main(['promptfoo-review', 'demo', '--out', str(directory)]) == 2
    for name, expected in (('unsafe', 1), ('repaired', 0), ('unknown-budget', 1)):
        packet = directory / name
        pin = digest((packet / 'request.json').read_bytes())
        assert main(['promptfoo-review', 'verify', str(packet), '--request-sha256', pin]) == expected
    assert main(['promptfoo-review', 'verify', str(packet), '--request-sha256', '0' * 64]) == 2
    assert main(['promptfoo-review', 'create', str(packet / 'request.json'), str(packet / 'baseline/source.json'),
                 str(packet / 'candidate/source.json'), '--request-sha256', pin, '--out', str(tmp_path / 'copy')]) == 1
