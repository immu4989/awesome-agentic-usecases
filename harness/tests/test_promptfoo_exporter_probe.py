from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from aau_harness.agent_bom import digest, rendered


spec = importlib.util.spec_from_file_location('promptfoo_probe', Path(__file__).parents[1] / 'tools/check_promptfoo_exporter.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def synthetic_source(variant):
    """Unit-test states only; actual SDK exports are separately generated in the CI probe."""
    provider = 'aau-synthetic-error' if variant == 'provider-error' else 'echo'
    rows = []
    for test in range(4 if variant == 'repeated' else 2):
        identity = 'alpha' if test < (2 if variant == 'repeated' else 1) else 'beta'
        for column in range(2):
            score = 1 - column
            error = variant == 'provider-error' and column == 1
            row = {'testIdx': test, 'promptIdx': column, 'promptId': digest(probe.PROMPTS[column].encode()),
                   'provider': {'id': provider}, 'vars': {'value': identity}, 'score': score,
                   'success': column == 0, 'failureReason': 2 if error else column,
                   'response': {'error': 'AAU_SYNTHETIC_PROVIDER_ERROR'} if error else
                               {'output': ('other: ' if column else '') + identity},
                   'namedScores': {}, 'gradingResult': {'pass': column == 0, 'score': score}}
            if error:
                row['error'] = 'AAU_SYNTHETIC_PROVIDER_ERROR'
            elif not (variant == 'missing-named-score' and test == 1):
                row['namedScores']['match'] = score
            rows.append(row)
    return {'metadata': {'promptfooVersion': '0.126.0'}, 'config': {}, 'results': {
        'version': 3, 'prompts': [{'id': digest(p.encode()), 'provider': provider} for p in probe.PROMPTS],
        'results': rows, 'stats': {'successes': len(rows) // 2, 'failures': 0 if variant == 'provider-error' else len(rows) // 2,
                                'errors': 2 if variant == 'provider-error' else 0}}}


@pytest.mark.parametrize('variant', probe.VARIANTS)
def test_expected_native_state_oracle(variant):
    source = synthetic_source(variant)
    assert probe.check_native_source(rendered(source), variant) == source['results']['stats']


@pytest.mark.parametrize('field,value', [('failureReason', 1), ('failureReason', True), ('error', 'unrelated import error'),
    ('score', True), ('score', 1), ('success', True), ('promptId', 'other'), ('provider', {'id': 'other'}),
    ('testIdx', True), ('vars', {'value': 'other'}), ('response', {'error': 'unrelated'})])
def test_provider_error_control_requires_the_intended_error_and_complete_identity(field, value):
    source = synthetic_source('provider-error')
    source['results']['results'][1][field] = value
    with pytest.raises(ValueError):
        probe.check_native_source(rendered(source), 'provider-error')


@pytest.mark.parametrize('variant', probe.VARIANTS)
def test_missing_extra_and_duplicate_census_rejected(variant):
    original = synthetic_source(variant)
    for change in ('missing', 'extra', 'duplicate'):
        source = deepcopy(original)
        rows = source['results']['results']
        if change == 'missing':
            rows.pop()
        elif change == 'extra':
            rows.append(deepcopy(rows[0]))
        else:
            rows[-1] = deepcopy(rows[0])
        with pytest.raises(ValueError):
            probe.check_native_source(rendered(source), variant)


def test_zero_imputation_does_not_satisfy_missing_named_score_control():
    source = synthetic_source('missing-named-score')
    source['results']['results'][3]['namedScores']['match'] = 0
    with pytest.raises(ValueError):
        probe.check_native_source(rendered(source), 'missing-named-score')


@pytest.mark.parametrize('change', ['producer', 'schema', 'count', 'output', 'score'])
def test_unrelated_changes_are_not_accepted_as_native_compatibility(change):
    source = synthetic_source('complete')
    if change == 'producer':
        source['metadata']['promptfooVersion'] = 'other'
    elif change == 'schema':
        source['results']['version'] = 4
    elif change == 'count':
        source['results']['stats']['errors'] = 1
    elif change == 'output':
        source['results']['results'][0]['response']['output'] = 'wrong'
    else:
        source['results']['results'][0]['namedScores']['match'] = 0
    with pytest.raises(ValueError):
        probe.check_native_source(rendered(source), 'complete')


def producer_inputs(directory):
    directory.mkdir()
    records = []
    for variant in probe.VARIANTS:
        raw = rendered(synthetic_source(variant))
        (directory / f'{variant}.json').write_bytes(raw)
        records.append({'variant': variant, 'file': f'{variant}.json', 'source_sha256': digest(raw),
                        'row_count': 8 if variant == 'repeated' else 4,
                        'outcomes': synthetic_source(variant)['results']['stats']})
    receipt = {'probe_version': 'aau-promptfoo-native-export/1.0', 'producer_version': '0.126.0', 'exports': records,
               'blocked_network_attempts': [{'api': 'fetch', 'kind': 'blocked_telemetry_disabled_notification', 'blocked': True}]}
    (directory / 'producer.json').write_bytes(rendered(receipt))
    return receipt


def test_complete_checker_preserves_sources_and_distinguishes_all_states(tmp_path):
    source = tmp_path / 'source'
    producer_inputs(source)
    report = probe.exercise(source, tmp_path / 'checked')
    assert len(report['checks']) == 9
    for variant in probe.VARIANTS:
        assert (tmp_path / 'checked/sources' / f'{variant}.json').read_bytes() == (source / f'{variant}.json').read_bytes()
    with pytest.raises(ValueError):
        probe.exercise(source, tmp_path / 'checked')
    with pytest.raises(ValueError):
        probe.exercise(source, source / 'nested')


@pytest.mark.parametrize('change', ['pin', 'inventory', 'blocked_attempts', 'row_count'])
def test_inconsistent_producer_receipt_rejected_before_output(tmp_path, change):
    source = tmp_path / 'source'
    receipt = producer_inputs(source)
    if change == 'pin':
        receipt['exports'][0]['source_sha256'] = '0' * 64
    elif change == 'inventory':
        receipt['exports'].pop()
    elif change == 'blocked_attempts':
        receipt['blocked_network_attempts'] = []
    else:
        receipt['exports'][0]['row_count'] = 7
    (source / 'producer.json').write_bytes(rendered(receipt))
    with pytest.raises(ValueError):
        probe.exercise(source, tmp_path / 'rejected')
    assert not (tmp_path / 'rejected').exists()
