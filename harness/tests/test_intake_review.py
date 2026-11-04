from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from aau_harness import intake_review as module, eval_csv_review
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_import import import_observations
from aau_harness.eval_pack import create_pack
from aau_harness.inspect_pack import InspectionError, inspect_pack
from aau_harness.evaluation_context import capture_context

# Shared synthetic native-pack fixtures, not production request approval.
from test_inspect_pack import packs as packs


def fixture_request(folder):
    """Test plumbing only: NEVER derive production approval from delivered evidence."""
    inspection = inspect_pack(folder)
    profile = inspection['profile']
    form = ('recordings' if (folder / 'baseline-recording.json').exists() else 'evaluations') if profile == 'evaluation-review' else module.FORMATS[profile]
    roles = module.required_inputs(profile, inspection['pack_version'], form)
    return {'request_version': 'aau-evidence-intake-request/1.0', 'profile': profile,
            'pack_version': inspection['pack_version'], 'input_format': form,
            'pinned_inputs': {role: digest((folder / paths[0]).read_bytes()) for role, paths in roles.items()}}


def review(request, folder):
    raw = rendered(request)
    return module.review_intake(raw, folder, request_sha256=digest(raw))


@pytest.mark.parametrize('name', ['evaluation-1.0', 'evaluation-1.1', 'evaluation-2.0', 'evaluation-3.0',
                                 'csv-False', 'csv-True', 'retry-False', 'retry-True', 'otlp-False', 'otlp-True',
                                 'service-False', 'service-True'])
def test_every_review_version_has_complete_exact_exported_input_bindings(packs, name):
    folder = packs[name]
    request = fixture_request(folder)
    report = review(request, folder)
    assert report == review(request, folder)
    missing_context = name.startswith('csv')  # The existing legacy fixture deliberately declares no context.
    assert report['status'] == ('request_constraints_not_met' if missing_context else 'request_constraints_met')
    assert report['declared_context']['status'] == ('unavailable' if missing_context else 'matched')
    assert report['failed_constraints'] == (['matching_declared_context'] if missing_context else [])
    assert not report['unmatched_input_roles']
    assert all(row['status'] == 'matched' for row in report['control_input_checks'])
    assert report['request_file_sha256'] == digest(rendered(request))
    assert 'SYNTHETIC-PRIVATE-SOURCE-CANARY' not in json.dumps(report)
    assert str(folder) not in json.dumps(report)
    assert report['implementation_sha256']['intake_review.py'] == digest(Path(module.__file__).read_bytes())
    roles = set(request['pinned_inputs'])
    assert {'policy', 'baseline'} <= roles
    if not name.startswith('evaluation'):
        assert {'baseline_plan', 'candidate_plan', 'diagnostics'} <= roles
    if name.startswith('service'):
        suite_rows = [row for row in report['control_input_checks'] if row['role'] == 'service_suite']
        assert [row['member'] for row in suite_rows] == ['baseline/suite.json', 'candidate/suite.json']
    assert ('operating_budget' in roles) == (name.endswith('True') or name == 'evaluation-3.0')


@pytest.mark.parametrize('budgeted', [False, True])
def test_diagnostic_and_budget_versions_also_support_evaluation_sources(tmp_path, budgeted):
    policy, baseline, candidate, diagnostics = demo_inputs()
    budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': policy['scenario_ids'], 'minimum_repeats': 4,
              'criteria': diagnostics['criteria'], 'cost_basis': 'synthetic', 'groups': [], 'limits': {'total_cost_usd': 2}}
    folder = tmp_path / 'pack'
    create_pack(policy, import_observations(baseline), import_observations(candidate), folder,
                diagnostics=diagnostics, operating_budget=budget if budgeted else None)
    request = fixture_request(folder)
    assert request['input_format'] == 'evaluations'
    assert review(request, folder)['status'] == 'request_constraints_met'


