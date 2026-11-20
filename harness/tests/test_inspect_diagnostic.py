from copy import deepcopy
from html.parser import HTMLParser
from itertools import product
import json
import os
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_inspect import inspect_payloads
from aau_harness.inspect_demo import example_inputs
from aau_harness.inspect_diagnostic import FILES, create_diagnostic, diagnostic_payloads, verify_diagnostic


def review(plan, source):
    raw = rendered(plan)
    return diagnostic_payloads(raw, rendered(source), plan_sha256=digest(raw))


def complete_inputs():
    plan, source = example_inputs()
    for row in source['samples']:
        row['scores'] = {'match': {'value': 'C'}, 'checks': {'value': {'authorized': 1}}}
    return plan, source


def test_complete_diagnostic_is_not_an_export_or_a_performance_verdict():
    plan, source = complete_inputs()
    original = deepcopy((plan, source))
    report, files = review(plan, source)
    assert report['status'] == 'no_diagnostic_findings'
    assert report['conversion_eligibility']['status'] == 'accepted_by_current_converter'
    assert report['pair_counts'] == {'missing': 0, 'unique': 4, 'duplicate': 0}
    assert set(files) == FILES and 'evaluation.json' not in files
    for row in source['samples']:
        row['scores'] = {'match': {'value': 'I'}, 'checks': {'value': {'authorized': 0}}}
    assert review(plan, source)[0]['status'] == 'no_diagnostic_findings'
    assert original[0] == plan
    assert json.loads(files['source.json']) == original[1]


def test_success_can_contain_scored_errors_and_limits_without_erasing_either():
    plan, source = complete_inputs()
    source['samples'][0]['error'] = {'message': 'Synthetic only'}
    source['samples'][1]['limit'] = {'type': 'time', 'limit': 5}
    report, files = review(plan, source)
    assert report['source_status'] == 'success' and report['status'] == 'review_required'
    assert report['row_marker_counts'] == {'error_recorded': 1, 'limit_recorded': 1}
    assert report['metric_state_counts']['completion'] == {'available': 4}
    assert report['conversion_eligibility']['status'] == 'rejected_by_current_converter'
    assert files['source.json'] == rendered(source)
    with pytest.raises(AgentBomError):
        inspect_payloads(rendered(plan), rendered(source), plan_sha256=digest(rendered(plan)))


def test_typed_ids_duplicates_missing_and_outside_plan_remain_distinct():
    plan, source = complete_inputs()
    source['samples'].pop()
    source['samples'].append(deepcopy(source['samples'][0]))
    source['samples'].append({'id': 1, 'epoch': 3})
    source['samples'].append({'id': 'other', 'epoch': 1})
    report, _ = review(plan, source)
    assert report['recorded_rows'] == 6
    assert report['pair_counts'] == {'missing': 1, 'unique': 2, 'duplicate': 1}
    assert report['planned_pairs'][0]['source_positions'] == [0, 3]
    assert report['planned_pairs'][2]['sample_id_type'] == 'str'
    assert report['planned_pairs'][3]['presence'] == 'missing'
    assert report['row_marker_counts']['outside_plan'] == 2
    assert report['rows'][4]['scenario_id'] is None


def test_independent_census_oracle_for_81_missing_unique_duplicate_patterns():
    plan, base = complete_inputs()
    for multiplicities in product((0, 1, 2), repeat=4):
        source = deepcopy(base)
        source['samples'] = [deepcopy(row) for row, n in zip(base['samples'], multiplicities) for _ in range(n)]
        report, _ = review(plan, source)
        assert report['pair_counts'] == {name: multiplicities.count(n) for n, name in enumerate(('missing', 'unique', 'duplicate'))}
        assert [len(p['source_positions']) for p in report['planned_pairs']] == list(multiplicities)
        assert sum(len(p['source_positions']) for p in report['planned_pairs']) == len(source['samples'])
        assert (report['status'] == 'no_diagnostic_findings') == (multiplicities == (1, 1, 1, 1))


@pytest.mark.parametrize('status', ['started', 'error', 'cancelled'])
def test_interrupted_and_header_only_evidence_is_not_filled_in(status):
    plan, source = complete_inputs()
    source['status'] = status
    del source['samples']
    del source['results']
    report, files = review(plan, source)
    assert report['samples_state'] == 'absent' and report['recorded_rows'] == 0
    assert report['pair_counts'] == {'missing': 4, 'unique': 0, 'duplicate': 0}
    assert {'code': 'samples_unavailable', 'pointer': '/samples'} in report['log_findings']
    assert not report['rows'] and not json.loads(files['source.json']).get('samples')


@pytest.mark.parametrize('field', ['error', 'error_retries', 'invalidation', 'limit'])
def test_lifecycle_markers_are_independent_of_scores_and_not_inferred_causes(field):
    plan, source = complete_inputs()
    source['samples'][0][field] = [{'message': 'sensitive-text-not-for-html'}] if field == 'error_retries' else {'message': 'sensitive-text-not-for-html'}
    report, files = review(plan, source)
    assert report['rows'][0]['markers'] == [{'code': field + '_recorded', 'pointer': '/samples/0/' + field}]
    assert report['rows'][0]['metric_states']['completion'] == 'available'
    assert b'sensitive-text-not-for-html' not in files['review.html']
    assert b'sensitive-text-not-for-html' in files['source.json']


