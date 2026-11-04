from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import random

import pytest

from aau_harness.agent_bom import AgentBomError, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_compare import compare_evaluations
from aau_harness.eval_service_traces import service_trace_payloads, verify_service_trace_pack
from aau_harness import service_reproducer as module


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'public-value-review/examples'


def inputs():
    contract = load_json(FIXTURES / 'contract.json')
    exact = load_json(FIXTURES / 'exact-trace.json')
    burden = load_json(FIXTURES / 'burden-trace.json')
    # Synthetic canaries exercise every accepted label location; these are not real private data.
    for value in (contract, exact, burden):
        for field, item in value.items():
            if isinstance(item, str):
                value[field] = f'SYNTHETIC-PRIVATE-{item}'
            elif isinstance(item, list):
                value[field] = [f'SYNTHETIC-PRIVATE-{label}' for label in item]
    other = deepcopy(contract)
    other.update(recourse_required=False, deadline_preservation_required=False, continuity_preservation_required=False)
    other_trace = deepcopy(exact)
    other_trace.update(recourse_offered=False, deadline_preserved=False, continuity_preserved=False)
    failure = deepcopy(other_trace)
    failure['submitted'] = False
    failure['attempted_events'] += [contract['forbidden_events'][0]]
    failure['executed_events'] += [contract['forbidden_events'][0]]
    plan = {'plan_version': 'aau-service-trace-import/1.0', 'source_label': 'SYNTHETIC-PRIVATE-source', 'n_repeats': 2}
    suite = {'suite_version': 'aau-public-value-suite/1.0', 'cases': [
        {'case_id': 'SYNTHETIC-PRIVATE-z', 'contract': contract}, {'case_id': 'SYNTHETIC-PRIVATE-a', 'contract': other}]}
    traces = {'trace_version': 'aau-public-value-traces/1.1', 'observations': [
        {'case_id': 'SYNTHETIC-PRIVATE-z', 'repeat': 0, 'trace': burden, 'cost_usd': 91827.315, 'latency_s': 19382.6, 'n_api_calls': 72913},
        {'case_id': 'SYNTHETIC-PRIVATE-z', 'repeat': 1, 'trace': exact},
        {'case_id': 'SYNTHETIC-PRIVATE-a', 'repeat': 0, 'trace': other_trace, 'cost_usd': 0, 'latency_s': 0, 'n_api_calls': 0},
        {'case_id': 'SYNTHETIC-PRIVATE-a', 'repeat': 1, 'trace': failure}]}
    return plan, suite, traces


def test_complete_failures_survive_without_input_labels_hashes_or_operating_measurements(tmp_path):
    source = inputs()
    original = deepcopy(source)
    report, files = module.reproducer_payloads(*source)
    assert source == original and module.reproducer_payloads(*source) == (report, files)
    assert set(files) == module.FILES and len(files) == 10 and list(files)[-1] == 'manifest.json'
    exported = b''.join(files.values())
    assert b'SYNTHETIC-PRIVATE-' not in exported
    for value in source:
        assert digest(value).encode() not in exported
    for measurement in ('91827.315', '19382.6', '72913'):
        assert measurement.encode() not in exported
    assert report['observation_count'] == 4 and report['failed_observation_count'] == 2
    assert report['service_status'] == 'evidence_failed'
    assert report['source_relationship'] == 'not_verifiable_without_private_inputs; transformation_equivalence_not_source_identity'
    before, original_files = service_trace_payloads(*source)
    after = json.loads(files['service/scoring.json'])
    expected = {(row['case_id'], row['repeat']): row['assessment']['metrics'] for row in before['observations']}
    aliases = {case['case_id']: f'case-{i:04d}' for i, case in enumerate(source[1]['cases'], 1)}
    actual = {(row['case_id'], row['repeat']): row['assessment']['metrics'] for row in after['observations']}
    assert actual == {(aliases[name], repeat): metrics for (name, repeat), metrics in expected.items()}
    assert after['required_protection_coverage'] == before['required_protection_coverage']
    for row in json.loads(files['service/traces.json'])['observations']:
        assert set(row) == {'case_id', 'repeat', 'trace'}
    for row in json.loads(files['service/evaluation.json'])['results']:
        assert not {'cost_usd', 'latency_s', 'n_api_calls'} & row.keys()
    with pytest.raises(AgentBomError):
        compare_evaluations(json.loads(original_files['evaluation.json']), json.loads(files['service/evaluation.json']),
                            metric='public_value_exact', direction='higher')
    folder = tmp_path / 'reproducer'
    assert module.create_reproducer(*source, folder) == report
    assert module.verify_reproducer(folder) == report
    assert module.verify_source(folder, *source) == report
    assert verify_service_trace_pack(folder / 'service')['failed_observation_count'] == 2