@pytest.mark.parametrize('budgeted', [False, True])
def test_csv_with_declared_matching_context_can_satisfy_request(tmp_path, budgeted):
    examples = Path(__file__).resolve().parents[1] / 'examples/evaluation-review'
    plan = load_json(examples / 'csv-plan.json')
    plan['evaluation_context'] = capture_context([{'scenario_id': 'service', 'fixture': True}],
                                                  {'fixture': 'intake-test'}, {'fixture.py': b'synthetic test scoring'})
    diagnostics = load_json(examples / 'csv-review-diagnostics.json')
    budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': plan['scenario_ids'],
              'minimum_repeats': plan['n_repeats'], 'criteria': diagnostics['criteria'],
              'cost_basis': diagnostics['cost_basis']['candidate'], 'groups': [], 'limits': {'total_cost_usd': 100}}
    folder = tmp_path / 'csv'
    eval_csv_review.create_handoff(load_json(examples / 'csv-review-policy.json'), plan,
                                  (examples / 'scored-observations.csv').read_bytes(), plan,
                                  (examples / 'scored-observations-repaired.csv').read_bytes(), diagnostics, folder,
                                  operating_budget=budget if budgeted else None)
    assert review(fixture_request(folder), folder)['status'] == 'request_constraints_met'


def test_relaxed_policy_can_pass_native_verification_but_not_receiving_request(tmp_path, packs):
    policy, baseline, _, diagnostics = demo_inputs()
    baseline = load_json(packs['evaluation-2.0'] / 'baseline-recording.json')
    policy['metrics'][1]['candidate_observation_limit'] = 1
    folder = tmp_path / 'relaxed'
    create_pack(policy, baseline, baseline, folder, recordings=True, diagnostics=diagnostics)
    assert inspect_pack(folder)['assessment']['status'] == 'constraints_met'
    report = review(fixture_request(packs['evaluation-2.0']), folder)
    assert report['status'] == 'request_constraints_not_met'
    assert report['unmatched_input_roles'] == ['policy']
    assert report['failed_constraints'] == []


@pytest.mark.parametrize('name', ['evaluation-3.0', 'csv-True', 'retry-True', 'otlp-True', 'service-True'])
def test_each_required_control_input_pin_is_enforced_without_short_circuiting(packs, name):
    request = fixture_request(packs[name])
    for role in request['pinned_inputs']:
        changed = deepcopy(request)
        changed['pinned_inputs'][role] = '0' * 64
        report = review(changed, packs[name])
        assert report['status'] == 'request_constraints_not_met'
        assert report['unmatched_input_roles'] == [role]
        assert all(row['status'] == ('mismatched' if row['role'] == role else 'matched')
                   for row in report['control_input_checks'])
    request['pinned_inputs'] = dict.fromkeys(request['pinned_inputs'], '0' * 64)
    assert review(request, packs[name])['unmatched_input_roles'] == sorted(request['pinned_inputs'])


@pytest.mark.parametrize('name', ['evaluation-1.0', 'evaluation-1.1', 'csv-review', 'service-challenge', 'csv-source'])
def test_wrong_profile_or_version_is_verified_but_does_not_satisfy_request(packs, name):
    report = review(fixture_request(packs['evaluation-3.0']), packs[name])
    assert report['pack_inspection']['verification_status'] == 'verified'
    assert report['status'] == 'request_constraints_not_met'
    assert 'pack_version' in report['failed_constraints']
    assert all(row['status'] == 'not_checked_profile_mismatch' and row['observed_sha256'] is None
               for row in report['control_input_checks'])


def test_same_version_different_format_is_not_substitutable(tmp_path, packs):
    policy, baseline, candidate, diagnostics = demo_inputs()
    folder = tmp_path / 'pack'
    create_pack(policy, import_observations(baseline), import_observations(candidate), folder, diagnostics=diagnostics)
    report = review(fixture_request(packs['evaluation-2.0']), folder)
    assert 'input_format' in report['failed_constraints']
    assert 'pack_version' not in report['failed_constraints']


