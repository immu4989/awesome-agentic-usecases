from copy import deepcopy
import json
from itertools import product
import os
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_import import import_observations
from aau_harness.eval_inspect import FILES, _read, create_inspect_pack, inspect_payloads, verify_inspect_pack


def inputs():
    plan = {'plan_version': 'aau-inspect-observation-plan/1.0', 'source_label': 'constructed interoperability test',
            'sample_map': [{'sample_id': 1, 'scenario_id': 'self-service'},
                           {'sample_id': '1', 'scenario_id': 'assisted'}], 'n_repeats': 2,
            'metrics': {'completion': {'scorer': 'match', 'value_key': None, 'encoding': 'labels',
                                       'labels': {'C': 1, 'I': 0, 'N': None}},
                        'authorization': {'scorer': 'checks', 'value_key': 'authorized', 'encoding': 'number'}}}
    source = {'version': 2, 'status': 'success', 'eval': {'config': {'epochs': 2},
              'dataset': {'sample_ids': [1, '1']}, 'packages': {'inspect_ai': 'constructed-example-not-an-execution'}},
              'results': {'total_samples': 4, 'completed_samples': 4},
              'samples': [{'id': identity, 'epoch': epoch, 'input': 'Constructed only', 'target': '',
                           'scores': {'match': {'value': label}, 'checks': {'value': {'authorized': auth}},
                                      'not-mapped': {'value': 1000}}}
                          for identity, epoch, label, auth in ((1, 1, 'C', 1), (1, 2, 'I', 1),
                                                               ('1', 1, 'C', None), ('1', 2, 'N', 0))]}
    return plan, source


def convert(plan, source):
    raw = rendered(plan)
    return inspect_payloads(raw, rendered(source), plan_sha256=digest(raw))


def test_typed_identity_epoch_mapping_raw_retention_and_missing_scores(tmp_path):
    plan, source = inputs()
    old_plan, old_source = deepcopy(plan), deepcopy(source)
    plan_raw = b' ' + rendered(plan)
    source_raw = b'\xef\xbb\xbf' + rendered(source).replace(b'\n', b'\r\n')
    pin = digest(plan_raw)
    report = create_inspect_pack(plan_raw, source_raw, tmp_path / 'pack', plan_sha256=pin)
    assert plan == old_plan and source == old_source
    assert (tmp_path / 'pack/source.json').read_bytes() == source_raw
    assert (tmp_path / 'pack/plan.json').read_bytes() == plan_raw
    assert set(p.name for p in (tmp_path / 'pack').iterdir()) == FILES
    assert report == verify_inspect_pack(tmp_path / 'pack', plan_sha256=pin,
                                         evaluation_path=tmp_path / 'pack/evaluation.json')
    assert report['unmapped_scorers'] == ['not-mapped']
    evaluation = json.loads((tmp_path / 'pack/evaluation.json').read_bytes())
    assert 'evaluation_context' not in evaluation
    by_key = {(r['scenario_id'], r['repeat']): r for r in evaluation['results']}
    assert by_key['self-service', 1]['metrics'] == {'completion': 0, 'authorization': 1}
    assert by_key['assisted', 0]['metrics'] == {'completion': 1}
    assert by_key['assisted', 1]['metrics'] == {'authorization': 0}
    assert all(not {'cost_usd', 'latency_s', 'n_api_calls'} & row.keys() for row in evaluation['results'])
    assert evaluation == import_observations(json.loads((tmp_path / 'pack/recording.json').read_bytes()))
    assert report['source_json_sha256'] == digest(source_raw)
    assert report['plan_sha256'] == pin