def test_unmapped_score_edits_are_kept_and_json_pointers_escape_names():
    plan, source = complete_inputs()
    source['samples'][0]['scores']['extra/~name'] = {'value': 0, 'history': [{'value': 1}], 'reason': 'zeroed'}
    source['samples'][0]['scores']['extra2'] = {'value': 0, 'history': [{'value': 1}]}
    report, _ = review(plan, source)
    markers = report['rows'][0]['markers']
    assert {'code': 'score_history_recorded', 'pointer': '/samples/0/scores/extra~1~0name/history'} in markers
    assert report['row_marker_counts']['score_history_recorded'] == 1  # Counts rows, not scorer fields.
    assert report['status'] == 'review_required'


@pytest.mark.parametrize('container,field,value', [('root', 'error', {}), ('root', 'invalidated', True),
    ('root', 'config_updates', [{}]), ('root', 'log_updates', [{}]), ('eval', 'shards', {}), ('results', 'early_stopping', {})])
def test_global_markers_are_visible(container, field, value):
    plan, source = complete_inputs()
    (source if container == 'root' else source[container])[field] = value
    report, _ = review(plan, source)
    assert any(r['pointer'].endswith('/' + field) for r in report['log_findings'])
    assert report['status'] == 'review_required'


@pytest.mark.parametrize('scores,metric,state', [
    (None, 'completion', 'scorer_absent'), ({}, 'completion', 'scorer_absent'),
    ([], 'completion', 'scores_shape_invalid'), ({'match': {}}, 'completion', 'score_shape_invalid'),
    ({'match': {'value': None}}, 'completion', 'value_null'),
    ({'match': {'value': 'N'}}, 'completion', 'label_maps_to_absent'),
    ({'match': {'value': 'unknown'}}, 'completion', 'label_unmapped'),
    ({'checks': {'value': {}}}, 'authorization', 'component_absent'),
    ({'checks': {'value': 1}}, 'authorization', 'component_shape_invalid'),
    ({'checks': {'value': {'authorized': False}}}, 'authorization', 'number_invalid'),
])
def test_mapped_metric_absence_and_invalid_values_are_distinguished(scores, metric, state):
    plan, source = complete_inputs()
    source['samples'][0]['scores'] = scores
    report, _ = review(plan, source)
    assert report['rows'][0]['metric_states'][metric] == state
    assert report['status'] == 'review_required'


def test_importable_missing_scores_still_require_diagnostic_review():
    plan, source = example_inputs()
    report, _ = review(plan, source)
    assert report['conversion_eligibility']['status'] == 'accepted_by_current_converter'
    assert report['status'] == 'review_required'
    assert report['metric_state_counts']['completion'] == {'available': 3, 'label_maps_to_absent': 1}