@pytest.mark.parametrize('name,status', [('failed', 'constraints_not_met'), ('unknown', 'constraints_not_verified')])
def test_matching_pins_never_promote_failed_policy_or_unknown_budget(packs, name, status):
    report = review(fixture_request(packs[name]), packs[name])
    assert report['status'] == 'request_constraints_not_met'
    assert report['unmatched_input_roles'] == []
    assert report['failed_constraints'] == ['policy_and_any_candidate_budget']
    assert report['pack_inspection']['assessment']['status'] == status


def test_missing_context_stays_descriptive_in_native_tool_but_fails_intake(tmp_path):
    policy, baseline, candidate, diagnostics = demo_inputs()
    for value in (baseline, candidate):
        del value['evaluation_context']
    folder = tmp_path / 'legacy'
    create_pack(policy, baseline, candidate, folder, recordings=True, diagnostics=diagnostics)
    assert inspect_pack(folder)['exit_code'] == 0
    report = review(fixture_request(folder), folder)
    assert report['failed_constraints'] == ['matching_declared_context']
    assert report['declared_context'] == {'status': 'unavailable', 'missing_sources': ['baseline', 'candidate']}


def test_candidate_observations_can_change_but_baseline_bytes_cannot(tmp_path):
    policy, baseline, candidate, diagnostics = demo_inputs()
    first, second, changed_base = (tmp_path / name for name in ('first', 'second', 'changed-base'))
    create_pack(policy, baseline, candidate, first, recordings=True, diagnostics=diagnostics)
    candidate['source_label'] = 'Another valid candidate'
    candidate['observations'][0]['cost_usd'] = 10
    create_pack(policy, baseline, candidate, second, recordings=True, diagnostics=diagnostics)
    request = fixture_request(first)
    assert review(request, second)['status'] == 'request_constraints_met'
    baseline['source_label'] = 'Changed baseline bytes'
    create_pack(policy, baseline, candidate, changed_base, recordings=True, diagnostics=diagnostics)
    assert review(request, changed_base)['unmatched_input_roles'] == ['baseline']
    assert request['pinned_inputs']['policy'] != digest(load_json(first / 'policy.json'))


@pytest.mark.parametrize('defect', ['field', 'version', 'profile', 'format', 'pin_missing', 'pin_extra', 'pin_uppercase',
                                   'pin_type', 'profile_type', 'candidate_pin', 'arbitrary_member', 'pins_type'])
def test_request_schema_is_closed_and_does_not_allow_omitted_requirements(packs, defect):
    request = fixture_request(packs['evaluation-2.0'])
    if defect == 'field':
        request['approved'] = True
    elif defect == 'version':
        request['pack_version'] = 'aau-evaluation-review-pack/99.0'
    elif defect == 'profile':
        request['profile'] = 'service-challenge'
    elif defect == 'format':
        request['input_format'] = 'csv'
    elif defect == 'pin_missing':
        del request['pinned_inputs']['policy']
    elif defect in ('pin_extra', 'candidate_pin', 'arbitrary_member'):
        request['pinned_inputs'][{'pin_extra': 'extra', 'candidate_pin': 'candidate', 'arbitrary_member': '../secret'}[defect]] = '0' * 64
    elif defect == 'pin_uppercase':
        request['pinned_inputs']['policy'] = 'A' * 64
    elif defect == 'pin_type':
        request['pinned_inputs']['policy'] = 1
    elif defect == 'profile_type':
        request['profile'] = []
    else:
        request['pinned_inputs'] = []
    with pytest.raises(InspectionError):
        review(request, packs['evaluation-2.0'])


@pytest.mark.parametrize('raw', [b'', b'[]', b'{"secret":1,"secret":2}', b'{"x":NaN}', b'\xff', b'x' * (MAX_JSON_BYTES + 1)],
                         ids=['empty', 'array', 'duplicate_key', 'nonfinite', 'invalid_utf8', 'oversized'])
def test_invalid_request_bytes_never_enter_pack_inspection(tmp_path, monkeypatch, raw):
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid request must be rejected first')
    monkeypatch.setattr(module, 'inspect_pack', forbidden)
    with pytest.raises(InspectionError):
        module.review_intake(raw, tmp_path, request_sha256=digest(raw))