def test_official_mock_fixture_and_version_provenance():
    root = Path(__file__).parent / 'fixtures/inspect-ai'
    raw = (root / 'scored_0.3.100.json').read_bytes()
    assert digest(raw) == '2920eb09222718abb780ce7204d744d977594e801393e69767cbdf9bbc4ced7f'
    assert raw[-1:] == b'\n'
    assert digest(raw[:-1]) == '1ed213000785c874c25f46d8a3785934b7c81f5a9e9a8aa90c0de42b9404b5cf'
    plan = {'plan_version': 'aau-inspect-observation-plan/1.0', 'source_label': 'upstream mock test only',
            'sample_map': [{'sample_id': 1, 'scenario_id': 'mock-addition'}], 'n_repeats': 1,
            'metrics': {'completion': {'scorer': 'graded', 'value_key': None, 'encoding': 'number'}}}
    report, files = inspect_payloads(rendered(plan), raw, plan_sha256=digest(rendered(plan)))
    assert report['declared_inspect_version'] == '0.3.100'
    assert report['observation_count'] == 1
    assert json.loads(files['recording.json'])['observations'] == [
        {'scenario_id': 'mock-addition', 'repeat': 0, 'metrics': {'completion': 1}}]
    assert files['source.json'] == raw
    original_report, original_files = inspect_payloads(rendered(plan), raw[:-1], plan_sha256=digest(rendered(plan)))
    assert original_files['source.json'] == raw[:-1]
    assert original_report['source_json_sha256'] == '1ed213000785c874c25f46d8a3785934b7c81f5a9e9a8aa90c0de42b9404b5cf'
    assert original_files['evaluation.json'] == files['evaluation.json']
    assert json.loads(raw)['eval']['model'] == 'mockllm/model'


@pytest.mark.parametrize('defect', ['version', 'bool-version', 'started', 'cancelled', 'error-status',
    'no-samples', 'missing-row', 'duplicate-row', 'unknown-id', 'bool-id', 'object-id', 'epoch-zero',
    'epoch-extra', 'epoch-bool', 'epoch-string', 'total-count', 'completed-count', 'logged-count',
    'root-count', 'bool-count', 'epoch-count', 'dataset-ids', 'duplicate-dataset-ids', 'shards',
    'early-stopping', 'sample-error', 'retries', 'invalidation', 'limit', 'root-error', 'invalidated',
    'config-edits', 'log-edits', 'score-history', 'score-reason', 'unmapped-score-history',
    'no-version', 'no-config', 'no-results', 'bad-scores', 'score-without-value', 'score-not-object'])
