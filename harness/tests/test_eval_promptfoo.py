from copy import deepcopy
from itertools import product
import json
import os
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_import import import_observations
from aau_harness.eval_promptfoo import FILES, _read, create_promptfoo_pack, promptfoo_payloads, verify_promptfoo_pack
from aau_harness.promptfoo_demo import example_inputs


def convert(plan, source):
    raw = rendered(plan)
    return promptfoo_payloads(raw, rendered(source), plan_sha256=digest(raw))


def test_pinned_upstream_fixture_keeps_assertion_failures_and_column_identity():
    raw = (Path(__file__).parent / 'fixtures/promptfoo/sample-export-0.118.10.json').read_bytes()
    assert digest(raw) == '60f4c9f191453cbc3ddaa95474828c48734d34f31eaee9e110f27970fe22a9e7'
    source = json.loads(raw)
    plan = {'plan_version': 'aau-promptfoo-observation-plan/1.0', 'source_label': 'Public upstream export, not our execution',
            'test_map': [{'test_index': i, 'scenario_id': f'riddle-{i}'} for i in range(2)],
            'columns': [{'prompt_index': i, 'prompt_id': p['id'], 'provider_id': p['provider']}
                        for i, p in enumerate(source['results']['prompts'])],
            'selected_prompt_index': 0, 'metrics': {'quality': {'field': 'score'}, 'passed': {'field': 'success'}}}
    for column, expected in ((0, [0.5, 2 / 3]), (1, [0.75, 2 / 3])):
        plan['selected_prompt_index'] = column
        report, files = promptfoo_payloads(rendered(plan), raw, plan_sha256=digest(rendered(plan)))
        assert report['declared_promptfoo_version'] == '0.118.10'
        assert report['validated_row_count'] == 4 and report['projected_row_count'] == 2
        assert report['source_outcomes'] == {'successes': 0, 'failures': 4, 'errors': 0}
        evaluation = json.loads(files['evaluation.json'])
        assert [r['metrics']['quality'] for r in evaluation['results']] == expected
        assert [r['metrics']['passed'] for r in evaluation['results']] == [0, 0]
        assert files['source.json'] == raw
        for origin in report['row_origins']:
            row = source['results']['results'][int(origin['source_pointer'].split('/')[-1])]
            assert row['testIdx'] == origin['test_index'] and row['promptIdx'] == column


def test_raw_retention_null_is_not_zero_and_no_operating_context_is_invented(tmp_path):
    plan, source = example_inputs()
    before = deepcopy((plan, source))
    raw_plan, raw_source = b' ' + rendered(plan), b'\xef\xbb\xbf' + rendered(source).replace(b'\n', b'\r\n')
    pin = digest(raw_plan)
    folder = tmp_path / 'pack'
    report = create_promptfoo_pack(raw_plan, raw_source, folder, plan_sha256=pin)
    assert (plan, source) == before
    assert report == verify_promptfoo_pack(folder, plan_sha256=pin, evaluation_path=folder / 'evaluation.json')
    assert (folder / 'source.json').read_bytes() == raw_source and (folder / 'plan.json').read_bytes() == raw_plan
    assert set(p.name for p in folder.iterdir()) == FILES
    evaluation = json.loads((folder / 'evaluation.json').read_bytes())
    assert evaluation == import_observations(json.loads((folder / 'recording.json').read_bytes()))
    assert 'evaluation_context' not in evaluation
    rows = {r['scenario_id']: r for r in evaluation['results']}
    assert rows['delegation']['metrics'] == {'quality': 0.9, 'passed': 0, 'authorization': 0}
    assert 'authorization' not in rows['unmeasured']['metrics']
    assert all(not {'cost_usd', 'latency_s', 'n_api_calls'} & r.keys() for r in evaluation['results'])
    assert len(report['unprojected_columns']) == 1
    with pytest.raises(AgentBomError, match='overwrite'):
        create_promptfoo_pack(raw_plan, raw_source, folder, plan_sha256=pin)


