from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess

import pytest

from aau_harness.agent_bom import digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness import inspect_pack as module
from aau_harness import eval_csv_review, eval_demo, eval_failure_demo, eval_failure_pack, eval_otlp_review
from aau_harness import eval_retry_demo, eval_retry_review, eval_service_review, service_challenge, service_reproducer
from aau_harness.eval_pack import create_pack
from aau_harness.eval_import import import_observations


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'harness/examples/evaluation-review'


def example(name):
    spec = importlib.util.spec_from_file_location(f'intake_{name}', EXAMPLES / f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture(scope='module')
def packs(tmp_path_factory):
    root = tmp_path_factory.mktemp('pack-inspection-fixtures')
    paths = {}
    policy, baseline, candidate, diagnostics = eval_demo.demo_inputs()
    baseline['source_label'] = candidate['source_label'] = 'SYNTHETIC-PRIVATE-SOURCE-CANARY'
    for version in ('1.0', '1.1', '2.0', '3.0'):
        recordings = version != '1.0'
        args = (baseline, candidate) if recordings else (import_observations(baseline), import_observations(candidate))
        budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': policy['scenario_ids'], 'minimum_repeats': 4,
                  'criteria': diagnostics['criteria'], 'cost_basis': 'synthetic', 'groups': [], 'limits': {'total_cost_usd': 2}}
        folder = root / f'evaluation-{version}'
        create_pack(policy, *args, folder, recordings=recordings, diagnostics=diagnostics if version in ('2.0', '3.0') else None,
                    operating_budget=budget if version == '3.0' else None)
        paths[f'evaluation-{version}'] = folder
    paths['evaluation-review'] = paths['evaluation-3.0']
    create_pack(policy, baseline, baseline, root / 'failed', recordings=True, diagnostics=diagnostics)
    paths['failed'] = root / 'failed'
    unknown = deepcopy(candidate)
    del unknown['observations'][0]['cost_usd']
    create_pack(policy, baseline, unknown, root / 'unknown', recordings=True, diagnostics=diagnostics, operating_budget=budget)
    paths['unknown'] = root / 'unknown'
    plan = load_json(EXAMPLES / 'csv-plan.json')
    for gated in (False, True):
        csv_budget = {'plan_version': 'aau-operating-budget/1.0',
                      'scenario_ids': plan['scenario_ids'], 'minimum_repeats': plan['n_repeats'],
                      'criteria': load_json(EXAMPLES / 'csv-review-diagnostics.json')['criteria'],
                      'cost_basis': 'synthetic', 'groups': [], 'limits': {'total_cost_usd': 100}}
        csv_diagnostics = load_json(EXAMPLES / 'csv-review-diagnostics.json')
        csv_budget['cost_basis'] = csv_diagnostics['cost_basis']['candidate']
        folder = root / f'csv-{gated}'
        eval_csv_review.create_handoff(load_json(EXAMPLES / 'csv-review-policy.json'), plan,
                                      (EXAMPLES / 'scored-observations.csv').read_bytes(), plan,
                                      (EXAMPLES / 'scored-observations-repaired.csv').read_bytes(), csv_diagnostics, folder,
                                      operating_budget=csv_budget if gated else None)
        paths[f'csv-{gated}'] = folder
        retry_policy, retry_plan, ledger, retry_diag, retry_budget, candidates = eval_retry_demo.demo_inputs()
        folder = root / f'retry-{gated}'
        eval_retry_review.create_handoff(retry_policy, retry_plan, ledger, retry_plan, candidates['repaired'], retry_diag, folder,
                                        operating_budget=retry_budget if gated else None)
        paths[f'retry-{gated}'] = folder
        args, otlp_budget = example('otlp_handoff').inputs()
        folder = root / f'otlp-{gated}'
        eval_otlp_review.create_handoff(*args, folder, operating_budget=otlp_budget if gated else None)
        paths[f'otlp-{gated}'] = folder
        svc_plan, suite, traces, burden, svc_policy, svc_diag, svc_budget = example('service_traces').example_inputs()
        folder = root / f'service-{gated}'
        eval_service_review.create_handoff(svc_policy, svc_plan, traces, svc_plan, traces, svc_diag, folder,
                                          service_suite=suite, operating_budget=svc_budget if gated else None)
        paths[f'service-{gated}'] = folder
    for family in ('csv', 'retry', 'otlp', 'service'):
        paths[f'{family}-review'] = paths[f'{family}-True']
        paths['service-traces' if family == 'service' else f'{family}-source'] = paths[f'{family}-True'] / 'baseline'
    paths['service-challenge'] = root / 'challenge'
    service_challenge.create_challenge(suite, paths['service-challenge'])
    paths['service-reproducer'] = root / 'reproducer'
    service_reproducer.create_reproducer(svc_plan, suite, burden, paths['service-reproducer'])
    for name in ('fixed-benchmark', 'few-scenarios'):
        paths[name] = root / name
        eval_failure_pack.create_failure_bound_pack(*eval_failure_demo.example_inputs()[name], paths[name])
    paths['failure-bounds'] = paths['few-scenarios']
    return paths