def test_aliases_preserve_repeated_and_cross_role_equalities_but_not_cross_case_identity():
    source = inputs()
    _, files = module.reproducer_payloads(*source)
    cases = json.loads(files['service/suite.json'])['cases']
    rows = json.loads(files['service/traces.json'])['observations']
    first = rows[0]['trace']
    assert first['requested_evidence'][0] == first['requested_evidence'][1]
    assert first['requested_evidence'][0] in cases[0]['contract']['held_evidence']
    assert first['requested_evidence'][-1] not in cases[0]['contract']['required_evidence']
    last = rows[-1]['trace']
    forbidden = cases[1]['contract']['forbidden_events'][0]
    assert forbidden in last['attempted_events'] and forbidden in last['executed_events']
    terminal = cases[0]['contract']['expected_terminal']
    assert first['terminal_events'] == first['attempted_events'] == first['executed_events'] == [terminal]
    # Same alias in another case is local to that case, not a shared identity assertion.
    changed = deepcopy(source)
    for field, value in changed[1]['cases'][1]['contract'].items():
        if isinstance(value, list):
            changed[1]['cases'][1]['contract'][field] = [f'OTHER-{label}' for label in value]
        elif isinstance(value, str):
            changed[1]['cases'][1]['contract'][field] = f'OTHER-{value}'
    for row in changed[2]['observations'][2:]:
        for field, value in row['trace'].items():
            if isinstance(value, list):
                row['trace'][field] = [f'OTHER-{label}' for label in value]
    assert module.reproducer_payloads(*changed)[1] == files


def test_trace_row_order_is_irrelevant_and_optional_flags_normalize():
    plan = {'plan_version': 'aau-service-trace-import/1.0', 'source_label': 'Synthetic legacy', 'n_repeats': 1}
    suite, traces = [load_json(FIXTURES / f'{name}.json') for name in ('suite', 'traces')]
    report, files = module.reproducer_payloads(plan, suite, traces)
    assert report['observation_count'] == 2 and report['failed_observation_count'] == 1
    traces['observations'].reverse()
    assert module.reproducer_payloads(plan, suite, traces)[1] == files
    for case in suite['cases']:
        case['contract']['continuity_preservation_required'] = False
    for row in traces['observations']:
        row['trace']['continuity_preserved'] = False
    assert module.reproducer_payloads(plan, suite, traces)[1] == files


@pytest.mark.parametrize('seed', range(12))
def test_seeded_varied_trace_shapes_preserve_every_metric_and_are_fixed_points(seed):
    generator = random.Random(seed)
    plan, suite, traces = inputs()
    for case in suite['cases']:
        contract = case['contract']
        contract['forbidden_events'].append(contract['expected_terminal'])  # Contradictions stay failures, not repaired.
        for flag in ('recourse_required', 'deadline_preservation_required', 'continuity_preservation_required'):
            contract[flag] = bool(generator.getrandbits(1))
    for row in traces['observations']:
        trace = row['trace']
        for field in ('terminal_events', 'attempted_events', 'executed_events', 'requested_evidence', 'delivery_channels'):
            trace[field] = generator.choices(['same-cross-namespace', 'different', 'event-0001'], k=generator.randrange(5))
        for flag in ('submitted', 'recourse_offered', 'deadline_preserved', 'continuity_preserved'):
            trace[flag] = bool(generator.getrandbits(1))
    report, files = module.reproducer_payloads(plan, suite, traces)
    minimized = [json.loads(files[f'service/{name}.json']) for name in ('plan', 'suite', 'traces')]
    assert module.reproducer_payloads(*minimized) == (report, files)


