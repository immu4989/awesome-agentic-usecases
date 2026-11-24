from copy import deepcopy
from itertools import product
import json

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_promptfoo import promptfoo_payloads
from aau_harness.promptfoo_demo import example_inputs
from aau_harness.promptfoo_diagnostic import FILES, create_diagnostic, diagnostic_payloads, verify_diagnostic


def review(plan, source):
    raw = rendered(plan)
    return diagnostic_payloads(raw, rendered(source), plan_sha256=digest(raw))


def complete():
    plan, source = example_inputs()
    source['results']['results'][5]['namedScores']['authorization'] = 1
    return plan, source


def test_assertion_failure_is_not_an_execution_error_or_quality_pass():
    plan, source = complete()
    report, files = review(plan, source)
    assert report['status'] == 'no_diagnostic_findings'
    assert report['conversion_eligibility']['status'] == 'accepted_by_current_converter'
    assert report['outcome_category_counts'] == {'none': 5, 'assertion_failure': 1, 'execution_error': 0, 'unknown': 0}
    assert report['rows'][3]['error_text_recorded']
    assert report['pair_counts'] == {'missing': 0, 'unique': 6, 'duplicate': 0}
    assert set(files) == FILES and 'evaluation.json' not in files
    assert files['source.json'] == rendered(source)


def test_errors_in_unselected_columns_keep_scores_available_but_do_not_convert():
    plan, source = complete()
    row = source['results']['results'][0]
    row.update(failureReason=2, success=False, error='synthetic provider error')
    row['response'] = {'error': 'synthetic provider error'}
    report, files = review(plan, source)
    assert report['status'] == 'review_required'
    assert not report['rows'][0]['selected_column']
    assert report['rows'][0]['metric_states']['quality'] == 'available'
    assert report['row_marker_counts']['execution_error_recorded'] == 1
    assert report['row_marker_counts']['response_error_recorded'] == 1
    assert report['conversion_eligibility']['status'] == 'rejected_by_current_converter'
    assert files['source.json'] == rendered(source)
    with pytest.raises(AgentBomError):
        promptfoo_payloads(rendered(plan), rendered(source), plan_sha256=digest(rendered(plan)))


def test_mixed_census_retains_all_positions_without_choosing_duplicate():
    plan, source = complete()
    rows = source['results']['results']
    rows.pop()
    rows.append(deepcopy(rows[0]))
    rows.extend([{'testIdx': 99, 'promptIdx': 0}, None, {'testIdx': True, 'promptIdx': 0}])
    report, _ = review(plan, source)
    assert report['recorded_rows'] == 9
    assert report['pair_counts'] == {'missing': 1, 'unique': 4, 'duplicate': 1}
    assert report['planned_pairs'][0]['source_positions'] == [0, 5]
    assert report['row_marker_counts']['duplicate_pair'] == 2
    assert report['row_marker_counts']['duplicate_result_id'] == 2
    assert report['row_marker_counts']['outside_plan'] == 3
    assert report['row_marker_counts']['row_shape_invalid'] == 1
    assert len(report['rows']) == len(rows)
    assert report['rows'][-1]['test_index'] is None


def test_census_against_81_independent_multiplicity_patterns():
    plan, source = complete()
    plan['test_map'] = plan['test_map'][:2]
    base = source['results']['results'][:4]
    for multiplicities in product((0, 1, 2), repeat=4):
        source['results']['results'] = [deepcopy(row) for row, n in zip(base, multiplicities) for _ in range(n)]
        report, _ = review(plan, source)
        assert report['pair_counts'] == {state: multiplicities.count(n) for n, state in enumerate(('missing', 'unique', 'duplicate'))}
        assert report['recorded_rows'] == sum(multiplicities)
        for pair, n in zip(report['planned_pairs'], multiplicities):
            assert len(pair['source_positions']) == n


@pytest.mark.parametrize('field,value,code', [
    ('failureReason', True, 'failure_category_unknown'), ('failureReason', {}, 'failure_category_unknown'),
    ('failureReason', 9, 'failure_category_unknown'), ('success', 1, 'success_state_inconsistent'),
    ('success', False, 'success_state_inconsistent'), ('error', [], 'error_shape_invalid'),
    ('error', 'not a successful result', 'successful_row_error_text'),
    ('response', [], 'response_shape_invalid'), ('vars', [], 'variables_shape_invalid'),
    ('vars', {'__repeatIndex': True}, 'repeat_marker_unsupported'), ('repeatIndex', 1, 'repeat_marker_unsupported'),
    ('id', [], 'result_id_invalid'), ('promptId', 'wrong', 'row_identity_mismatch'),
    ('provider', {'id': 'wrong'}, 'row_identity_mismatch'), ('score', True, 'score_or_grading_invalid'),
    ('gradingResult', {'pass': True, 'score': 0}, 'score_or_grading_invalid'),
    ('namedScores', {'unmapped': []}, 'named_scores_invalid'), ('namedScores', [], 'named_scores_invalid'),
])
def test_recorded_defects_are_findings_without_crashes_or_repairs(field, value, code):
    plan, source = complete()
    source['results']['results'][0][field] = value
    report, files = review(plan, source)
    assert code in report['row_marker_counts']
    assert report['conversion_eligibility']['status'] == 'rejected_by_current_converter'
    assert files['source.json'] == rendered(source)


@pytest.mark.parametrize('value,state', [(None, 'null'), (False, 'invalid'), ('1', 'invalid'), (0, 'available')])
def test_metric_missingness_and_availability_are_not_scores(value, state):
    plan, source = complete()
    source['results']['results'][0]['namedScores']['authorization'] = value
    report, _ = review(plan, source)
    assert report['rows'][0]['metric_states']['authorization'] == state
    del source['results']['results'][0]['namedScores']['authorization']
    assert review(plan, source)[0]['rows'][0]['metric_states']['authorization'] == 'absent'