@pytest.mark.parametrize('profile', sorted(module.PROFILES))
def test_every_supported_family_is_fully_verified_without_copying_source_labels(packs, profile):
    folder = packs[profile]
    report = module.inspect_pack(folder, expect=profile)
    assert report == module.inspect_pack(folder, expect=profile)
    assert report['verification_status'] == 'verified' and report['profile'] == profile
    assert report['file_count'] == len([p for p in folder.rglob('*') if p.is_file()])
    assert report['captured_files_sha256'] == {
        p.relative_to(folder).as_posix(): digest(p.read_bytes()) for p in folder.rglob('*') if p.is_file()}
    assert report['captured_inventory_sha256'] == digest(report['captured_files_sha256'])
    assert (folder / report['read_after_verification']).is_file()
    assert report['inspector_sha256'] == digest(Path(module.__file__).read_bytes())
    assert 'SYNTHETIC-PRIVATE-SOURCE-CANARY' not in json.dumps(report)
    assert str(folder) not in json.dumps(report)
    assert report['exit_code'] == (1 if profile == 'service-reproducer' else 0)
    if profile.endswith('-source'):
        assert report['assessment']['kind'] == 'not_assessed' and report['assessment']['status'] == 'conversion_only'
    if profile == 'service-challenge':
        assert report['assessment']['status'] == 'adapter_responses_not_supplied'
    if profile == 'failure-bounds':
        assert report['assessment']['kind'] == 'diagnostic_not_a_gate'
        assert report['assessment']['status'] == 'conditional_bounds_exceed_limits'


@pytest.mark.parametrize('version', ['1.0', '1.1', '2.0', '3.0'])
def test_every_supported_review_version_and_budget_requirement(packs, version):
    folder = packs[f'evaluation-{version}']
    result = module.inspect_pack(folder)
    assert result['pack_version'] == f'aau-evaluation-review-pack/{version}'
    if version == '3.0':
        assert module.inspect_pack(folder, require_budget=True)['assessment']['candidate_budget_status'] == 'constraints_met'
    else:
        assert result['assessment']['candidate_budget_status'] is None
        with pytest.raises(module.InspectionError, match='full_verification_failed'):
            module.inspect_pack(folder, require_budget=True)


@pytest.mark.parametrize('family', ['csv', 'retry', 'otlp', 'service'])
@pytest.mark.parametrize('gated', [False, True])
def test_every_handoff_version_is_routed_without_weakening_budget_gates(packs, family, gated):
    report = module.inspect_pack(packs[f'{family}-{gated}'], expect=f'{family}-review')
    assert report['assessment']['kind'] == ('supplied_policy_and_candidate_budget' if gated else 'supplied_policy')
    assert ('--require-budget' in report['specific_verification_argv']) == gated
    if gated:
        assert module.inspect_pack(packs[f'{family}-{gated}'], require_budget=True)['exit_code'] == 0
    else:
        with pytest.raises(module.InspectionError):
            module.inspect_pack(packs[f'{family}-{gated}'], require_budget=True)