def test_rejects_incomplete_or_out_of_subset_log_before_writing(tmp_path, defect):
    plan, source = inputs()
    first = source['samples'][0]
    if defect == 'version':
        source['version'] = 3
    elif defect == 'bool-version':
        source['version'] = True
    elif defect in ('started', 'cancelled', 'error-status'):
        source['status'] = 'error' if defect == 'error-status' else defect
    elif defect == 'no-samples':
        del source['samples']
    elif defect == 'missing-row':
        source['samples'].pop()
    elif defect == 'duplicate-row':
        source['samples'][-1] = deepcopy(first)
    elif defect.endswith('-id'):
        first['id'] = {'unknown-id': 'unknown', 'bool-id': True, 'object-id': {}}[defect]
    elif defect in ('epoch-zero', 'epoch-extra', 'epoch-bool', 'epoch-string'):
        first['epoch'] = {'epoch-zero': 0, 'epoch-extra': 3, 'epoch-bool': True, 'epoch-string': '1'}[defect]
    elif defect in ('total-count', 'completed-count', 'logged-count', 'bool-count'):
        key = {'total-count': 'total_samples', 'completed-count': 'completed_samples',
               'logged-count': 'logged_samples', 'bool-count': 'total_samples'}[defect]
        source['results'][key] = True if defect == 'bool-count' else 3
    elif defect == 'root-count':
        source['total_samples'] = 5
    elif defect == 'epoch-count':
        source['eval']['config']['epochs'] = 1
    elif defect in ('dataset-ids', 'duplicate-dataset-ids'):
        source['eval']['dataset']['sample_ids'] = [1, 'other'] if defect == 'dataset-ids' else [1, 1]
    elif defect == 'shards':
        source['eval']['shards'] = {}
    elif defect == 'early-stopping':
        source['results']['early_stopping'] = {}
    elif defect in ('sample-error', 'retries', 'invalidation', 'limit'):
        key = {'sample-error': 'error', 'retries': 'error_retries'}.get(defect, defect)
        first[key] = {'message': 'synthetic'}
    elif defect == 'root-error':
        source['error'] = {}
    elif defect == 'invalidated':
        source['invalidated'] = True
    elif defect in ('config-edits', 'log-edits'):
        source['config_updates' if defect == 'config-edits' else 'log_updates'] = [{}]
    elif defect in ('score-history', 'unmapped-score-history'):
        first['scores']['match' if defect == 'score-history' else 'not-mapped']['history'] = [{}]
    elif defect == 'score-reason':
        first['scores']['match']['reason'] = 'excluded'
    elif defect == 'no-version':
        source['eval']['packages'] = {}
    elif defect == 'no-config':
        del source['eval']['config']
    elif defect == 'no-results':
        del source['results']
    elif defect == 'bad-scores':
        first['scores'] = []
    elif defect == 'score-without-value':
        first['scores']['match'] = {}
    else:
        first['scores']['match'] = 'C'
    with pytest.raises(AgentBomError):
        create_inspect_pack(rendered(plan), rendered(source), tmp_path / 'rejected', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('value', [True, False, '1', [], {'nested': 1}, 10**400, float('inf'), float('nan')])
def test_numeric_scores_do_not_coerce_or_overflow(value):
    plan, source = inputs()
    source['samples'][0]['scores']['checks']['value']['authorized'] = value
    with pytest.raises(AgentBomError):
        convert(plan, source)


@pytest.mark.parametrize('value', ['P', 'true', 1, True, {}, ['C']])
def test_unmapped_or_wrong_type_labels_do_not_fall_back(value):
    plan, source = inputs()
    source['samples'][0]['scores']['match']['value'] = value
    with pytest.raises(AgentBomError):
        convert(plan, source)


@pytest.mark.parametrize('defect', ['extra', 'version', 'empty-map', 'duplicate-id', 'duplicate-scenario',
    'bool-id', 'bool-repeats', 'too-many', 'empty-metrics', 'bad-map', 'duplicate-metric-source',
    'unknown-encoding', 'number-labels', 'labels-empty', 'labels-bool', 'label-empty', 'context'])
def test_closed_plan_and_explicit_semantics(defect):
    plan, source = inputs()
    if defect in ('extra', 'context'):
        plan[defect] = {}
    elif defect == 'version':
        plan['plan_version'] += '-unknown'
    elif defect == 'empty-map':
        plan['sample_map'] = []
    elif defect in ('duplicate-id', 'duplicate-scenario'):
        field = 'sample_id' if defect == 'duplicate-id' else 'scenario_id'
        plan['sample_map'][1][field] = plan['sample_map'][0][field]
    elif defect == 'bool-id':
        plan['sample_map'][0]['sample_id'] = True
    elif defect in ('bool-repeats', 'too-many'):
        plan['n_repeats'] = True if defect == 'bool-repeats' else 10001
    elif defect == 'empty-metrics':
        plan['metrics'] = {}
    elif defect == 'bad-map':
        plan['metrics']['completion']['transform'] = 'eval(value)'
    elif defect == 'duplicate-metric-source':
        plan['metrics']['alias'] = deepcopy(plan['metrics']['completion'])
    elif defect == 'unknown-encoding':
        plan['metrics']['completion']['encoding'] = 'guess'
    elif defect == 'number-labels':
        plan['metrics']['authorization']['labels'] = {'C': 1}
    elif defect == 'labels-empty':
        plan['metrics']['completion']['labels'] = {}
    elif defect == 'labels-bool':
        plan['metrics']['completion']['labels']['C'] = True
    else:
        plan['metrics']['completion']['labels'][''] = 0
    with pytest.raises(AgentBomError):
        convert(plan, source)


@pytest.mark.parametrize('missing', ['scorer', 'scores', 'key', 'null'])
def test_missing_metric_is_absent_not_zero(missing):
    plan, source = inputs()
    for sample in source['samples']:
        if missing == 'scorer':
            del sample['scores']['checks']
        elif missing == 'key':
            sample['scores']['checks']['value'] = {}
        elif missing == 'null':
            sample['scores']['checks']['value']['authorized'] = None
    if missing == 'scores':
        source['samples'][0]['scores'] = None
    report, files = convert(plan, source)
    recording = json.loads(files['recording.json'])
    if missing == 'scores':
        assert recording['observations'][0]['metrics'] == {}
    else:
        assert report['unreported_metrics'] == ['authorization']
        assert all('authorization' not in row['metrics'] for row in recording['observations'])


def test_empty_measurements_fail_and_false_aggregate_metrics_are_not_imported():
    plan, source = inputs()
    source['results']['scores'] = [{'name': 'forged-aggregate', 'metrics': {'accuracy': {'value': 999}}}]
    report, files = convert(plan, source)
    assert 'forged-aggregate' not in json.loads(files['evaluation.json'])['metric_means']
    assert report['observation_count'] == 4
    for sample in source['samples']:
        sample['scores'] = None
    with pytest.raises(AgentBomError):
        convert(plan, source)


@pytest.mark.parametrize('raw', [b'', b'[]', b'{} trailing', b'{"version":2,"version":2}', b'{"x":NaN}',
                               b'{"unused":1e999}', b'{"x":"\xff"}', b'[' * 1500, b'x' * (MAX_JSON_BYTES + 1)])
def test_malformed_or_nonfinite_source_is_rejected(raw):
    plan, _ = inputs()
    with pytest.raises(AgentBomError):
        inspect_payloads(rendered(plan), raw, plan_sha256=digest(rendered(plan)))


def test_receiver_pin_cannot_be_updated_by_supplier_pack_rehash(tmp_path):
    plan, source = inputs()
    pin = digest(rendered(plan))
    plan['metrics']['completion']['labels']['I'] = 1
    forged_pin = digest(rendered(plan))
    create_inspect_pack(rendered(plan), rendered(source), tmp_path / 'pack', plan_sha256=forged_pin)
    with pytest.raises(AgentBomError, match='pin'):
        verify_inspect_pack(tmp_path / 'pack', plan_sha256=pin)


@pytest.mark.parametrize('member', sorted(FILES))
def test_each_pack_member_is_recomputed_and_overwrite_refused(tmp_path, member):
    plan, source = inputs()
    pin = digest(rendered(plan))
    path = tmp_path / 'pack'
    create_inspect_pack(rendered(plan), rendered(source), path, plan_sha256=pin)
    with pytest.raises(AgentBomError, match='overwrite'):
        create_inspect_pack(rendered(plan), rendered(source), path, plan_sha256=pin)
    with (path / member).open('ab') as stream:
        stream.write(b' ')
    # Source bytes are data: updating the source also requires rebuilding all derived hashes.
    with pytest.raises(AgentBomError):
        verify_inspect_pack(path, plan_sha256=pin)


def test_file_boundaries_and_cli(tmp_path, capsys):
    plan, source = inputs()
    plan_path, source_path = tmp_path / 'plan.json', tmp_path / 'source.json'
    plan_path.write_bytes(rendered(plan))
    source_path.write_bytes(rendered(source))
    pin = digest(rendered(plan))
    cmd = ['inspect-eval', 'create', str(plan_path), str(source_path), '--out', str(tmp_path / 'pack')]
    assert main(cmd + ['--plan-sha256', '0' * 64]) == 2
    assert not (tmp_path / 'pack').exists()
    assert main(cmd + ['--plan-sha256', pin]) == 0
    verify = ['inspect-eval', 'verify', str(tmp_path / 'pack'), '--plan-sha256', pin]
    assert main(verify) == 0
    assert main(verify + ['--evaluation', str(source_path)]) == 2
    alias = tmp_path / 'alias'
    alias.symlink_to(source_path)
    with pytest.raises(AgentBomError):
        _read(alias)
    (tmp_path / 'pack/extra').write_text('extra')
    assert main(verify) == 2
    assert 'error:' in capsys.readouterr().err


def test_default_epoch_is_one_not_observed_count():
    plan, source = inputs()
    del source['eval']['config']['epochs']
    with pytest.raises(AgentBomError, match='epochs'):
        convert(plan, source)
    plan['n_repeats'] = 1
    source['samples'] = [sample for sample in source['samples'] if sample['epoch'] == 1]
    source['results'] = {'total_samples': 2, 'completed_samples': 2}
    assert convert(plan, source)[0]['epoch_count'] == 1


def test_never_invokes_log_code_or_resolves_attachments(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution attempted')
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)
    plan, source = inputs()
    source['eval']['task_file'] = '/not/a/real/task.py'
    source['eval']['model_base_url'] = 'https://do-not-connect.invalid'
    source['samples'][0]['attachments'] = {'example': 'attachment://do-not-load'}
    source['samples'][0]['setup'] = 'exit 99'
    assert convert(plan, source)[0]['observation_count'] == 4


def test_installed_style_demo_has_replay_and_failure_example(tmp_path):
    root = tmp_path / 'demo'
    assert main(['inspect-eval', 'demo', '--out', str(root)]) == 0
    pin = digest((root / 'plan.json').read_bytes())
    assert verify_inspect_pack(root / 'converted', plan_sha256=pin)['observation_count'] == 4
    assert pin in (root / 'README.md').read_text()
    assert main(['inspect-eval', 'demo', '--out', str(root)]) == 2
    assert main(['inspect-eval', 'create', str(root / 'plan.json'), str(root / 'incomplete-source.json'),
                 '--plan-sha256', pin, '--out', str(tmp_path / 'rejected')]) == 2
    assert not (tmp_path / 'rejected').exists()


def test_independent_projection_oracle_over_81_score_and_missing_patterns():
    for values in product(('C', 'I', 'N'), repeat=4):
        plan, source = inputs()
        expected = []
        for sample, label in zip(source['samples'], values):
            sample['scores'] = {'match': {'value': label}}
            # Independent explicit expectations; do not reuse the adapter's label map.
            metric = {} if label == 'N' else {'completion': 1 if label == 'C' else 0}
            expected.append({'scenario_id': 'self-service' if type(sample['id']) is int else 'assisted',
                             'repeat': sample['epoch'] - 1, 'metrics': metric})
        if all(label == 'N' for label in values):
            with pytest.raises(AgentBomError):
                convert(plan, source)
            continue
        report, files = convert(plan, source)
        assert json.loads(files['recording.json'])['observations'] == expected
        assert report['metric_coverage']['completion']['reporting_observations'] == sum(v != 'N' for v in values)
        assert report['metric_coverage']['completion']['declared_observations'] == 4
        assert report['unreported_metrics'] == ['authorization']


@pytest.mark.parametrize('defect', ['linked-directory', 'linked-member', 'fifo-member', 'missing-member'])
def test_pack_capture_rejects_nonregular_or_incomplete_inventory(tmp_path, defect):
    plan, source = inputs()
    pin, folder = digest(rendered(plan)), tmp_path / 'pack'
    create_inspect_pack(rendered(plan), rendered(source), folder, plan_sha256=pin)
    if defect == 'linked-directory':
        alias = tmp_path / 'alias'
        alias.symlink_to(folder, target_is_directory=True)
        folder = alias
    else:
        member = folder / 'source.json'
        member.unlink()
        if defect == 'linked-member':
            original = tmp_path / 'original.json'
            original.write_bytes(rendered(source))
            member.symlink_to(original)
        elif defect == 'fifo-member':
            if not hasattr(os, 'mkfifo'):
                pytest.skip('FIFO unavailable on this platform')
            os.mkfifo(member)
    with pytest.raises(AgentBomError):
        verify_inspect_pack(folder, plan_sha256=pin)