@pytest.mark.parametrize('location', ['config', 'runtime'])
def test_explicit_repeat_options_are_retained_not_reinterpreted(location):
    plan, source = complete()
    if location == 'config':
        source['config']['evaluateOptions'] = {'repeat': 2}
    else:
        source['runtimeOptions'] = {'repeat': 2}
    report, _ = review(plan, source)
    assert any(f['code'] == 'repeat_options_unsupported' for f in report['log_findings'])
    assert report['pair_counts']['unique'] == 6
    assert report['conversion_eligibility']['status'] == 'rejected_by_current_converter'


@pytest.mark.parametrize('change', ['no_rows', 'null_rows', 'no_stats', 'wrong_count', 'bad_prompts', 'wrong_prompt'])
def test_missing_or_conflicting_envelope_evidence_is_visible(change):
    plan, source = complete()
    summary = source['results']
    if change == 'no_rows':
        del summary['results']
    elif change == 'null_rows':
        summary['results'] = None
    elif change == 'no_stats':
        del summary['stats']
    elif change == 'wrong_count':
        summary['stats']['successes'] = True
    elif change == 'bad_prompts':
        summary['prompts'] = []
    else:
        summary['prompts'][0]['id'] = 'wrong'
    report, _ = review(plan, source)
    assert report['log_findings']
    assert report['conversion_eligibility']['status'] == 'rejected_by_current_converter'
    if change.endswith('rows'):
        assert report['pair_counts']['missing'] == 6 and report['rows_state'] == 'unavailable'


@pytest.mark.parametrize('raw', [b'[]', b'{"x":1,"x":2}', b'{"x":NaN}', b' ', b'x' * (MAX_JSON_BYTES + 1)])
def test_unsupported_json_rejected_before_output(tmp_path, raw):
    plan, _ = complete()
    with pytest.raises(AgentBomError):
        create_diagnostic(rendered(plan), raw, tmp_path / 'bad', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'bad').exists()


def test_unsupported_envelope_and_row_limits():
    plan, source = complete()
    for version in (True, 2, '3'):
        source['results']['version'] = version
        with pytest.raises(AgentBomError):
            review(plan, source)
    source['results']['version'] = 3
    for rows in ({}, [None] * 10001):
        source['results']['results'] = rows
        with pytest.raises(AgentBomError):
            review(plan, source)


def test_expansion_limit_is_enforced_without_output(tmp_path):
    plan, source = complete()
    source['results']['results'] = [None] * 10000
    with pytest.raises(AgentBomError, match='2 MB'):
        create_diagnostic(rendered(plan), rendered(source), tmp_path / 'huge', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'huge').exists()


@pytest.mark.parametrize('member', sorted(FILES))
def test_exact_replay_rejects_each_changed_member(tmp_path, member):
    plan, source = complete()
    raw, pin = rendered(plan), digest(rendered(plan))
    directory = tmp_path / 'packet'
    report = create_diagnostic(raw, rendered(source), directory, plan_sha256=pin)
    assert verify_diagnostic(directory, plan_sha256=pin) == report
    with (directory / member).open('ab') as stream:
        stream.write(b' ')
    with pytest.raises(AgentBomError):
        verify_diagnostic(directory, plan_sha256=pin)


def test_replay_pin_overwrite_inventory_symlinks_and_escaped_html(tmp_path):
    plan, source = complete()
    plan['test_map'][0]['scenario_id'] = '<script>alert(1)</script>'
    raw, pin = rendered(plan), digest(rendered(plan))
    directory = tmp_path / 'packet'
    create_diagnostic(raw, rendered(source), directory, plan_sha256=pin)
    html = (directory / 'review.html').read_text()
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'tabindex="0"' in html and 'scope="row"' in html
    for operation in (lambda: verify_diagnostic(directory, plan_sha256='0' * 64),
                      lambda: create_diagnostic(raw, rendered(source), directory, plan_sha256=pin)):
        with pytest.raises(AgentBomError):
            operation()
    (directory / 'extra').write_text('x')
    with pytest.raises(AgentBomError):
        verify_diagnostic(directory, plan_sha256=pin)
    (directory / 'extra').unlink()
    target = tmp_path / 'source-copy.json'
    target.write_bytes((directory / 'source.json').read_bytes())
    (directory / 'source.json').unlink()
    (directory / 'source.json').symlink_to(target)
    with pytest.raises(AgentBomError):
        verify_diagnostic(directory, plan_sha256=pin)


def test_cli_demo_and_exit_codes(tmp_path):
    directory = tmp_path / 'demo'
    assert main(['promptfoo-eval', 'demo', '--out', str(directory)]) == 0
    pin = digest((directory / 'plan.json').read_bytes())
    packet = directory / 'diagnostic'
    assert main(['promptfoo-eval', 'verify-diagnostic', str(packet), '--plan-sha256', pin]) == 1
    report = json.loads((packet / 'diagnostic.json').read_bytes())
    assert report['pair_counts'] == {'missing': 1, 'unique': 4, 'duplicate': 1}
    assert report['recorded_rows'] == 7
    assert main(['promptfoo-eval', 'verify-diagnostic', str(packet), '--plan-sha256', '0' * 64]) == 2
    plan, source = complete()
    (tmp_path / 'plan.json').write_bytes(rendered(plan))
    (tmp_path / 'source.json').write_bytes(rendered(source))
    args = ['promptfoo-eval', 'diagnose', str(tmp_path / 'plan.json'), str(tmp_path / 'source.json'),
            '--plan-sha256', digest(rendered(plan)), '--out', str(tmp_path / 'complete')]
    assert main(args) == 0
    assert main(args) == 2
