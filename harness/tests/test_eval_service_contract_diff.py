from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_compare import compare_evaluations
from aau_harness import eval_service_contract_diff as module
from aau_harness.eval_service_contract_diff import compare_service_contracts
from aau_harness.eval_service_traces import service_trace_payloads


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'public-value-review/examples'


def inputs():
    suite = load_json(FIXTURES / 'suite.json')
    traces = load_json(FIXTURES / 'traces.json')
    plan = {'plan_version': 'aau-service-trace-import/1.0', 'source_label': 'Frozen synthetic observations', 'n_repeats': 1}
    return suite, deepcopy(suite), plan, traces


def test_removing_recourse_changes_scores_without_changing_any_observation():
    baseline, candidate, plan, traces = inputs()
    candidate['cases'][0]['contract']['recourse_required'] = False
    originals = deepcopy((baseline, candidate, plan, traces))
    report = compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    assert (baseline, candidate, plan, traces) == originals
    assert report == compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    assert report['status'] == 'review_required'
    assert report['changes'] == [{'case_id': 'recourse-required', 'field': 'recourse_required',
                                  'kind': 'protection_no_longer_required', 'baseline': True, 'candidate': False}]
    impact = report['frozen_trace_review']
    assert impact['joint_pass_counts'] == {'baseline': 1, 'candidate': 2}
    assert impact['joint_transition_counts'] == {'became_satisfied': 1, 'became_unsatisfied': 0,
                                                'unchanged_satisfied': 1, 'unchanged_unsatisfied': 0}
    assert impact['traces_sha256'] == digest(traces) and impact['plan_sha256'] == digest(plan)
    assert impact['required_protection_coverage']['baseline']['recourse_preserved']['required_observation_count'] == 1
    assert impact['required_protection_coverage']['candidate']['recourse_preserved']['required_observation_count'] == 0
    for row in impact['observations']:
        assert row['baseline_assessment']['trace_sha256'] == row['candidate_assessment']['trace_sha256']
    changed = next(row for row in impact['observations'] if row['case_id'] == 'recourse-required')
    assert {c['metric'] for c in changed['changed_metrics']} == {'recourse_preserved', 'public_value_exact'}
    assert changed['baseline_assessment']['findings'][0]['obligation'] == 'recourse_preserved'
    assert changed['candidate_assessment']['findings'] == []
    assert set(report['implementation_sha256']) == set(module.SCORING_FILES) | {'eval_service_contract_diff.py'}
    assert report['implementation_sha256']['eval_service_contract_diff.py'] == digest(Path(module.__file__).read_bytes())


@pytest.mark.parametrize('flag', sorted(module.CONTRACT_FLAGS))
@pytest.mark.parametrize('required', [False, True])
def test_protection_change_direction_is_explicit(flag, required):
    baseline, candidate, _, _ = inputs()
    baseline['cases'][0]['contract'][flag] = not required
    candidate['cases'][0]['contract'][flag] = required
    report = compare_service_contracts(baseline, candidate)
    assert report['changes'] == [{'case_id': 'recourse-required', 'field': flag,
                                  'kind': 'protection_required' if required else 'protection_no_longer_required',
                                  'baseline': not required, 'candidate': required}]
    assert report['status'] == 'review_required' and report['frozen_trace_review'] == {'status': 'not_requested'}


@pytest.mark.parametrize('field,value,kind', [('version', 'owner-revision-2', 'version_changed'),
                                           ('expected_terminal', 'request_evidence', 'terminal_changed'),
                                           ('required_channel', 'mail', 'channel_changed')])
def test_labels_require_review_without_inventing_a_strength_order(field, value, kind):
    baseline, candidate, _, _ = inputs()
    candidate['cases'][0]['contract'][field] = value
    report = compare_service_contracts(baseline, candidate)
    assert report['changes'][0]['kind'] == kind and report['changes'][0]['candidate'] == value
    assert report['status'] == 'review_required'


def test_both_added_and_removed_prohibitions_remain_visible():
    baseline, candidate, _, _ = inputs()
    candidate['cases'][0]['contract']['forbidden_events'] = ['disclose_record']
    change = compare_service_contracts(baseline, candidate)['changes'][0]
    assert change['kind'] == 'prohibitions_changed'
    assert change['removed'] == ['deny_application'] and change['added'] == ['disclose_record']