@pytest.mark.parametrize('name,status,kind,code', [
    ('failed', 'constraints_not_met', 'supplied_policy', 1),
    ('unknown', 'constraints_not_verified', 'supplied_policy_and_candidate_budget', 1),
    ('fixed-benchmark', 'population_inference_withheld', 'diagnostic_not_a_gate', 0),
    ('service-reproducer', 'evidence_failed', 'supplied_service_obligations', 1),
])
def test_failed_unknown_and_non_decision_results_are_not_promoted(packs, name, status, kind, code):
    result = module.inspect_pack(packs[name])
    assert result['verification_status'] == 'verified' and result['exit_code'] == code
    assert result['assessment']['status'] == status and result['assessment']['kind'] == kind
    if name == 'unknown':
        assert result['assessment']['policy_status'] == 'constraints_met'
        assert result['assessment']['candidate_budget_status'] == 'constraints_not_verified'


@pytest.mark.parametrize('profile', sorted(module.PROFILES))
def test_expected_profile_prevents_substitution_and_budget_rejects_non_review_packs(packs, profile):
    other = 'csv-source' if profile != 'csv-source' else 'service-challenge'
    with pytest.raises(module.InspectionError, match='unexpected_pack_profile'):
        module.inspect_pack(packs[profile], expect=other)
    if module.PROFILES[profile][3] != 'review':
        with pytest.raises(module.InspectionError, match='budget_layer_not_supported'):
            module.inspect_pack(packs[profile], require_budget=True)


