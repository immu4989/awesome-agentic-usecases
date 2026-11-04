from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from aau_harness.agent_bom import AgentBomError, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_pack import verify_pack
from aau_harness.eval_service_review import create_handoff, handoff_payloads, verify_handoff
from aau_harness.eval_service_traces import create_service_trace_pack, verify_service_trace_pack


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / '.github/actions/aau-evaluation-review/run.py'


def example_module():
    spec = importlib.util.spec_from_file_location('service_examples', ROOT / 'harness/examples/evaluation-review/service_traces.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(outcome='repaired'):
    plan, suite, base, burden, policy, diagnostics, budget = example_module().example_inputs()
    candidate = deepcopy(burden if outcome == 'burden' else base)
    if outcome == 'slow':
        candidate['observations'][0]['latency_s'] = 10
    elif outcome == 'unknown':
        del candidate['observations'][0]['cost_usd']
    elif outcome == 'baseline-failed':
        base = burden
    return [policy, plan, base, deepcopy(plan), candidate, diagnostics], suite, budget


@pytest.mark.parametrize('outcome,policy_status,budget_status', [
    ('burden', 'constraints_not_met', 'constraints_not_met'),
    ('slow', 'constraints_met', 'constraints_not_met'),
    ('unknown', 'constraints_met', 'constraints_not_verified'),
    ('repaired', 'constraints_met', 'constraints_met'),
    ('baseline-failed', 'constraints_met', 'constraints_met')])
@pytest.mark.parametrize('gated', [False, True])
def test_complete_source_chain_preserves_independent_outcomes(tmp_path, outcome, policy_status, budget_status, gated):
    args, suite, budget = inputs(outcome)
    original = deepcopy((args, suite, budget))
    folder = tmp_path / 'handoff'
    result = create_handoff(*args, folder, service_suite=suite, operating_budget=budget if gated else None)
    assert (args, suite, budget) == original
    assert verify_handoff(folder, require_budget=gated) == result
    assert len([p for p in folder.rglob('*') if p.is_file()]) == (33 if gated else 30)
    assert load_json(folder / 'review/review.json')['status'] == policy_status
    expected = policy_status if not gated or policy_status != 'constraints_met' else budget_status
    assert result['status'] == expected
    if gated:
        assert result['policy_status'] == policy_status and result['candidate_budget_status'] == budget_status
    for side, traces in [('baseline', args[2]), ('candidate', args[4])]:
        assert load_json(folder / side / 'suite.json') == suite
        assert load_json(folder / side / 'traces.json') == traces
        verify_service_trace_pack(folder / side, evaluation_path=folder / 'review' / f'{side}.json')
    verify_pack(folder / 'review', require_recordings=True, require_diagnostics=True, require_budget=gated)
    assert handoff_payloads(*args, service_suite=suite, operating_budget=budget) == handoff_payloads(
        *args, service_suite=suite, operating_budget=budget)
    if outcome == 'burden':
        scores = load_json(folder / 'review/candidate.json')['metric_means']
        assert scores['service_completion'] == 1 and scores['public_value_exact'] == .75
        assert result['sources']['candidate']['failed_observations'] == [{'case_id': 'assisted-service', 'repeat': 0}]
        assert result['sources']['candidate']['required_protection_coverage']['recourse_preserved'] == {
            'required_observation_count': 2, 'satisfied_required_observation_count': 1, 'not_required_observation_count': 2}


MEMBERS = sorted(handoff_payloads(*inputs()[0], service_suite=inputs()[1], operating_budget=inputs()[2])[1])


@pytest.mark.parametrize('member', MEMBERS)
def test_every_member_recomputes_despite_rehashed_manifest(tmp_path, member):
    args, suite, budget = inputs()
    folder = tmp_path / 'handoff'
    create_handoff(*args, folder, service_suite=suite, operating_budget=budget)
    target = folder / member
    target.write_bytes(target.read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = load_json(folder / 'manifest.json')
        manifest['files'][member] = digest(target.read_bytes())
        (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_handoff(folder)


@pytest.mark.parametrize('replacement', ['baseline', 'candidate', 'review'])
def test_individually_valid_nested_substitution_cannot_replace_source_chain(tmp_path, replacement):
    args, suite, budget = inputs()
    original, alternate = tmp_path / 'original', tmp_path / 'alternate'
    create_handoff(*args, original, service_suite=suite, operating_budget=budget)
    args[1]['source_label'] = 'Other independently valid baseline'
    args[3]['source_label'] = 'Other independently valid candidate'
    create_handoff(*args, alternate, service_suite=suite, operating_budget=budget)
    for path in (alternate / replacement).iterdir():
        shutil.copyfile(path, original / replacement / path.name)
    if replacement == 'review':
        verify_pack(original / replacement, require_budget=True)
    else:
        verify_service_trace_pack(original / replacement)
    manifest = load_json(original / 'manifest.json')
    for name in manifest['files']:
        manifest['files'][name] = digest((original / name).read_bytes())
    (original / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match='does not recompute'):
        verify_handoff(original, require_budget=True)


def test_separately_valid_candidate_with_different_contract_is_not_a_common_suite(tmp_path):
    args, suite, budget = inputs()
    folder = tmp_path / 'handoff'
    create_handoff(*args, folder, service_suite=suite, operating_budget=budget)
    suite['cases'][0]['contract']['recourse_required'] = False
    alternate = tmp_path / 'changed-contract'
    create_service_trace_pack(args[3], suite, args[4], alternate)
    for path in alternate.iterdir():
        shutil.copyfile(path, folder / 'candidate' / path.name)
    verify_service_trace_pack(folder / 'candidate')
    with pytest.raises(AgentBomError, match='does not recompute'):
        verify_handoff(folder)


@pytest.mark.parametrize('layer', ['policy', 'diagnostics', 'budget'])
@pytest.mark.parametrize('defect', ['missing', 'relaxed', 'reversed', 'boolean', 'above-binary-range'])
def test_completion_only_or_relaxed_obligation_profiles_are_rejected_before_output(tmp_path, layer, defect):
    args, suite, budget = inputs('burden')
    rules = args[0]['metrics'] if layer == 'policy' else (args[5] if layer == 'diagnostics' else budget)['criteria']
    rule = next(r for r in rules if r['metric'] == 'public_value_exact')
    field = 'candidate_observation_limit' if layer == 'policy' else 'limit'
    if defect == 'missing':
        rule['metric'] = 'submitted'
    elif defect == 'reversed':
        rule['direction'] = 'lower'
    else:
        rule[field] = {'relaxed': 0, 'boolean': True, 'above-binary-range': 2}[defect]
    with pytest.raises(AgentBomError):
        create_handoff(*args, tmp_path / 'bad', service_suite=suite, operating_budget=budget)
    assert not (tmp_path / 'bad').exists()


def test_subgroup_only_obligation_does_not_replace_global_candidate_floor(tmp_path):
    args, suite, budget = inputs('burden')
    rule = args[0]['metrics'].pop()
    # A global rule remains, but its weakened floor cannot be replaced by stricter cohorts.
    args[0]['metrics'].append({**rule, 'candidate_observation_limit': 0})
    args[0].update(policy_version='aau-evaluation-review-policy/1.1', cohorts=[
        {'cohort_id': 'all', 'scenario_ids': args[0]['scenario_ids'], 'metrics': [rule]}])
    with pytest.raises(AgentBomError, match='global policy'):
        create_handoff(*args, tmp_path / 'bad', service_suite=suite, operating_budget=budget)


@pytest.mark.parametrize('defect', ['no-diagnostics', 'missing-case', 'source-score', 'extra-file', 'missing-file',
                                   'root-link', 'member-link', 'group-link', 'large', 'version'])
def test_invalid_source_or_layout_is_not_verified(tmp_path, defect):
    args, suite, budget = inputs()
    folder = tmp_path / 'handoff'
    if defect in ('no-diagnostics', 'missing-case', 'source-score'):
        if defect == 'no-diagnostics':
            args[5] = None
        elif defect == 'missing-case':
            args[4]['observations'].pop()
        else:
            args[4]['observations'][0]['metrics'] = {'public_value_exact': 1}
        with pytest.raises(AgentBomError):
            create_handoff(*args, folder, service_suite=suite, operating_budget=budget)
        assert not folder.exists()
        return
    create_handoff(*args, folder, service_suite=suite, operating_budget=budget)
    if defect == 'extra-file':
        (folder / 'candidate/extra').write_text('x')
    elif defect == 'missing-file':
        (folder / 'baseline/traces.json').unlink()
    elif defect.endswith('link'):
        target = {'root-link': folder, 'group-link': folder / 'candidate', 'member-link': folder / 'manifest.json'}[defect]
        target.rename(tmp_path / 'moved')
        target.symlink_to(tmp_path / 'moved', target_is_directory=(tmp_path / 'moved').is_dir())
    elif defect == 'large':
        (folder / 'README.txt').write_bytes(b'x' * 2_000_001)
    else:
        (folder / 'manifest.json').write_text('{"pack_version":"future"}')
    with pytest.raises(AgentBomError):
        verify_handoff(folder)


def setup_action(tmp_path, outcome='repaired', gated=True):
    args, suite, budget = inputs(outcome)
    workspace = tmp_path / 'workspace with spaces'
    workspace.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith('AAU_EVAL_')}
    env.update(GITHUB_WORKSPACE=str(workspace), GITHUB_STEP_SUMMARY=str(tmp_path / 'summary.md'),
               AAU_EVAL_INPUT_FORMAT='service-traces', AAU_EVAL_OUTPUT='service handoff')
    values = dict(zip(['POLICY', 'BASELINE_PLAN', 'BASELINE', 'CANDIDATE_PLAN', 'CANDIDATE', 'DIAGNOSTICS'], args))
    values['SERVICE_SUITE'] = suite
    if gated:
        values['OPERATING_BUDGET'] = budget
    for key, value in values.items():
        filename = f'{key.lower()}.json'
        (workspace / filename).write_bytes(rendered(value))
        env[f'AAU_EVAL_{key}'] = filename
        if key != 'CANDIDATE':
            env[f'AAU_EVAL_{key}_SHA256'] = digest((workspace / filename).read_bytes())
    return workspace, env


def run_action(env):
    return subprocess.run([sys.executable, str(DRIVER)], env=env, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize('outcome,code', [('burden', 1), ('slow', 1), ('unknown', 1), ('repaired', 0), ('baseline-failed', 0)])
def test_action_complete_review_with_private_summary(tmp_path, outcome, code):
    workspace, env = setup_action(tmp_path, outcome)
    result = run_action(env)
    assert result.returncode == code, result.stderr
    report = verify_handoff(workspace / 'service handoff', require_budget=True)
    assert (report['status'] == 'constraints_met') == (code == 0)
    summary = (tmp_path / 'summary.md').read_text()
    assert 'all 33 files recomputed' in summary and 'common contract-suite' in summary
    assert not any(value in summary for value in ('assisted-service', 'bank_password', 'phone_711', '0.12'))
    assert run_action(env).returncode == 2


@pytest.mark.parametrize('key', ['POLICY', 'BASELINE', 'BASELINE_PLAN', 'CANDIDATE_PLAN', 'DIAGNOSTICS', 'SERVICE_SUITE', 'OPERATING_BUDGET'])
@pytest.mark.parametrize('defect', ['missing-pin', 'byte-drift'])
def test_action_approval_pins_are_independent(tmp_path, key, defect):
    workspace, env = setup_action(tmp_path)
    if defect == 'missing-pin':
        del env[f'AAU_EVAL_{key}_SHA256']
    else:
        path = workspace / env[f'AAU_EVAL_{key}']
        path.write_bytes(path.read_bytes() + b'\n')
    assert run_action(env).returncode == 2
    assert not (workspace / 'service handoff').exists()


def test_relaxing_both_contract_copies_can_recompute_but_cannot_bypass_independent_pin(tmp_path):
    workspace, env = setup_action(tmp_path)
    path = workspace / env['AAU_EVAL_SERVICE_SUITE']
    suite = load_json(path)
    suite['cases'][0]['contract']['recourse_required'] = False
    path.write_bytes(rendered(suite))
    # The inputs remain well formed and a coordinated CLI rebuild is internally consistent.
    args, _, budget = inputs()
    create_handoff(*args, tmp_path / 'changed', service_suite=suite, operating_budget=budget)
    verify_handoff(tmp_path / 'changed', require_budget=True)
    assert run_action(env).returncode == 2
    assert not (workspace / 'service handoff').exists()


@pytest.mark.parametrize('value', ['../outside', '/tmp/outside', 'bad\npath', 'alias'])
def test_action_suite_paths_cannot_escape_workspace(tmp_path, value):
    workspace, env = setup_action(tmp_path)
    (workspace / 'alias').symlink_to(workspace / env['AAU_EVAL_SERVICE_SUITE'])
    env['AAU_EVAL_SERVICE_SUITE'] = value
    assert run_action(env).returncode == 2
    assert not (workspace / 'service handoff').exists()


@pytest.mark.parametrize('input_format', ['evaluations', 'recordings', 'csv', 'retries', 'otlp'])
def test_action_does_not_ignore_contract_suite_in_wrong_mode(tmp_path, input_format):
    workspace, env = setup_action(tmp_path)
    env['AAU_EVAL_INPUT_FORMAT'] = input_format
    assert run_action(env).returncode == 2
    assert not (workspace / 'service handoff').exists()


def test_action_bad_source_does_not_echo_annotation_or_raw_data(tmp_path):
    workspace, env = setup_action(tmp_path)
    (workspace / env['AAU_EVAL_CANDIDATE']).write_text('::error::PRIVATE_SERVICE_DATA')
    result = run_action(env)
    assert result.returncode == 2
    assert 'PRIVATE_SERVICE_DATA' not in result.stdout + result.stderr
    assert '::error::' not in result.stdout + result.stderr
    assert not (workspace / 'service handoff').exists()


def test_ungated_handoff_cannot_satisfy_mandatory_budget_and_cli_preserves_failures(tmp_path):
    workspace, env = setup_action(tmp_path, 'burden', gated=False)
    assert run_action(env).returncode == 1
    folder = workspace / 'service handoff'
    assert verify_handoff(folder)['status'] == 'constraints_not_met'
    assert main(['service-review', 'verify', str(folder)]) == 1
    assert main(['service-review', 'verify', str(folder), '--require-budget']) == 2
    args = ['service-review', 'create', *(str(workspace / env[f'AAU_EVAL_{key}']) for key in
            ['POLICY', 'SERVICE_SUITE', 'BASELINE_PLAN', 'BASELINE', 'CANDIDATE_PLAN', 'CANDIDATE']),
            '--diagnostics', str(workspace / env['AAU_EVAL_DIAGNOSTICS']), '--out', str(tmp_path / 'cli')]
    assert main(args) == 1 and main(args) == 2
    assert verify_handoff(tmp_path / 'cli')['status'] == 'constraints_not_met'


def test_action_metadata_forwards_suite_approval_inputs():
    action = (DRIVER.parent / 'action.yml').read_text()
    for key in ('service-suite', 'service-suite-sha256'):
        assert f'  {key}:\n' in action
        env_key = key.upper().replace('-', '_')
        assert f'AAU_EVAL_{env_key}: ${{{{ inputs.{key} }}}}' in action


def test_example_generates_four_verified_handoffs_with_different_failure_shapes(tmp_path):
    example_module().create_handoffs(tmp_path / 'demo')
    assert len([p for p in (tmp_path / 'demo').rglob('*') if p.is_file()]) == 133
    for name, expected in [('burden', 'constraints_not_met'), ('slow', 'constraints_not_met'),
                           ('unknown', 'constraints_not_verified'), ('repaired', 'constraints_met')]:
        assert verify_handoff(tmp_path / 'demo' / name, require_budget=True)['status'] == expected
    assert (tmp_path / 'demo/README.txt').is_file()
