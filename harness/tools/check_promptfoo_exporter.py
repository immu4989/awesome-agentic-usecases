"""Check fixed native Promptfoo export states with the installed offline importer; no exporter execution."""

import argparse
from importlib.metadata import version
from pathlib import Path
import shutil

from aau_harness.agent_bom import AgentBomError, digest, rendered, write_json
from aau_harness.eval_promptfoo import _json, _read, create_promptfoo_pack, promptfoo_payloads, verify_promptfoo_pack
from aau_harness.promptfoo_diagnostic import create_diagnostic, verify_diagnostic
from aau_harness.promptfoo_review import create_handoff, verify_handoff
from aau_harness.evidence_index import create_index, verify_index


VARIANTS = ('complete', 'missing-named-score', 'provider-error', 'repeated')
PROMPTS = ('{{value}}', 'other: {{value}}')


def planned_mapping(variant, column):
    return {'plan_version': 'aau-promptfoo-observation-plan/1.0',
            'source_label': 'Fixed native Promptfoo 0.126.0 synthetic compatibility exercise',
            'test_map': [{'test_index': 0, 'scenario_id': 'alpha'}, {'test_index': 1, 'scenario_id': 'beta'}],
            'columns': [{'prompt_index': i, 'prompt_id': digest(template.encode()),
                         'provider_id': 'aau-synthetic-error' if variant == 'provider-error' else 'echo'}
                        for i, template in enumerate(PROMPTS)],
            'selected_prompt_index': column,
            'metrics': {'quality': {'field': 'score'}, 'passed': {'field': 'success'},
                        'match': {'field': 'namedScores', 'name': 'match'}}}


def check_native_source(raw, variant):
    if variant not in VARIANTS:
        raise ValueError('unknown native test variant')
    source = _json(raw)
    if source.get('metadata', {}).get('promptfooVersion') != '0.126.0' or source.get('results', {}).get('version') != 3:
        raise ValueError('wrong native export version')
    rows = source['results'].get('results', [])
    repeats = variant == 'repeated'
    expected = {(test, column) for test in range(4 if repeats else 2) for column in range(2)}
    if len(rows) != len(expected) or {(r.get('testIdx'), r.get('promptIdx')) for r in rows} != expected:
        raise ValueError('native exporter did not produce the fixed complete census')
    counts = {'successes': 0, 'failures': 0, 'errors': 0}
    for row in rows:
        test, column = row['testIdx'], row['promptIdx']
        if (type(test) is not int or type(column) is not int or type(row.get('failureReason')) is not int
                or type(row.get('score')) not in (int, float)):
            raise ValueError('native result index, reason, or score types changed')
        identity = 'alpha' if test < (2 if repeats else 1) else 'beta'
        expected_reason = 0 if column == 0 else 2 if variant == 'provider-error' else 1
        expected_score = 1 if column == 0 else 0
        provider = 'aau-synthetic-error' if variant == 'provider-error' else 'echo'
        if (row.get('vars', {}).get('value') != identity or row.get('failureReason') != expected_reason
                or row.get('success') is not (column == 0) or row.get('score') != expected_score
                or row.get('promptId') != digest(PROMPTS[column].encode()) or row.get('provider', {}).get('id') != provider):
            raise ValueError('native case identity or intended outcome changed')
        if expected_reason == 2:
            if row.get('error') != 'AAU_SYNTHETIC_PROVIDER_ERROR' or row.get('response', {}).get('error') != row['error']:
                raise ValueError('negative control failed for an unrelated provider error')
        else:
            expected_output = ('other: ' if column else '') + identity
            if row.get('response', {}).get('output') != expected_output:
                raise ValueError('synthetic provider output changed')
            score = row.get('namedScores', {}).get('match')
            if variant == 'missing-named-score' and test == 1:
                if 'match' in row.get('namedScores', {}):
                    raise ValueError('missing named score unexpectedly present')
            elif score != expected_score:
                raise ValueError('native named score changed')
        counts[('successes', 'failures', 'errors')[expected_reason]] += 1
    if any(source['results'].get('stats', {}).get(key) != value for key, value in counts.items()):
        raise ValueError('native outcome counts changed')
    return counts