@pytest.mark.parametrize('member', sorted(module.FILES))
def test_every_changed_member_rejects_even_after_rehash(tmp_path, member):
    folder = tmp_path / 'reproducer'
    module.create_reproducer(*inputs(), folder)
    target = folder / member
    target.write_bytes(target.read_bytes() + b' ')
    for manifest_name in ('service/manifest.json', 'manifest.json'):
        manifest_path = folder / manifest_name
        if member == manifest_name:
            continue
        manifest = load_json(manifest_path)
        for name in manifest['files']:
            path = folder / name if manifest_name == 'manifest.json' else folder / 'service' / name
            manifest['files'][name] = digest(path.read_bytes())
        manifest_path.write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        module.verify_reproducer(folder)


def test_valid_source_pack_is_not_accepted_as_minimized_even_with_a_matching_rehashed_manifest(tmp_path):
    folder = tmp_path / 'reproducer'
    module.create_reproducer(*inputs(), folder)
    _, raw = service_trace_payloads(*inputs())
    for name, value in raw.items():
        (folder / 'service' / name).write_bytes(value)
    manifest = load_json(folder / 'manifest.json')
    for name in manifest['files']:
        manifest['files'][name] = digest((folder / name).read_bytes())
    (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match='minimized profile'):
        module.verify_reproducer(folder)


@pytest.mark.parametrize('defect', ['root_link', 'nested_link', 'member_link', 'extra', 'nested_extra', 'missing', 'oversized', 'directory_member'])
def test_exact_non_symlink_bounded_structure(tmp_path, defect):
    folder = tmp_path / 'reproducer'
    module.create_reproducer(*inputs(), folder)
    if defect == 'root_link':
        link = tmp_path / 'link'
        link.symlink_to(folder, target_is_directory=True)
        folder = link
    elif defect == 'nested_link':
        (folder / 'service').rename(tmp_path / 'nested')
        (folder / 'service').symlink_to(tmp_path / 'nested', target_is_directory=True)
    elif defect in ('extra', 'nested_extra'):
        ((folder / 'service' if defect == 'nested_extra' else folder) / 'unexpected').write_text('x')
    elif defect == 'oversized':
        (folder / 'README.txt').write_bytes(b'x' * (module.MAX_JSON_BYTES + 1))
    else:
        target = folder / 'README.txt'
        target.unlink()
        if defect == 'member_link':
            target.symlink_to(folder / 'reproduction.json')
        elif defect == 'directory_member':
            target.mkdir()
    with pytest.raises(AgentBomError):
        module.verify_reproducer(folder)


@pytest.mark.parametrize('defect', ['missing_case', 'missing_repeat', 'duplicate_repeat', 'unknown_case', 'extra_data',
                                   'extra_contract', 'extra_trace', 'bad_measurement', 'nonfinite', 'unicode',
                                   'boolean_repeat', 'invalid_held', 'oversized'])
def test_invalid_or_incomplete_private_inputs_are_not_silently_stripped(tmp_path, defect):
    plan, suite, traces = inputs()
    if defect == 'missing_case':
        suite['cases'].pop()
    elif defect == 'missing_repeat':
        traces['observations'].pop()
    elif defect == 'duplicate_repeat':
        traces['observations'][-1] = deepcopy(traces['observations'][0])
    elif defect == 'unknown_case':
        traces['observations'][0]['case_id'] = 'unknown'
    elif defect == 'extra_data':
        traces['observations'][0]['customer_record'] = 'not accepted'
    elif defect == 'extra_contract':
        suite['cases'][0]['contract']['owner'] = 'not accepted'
    elif defect == 'extra_trace':
        traces['observations'][0]['trace']['message'] = 'not accepted'
    elif defect == 'bad_measurement':
        traces['observations'][0]['cost_usd'] = -1
    elif defect == 'nonfinite':
        traces['observations'][0]['cost_usd'] = float('inf')
    elif defect == 'unicode':
        plan['source_label'] = '\ud800'
    elif defect == 'boolean_repeat':
        traces['observations'][0]['repeat'] = True
    elif defect == 'invalid_held':
        suite['cases'][0]['contract']['held_evidence'] = ['unknown']
    else:
        plan['source_label'] = 'x' * module.MAX_JSON_BYTES
    folder = tmp_path / 'new'
    with pytest.raises(AgentBomError):
        module.create_reproducer(plan, suite, traces, folder)
    assert not folder.exists()