@pytest.mark.parametrize('edit', ['prohibition', 'held_claim', 'channel', 'terminal', 'required_evidence', 'new_protection'])
def test_controlled_single_edit_rescoring_preserves_all_assessments(edit):
    baseline, candidate, plan, traces = inputs()
    left = baseline['cases'][0]['contract']
    right = candidate['cases'][0]['contract']
    trace = next(row['trace'] for row in traces['observations'] if row['case_id'] == 'recourse-required')
    trace['recourse_offered'] = True
    expected = 'became_satisfied'
    if edit == 'prohibition':
        trace['attempted_events'].append('deny_application')
        trace['executed_events'].append('deny_application')
        right['forbidden_events'] = []
    elif edit == 'held_claim':
        left['required_evidence'] = right['required_evidence'] = ['identity']
        right['held_evidence'] = ['identity']
    elif edit == 'channel':
        trace['delivery_channels'] = ['mail']
        right['required_channel'] = 'mail'
    elif edit == 'terminal':
        trace['terminal_events'] = ['request_evidence']
        right['expected_terminal'] = 'request_evidence'
    elif edit == 'required_evidence':
        left['required_evidence'] = ['identity']
    else:
        right['continuity_preservation_required'] = True
        trace['continuity_preserved'] = False
        expected = 'became_unsatisfied'
    report = compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    assert report['frozen_trace_review']['joint_transition_counts'][expected] == 1
    assert len(report['frozen_trace_review']['observations']) == 2
    if edit == 'held_claim':
        assert report['evidence_request_sets'] == [{'case_id': 'recourse-required', 'baseline_missing_evidence': ['identity'],
                                                   'candidate_missing_evidence': [],
                                                   'boundary': 'Derived request sets under changed declarations, not proof that evidence was acquired or burden reduced.'}]


def test_changed_declarations_are_visible_even_if_request_set_and_scores_stay_equal():
    baseline, candidate, plan, traces = inputs()
    contract = candidate['cases'][0]['contract']
    contract['required_evidence'] = contract['held_evidence'] = ['already-held']
    report = compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    assert report['status'] == 'review_required' and len(report['changes']) == 2
    assert report['evidence_request_sets'][0]['baseline_missing_evidence'] == []
    assert report['evidence_request_sets'][0]['candidate_missing_evidence'] == []
    assert report['frozen_trace_review']['joint_transition_counts']['became_satisfied'] == 0
    assert report['frozen_trace_review']['joint_transition_counts']['became_unsatisfied'] == 0


def test_set_order_case_order_and_optional_false_are_not_behavior_changes():
    baseline, _, plan, traces = inputs()
    baseline['cases'][0]['contract'].update(required_evidence=['identity', 'ownership'], held_evidence=['identity', 'ownership'],
                                           forbidden_events=['deny_application', 'disclose_record'])
    candidate = deepcopy(baseline)
    candidate['cases'].reverse()
    for case in candidate['cases']:
        case['contract']['continuity_preservation_required'] = False
        for field in module.CONTRACT_LISTS:
            case['contract'][field].reverse()
    report = compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    assert report['baseline_sha256'] != report['candidate_sha256']
    assert report['changes'] == [] and report['status'] == 'no_contract_change_detected'
    assert report['frozen_trace_review']['joint_transition_counts']['unchanged_unsatisfied'] == 1
    # Byte/value pins can still change: this diagnostic does not override normal context checks.
    assert report['frozen_trace_review']['scoring_contexts']['baseline'] != report['frozen_trace_review']['scoring_contexts']['candidate']


def test_version_change_requires_review_even_when_all_scores_are_unchanged():
    baseline, candidate, plan, traces = inputs()
    candidate['cases'][0]['contract']['version'] = 'owner-revision-2'
    report = compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    assert report['status'] == 'review_required'
    assert all(not row['changed_metrics'] for row in report['frozen_trace_review']['observations'])


@pytest.mark.parametrize('edit', ['add', 'remove', 'rename'])
def test_all_scope_changes_are_retained_and_probes_never_use_a_favorable_intersection(edit):
    baseline, candidate, plan, traces = inputs()
    if edit == 'add':
        candidate['cases'].append({'case_id': 'new-case', 'contract': deepcopy(candidate['cases'][0]['contract'])})
    elif edit == 'remove':
        candidate['cases'].pop(0)  # Remove the failing case.
    else:
        candidate['cases'][0]['case_id'] = 'renamed-case'
    report = compare_service_contracts(baseline, candidate)
    assert report['status'] == 'review_required'
    assert len(report['changes']) == (2 if edit == 'rename' else 1)
    assert all(c['baseline'] is not None or c['candidate'] is not None for c in report['changes'])
    assert report['case_census']['removed'] == ([] if edit == 'add' else ['recourse-required'])
    with pytest.raises(AgentBomError, match='no intersection filtering'):
        compare_service_contracts(baseline, candidate, plan=plan, traces=traces)


def test_different_contexts_still_cannot_enter_an_ordinary_score_comparison():
    baseline, candidate, plan, traces = inputs()
    candidate['cases'][0]['contract']['recourse_required'] = False
    compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    evaluations = [json.loads(service_trace_payloads(plan, suite, traces)[1]['evaluation.json']) for suite in (baseline, candidate)]
    with pytest.raises(AgentBomError, match='contexts differ'):
        compare_evaluations(*evaluations, metric='public_value_exact', direction='higher')


@pytest.mark.parametrize('defect', ['empty', 'too_many', 'wrong_version', 'extra_suite', 'duplicate_case', 'case_controls',
                                   'contract_extra', 'flag_integer', 'bad_label', 'duplicates', 'held_outside_required',
                                   'nonfinite', 'non_utf8', 'oversized', 'plan_only', 'traces_only',
                                   'missing_trace', 'duplicate_trace', 'extra_trace', 'input_scores'])