def exercise(source_dir, out):
    if out.exists() or out.is_symlink() or out.resolve().is_relative_to(source_dir.resolve()):
        raise ValueError('new output must be outside native source directory')
    producer_raw = _read(source_dir / 'producer.json')
    producer = _json(producer_raw)
    if (producer.get('probe_version') != 'aau-promptfoo-native-export/1.0' or producer.get('producer_version') != '0.126.0'
            or producer.get('blocked_network_attempts') != [
                {'api': 'fetch', 'kind': 'blocked_telemetry_disabled_notification', 'blocked': True}]):
        raise ValueError('producer identity or expected blocked-notification record changed')
    records = producer.get('exports', [])
    if len(records) != 4 or {r.get('variant') for r in records} != set(VARIANTS):
        raise ValueError('native export inventory changed')
    sources = {}
    for variant in VARIANTS:
        raw = _read(source_dir / f'{variant}.json')
        counts = check_native_source(raw, variant)
        record = next(r for r in records if r['variant'] == variant)
        if (record.get('file') != f'{variant}.json' or record.get('source_sha256') != digest(raw)
                or record.get('outcomes') != counts or record.get('row_count') != (8 if variant == 'repeated' else 4)):
            raise ValueError('native producer receipt does not match source bytes and expected outcomes')
        sources[variant] = raw
    out.mkdir(parents=True, exist_ok=False)
    (out / 'sources').mkdir()
    (out / 'producer.json').write_bytes(producer_raw)
    for variant, raw in sources.items():
        (out / 'sources' / f'{variant}.json').write_bytes(raw)
    checks = []
    for variant, column in (('complete', 0), ('complete', 1), ('missing-named-score', 1)):
        plan_raw = rendered(planned_mapping(variant, column))
        pin = digest(plan_raw)
        name = f'{variant}-column-{column}'
        directory = out / name
        report = create_promptfoo_pack(plan_raw, sources[variant], directory, plan_sha256=pin)
        if verify_promptfoo_pack(directory, plan_sha256=pin) != report or (directory / 'source.json').read_bytes() != sources[variant]:
            raise ValueError('native source-to-evaluation replay mismatch')
        evaluation = _json((directory / 'evaluation.json').read_bytes())
        by_id = {row['scenario_id']: row for row in evaluation['results']}
        expected = 1 if column == 0 else 0
        for identity in ('alpha', 'beta'):
            metrics = {'quality': expected, 'passed': expected}
            if variant != 'missing-named-score' or identity == 'alpha':
                metrics['match'] = expected
            if (by_id[identity]['metrics'] != metrics
                    or {'cost_usd', 'latency_s', 'n_api_calls'} & set(by_id[identity])):
                raise ValueError('import changed native score values, missingness, or invented operating measurements')
        if 'evaluation_context' in evaluation:
            raise ValueError('import invented execution context')
        checks.append({'case': name, 'status': 'exact_projection_and_replay', 'plan_sha256': pin})
    for variant, reason in (('provider-error', 'execution errors'), ('repeated', 'full planned test/column census')):
        plan_raw = rendered(planned_mapping(variant, 0))
        try:
            promptfoo_payloads(plan_raw, sources[variant], plan_sha256=digest(plan_raw))
        except AgentBomError as exc:
            if reason not in str(exc):
                raise ValueError('negative control rejected for an unrelated reason') from exc
        else:
            raise ValueError('unsupported native export was silently accepted')
        checks.append({'case': variant, 'status': 'intended_native_state_rejected'})
        directory = out / f'{variant}-diagnostic'
        diagnostic = create_diagnostic(plan_raw, sources[variant], directory, plan_sha256=digest(plan_raw))
        if (verify_diagnostic(directory, plan_sha256=digest(plan_raw)) != diagnostic
                or diagnostic['conversion_eligibility']['status'] != 'rejected_by_current_converter'
                or (directory / 'source.json').read_bytes() != sources[variant]
                or (directory / 'evaluation.json').exists()):
            raise ValueError('native diagnostic repaired evidence or did not replay')
        if variant == 'provider-error':
            if diagnostic['row_marker_counts'].get('execution_error_recorded') != 2 or diagnostic['pair_counts']['unique'] != 4:
                raise ValueError('native diagnostic hid provider errors')
        elif diagnostic['row_marker_counts'].get('outside_plan') != 4 or diagnostic['recorded_rows'] != 8:
            raise ValueError('native diagnostic reinterpreted repeated tests as new planned cases')
        checks.append({'case': f'{variant}-diagnostic', 'status': 'retained_without_conversion'})
    directory = out / 'complete-column-0'
    pin = digest((directory / 'plan.json').read_bytes())
    try:
        verify_promptfoo_pack(directory, plan_sha256='0' * 64)
    except AgentBomError:
        checks.append({'case': 'wrong-plan-pin', 'status': 'rejected'})
    else:
        raise ValueError('wrong receiver pin accepted')
    tampered = out / 'tampered-negative-control'
    shutil.copytree(directory, tampered)
    with (tampered / 'evaluation.json').open('ab') as stream:
        stream.write(b' ')
    try:
        verify_promptfoo_pack(tampered, plan_sha256=pin)
    except AgentBomError:
        checks.append({'case': 'changed-derived-evaluation', 'status': 'rejected'})
    else:
        raise ValueError('changed derived evaluation accepted')
    # Same synthetic native export, two explicitly selected columns: not independent systems or executions.
    for selected, status in ((0, 'constraints_met'), (1, 'constraints_not_met')):
        criteria = [{'metric': 'quality', 'direction': 'higher', 'limit': 1}]
        request = {'request_version': 'aau-promptfoo-review-request/1.0',
                   'baseline_source_sha256': digest(sources['complete']),
                   'baseline_plan': planned_mapping('complete', 1 - selected),
                   'candidate_plan': planned_mapping('complete', selected),
                   'policy': {'policy_version': 'aau-evaluation-review-policy/1.0',
                              'scenario_ids': ['alpha', 'beta'], 'minimum_repeats': 1,
                              'metrics': [{'metric': 'quality', 'direction': 'higher', 'candidate_observation_limit': 1,
                                           'max_mean_regression': 0, 'max_regressed_scenarios': 0}]},
                   'diagnostics': {'plan_version': 'aau-evaluation-diagnostics/1.0', 'criteria': criteria,
                                   'draw_sizes': [1], 'cost_basis': {'baseline': 'synthetic', 'candidate': 'synthetic'}},
                   'operating_budget': None}
        request_raw = rendered(request)
        directory = out / f'native-handoff-column-{selected}'
        handoff = create_handoff(request_raw, sources['complete'], sources['complete'], directory,
                                 request_sha256=digest(request_raw))
        if (verify_handoff(directory, request_sha256=digest(request_raw)) != handoff or handoff['status'] != status
                or handoff['declared_context']['status'] != 'unavailable'
                or (directory / 'candidate/source.json').read_bytes() != sources['complete']):
            raise ValueError('native source-to-policy handoff changed source, selection, or expected outcome')
        checks.append({'case': f'native-handoff-column-{selected}', 'status': status})
    delivery = out / 'index-delivery'
    shutil.copytree(out / 'provider-error-diagnostic', delivery / 'diagnostic')
    error_pin = digest(rendered(planned_mapping('provider-error', 0)))
    request = {'request_version': 'aau-evidence-index-request/1.0', 'purpose': 'Synthetic native provider-error evidence',
               'items': [{'item_id': name, 'profile': 'promptfoo-' + name, 'purpose': 'Require this native evidence layer',
                          'controls': {'plan_sha256': error_pin}} for name in ('conversion', 'diagnostic')],
               'bindings': [{'left': {'item_id': 'conversion', 'role': 'source'},
                             'right': {'item_id': 'diagnostic', 'role': 'source'}}]}
    request_raw = rendered(request)
    index = create_index(request_raw, delivery, out / 'source-index', request_sha256=digest(request_raw))
    if (verify_index(out / 'source-index', request_sha256=digest(request_raw)) != index
            or index['exit_code'] != 1 or index['items'][0]['verification_status'] != 'missing'
            or index['items'][1]['verification_status'] != 'verified'
            or index['items'][1]['native_report']['conversion_eligibility']['status'] != 'rejected_by_current_converter'):
        raise ValueError('native provider-error index substituted diagnostic evidence for conversion')
    checks.append({'case': 'provider-error-source-index', 'status': 'missing_conversion_retained'})
    report = {'probe_version': 'aau-promptfoo-import-compatibility/1.0', 'aau_harness_version': version('aau-harness'),
              'producer_receipt_sha256': digest(producer_raw), 'checks': checks,
              'boundary': 'Four fixed native-export states: five projection/rejection checks, two diagnostics, two replay controls, '
                          'two policy handoffs selecting columns of the same synthetic export, and one incomplete source index. '
                          'Not a model evaluation, independent reproduction, source authentication, all-version support, '
                          'OS network sandbox, sanitized sharing artifact, or agency approval.'}
    write_json(report, out / 'compatibility.json')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = exercise(args.source, args.out)
    print(f'{len(report["checks"])} native Promptfoo importer checks passed; no model-performance claim.')


if __name__ == '__main__':
    main()