@pytest.mark.parametrize('member', sorted(FILES))
def test_source_retention_and_full_replay_reject_rehashed_tampering(tmp_path, member):
    plan, source = example_inputs()
    plan_raw = b' ' + rendered(plan)
    source_raw = b'\xef\xbb\xbf' + rendered(source).replace(b'\n', b'\r\n')
    folder, pin = tmp_path / 'pack', digest(plan_raw)
    create_diagnostic(plan_raw, source_raw, folder, plan_sha256=pin)
    assert (folder / 'source.json').read_bytes() == source_raw
    assert verify_diagnostic(folder, plan_sha256=pin)['status'] == 'review_required'
    with pytest.raises(AgentBomError, match='overwrite'):
        create_diagnostic(plan_raw, source_raw, folder, plan_sha256=pin)
    with (folder / member).open('ab') as stream:
        stream.write(b' ')
    if member != 'manifest.json':
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        manifest['files'][member] = digest((folder / member).read_bytes())
        (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_diagnostic(folder, plan_sha256=pin)


@pytest.mark.parametrize('defect', ['bad-version', 'bad-status', 'bad-samples', 'too-many-rows', 'non-object-row',
    'bad-id', 'bool-epoch', 'zero-epoch', 'huge-epoch', 'bad-scorer'])
def test_invalid_structural_inputs_are_rejected_before_output(tmp_path, defect):
    plan, source = complete_inputs()
    if defect == 'bad-version':
        source['version'] = True
    elif defect == 'bad-status':
        source['status'] = 'unknown'
    elif defect == 'bad-samples':
        source['samples'] = {}
    elif defect == 'too-many-rows':
        source['samples'] = [{}] * 10001
    elif defect == 'non-object-row':
        source['samples'][0] = []
    elif defect == 'bad-id':
        source['samples'][0]['id'] = True
    elif defect == 'bad-scorer':
        source['samples'][0]['scores'][' '] = {'value': 1}
    else:
        source['samples'][0]['epoch'] = {'bool-epoch': True, 'zero-epoch': 0, 'huge-epoch': 10001}[defect]
    with pytest.raises(AgentBomError):
        create_diagnostic(rendered(plan), rendered(source), tmp_path / 'bad', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('raw', [b'{"version":2,"x":NaN}', b'{"x":1e999}', b'{"x":1,"x":2}',
                               b'[]', b'\xff', b'[' * 2000, b'x' * (MAX_JSON_BYTES + 1)])
def test_malformed_nonfinite_and_oversized_json_remains_unsupported(raw):
    plan, _ = complete_inputs()
    with pytest.raises(AgentBomError):
        diagnostic_payloads(rendered(plan), raw, plan_sha256=digest(rendered(plan)))


def test_upstream_mock_fixture_is_observed_compatibility_not_a_real_model_trial():
    raw = (Path(__file__).parent / 'fixtures/inspect-ai/scored_0.3.100.json').read_bytes()
    plan = {'plan_version': 'aau-inspect-observation-plan/1.0', 'source_label': 'upstream mock fixture',
            'sample_map': [{'sample_id': 1, 'scenario_id': 'mock-addition'}], 'n_repeats': 1,
            'metrics': {'completion': {'scorer': 'graded', 'value_key': None, 'encoding': 'number'}}}
    report, files = diagnostic_payloads(rendered(plan), raw, plan_sha256=digest(rendered(plan)))
    assert report['status'] == 'no_diagnostic_findings' and report['recorded_rows'] == 1
    assert files['source.json'] == raw and json.loads(raw)['eval']['model'] == 'mockllm/model'


def test_cli_demo_preserves_findings_and_distinguishes_invalid_replay(tmp_path):
    root = tmp_path / 'demo'
    assert main(['inspect-eval', 'demo', '--out', str(root)]) == 0
    pin = digest((root / 'plan.json').read_bytes())
    assert main(['inspect-eval', 'verify-diagnostic', str(root / 'diagnostic'), '--plan-sha256', pin]) == 1
    report = verify_diagnostic(root / 'diagnostic', plan_sha256=pin)
    assert report['pair_counts'] == {'missing': 1, 'unique': 2, 'duplicate': 1}
    assert report['row_marker_counts']['outside_plan'] == 1 and report['recorded_rows'] == 5
    assert main(['inspect-eval', 'diagnose', str(root / 'plan.json'), str(root / 'interrupted-source.json'),
                 '--plan-sha256', pin, '--out', str(tmp_path / 'copy')]) == 1
    assert main(['inspect-eval', 'verify-diagnostic', str(root / 'diagnostic'), '--plan-sha256', '0' * 64]) == 2


@pytest.mark.parametrize('defect', ['extra', 'missing', 'directory', 'symlink', 'fifo'])
def test_packet_inventory_is_closed(tmp_path, defect):
    plan, source = complete_inputs()
    folder, pin = tmp_path / 'pack', digest(rendered(plan))
    create_diagnostic(rendered(plan), rendered(source), folder, plan_sha256=pin)
    if defect == 'extra':
        (folder / 'extra').write_text('extra')
    elif defect == 'directory':
        (folder / 'nested').mkdir()
    else:
        (folder / 'source.json').unlink()
        if defect == 'symlink':
            (folder / 'source.json').symlink_to(folder / 'plan.json')
        elif defect == 'fifo':
            if not hasattr(os, 'mkfifo'):
                pytest.skip('FIFO unavailable')
            os.mkfifo(folder / 'source.json')
    with pytest.raises(AgentBomError):
        verify_diagnostic(folder, plan_sha256=pin)


def test_offline_html_escapes_supplied_identifiers_and_no_log_code_executes(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution attempted')
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)
    plan, source = complete_inputs()
    plan['sample_map'][0]['scenario_id'] = '<script>alert(1)</script>'
    source['eval']['task_file'] = 'https://do-not-run.invalid/task.py'
    source['samples'][0]['scores']['<img src=x>'] = {'value': 1, 'history': [{}]}
    _, files = review(plan, source)
    class Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag not in ('script', 'img', 'iframe', 'link')
            if tag == 'th':
                assert dict(attrs).get('scope') in ('col', 'row')
            if ('class', 'scroll') in attrs:
                assert ('tabindex', '0') in attrs
    html = files['review.html'].decode()
    Parser().feed(html)
    assert '&lt;script&gt;' in html and '&lt;img' in html


def test_expansion_is_bounded_before_any_output(tmp_path):
    plan, source = complete_inputs()
    plan['metrics'] = {str(i).zfill(200): {'scorer': f's-{i}', 'value_key': None, 'encoding': 'number'} for i in range(100)}
    source['samples'] = [{'id': 1, 'epoch': 1, 'scores': {}} for _ in range(100)]
    assert len(rendered(source)) < MAX_JSON_BYTES
    with pytest.raises(AgentBomError, match='expanded Inspect diagnostic'):
        create_diagnostic(rendered(plan), rendered(source), tmp_path / 'large', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'large').exists()