@pytest.mark.parametrize('profile', sorted(module.PROFILES))
def test_every_dispatch_recomputes_tampered_evidence_instead_of_trusting_manifest_hashes(tmp_path, packs, profile):
    folder = tmp_path / 'pack'
    shutil.copytree(packs[profile], folder)
    target = folder / module.PROFILES[profile][5]
    target.write_bytes(target.read_bytes() + b' ')
    manifest = load_json(folder / 'manifest.json')
    manifest['files'][target.relative_to(folder).as_posix()] = digest(target.read_bytes())
    (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(module.InspectionError, match='full_verification_failed'):
        module.inspect_pack(folder)


def test_invalid_parent_does_not_fall_back_to_valid_nested_review(tmp_path, packs):
    folder = tmp_path / 'pack'
    shutil.copytree(packs['otlp-review'], folder)
    (folder / 'candidate/source.otlp').write_bytes(b'{}')
    with pytest.raises(module.InspectionError, match='full_verification_failed'):
        module.inspect_pack(folder)
    assert module.inspect_pack(folder / 'review')['profile'] == 'evaluation-review'
    with pytest.raises(module.InspectionError, match='unexpected_pack_profile'):
        module.inspect_pack(folder / 'review', expect='otlp-review')


def test_local_copy_is_used_cleaned_and_bound_without_claiming_live_atomicity(tmp_path, packs, monkeypatch):
    folder = tmp_path / 'pack'
    shutil.copytree(packs['service-challenge'], folder)
    profile = module.PROFILES['service-challenge']
    verifier, snapshots = profile[2], []
    original_digest = digest((folder / 'README.txt').read_bytes())

    def observed(snapshot):
        snapshots.append(snapshot)
        assert snapshot != folder
        (folder / 'README.txt').write_text('Changed after capture')
        return verifier(snapshot)

    monkeypatch.setitem(module.PROFILES, 'service-challenge', (*profile[:2], observed, *profile[3:]))
    report = module.inspect_pack(folder)
    assert report['captured_files_sha256']['README.txt'] == original_digest
    assert not snapshots[0].exists()
    assert 'not an atomic capture' in report['boundary']


@pytest.mark.parametrize('defect', ['extra_empty_directory', 'extra_file', 'symlink', 'root_symlink', 'nested_symlink',
                                   'oversized', 'too_many_files', 'too_deep', 'too_many_directories', 'bad_name',
                                   'no_manifest', 'unknown_version', 'malformed_manifest', 'archive', 'fifo'])
def test_untrusted_filesystem_and_format_inputs_fail_closed(tmp_path, packs, defect):
    folder = tmp_path / 'pack'
    shutil.copytree(packs['service-reproducer'], folder)
    if defect == 'extra_empty_directory':
        (folder / 'empty').mkdir()
    elif defect == 'extra_file':
        (folder / 'execute.py').write_text('raise RuntimeError("must never run")')
    elif defect == 'symlink':
        (folder / 'README.txt').unlink()
        (folder / 'README.txt').symlink_to(folder / 'reproduction.json')
    elif defect == 'root_symlink':
        link = tmp_path / 'link'
        link.symlink_to(folder, target_is_directory=True)
        folder = link
    elif defect == 'nested_symlink':
        (folder / 'service').rename(tmp_path / 'elsewhere')
        (folder / 'service').symlink_to(tmp_path / 'elsewhere', target_is_directory=True)
    elif defect == 'oversized':
        (folder / 'README.txt').write_bytes(b'x' * (module.MAX_JSON_BYTES + 1))
    elif defect == 'too_many_files':
        for i in range(module.MAX_FILES + 1):
            (folder / f'extra-{i}').write_text('x')
    elif defect == 'too_deep':
        (folder / 'a/b/c/d').mkdir(parents=True)
    elif defect == 'too_many_directories':
        for i in range(module.MAX_DIRECTORIES):
            (folder / f'dir-{i}').mkdir()
    elif defect == 'bad_name':
        (folder / 'SENSITIVE NAME').write_text('x')
    elif defect == 'no_manifest':
        (folder / 'manifest.json').unlink()
    elif defect == 'unknown_version':
        (folder / 'manifest.json').write_text('{"pack_version":"SENSITIVE-plugin:execute"}')
    elif defect == 'malformed_manifest':
        (folder / 'manifest.json').write_text('{"secret":1,"secret":2}')
    elif defect == 'archive':
        folder = tmp_path / 'pack.zip'
        folder.write_bytes(b'not expanded')
    else:
        if not hasattr(os, 'mkfifo'):
            pytest.skip('FIFO not available on this platform')
        os.mkfifo(folder / 'pipe')
    with pytest.raises(module.InspectionError):
        module.inspect_pack(folder)


def test_total_byte_limit_and_invalid_api_requirements(packs, monkeypatch):
    monkeypatch.setattr(module, 'MAX_TOTAL_BYTES', 1)
    with pytest.raises(module.InspectionError, match='pack_resource_limit'):
        module.inspect_pack(packs['service-challenge'])
    with pytest.raises(module.InspectionError, match='unsupported_expected_profile'):
        module.inspect_pack(packs['service-challenge'], expect='arbitrary-plugin')
    with pytest.raises(module.InspectionError, match='invalid_budget_requirement'):
        module.inspect_pack(packs['service-challenge'], require_budget=1)


def test_no_subprocess_or_network_is_used(packs, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('intake must not execute adapters, commands, or network requests')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    for profile in module.PROFILES:
        assert module.inspect_pack(packs[profile])['verification_status'] == 'verified'


def test_cli_preserves_failure_exit_codes_verifies_reports_and_never_modifies_the_pack(tmp_path, packs, capsys):
    folder = packs['failed']
    output = tmp_path / 'inspection.json'
    args = ['inspect-pack', str(folder), '--expect', 'evaluation-review']
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    assert main([*args, '--out', str(output)]) == 1
    assert main([*args, '--verify', str(output)]) == 1
    assert main([*args, '--out', str(output)]) == 2
    assert main([*args, '--out', str(folder / 'inspection.json')]) == 2
    assert main(['inspect-pack', str(folder), '--verify', str(output)]) == 2  # Requirement binding also matters.
    assert before == {p.name: p.read_bytes() for p in folder.iterdir()}
    assert main(['inspect-pack', str(tmp_path / 'PRIVATE-PATH')]) == 2
    captured = capsys.readouterr()
    assert 'PRIVATE-PATH' not in captured.out + captured.err
    assert 'SYNTHETIC-PRIVATE-SOURCE-CANARY' not in captured.out + captured.err
    assert main(['inspect-pack', str(packs['service-challenge'])]) == 0
    assert json.loads(capsys.readouterr().out)['assessment']['status'] == 'adapter_responses_not_supplied'