def test_invalid_or_incomplete_inputs_fail_closed(defect):
    baseline, candidate, plan, traces = inputs()
    contract = candidate['cases'][0]['contract']
    if defect == 'empty':
        candidate['cases'] = []
    elif defect == 'too_many':
        candidate['cases'] *= 251
    elif defect == 'wrong_version':
        candidate['suite_version'] = 'unknown'
    elif defect == 'extra_suite':
        candidate['extra'] = True
    elif defect == 'duplicate_case':
        candidate['cases'].append(deepcopy(candidate['cases'][0]))
    elif defect == 'case_controls':
        candidate['cases'][0]['case_id'] = 'bad\ncase'
    elif defect == 'contract_extra':
        contract['extra'] = True
    elif defect == 'flag_integer':
        contract['recourse_required'] = 0
    elif defect == 'bad_label':
        contract['required_channel'] = ''
    elif defect == 'duplicates':
        contract['forbidden_events'] *= 2
    elif defect == 'held_outside_required':
        contract['held_evidence'] = ['outside']
    elif defect == 'nonfinite':
        contract['version'] = float('nan')
    elif defect == 'non_utf8':
        contract['version'] = '\ud800'
    elif defect == 'oversized':
        contract['version'] = 'x' * 2_000_001
    elif defect == 'plan_only':
        traces = None
    elif defect == 'traces_only':
        plan = None
    elif defect == 'missing_trace':
        traces['observations'].pop()
    elif defect == 'duplicate_trace':
        traces['observations'][1] = deepcopy(traces['observations'][0])
    elif defect == 'extra_trace':
        traces['observations'].append(deepcopy(traces['observations'][0]))
    else:
        traces['observations'][0]['metrics'] = {'public_value_exact': 1}
    with pytest.raises(AgentBomError):
        compare_service_contracts(baseline, candidate, plan=plan, traces=traces)


def test_repeated_trace_version_preserves_every_case_repeat_including_failures():
    baseline, candidate, plan, traces = inputs()
    candidate['cases'][0]['contract']['recourse_required'] = False
    plan['n_repeats'] = 2
    traces = {'trace_version': 'aau-public-value-traces/1.1',
              'observations': [{**deepcopy(row), 'repeat': repeat} for row in traces['observations'] for repeat in range(2)]}
    report = compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
    assert report['frozen_trace_review']['observation_count'] == 4
    assert report['frozen_trace_review']['joint_transition_counts']['became_satisfied'] == 2
    assert len(report['frozen_trace_review']['observations']) == 4


def test_oversized_report_is_rejected_not_truncated(monkeypatch):
    baseline, candidate, plan, traces = inputs()
    monkeypatch.setattr(module, 'MAX_JSON_BYTES', 100)
    with pytest.raises(AgentBomError, match='no changes or findings are truncated'):
        compare_service_contracts(baseline, candidate, plan=plan, traces=traces)


@pytest.mark.parametrize('changed,expected', [(True, 1), (False, 0)])
def test_cli_exit_is_change_review_not_successful_service_or_approval(tmp_path, changed, expected):
    baseline, candidate, plan, traces = inputs()
    if changed:
        candidate['cases'][0]['contract']['recourse_required'] = False
    for name, value in [('baseline', baseline), ('candidate', candidate), ('plan', plan), ('traces', traces)]:
        (tmp_path / f'{name}.json').write_bytes(rendered(value))
    sources = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    args = ['compare-service-contracts', str(tmp_path / 'baseline.json'), str(tmp_path / 'candidate.json'),
            '--plan', str(tmp_path / 'plan.json'), '--traces', str(tmp_path / 'traces.json')]
    report_path = tmp_path / 'report.json'
    assert main([*args, '--out', str(report_path)]) == expected
    assert main([*args, '--verify', str(report_path)]) == expected
    assert main([*args, '--out', str(report_path)]) == 2
    assert all((tmp_path / name).read_bytes() == raw for name, raw in sources.items())
    report = load_json(report_path)
    report['changes'] = [] if changed else [{'invented': True}]
    report_path.write_bytes(rendered(report))
    assert main([*args, '--verify', str(report_path)]) == 2


def test_example_recomputes_controlled_requirement_edits(tmp_path):
    path = ROOT / 'harness/examples/evaluation-review/service_contract_changes.py'
    spec = importlib.util.spec_from_file_location('service_contract_example', path)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    example.create_example(tmp_path / 'demo')
    assert len([p for p in (tmp_path / 'demo').rglob('*') if p.is_file()]) == 21
    for folder in sorted(p for p in (tmp_path / 'demo').iterdir() if p.is_dir()):
        report = compare_service_contracts(load_json(folder / 'baseline-suite.json'), load_json(folder / 'candidate-suite.json'),
                                           plan=load_json(folder / 'plan.json'), traces=load_json(folder / 'traces.json'))
        assert rendered(report) == (folder / 'review.json').read_bytes()
