from copy import deepcopy
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
from xml.etree import ElementTree as ET

import pytest

from aau_harness import evidence_ci as module
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_pack import create_pack
from aau_harness.inspect_pack import InspectionError

from test_inspect_pack import packs as packs
from test_intake_review import fixture_request
from test_evidence_series import fixtures as fixtures, history


def export(request, directory, out, **kwargs):
    return module.export_ci(request, directory, request_sha256=digest(request), out=out, **kwargs)


def assert_xml(bundle, report):
    root = ET.fromstring((bundle / 'junit.xml').read_bytes())
    assert root.tag == 'testsuites'
    tests = root.findall('.//testcase')
    assert len(tests) == report['counts']['tests']
    assert len({test.attrib['name'] for test in tests}) == len(tests)
    for node, counts in [(root, report['counts']), *zip(root.findall('testsuite'), [s['counts'] for s in report['suites']])]:
        for key, value in counts.items():
            assert node.attrib[key] == str(value)
        assert len(node.findall('.//testcase')) == counts['tests']
        assert len(node.findall('.//failure')) == counts['failures']
        assert len(node.findall('.//error')) == counts['errors']
    assert not root.findall('.//skipped')
    assert not root.findall('.//system-out') and not root.findall('.//system-err')
    assert all('time' not in node.attrib and 'timestamp' not in node.attrib for node in root.iter())
    assert all(len(test.findall('failure')) + len(test.findall('error')) <= 1 for test in tests)
    assert all(node.text for node in root.findall('.//failure') + root.findall('.//error'))
    assert {p.attrib['value'] for p in root.findall('.//property') if p.attrib['name'] == 'report_sha256'} == {digest(rendered(report))}
    assert (report['exit_code'] == 0) == (report['counts']['errors'] + report['counts']['failures'] == 0)


@pytest.mark.parametrize('mode', ['intake', 'series'])
@pytest.mark.parametrize('name', ['evaluation-1.0', 'evaluation-1.1', 'evaluation-2.0', 'evaluation-3.0',
                                 'csv-False', 'csv-True', 'retry-False', 'retry-True', 'otlp-False', 'otlp-True',
                                 'service-False', 'service-True'])
