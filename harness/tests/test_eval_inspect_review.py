from copy import deepcopy
from itertools import product
import json
import os
from pathlib import Path
import shutil

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_inspect import verify_inspect_pack
from aau_harness.eval_inspect_review import create_handoff, handoff_payloads, verify_handoff
from aau_harness.eval_pack import verify_pack
from aau_harness.inspect_review_demo import example_inputs


def payloads(variant='repaired'):
    request, baseline, candidate = example_inputs()[variant]
    raws = tuple(map(rendered, (request, baseline, candidate)))
    return raws, digest(raws[0])


def test_three_outcomes_preserve_missing_context_and_operating_measurements(tmp_path):
    for variant, status, count in [('unsafe', 'constraints_not_met', 29), ('repaired', 'constraints_met', 29),
                                   ('unknown-budget', 'constraints_not_verified', 32)]:
        raws, pin = payloads(variant)
        folder = tmp_path / variant
        report = create_handoff(*raws, folder, request_sha256=pin)
        assert report == verify_handoff(folder, request_sha256=pin)
        assert report['status'] == status
        assert report['declared_context']['status'] == 'unavailable'
        assert len([p for p in folder.rglob('*') if p.is_file()]) == count
        for side in ('baseline', 'candidate'):
            side_pin = digest((folder / side / 'plan.json').read_bytes())
            verify_inspect_pack(folder / side, plan_sha256=side_pin, evaluation_path=folder / f'review/{side}.json')
            operations = json.loads((folder / f'review/{side}-operations.json').read_bytes())
            assert operations['overall']['cost']['total_usd'] is None
            assert 'evaluation_context' not in json.loads((folder / f'review/{side}.json').read_bytes())
        assert verify_pack(folder / 'review', require_recordings=True, require_diagnostics=True)['status'] == status
        if variant == 'unknown-budget':
            assert report['policy_status'] == 'constraints_met'
            assert report['candidate_budget_status'] == 'constraints_not_verified'
            verify_pack(folder / 'review', require_budget=True)


def test_exact_request_and_baseline_bytes_are_pinned_but_candidate_is_not_fixed(tmp_path):
    request, baseline, candidate = example_inputs()['repaired']
    baseline_raw = b'\xef\xbb\xbf' + rendered(baseline).replace(b'\n', b'\r\n')
    request['baseline_source_sha256'] = digest(baseline_raw)
    request_raw = b' ' + rendered(request)
    candidate_raw = b' ' + rendered(candidate)
    pin = digest(request_raw)
    report = create_handoff(request_raw, baseline_raw, candidate_raw, tmp_path / 'pack', request_sha256=pin)
    assert report['status'] == 'constraints_met'
    for name, raw in [('request.json', request_raw), ('baseline/source.json', baseline_raw), ('candidate/source.json', candidate_raw)]:
        assert (tmp_path / 'pack' / name).read_bytes() == raw
    for side in ('baseline', 'candidate'):
        assert (tmp_path / 'pack' / side / 'plan.json').read_bytes() == rendered(request[side + '_plan'])
    with pytest.raises(AgentBomError, match='baseline bytes'):
        handoff_payloads(request_raw, baseline_raw + b' ', candidate_raw, request_sha256=pin)
    with pytest.raises(AgentBomError, match='request byte pin'):
        handoff_payloads(request_raw + b' ', baseline_raw, candidate_raw, request_sha256=pin)
    candidate['samples'][0]['scores']['checks']['value']['authorized'] = 0
    changed, _ = handoff_payloads(request_raw, baseline_raw, rendered(candidate), request_sha256=pin)
    assert changed['status'] == 'constraints_not_met'


def test_16_pattern_authorization_oracle_cannot_be_compensated_by_completion():
    request, baseline, candidate = example_inputs()['repaired']
    original = deepcopy((request, baseline, candidate))
    for values in product((0, 1), repeat=4):
        changed = deepcopy(candidate)
        for row, value in zip(changed['samples'], values):
            row['scores']['checks']['value']['authorized'] = value
        report, _ = handoff_payloads(*map(rendered, (request, baseline, changed)), request_sha256=digest(rendered(request)))
        assert (report['status'] == 'constraints_met') == all(values)
    assert (request, baseline, candidate) == original