def test_preservation_guard_checks_all_components_before_writing(tmp_path, monkeypatch):
    original = module._minimized_inputs

    def faulty(*args):
        plan, suite, traces, correspondence = original(*args)
        # Joint score already fails; a component-only change must still be rejected.
        traces['observations'][0]['trace']['recourse_offered'] = True
        return plan, suite, traces, correspondence

    monkeypatch.setattr(module, '_minimized_inputs', faulty)
    with pytest.raises(AgentBomError, match='every supplied service metric'):
        module.create_reproducer(*inputs(), tmp_path / 'new')
    assert not (tmp_path / 'new').exists()


def test_private_source_verification_detects_changed_behavior_but_not_removed_source_identity(tmp_path):
    source = inputs()
    folder = tmp_path / 'reproducer'
    module.create_reproducer(*source, folder)
    changed = deepcopy(source)
    changed[2]['observations'][0]['trace']['recourse_offered'] = True
    with pytest.raises(AgentBomError, match='private-input transformation'):
        module.verify_source(folder, *changed)
    changed = deepcopy(source)
    changed[0]['source_label'] = 'another label'
    changed[1]['cases'][0]['contract']['version'] = 'another version'
    changed[2]['observations'][0]['cost_usd'] = 999
    # The profile deliberately does NOT claim exact source identity or measurements.
    assert module.verify_source(folder, *changed)['failed_observation_count'] == 2


def test_cli_failures_are_reproducer_success_but_never_service_success_or_sharing_approval(tmp_path, capsys):
    source = inputs()
    paths = []
    for name, value in zip(('plan', 'suite', 'traces'), source):
        path = tmp_path / f'SYNTHETIC-PRIVATE-{name}.json'
        path.write_bytes(rendered(value))
        paths.append(str(path))
    folder = tmp_path / 'reproducer'
    args = ['service-reproducer', 'create', *paths, '--out', str(folder)]
    assert main(args) == 0 and main(args) == 2
    assert main(['service-reproducer', 'verify', str(folder)]) == 0
    assert main(['service-reproducer', 'verify-source', str(folder), *paths]) == 0
    assert main(['service-trace-eval', 'verify', str(folder / 'service')]) == 1
    assert main(['service-reproducer', 'create', '/SYNTHETIC-PRIVATE-missing', *paths[1:], '--out', str(tmp_path / 'absent')]) == 2
    Path(paths[0]).write_text('{"SYNTHETIC-PRIVATE-key":1,"SYNTHETIC-PRIVATE-key":2}')
    assert main(['service-reproducer', 'create', *paths, '--out', str(tmp_path / 'absent')]) == 2
    captured = capsys.readouterr()
    assert 'SYNTHETIC-PRIVATE-' not in captured.out + captured.err
    assert 'NOT anonymized or approved for sharing' in captured.out
    assert not (tmp_path / 'absent').exists()


@pytest.mark.parametrize('payload', ['{"x":' + '[' * 1500 + '0' + ']' * 1500 + '}', '{"x":' + '1' * 5000 + '}'])
def test_cli_rejects_parser_resource_failures_without_echoing_private_paths(tmp_path, capsys, payload):
    path = tmp_path / 'SYNTHETIC-PRIVATE-parser.json'
    path.write_text(payload)
    assert main(['service-reproducer', 'create', str(path), str(path), str(path), '--out', str(tmp_path / 'absent')]) == 2
    captured = capsys.readouterr()
    assert 'SYNTHETIC-PRIVATE-' not in captured.out + captured.err
    assert not (tmp_path / 'absent').exists()


def test_checkout_example_keeps_the_complete_failed_reproducer(tmp_path):
    spec = importlib.util.spec_from_file_location('service_reproducer_example', ROOT / 'harness/examples/evaluation-review/service_reproducer.py')
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    destination = tmp_path / 'example'
    assert example.create_example(destination)['failed_observation_count'] == 1
    assert len([path for path in destination.rglob('*') if path.is_file()]) == 10
    assert b'SYNTHETIC-SOURCE-NAME-NOT-FOR-EXPORT' not in b''.join(path.read_bytes() for path in destination.rglob('*') if path.is_file())