def change(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


@pytest.mark.parametrize('path,value', [
    (('results', 'version'), True), (('results', 'version'), 2), (('metadata', 'promptfooVersion'), None),
    (('config', 'evaluateOptions', 'repeat'), 2), (('config', 'evaluateOptions', 'repeat'), True),
    (('runtimeOptions',), {'repeat': 2}), (('results', 'stats', 'successes'), 6), (('results', 'stats', 'errors'), False),
    (('results', 'prompts', 0, 'id'), 'wrong'), (('results', 'prompts', 0, 'provider'), 'wrong'),
    (('results', 'results', 0, 'testIdx'), True), (('results', 'results', 0, 'testIdx'), '0'),
    (('results', 'results', 0, 'testIdx'), 3), (('results', 'results', 0, 'promptIdx'), -1),
    (('results', 'results', 0, 'promptId'), 'wrong'), (('results', 'results', 0, 'provider'), {'id': 'wrong'}),
    (('results', 'results', 0, 'failureReason'), 2), (('results', 'results', 0, 'failureReason'), True),
    (('results', 'results', 0, 'failureReason'), 9), (('results', 'results', 0, 'success'), False),
    (('results', 'results', 0, 'success'), 1), (('results', 'results', 0, 'error'), 'ambiguous error'),
    (('results', 'results', 0, 'response'), {'error': 'provider error'}),
    (('results', 'results', 0, 'score'), '1'), (('results', 'results', 0, 'score'), True),
    (('results', 'results', 0, 'score'), 10**16), (('results', 'results', 0, 'gradingResult'), {'pass': True, 'score': 0}),
    (('results', 'results', 3, 'gradingResult'), None), (('results', 'results', 3, 'failureReason'), 0),
    (('results', 'results', 0, 'vars'), {'__repeatIndex': 1}), (('results', 'results', 0, 'repeatIndex'), True),
    (('results', 'results', 0, 'namedScores'), {'bad': '1'}), (('results', 'results', 0, 'id'), 'constructed-0-1'),
])
def test_invalid_or_ambiguous_source_states_rejected_even_in_unselected_column(path, value):
    plan, source = example_inputs()
    change(source, path, value)
    with pytest.raises(AgentBomError):
        convert(plan, source)


@pytest.mark.parametrize('path,value', [
    (('plan_version',), 'bad'), (('source_label',), ''), (('extra',), 1), (('test_map',), []), (('columns',), []),
    (('test_map', 0, 'test_index'), False), (('test_map', 0, 'test_index'), 1),
    (('test_map', 0, 'scenario_id'), 'delegation'), (('columns', 0, 'prompt_index'), 1),
    (('columns', 0, 'provider_id'), None), (('selected_prompt_index',), True), (('selected_prompt_index',), 2),
    (('metrics',), {}), (('metrics', 'quality'), {'field': 'response'}),
    (('metrics', 'authorization'), {'field': 'namedScores'}), (('metrics', 'quality'), {'field': 'success'}),
])
def test_plan_is_closed_and_requires_explicit_unique_mappings(path, value):
    plan, source = example_inputs()
    change(plan, path, value)
    with pytest.raises(AgentBomError):
        convert(plan, source)


@pytest.mark.parametrize('defect', ['missing', 'extra', 'duplicate', 'missing-column'])
def test_no_partial_or_duplicated_census(defect):
    plan, source = example_inputs()
    rows = source['results']['results']
    if defect == 'missing':
        rows.pop()
    elif defect == 'extra':
        rows.append(deepcopy(rows[0]))
    elif defect == 'duplicate':
        rows[-1] = deepcopy(rows[0])
    else:
        source['results']['prompts'].pop()
    with pytest.raises(AgentBomError):
        convert(plan, source)


def test_all_64_success_failure_patterns_obey_selected_column_not_aggregate():
    for outcomes in product((False, True), repeat=6):
        plan, source = example_inputs()
        for row, passed in zip(source['results']['results'], outcomes):
            row.update(success=passed, failureReason=0 if passed else 1, score=int(passed), error=None,
                       gradingResult={'pass': passed, 'score': int(passed)})
        source['results']['stats'] = {'successes': sum(outcomes), 'failures': 6 - sum(outcomes), 'errors': 0}
        source['results']['prompts'][1]['metrics'] = {'score': 99999}  # Never used for projection.
        report, files = convert(plan, source)
        rows = {r['scenario_id']: r['metrics']['passed'] for r in json.loads(files['evaluation.json'])['results']}
        assert rows == {name: int(outcomes[i * 2 + 1]) for i, name in enumerate(('routing', 'delegation', 'unmeasured'))}
        assert report['source_outcomes']['failures'] == 6 - sum(outcomes)


def test_missing_named_score_and_null_match_but_unknown_non_numeric_is_not_silently_dropped():
    plan, source = example_inputs()
    report, first = convert(plan, source)
    del source['results']['results'][5]['namedScores']['authorization']
    _, second = convert(plan, source)
    assert first['evaluation.json'] == second['evaluation.json']
    plan['metrics']['absent'] = {'field': 'namedScores', 'name': 'never-measured'}
    report, _ = convert(plan, source)
    assert report['unreported_metrics'] == ['absent']
    source['results']['results'][5]['namedScores']['unmapped'] = False
    with pytest.raises(AgentBomError):
        convert(plan, source)


@pytest.mark.parametrize('name', sorted(FILES))
def test_each_file_tamper_and_supplier_rehashed_manifest_rejected(tmp_path, name):
    plan, source = example_inputs()
    raw = rendered(plan)
    folder = tmp_path / 'pack'
    create_promptfoo_pack(raw, rendered(source), folder, plan_sha256=digest(raw))
    with (folder / name).open('ab') as stream:
        stream.write(b' ')
    if name != 'manifest.json':
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        manifest['files'][name] = digest((folder / name).read_bytes())
        (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_promptfoo_pack(folder, plan_sha256=digest(raw))


@pytest.mark.parametrize('raw', [b'[]', b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":1e999}', b'\xff', b'[' * 2000,
                                  b' ' * (MAX_JSON_BYTES + 1)])
def test_malformed_source_is_rejected_without_output(tmp_path, raw):
    plan, _ = example_inputs()
    with pytest.raises(AgentBomError):
        create_promptfoo_pack(rendered(plan), raw, tmp_path / 'bad', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'bad').exists()


def test_verification_pin_downstream_binding_and_closed_inventory(tmp_path):
    plan, source = example_inputs()
    raw = rendered(plan)
    folder = tmp_path / 'pack'
    create_promptfoo_pack(raw, rendered(source), folder, plan_sha256=digest(raw))
    with pytest.raises(AgentBomError):
        verify_promptfoo_pack(folder, plan_sha256='0' * 64)
    other = tmp_path / 'other.json'
    other.write_text('{}')
    with pytest.raises(AgentBomError, match='downstream'):
        verify_promptfoo_pack(folder, plan_sha256=digest(raw), evaluation_path=other)
    (folder / 'extra').write_text('x')
    with pytest.raises(AgentBomError, match='six files'):
        verify_promptfoo_pack(folder, plan_sha256=digest(raw))
    (folder / 'extra').unlink()
    (folder / 'recording.json').unlink()
    with pytest.raises(AgentBomError, match='six files'):
        verify_promptfoo_pack(folder, plan_sha256=digest(raw))


def test_nonregular_files_and_no_execution(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('input code or network executed')
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)
    monkeypatch.setattr('urllib.request.urlopen', forbidden)
    plan, source = example_inputs()
    source['config']['providers'] = ['file:///do-not-open.py', 'https://do-not-fetch.invalid/']
    source['config']['tests'] = [{'assert': [{'type': 'python', 'value': 'raise RuntimeError()'}]}]
    source['blobAssets'] = [{'url': 'https://do-not-fetch.invalid/', 'data': 'not-executed'}]
    convert(plan, source)
    target = tmp_path / 'target'
    target.write_text('{}')
    link = tmp_path / 'link'
    link.symlink_to(target)
    with pytest.raises(AgentBomError):
        _read(link)
    if hasattr(os, 'mkfifo'):
        fifo = tmp_path / 'fifo'
        os.mkfifo(fifo)
        with pytest.raises(AgentBomError):
            _read(fifo)


def test_cli_demo_and_malformed_sources(tmp_path):
    folder = tmp_path / 'demo'
    assert main(['promptfoo-eval', 'demo', '--out', str(folder)]) == 0
    assert main(['promptfoo-eval', 'demo', '--out', str(folder)]) == 2
    pin = digest((folder / 'plan.json').read_bytes())
    assert main(['promptfoo-eval', 'verify', str(folder / 'converted'), '--plan-sha256', pin]) == 0
    assert main(['promptfoo-eval', 'verify', str(folder / 'converted'), '--plan-sha256', '0' * 64]) == 2
    for name in ('missing-row', 'execution-error'):
        assert main(['promptfoo-eval', 'create', str(folder / 'plan.json'), str(folder / f'{name}.json'),
                     '--plan-sha256', pin, '--out', str(tmp_path / name)]) == 2
        assert not (tmp_path / name).exists()


def test_noncontiguous_test_indices_and_source_row_reordering_do_not_reassign_cases():
    plan, source = example_inputs()
    _, before = convert(plan, source)
    for item in plan['test_map']:
        item['test_index'] = 10 + item['test_index'] * 2
    for row in source['results']['results']:
        row['testIdx'] = 10 + row['testIdx'] * 2
    source['results']['results'].reverse()
    report, after = convert(plan, source)
    # Recording/source provenance changes, but case-level values and summaries do not.
    left, right = json.loads(before['evaluation.json']), json.loads(after['evaluation.json'])
    left.pop('provenance')
    right.pop('provenance')
    assert left == right
    for origin in report['row_origins']:
        assert source['results']['results'][int(origin['source_pointer'].split('/')[-1])]['testIdx'] == origin['test_index']


def test_all_mapped_metrics_missing_is_not_a_successful_empty_evaluation():
    plan, source = example_inputs()
    plan['metrics'] = {'unknown': {'field': 'namedScores', 'name': 'not-recorded'}}
    with pytest.raises(AgentBomError, match='at least one measured metric'):
        convert(plan, source)


def test_directory_and_packet_member_symlinks_are_rejected(tmp_path):
    plan, source = example_inputs()
    folder = tmp_path / 'pack'
    pin = digest(rendered(plan))
    create_promptfoo_pack(rendered(plan), rendered(source), folder, plan_sha256=pin)
    linked = tmp_path / 'linked'
    linked.symlink_to(folder, target_is_directory=True)
    with pytest.raises(AgentBomError, match='real directory'):
        verify_promptfoo_pack(linked, plan_sha256=pin)
    copied = tmp_path / 'copied-source.json'
    (folder / 'source.json').rename(copied)
    (folder / 'source.json').symlink_to(copied)
    with pytest.raises(AgentBomError, match='non-symlink'):
        verify_promptfoo_pack(folder, plan_sha256=pin)