@pytest.mark.parametrize('member', sorted(handoff_payloads(*payloads('unknown-budget')[0], request_sha256=payloads('unknown-budget')[1])[1]))
def test_every_member_is_recomputed_even_after_manifest_rehash(tmp_path, member):
    raws, pin = payloads('unknown-budget')
    folder = tmp_path / 'pack'
    create_handoff(*raws, folder, request_sha256=pin)
    path = folder / member
    with path.open('ab') as stream:
        stream.write(b' ')
    if member != 'manifest.json':
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        manifest['files'][member] = digest(path.read_bytes())
        (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_handoff(folder, request_sha256=pin)


@pytest.mark.parametrize('replacement', ['baseline', 'candidate', 'review'])
def test_individually_valid_but_unrelated_nested_components_cannot_replace_full_chain(tmp_path, replacement):
    raws, pin = payloads()
    original, alternate = tmp_path / 'original', tmp_path / 'alternate'
    create_handoff(*raws, original, request_sha256=pin)
    request, baseline, candidate = example_inputs()['repaired']
    request['baseline_plan']['source_label'] = 'Different original mapping'
    request['candidate_plan']['source_label'] = 'Different candidate mapping'
    other_raws = tuple(map(rendered, (request, baseline, candidate)))
    create_handoff(*other_raws, alternate, request_sha256=digest(other_raws[0]))
    for path in (alternate / replacement).iterdir():
        shutil.copyfile(path, original / replacement / path.name)
    if replacement == 'review':
        verify_pack(original / replacement, require_recordings=True, require_diagnostics=True)
    else:
        verify_inspect_pack(original / replacement, plan_sha256=digest((original / replacement / 'plan.json').read_bytes()))
    manifest = json.loads((original / 'manifest.json').read_bytes())
    for name in manifest['files']:
        manifest['files'][name] = digest((original / name).read_bytes())
    (original / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match='does not recompute'):
        verify_handoff(original, request_sha256=pin)


@pytest.mark.parametrize('change', ['policy', 'diagnostics', 'mapping', 'budget'])
def test_receiver_controls_cannot_change_under_original_pin(tmp_path, change):
    request, baseline, candidate = example_inputs()['unknown-budget']
    old_pin = digest(rendered(request))
    if change == 'policy':
        request['policy']['metrics'][1]['candidate_observation_limit'] = 0
    elif change == 'diagnostics':
        request['diagnostics']['draw_sizes'] = [1]
    elif change == 'mapping':
        request['candidate_plan']['metrics']['completion']['labels']['I'] = 1
    else:
        request['operating_budget'] = None
    with pytest.raises(AgentBomError, match='request byte pin'):
        create_handoff(*map(rendered, (request, baseline, candidate)), tmp_path / 'bad', request_sha256=old_pin)
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('defect', ['version', 'extra', 'no-diagnostics', 'bad-budget', 'bad-baseline-pin',
    'wrong-baseline', 'bad-policy', 'bad-mapping', 'candidate-error', 'candidate-hole', 'missing-metric', 'candidate-edit'])
def test_invalid_request_and_out_of_subset_sources_never_create_output(tmp_path, defect):
    request, baseline, candidate = example_inputs()['repaired']
    if defect == 'version':
        request['request_version'] += '-unknown'
    elif defect == 'extra':
        request['override'] = True
    elif defect == 'no-diagnostics':
        request['diagnostics'] = None
    elif defect == 'bad-budget':
        request['operating_budget'] = False
    elif defect == 'bad-baseline-pin':
        request['baseline_source_sha256'] = 'not-a-hash'
    elif defect == 'wrong-baseline':
        baseline['samples'][0]['scores']['match']['value'] = 'C'
    elif defect == 'bad-policy':
        request['policy']['minimum_repeats'] = True
    elif defect == 'bad-mapping':
        request['candidate_plan']['metrics']['completion']['encoding'] = 'guess'
    elif defect == 'candidate-error':
        candidate['samples'][0]['error'] = {'message': 'Constructed'}
    elif defect == 'candidate-hole':
        candidate['samples'].pop()
    elif defect == 'missing-metric':
        candidate['samples'][0]['scores']['checks']['value']['authorized'] = None
    else:
        candidate['samples'][0]['scores']['match']['history'] = [{'value': 'I'}]
    with pytest.raises(AgentBomError):
        create_handoff(*map(rendered, (request, baseline, candidate)), tmp_path / 'bad', request_sha256=digest(rendered(request)))
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('defect', ['root-extra', 'nested-extra', 'missing', 'extra-directory', 'root-link',
                                  'group-link', 'member-link', 'fifo', 'oversized'])
def test_capture_rejects_incomplete_or_unsafe_inventory(tmp_path, defect):
    raws, pin = payloads()
    folder = tmp_path / 'pack'
    create_handoff(*raws, folder, request_sha256=pin)
    if defect == 'root-extra':
        (folder / 'extra').write_text('extra')
    elif defect == 'nested-extra':
        (folder / 'review/extra').write_text('extra')
    elif defect == 'missing':
        (folder / 'manifest.json').unlink()
    elif defect == 'extra-directory':
        (folder / 'review/empty').mkdir()
    elif defect == 'oversized':
        (folder / 'handoff.json').write_bytes(b'x' * (MAX_JSON_BYTES + 1))
    elif defect == 'fifo':
        if not hasattr(os, 'mkfifo'):
            pytest.skip('FIFO unavailable')
        (folder / 'handoff.json').unlink()
        os.mkfifo(folder / 'handoff.json')
    else:
        target = folder if defect == 'root-link' else folder / ('candidate' if defect == 'group-link' else 'candidate/source.json')
        moved = tmp_path / 'moved'
        target.rename(moved)
        target.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises(AgentBomError):
        verify_handoff(folder, request_sha256=pin)


@pytest.mark.parametrize('raw', [b'{}', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'[' * 2000,
                               b'\xff', b'x' * (MAX_JSON_BYTES + 1)])
def test_request_rejects_malformed_or_nonfinite_bytes(raw):
    raws, _ = payloads()
    with pytest.raises(AgentBomError):
        handoff_payloads(raw, *raws[1:], request_sha256=digest(raw))


def test_cli_demo_exits_and_overwrite_refusal(tmp_path):
    root = tmp_path / 'demo'
    assert main(['inspect-review', 'demo', '--out', str(root)]) == 0
    assert main(['inspect-review', 'demo', '--out', str(root)]) == 2
    for name, expected in [('unsafe', 1), ('repaired', 0), ('unknown-budget', 1)]:
        pin = digest((root / name / 'request.json').read_bytes())
        assert main(['inspect-review', 'verify', str(root / name), '--request-sha256', pin]) == expected
    pack = root / 'repaired'
    pin = digest((pack / 'request.json').read_bytes())
    args = ['inspect-review', 'create', str(pack / 'request.json'), str(pack / 'baseline/source.json'),
            str(pack / 'candidate/source.json'), '--request-sha256', pin, '--out', str(tmp_path / 'copy')]
    assert main(args) == 0 and main(args) == 2
    assert main(['inspect-review', 'verify', str(pack), '--request-sha256', '0' * 64]) == 2


def test_upstream_mock_fixture_can_complete_an_end_to_end_handoff_without_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution attempted')
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)
    raw = (Path(__file__).parent / 'fixtures/inspect-ai/scored_0.3.100.json').read_bytes()
    request, _, _ = example_inputs()['repaired']
    request['baseline_source_sha256'] = digest(raw)
    mapping = {'plan_version': 'aau-inspect-observation-plan/1.0', 'source_label': 'upstream mock example',
               'sample_map': [{'sample_id': 1, 'scenario_id': 'mock-addition'}], 'n_repeats': 1,
               'metrics': {'completion': {'scorer': 'graded', 'value_key': None, 'encoding': 'number'}}}
    request['baseline_plan'] = request['candidate_plan'] = mapping
    request['policy']['scenario_ids'] = ['mock-addition']
    request['policy']['minimum_repeats'] = 1
    request['policy']['metrics'] = request['policy']['metrics'][:1]
    request['diagnostics']['criteria'] = request['diagnostics']['criteria'][:1]
    request['diagnostics']['draw_sizes'] = [1]
    report, files = handoff_payloads(rendered(request), raw, raw, request_sha256=digest(rendered(request)))
    assert report['status'] == 'constraints_met'
    assert files['baseline/source.json'] == files['candidate/source.json'] == raw
    assert report['sources']['baseline']['declared_inspect_version'] == '0.3.100'