def test_every_review_version_recomputes_full_bundle(tmp_path, packs, name, mode):
    source = packs[name]
    request = rendered(fixture_request(source))  # Test-only plumbing, not production approval.
    kwargs = {}
    if mode == 'series':
        for checkpoint in ('private-checkpoint-canary', 'later'):
            shutil.copytree(source, tmp_path / 'history' / checkpoint)
        source = tmp_path / 'history'
        plan = rendered({'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ['private-checkpoint-canary', 'later']})
        kwargs = {'plan_raw': plan, 'plan_sha256': digest(plan)}
    bundle = tmp_path / 'ci'
    report = export(request, source, bundle, **kwargs)
    assert report == module.export_ci(request, source, request_sha256=digest(request), verify=bundle, **kwargs)
    assert report['exit_code'] == (1 if name.startswith('csv') else 0)
    assert report['mode'] == mode
    assert set(p.name for p in bundle.iterdir()) == {'manifest.json', 'report.json', 'junit.xml', 'summary.md'}
    assert_xml(bundle, report)
    for filename in ('junit.xml', 'summary.md'):
        text = (bundle / filename).read_text()
        assert 'private-checkpoint-canary' not in text and str(source) not in text
        assert 'SYNTHETIC-PRIVATE-SOURCE-CANARY' not in text
    if mode == 'series':
        assert 'private-checkpoint-canary' in (bundle / 'report.json').read_text()
    assert report['implementation_sha256']['evidence_ci.py'] == digest(Path(module.__file__).read_bytes())


@pytest.mark.parametrize('name,code,failures,errors', [
    ('passed', 0, 0, 0), ('failed', 1, 1, 0), ('unknown', 1, 0, 1), ('expensive', 1, 1, 0),
    ('changed-policy', 1, 1, 0), ('changed-baseline', 1, 1, 0), ('downgraded', 1, 1, 6),
])
def test_policy_budget_context_and_pin_outcomes_are_not_promoted(tmp_path, fixtures, name, code, failures, errors):
    root, request = fixtures
    report = export(request, root / name, tmp_path / 'ci')
    assert report['exit_code'] == code
    assert report['counts']['failures'] == failures and report['counts']['errors'] == errors
    assert_xml(tmp_path / 'ci', report)


def test_failed_policy_never_hides_unknown_budget(tmp_path, fixtures):
    root, request = fixtures
    policy, baseline, _, diagnostics = demo_inputs()
    baseline = load_json(root / 'passed/baseline-recording.json')
    candidate = deepcopy(baseline)
    del candidate['observations'][0]['cost_usd']
    create_pack(policy, baseline, candidate, tmp_path / 'source', recordings=True, diagnostics=diagnostics,
                operating_budget=load_json(root / 'passed/operating-budget.json'))
    report = export(request, tmp_path / 'source', tmp_path / 'ci')
    outcomes = {row['name']: row['outcome'] for row in report['suites'][0]['cases']}
    assert outcomes['policy-outcome'] == 'failure'
    assert outcomes['candidate-budget-outcome'] == 'error'
    assert report['exit_code'] == 1
    assert_xml(tmp_path / 'ci', report)


@pytest.mark.parametrize('middle,code', [('passed', 0), ('failed', 1), ('unknown', 1), ('changed-policy', 1), ('missing', 1), ('invalid', 2)])
def test_later_pass_does_not_hide_earlier_checks(tmp_path, fixtures, middle, code):
    plan, request, root = history(tmp_path, fixtures, ['passed', middle, 'passed'])
    report = export(request, root, tmp_path / 'ci', plan_raw=plan, plan_sha256=digest(plan))
    assert report['exit_code'] == code
    assert report['native_review']['latest_checkpoint']['status'] == 'request_constraints_met'
    assert len(report['suites']) == 3
    if middle in ('missing', 'invalid'):
        assert report['suites'][1]['counts'] == {'tests': 1, 'errors': 1, 'failures': 0, 'skipped': 0}
    assert_xml(tmp_path / 'ci', report)


@pytest.mark.parametrize('name', ['service-challenge', 'csv-source', 'failure-bounds'])
def test_verified_nondecision_evidence_is_not_a_green_ci_gate(tmp_path, packs, name):
    request = rendered(fixture_request(packs['evaluation-3.0']))
    report = export(request, packs[name], tmp_path / 'ci')
    assert report['exit_code'] == 1
    assert report['counts']['errors'] and report['counts']['failures']
    assert_xml(tmp_path / 'ci', report)


@pytest.mark.parametrize('defect', ['missing', 'malformed', 'symlink'])
def test_invalid_intake_produces_error_artifact_but_never_binds_invalid_bytes(tmp_path, fixtures, defect):
    root, request = fixtures
    source = tmp_path / 'source'
    if defect == 'malformed':
        source.mkdir()
        (source / 'manifest.json').write_bytes(b'{}')
    elif defect == 'symlink':
        source.symlink_to(root / 'passed', target_is_directory=True)
    report = export(request, source, tmp_path / 'ci')
    assert report['exit_code'] == 2 and report['native_review'] is None
    assert not report['invalid_evidence_bytes_bound']
    assert report['counts'] == {'tests': 1, 'errors': 1, 'failures': 0, 'skipped': 0}
    if defect == 'malformed':
        (source / 'manifest.json').write_bytes(b'other invalid bytes')
        # Same diagnostic is not a claim of byte identity for evidence that never verified.
        assert module.export_ci(request, source, request_sha256=digest(request), verify=tmp_path / 'ci') == report
    assert_xml(tmp_path / 'ci', report)


@pytest.mark.parametrize('defect', ['pin', 'request', 'plan_pin', 'plan', 'missing_plan_pin'])
def test_invalid_controls_are_rejected_before_evidence_or_artifact_creation(tmp_path, fixtures, monkeypatch, defect):
    _, request = fixtures
    plan = rendered({'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ['first', 'second']})
    request_pin, plan_pin = digest(request), digest(plan)
    if defect == 'pin':
        request_pin = '0' * 64
    elif defect == 'request':
        request = b'{}'
        request_pin = digest(request)
    elif defect == 'plan_pin':
        plan_pin = '0' * 64
    elif defect == 'plan':
        plan = b'{}'
        plan_pin = digest(plan)
    else:
        plan_pin = None
    def forbidden(*args, **kwargs):
        pytest.fail('Evidence must not be read with invalid controls')
    monkeypatch.setattr(module, 'review_intake', forbidden)
    monkeypatch.setattr(module, 'review_series', forbidden)
    with pytest.raises(ValueError):
        module.export_ci(request, tmp_path / 'source', request_sha256=request_pin, plan_raw=plan, plan_sha256=plan_pin, out=tmp_path / 'ci')
    assert not (tmp_path / 'ci').exists()


@pytest.mark.parametrize('member', ['report.json', 'junit.xml', 'summary.md', 'manifest.json'])
def test_manifest_rehash_cannot_bless_modified_presentation(tmp_path, fixtures, member):
    root, request = fixtures
    bundle = tmp_path / 'ci'
    export(request, root / 'passed', bundle)
    path = bundle / member
    path.write_bytes(path.read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = load_json(bundle / 'manifest.json')
        manifest['files_sha256'][member] = digest(path.read_bytes())
        (bundle / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(InspectionError, match='does_not_recompute'):
        module.export_ci(request, root / 'passed', request_sha256=digest(request), verify=bundle)


@pytest.mark.parametrize('defect', ['extra', 'missing', 'directory', 'symlink', 'fifo', 'oversized', 'root_link'])
def test_exact_regular_bounded_bundle_required(tmp_path, fixtures, defect):
    root, request = fixtures
    bundle = tmp_path / 'ci'
    export(request, root / 'passed', bundle)
    if defect == 'extra':
        (bundle / 'extra.txt').write_bytes(b'extra')
    elif defect == 'directory':
        (bundle / 'empty').mkdir()
    elif defect == 'root_link':
        (tmp_path / 'link').symlink_to(bundle, target_is_directory=True)
        bundle = tmp_path / 'link'
    else:
        (bundle / 'junit.xml').unlink()
        if defect == 'symlink':
            (bundle / 'junit.xml').symlink_to(bundle / 'summary.md')
        elif defect == 'fifo':
            if not hasattr(os, 'mkfifo'):
                pytest.skip('FIFO unavailable')
            os.mkfifo(bundle / 'junit.xml')
        elif defect == 'oversized':
            (bundle / 'junit.xml').write_bytes(b' ' * (MAX_JSON_BYTES + 1))
    with pytest.raises(InspectionError):
        module.export_ci(request, root / 'passed', request_sha256=digest(request), verify=bundle)


def test_changed_full_source_is_detected_even_when_controls_still_match(tmp_path, fixtures):
    root, request = fixtures
    source = tmp_path / 'source'
    shutil.copytree(root / 'passed', source)
    bundle = tmp_path / 'ci'
    export(request, source, bundle)
    (source / 'candidate-recording.json').write_bytes(b'{}')
    with pytest.raises(InspectionError, match='does_not_recompute'):
        module.export_ci(request, source, request_sha256=digest(request), verify=bundle)


def test_valid_changed_candidate_with_same_verdict_cannot_replay_old_bundle(tmp_path, fixtures):
    root, request = fixtures
    bundle = tmp_path / 'ci'
    original = export(request, root / 'passed', bundle)
    policy, baseline, candidate, diagnostics = demo_inputs()
    baseline = load_json(root / 'passed/baseline-recording.json')
    candidate['source_label'] = 'PRIVATE<&\x00-CANDIDATE'
    candidate['observations'][0]['cost_usd'] = 0.1
    source = tmp_path / 'changed'
    create_pack(policy, baseline, candidate, source, recordings=True, diagnostics=diagnostics,
                operating_budget=load_json(root / 'passed/operating-budget.json'))
    changed = module.review_ci(request, source, request_sha256=digest(request))
    assert original['exit_code'] == changed['exit_code'] == 0
    with pytest.raises(InspectionError, match='does_not_recompute'):
        module.export_ci(request, source, request_sha256=digest(request), verify=bundle)
    changed_bundle = tmp_path / 'new-ci'
    export(request, source, changed_bundle)
    for name in ('junit.xml', 'summary.md'):
        assert 'PRIVATE' not in (changed_bundle / name).read_text()
    assert_xml(changed_bundle, changed)


@pytest.mark.parametrize('defect', ['bad_controls', 'unexpected_root'])
def test_invalid_series_root_or_controls_do_not_emit_a_diagnostic_bundle(tmp_path, fixtures, defect):
    plan, request, root = history(tmp_path, fixtures, ['passed', 'passed'])
    if defect == 'bad_controls':
        plan = b'{"SECRET-KEY":1,"SECRET-KEY":2}'
    else:
        (root / 'unexpected').write_bytes(b'not a declared checkpoint')
    (tmp_path / 'plan.json').write_bytes(plan)
    (tmp_path / 'request.json').write_bytes(request)
    assert main(['review-ci', 'series', str(tmp_path / 'plan.json'), str(tmp_path / 'request.json'), str(root),
                 '--request-sha256', digest(request), '--plan-sha256', digest(plan), '--out', str(tmp_path / 'ci')]) == 2
    assert not (tmp_path / 'ci').exists()


@pytest.mark.parametrize('middle,code', [('passed', 0), ('failed', 1), ('missing', 1), ('invalid', 2)])
def test_series_cli_replays_all_outcomes(tmp_path, fixtures, middle, code):
    plan, request, root = history(tmp_path, fixtures, ['passed', middle, 'passed'])
    (tmp_path / 'plan.json').write_bytes(plan)
    (tmp_path / 'request.json').write_bytes(request)
    command = ['review-ci', 'series', str(tmp_path / 'plan.json'), str(tmp_path / 'request.json'), str(root),
               '--request-sha256', digest(request), '--plan-sha256', digest(plan)]
    assert main([*command, '--out', str(tmp_path / 'ci')]) == code
    assert main([*command, '--verify', str(tmp_path / 'ci')]) == code


def test_composed_report_is_bounded_before_any_output(tmp_path, fixtures, monkeypatch):
    root, request = fixtures
    native = module.review_intake(request, root / 'passed', request_sha256=digest(request))
    native['boundary'] = 'x' * MAX_JSON_BYTES
    monkeypatch.setattr(module, 'review_intake', lambda *a, **kw: native)
    with pytest.raises(InspectionError, match='ci_report_exceeds_limit'):
        export(request, root / 'passed', tmp_path / 'ci')
    assert not (tmp_path / 'ci').exists()


def test_six_synthetic_adoption_contrasts_replay_and_parse(tmp_path):
    example = Path(__file__).resolve().parents[1] / 'examples/evaluation-review/ci_reporting.py'
    expected = runpy.run_path(str(example))['create_example'](tmp_path / 'walkthrough')
    assert expected == {'passed': 0, 'failed': 1, 'unknown': 1, 'substituted': 1, 'invalid': 2, 'history': 1}
    root = tmp_path / 'walkthrough'
    for name, code in expected.items():
        report = load_json(root / 'reports' / name / 'report.json')
        assert report['exit_code'] == code
        assert_xml(root / 'reports' / name, report)
    assert (root / 'README.txt').is_file()
    with pytest.raises(FileExistsError):
        runpy.run_path(str(example))['create_example'](root)


def test_existing_and_nested_output_rejected(tmp_path, fixtures):
    root, request = fixtures
    bundle = tmp_path / 'ci'
    export(request, root / 'passed', bundle)
    before = {p.name: p.read_bytes() for p in bundle.iterdir()}
    with pytest.raises(InspectionError, match='already_exists'):
        export(request, root / 'passed', bundle)
    assert before == {p.name: p.read_bytes() for p in bundle.iterdir()}
    with pytest.raises(InspectionError, match='outside_evidence'):
        export(request, root / 'passed', root / 'passed' / 'new')


@pytest.mark.parametrize('name,code', [('passed', 0), ('failed', 1), ('unknown', 1), ('absent', 2)])
def test_cli_exit_and_verification_preserve_native_outcomes(tmp_path, fixtures, name, code, capsys):
    root, request = fixtures
    request_path = tmp_path / 'request.json'
    request_path.write_bytes(request)
    command = ['review-ci', 'intake', str(request_path), str(root / name), '--request-sha256', digest(request)]
    assert main([*command, '--out', str(tmp_path / 'ci')]) == code
    assert main([*command, '--verify', str(tmp_path / 'ci')]) == code
    assert 'Not deployment approval' in capsys.readouterr().out
    request_path.write_bytes(request + b' ')
    assert main([*command, '--out', str(tmp_path / 'other')]) == 2
    assert not (tmp_path / 'other').exists()


def test_no_adapter_subprocess_or_network_is_executed(tmp_path, fixtures, monkeypatch):
    root, request = fixtures
    def forbidden(*args, **kwargs):
        pytest.fail('CI presentation must remain offline and not execute adapters')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    report = export(request, root / 'passed', tmp_path / 'ci')
    assert report['exit_code'] == 0
    assert 'PRIVATE-SOURCE-CANARY' not in json.dumps(report)