@pytest.mark.parametrize('bad_pin', ['0' * 64, 'A' * 64, '', None, True])
def test_expected_request_pin_is_checked_before_parsing_or_reading_evidence(tmp_path, monkeypatch, bad_pin):
    def forbidden(*args, **kwargs):
        raise AssertionError('incorrect pin must be rejected first')
    monkeypatch.setattr(module, '_parse_json', forbidden)
    monkeypatch.setattr(module, 'inspect_pack', forbidden)
    with pytest.raises(InspectionError, match='request_byte_pin_mismatch'):
        module.review_intake(b'not JSON', tmp_path, request_sha256=bad_pin)


@pytest.mark.parametrize('mutation', ['file', 'empty_directory'])
def test_second_capture_must_match_fully_verified_inventory(tmp_path, packs, monkeypatch, mutation):
    folder = tmp_path / 'pack'
    shutil.copytree(packs['evaluation-2.0'], folder)
    request = fixture_request(folder)
    original = module.inspect_pack
    def mutate_after_verification(path):
        result = original(path)
        if mutation == 'file':
            (path / 'policy.json').write_bytes(b'{}')
        else:
            (path / 'empty').mkdir()
        return result
    monkeypatch.setattr(module, 'inspect_pack', mutate_after_verification)
    with pytest.raises(InspectionError, match='pack_changed_after_inspection'):
        review(request, folder)


def test_invalid_parent_never_uses_valid_nested_review(tmp_path, packs):
    folder = tmp_path / 'pack'
    shutil.copytree(packs['otlp-review'], folder)
    request = fixture_request(folder)
    (folder / 'candidate/source.otlp').write_bytes(b'{}')
    assert inspect_pack(folder / 'review')['exit_code'] == 0
    with pytest.raises(InspectionError, match='full_verification_failed'):
        review(request, folder)


def test_cli_success_failure_invalid_reverification_no_overwrite_and_private_errors(tmp_path, packs, capsys):
    request_file = tmp_path / 'request.json'
    raw = rendered(fixture_request(packs['evaluation-2.0']))
    request_file.write_bytes(raw)
    prefix = ['review-intake', str(request_file)]
    suffix = ['--request-sha256', digest(raw)]
    output = tmp_path / 'report.json'
    args = [*prefix, str(packs['evaluation-2.0']), *suffix]
    assert main([*args, '--out', str(output)]) == 0
    assert main([*args, '--verify', str(output)]) == 0
    assert main([*args, '--out', str(output)]) == 2
    assert main([*args, '--out', str(packs['evaluation-2.0'] / 'report.json')]) == 2
    assert main([*prefix, str(packs['failed']), *suffix, '--out', str(tmp_path / 'failed.json')]) == 1
    assert main([*prefix, str(packs['failed']), *suffix, '--verify', str(tmp_path / 'failed.json')]) == 1
    assert main([*prefix, str(packs['evaluation-1.0']), *suffix, '--verify', str(output)]) == 2
    request_file.write_bytes(raw + b' ')
    assert main([*args, '--out', str(tmp_path / 'invalid.json')]) == 2
    assert not (tmp_path / 'invalid.json').exists()
    request_file.write_bytes(b'{"PRIVATE-KEY":1,"PRIVATE-KEY":2}')
    assert main([*prefix, str(tmp_path / 'PRIVATE-PATH'), '--request-sha256', digest(request_file.read_bytes()),
                 '--out', str(tmp_path / 'invalid.json')]) == 2
    output_text = capsys.readouterr()
    assert 'PRIVATE-KEY' not in output_text.out + output_text.err
    assert 'PRIVATE-PATH' not in output_text.out + output_text.err


def test_request_file_symlink_is_rejected(tmp_path, packs):
    request = tmp_path / 'request.json'
    raw = rendered(fixture_request(packs['evaluation-2.0']))
    request.write_bytes(raw)
    link = tmp_path / 'link.json'
    link.symlink_to(request)
    assert main(['review-intake', str(link), str(packs['evaluation-2.0']), '--request-sha256', digest(raw),
                 '--out', str(tmp_path / 'report.json')]) == 2
