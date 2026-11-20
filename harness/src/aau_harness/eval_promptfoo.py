"""Offline, receiver-pinned projection of a bounded Promptfoo version-3 JSON export."""

import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, _parse_json, digest, rendered
from .eval_import import import_observations
from .eval_inspect import _read as _bounded_read


FILES = {'source.json', 'plan.json', 'recording.json', 'evaluation.json', 'conversion.json', 'manifest.json'}
BOUNDARY = (
    'Offline projection of supplied Promptfoo version-3 OutputFile exports, not execution, source '
    'authentication, scoring validation, deployment approval, or government adoption. One declared '
    'prompt/provider column is projected; every planned test/column pair must be present exactly once. '
    'Only single-repeat exports are supported. Failed assertions are retained; execution errors and '
    'ambiguous failure states are rejected, including in unselected columns. Missing/null named scores '
    'remain absent, never zero. Aggregate scores are not imported. No costs, latency, API counts, or '
    'evaluation-context fingerprints are inferred. Completeness is relative to the independently pinned '
    'plan, not proof of complete external history, absence of edits, or authentic execution. Config, '
    'assertions, providers, transcripts, URLs, traces, and attachments are data: never executed or fetched. '
    'This is a bounded subset, not full Promptfoo schema validation or all-version compatibility. Raw '
    'bytes may contain private data or credentials; review before sharing. Hashes bind bytes, not trust.'
)


def _fail(message):
    raise AgentBomError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 200


def _index(value):
    return type(value) is int and 0 <= value < 10000


def _number(value):
    if type(value) not in (int, float) or abs(value) > 10**15 or not math.isfinite(value):
        _fail('Promptfoo scores must be finite bounded numbers, not booleans or strings')
    return value


def _json(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_JSON_BYTES:
        _fail('Promptfoo inputs require 1 to 2000000 bytes')
    try:
        value = _parse_json(raw)
        json.dumps(value, allow_nan=False)
        if not isinstance(value, dict):
            raise ValueError('object required')
        return value
    except (ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise AgentBomError('Promptfoo inputs require finite JSON objects without duplicate keys') from exc


def _read(path):
    # Share the existing bounded non-symlink reader; do not load any exporter code.
    try:
        return _bounded_read(path)
    except AgentBomError as exc:
        raise AgentBomError('Promptfoo inputs must be bounded regular non-symlink files') from exc


def _plan(raw, pin):
    if not isinstance(pin, str) or len(pin) != 64 or set(pin) - set('0123456789abcdef') or digest(raw) != pin:
        _fail('Promptfoo plan differs from the independently supplied SHA-256 pin')
    plan = _json(raw)
    fields = {'plan_version', 'source_label', 'test_map', 'columns', 'selected_prompt_index', 'metrics'}
    if set(plan) != fields or plan['plan_version'] != 'aau-promptfoo-observation-plan/1.0':
        _fail('unsupported Promptfoo plan fields or version')
    tests, columns, metrics = plan['test_map'], plan['columns'], plan['metrics']
    if (not _text(plan['source_label']) or not isinstance(tests, list) or not 1 <= len(tests) <= 500
            or not isinstance(columns, list) or not 1 <= len(columns) <= 20):
        _fail('plan requires a label, 1 to 500 tests and 1 to 20 columns')
    identities, scenarios = {}, set()
    for item in tests:
        if (not isinstance(item, dict) or set(item) != {'test_index', 'scenario_id'}
                or not _index(item['test_index']) or not _text(item['scenario_id'])
                or item['test_index'] in identities or item['scenario_id'] in scenarios):
            _fail('test mapping needs unique integer indices and unique scenario IDs')
        identities[item['test_index']] = item['scenario_id']
        scenarios.add(item['scenario_id'])
    for index, column in enumerate(columns):
        if (not isinstance(column, dict) or set(column) != {'prompt_index', 'prompt_id', 'provider_id'}
                or not _index(column['prompt_index']) or column['prompt_index'] != index
                or not _text(column['prompt_id']) or not _text(column['provider_id'])):
            _fail('columns require contiguous zero-based indices and explicit prompt/provider IDs')
    selected = plan['selected_prompt_index']
    if not _index(selected) or selected >= len(columns):
        _fail('selected column is outside the declared column inventory')
    if not isinstance(metrics, dict) or not 1 <= len(metrics) <= 100 or any(not _text(m) for m in metrics):
        _fail('plan requires 1 to 100 explicit metric mappings')
    seen = set()
    for mapping in metrics.values():
        if not isinstance(mapping, dict):
            _fail('metric mapping must be an object')
        if set(mapping) == {'field'} and mapping['field'] in ('score', 'success'):
            key = mapping['field'], None
        elif set(mapping) == {'field', 'name'} and mapping['field'] == 'namedScores' and _text(mapping['name']):
            key = mapping['field'], mapping['name']
        else:
            _fail('metric field must be score, success, or an explicitly named namedScores entry')
        if key in seen:
            _fail('a source score cannot be relabeled as multiple metrics')
        seen.add(key)
    return plan, identities


def _single_repeat(options):
    if options is None:
        return
    if not isinstance(options, dict):
        _fail('export options must be objects')
    if 'repeat' in options and (type(options['repeat']) is not int or options['repeat'] != 1):
        _fail('only single-repeat exports are supported; repeated rows are never guessed or averaged')


def promptfoo_payloads(plan_raw, source_raw, *, plan_sha256):
    plan, tests = _plan(plan_raw, plan_sha256)
    source = _json(source_raw)
    summary, metadata, config = source.get('results'), source.get('metadata'), source.get('config')
    if (not isinstance(summary, dict) or type(summary.get('version')) is not int or summary['version'] != 3
            or not isinstance(metadata, dict) or not _text(metadata.get('promptfooVersion'))
            or not isinstance(config, dict)):
        _fail('requires a version-3 OutputFile envelope, config, and declared promptfooVersion')
    _single_repeat(config.get('evaluateOptions'))
    _single_repeat(source.get('runtimeOptions'))
    prompts, rows, stats = summary.get('prompts'), summary.get('results'), summary.get('stats')
    columns = plan['columns']
    if not isinstance(prompts, list) or len(prompts) != len(columns):
        _fail('export prompt inventory does not match the planned columns')
    for prompt, column in zip(prompts, columns):
        if (not isinstance(prompt, dict) or prompt.get('id') != column['prompt_id']
                or prompt.get('provider') != column['provider_id']):
            _fail('export prompt/provider identity differs from the plan')
    total = len(tests) * len(columns)
    if not isinstance(rows, list) or len(rows) != total or not isinstance(stats, dict):
        _fail('export must contain the full planned test/column census and summary counts')
    counts = {'successes': 0, 'failures': 0, 'errors': 0}
    seen, ids, observations, origins, named, expanded = set(), set(), [], [], set(), 0
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail('export result rows must be objects')
        test, column_index = row.get('testIdx'), row.get('promptIdx')
        if not _index(test) or test not in tests or not _index(column_index) or column_index >= len(columns):
            _fail('row index lies outside the planned census')
        key = test, column_index
        if key in seen:
            _fail('duplicate test/column pair; repeated attempts are unsupported')
        seen.add(key)
        if 'id' in row:
            if not _text(row['id']) or row['id'] in ids:
                _fail('recorded result IDs must be unique nonblank strings')
            ids.add(row['id'])
        column, provider = columns[column_index], row.get('provider')
        if (row.get('promptId') != column['prompt_id'] or not isinstance(provider, dict)
                or provider.get('id') != column['provider_id']):
            _fail('row prompt/provider identity differs from its declared column')
        variables = row.get('vars', {})
        if not isinstance(variables, dict):
            _fail('recorded variables must be an object')
        for container, field in ((variables, '__repeatIndex'), (row, 'repeatIndex')):
            if field in container and (type(container[field]) is not int or container[field] != 0):
                _fail('nonzero or invalid repeat markers are unsupported')
        reason, success = row.get('failureReason'), row.get('success')
        if type(reason) is not int or reason not in (0, 1) or type(success) is not bool or success != (reason == 0):
            _fail('execution errors, unknown failure categories, and inconsistent success states are unsupported')
        error = row.get('error')
        if error is not None and not isinstance(error, str):
            _fail('recorded error text must be a string or null')
        if success and error:
            _fail('successful row contains ambiguous error text')
        response = row.get('response')
        if response is not None and (not isinstance(response, dict) or response.get('error') not in (None, '')):
            _fail('provider response errors are unsupported even when grading reports a failure')
        score = _number(row.get('score'))
        grading = row.get('gradingResult')
        if reason == 1 and not isinstance(grading, dict):
            _fail('assertion failure requires a recorded grading result')
        if grading is not None and (not isinstance(grading, dict) or type(grading.get('pass')) is not bool
                or grading['pass'] != success or _number(grading.get('score')) != score):
            _fail('recorded grading result disagrees with the result row')
        counts['successes' if success else 'failures'] += 1
        named_scores = row.get('namedScores', {})
        if not isinstance(named_scores, dict) or any(not _text(name) for name in named_scores):
            _fail('namedScores must be a named object')
        for value in named_scores.values():
            if value is not None:
                _number(value)
        if column_index != plan['selected_prompt_index']:
            continue
        named.update(named_scores)
        observation = {'scenario_id': tests[test], 'repeat': 0, 'metrics': {}}
        for metric, mapping in plan['metrics'].items():
            field = mapping['field']
            value = int(success) if field == 'success' else score if field == 'score' else named_scores.get(mapping['name'])
            if value is not None:
                observation['metrics'][metric] = value
        expanded += len(rendered(observation))
        if expanded > MAX_JSON_BYTES:
            _fail('expanded Promptfoo observations exceed 2 MB')
        observations.append(observation)
        origins.append({'scenario_id': tests[test], 'source_pointer': f'/results/results/{position}',
                        'test_index': test, 'prompt_index': column_index, 'failure_reason': reason})
    if any(type(stats.get(key)) is not int or stats[key] != value for key, value in counts.items()):
        _fail('declared export counts disagree with observed row outcomes')
    recording = {'format_version': 'aau-recorded-observations/1.0', 'source_label': plan['source_label'],
                 'scenario_ids': [item['scenario_id'] for item in plan['test_map']], 'n_repeats': 1,
                 'observations': observations}
    evaluation = import_observations(recording)
    report = {'report_version': 'aau-promptfoo-observation-conversion/1.0', 'source_json_sha256': digest(source_raw),
              'plan_sha256': digest(plan_raw), 'declared_promptfoo_version': metadata['promptfooVersion'],
              'source_summary_version': 3, 'validated_row_count': total, 'projected_row_count': len(observations),
              'selected_column': deepcopy(columns[plan['selected_prompt_index']]),
              'unprojected_columns': deepcopy([c for c in columns if c['prompt_index'] != plan['selected_prompt_index']]),
              'source_outcomes': counts, 'row_origins': origins, 'metric_mapping': deepcopy(plan['metrics']),
              'metric_coverage': evaluation['metric_coverage'],
              'unreported_metrics': sorted(set(plan['metrics']) - set(evaluation['metric_coverage'])),
              'unmapped_named_scores': sorted(named - {m['name'] for m in plan['metrics'].values() if m['field'] == 'namedScores'}),
              'recording_sha256': digest(recording), 'evaluation_sha256': digest(evaluation), 'boundary': BOUNDARY}
    payloads = {'source.json': source_raw, 'plan.json': plan_raw, 'recording.json': rendered(recording),
                'evaluation.json': rendered(evaluation), 'conversion.json': rendered(report)}
    payloads['manifest.json'] = rendered({'pack_version': 'aau-promptfoo-observation-pack/1.0',
                                        'files': {name: digest(value) for name, value in sorted(payloads.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        _fail('Promptfoo packet member exceeds 2 MB')
    return report, payloads


def create_promptfoo_pack(plan_raw, source_raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('refusing to overwrite an existing Promptfoo conversion destination')
    report, payloads = promptfoo_payloads(plan_raw, source_raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in payloads.items():
        with (directory / name).open('xb') as stream:
            stream.write(value)
    return report


def verify_promptfoo_pack(directory, *, plan_sha256, evaluation_path=None):
    if directory.is_symlink() or not directory.is_dir():
        _fail('Promptfoo conversion requires a real directory')
    captured = {}
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name not in FILES:
                _fail('Promptfoo conversion requires exactly six files')
            captured[entry.name] = _read(Path(entry.path))
    if set(captured) != FILES:
        _fail('Promptfoo conversion requires exactly six files')
    report, expected = promptfoo_payloads(captured['plan.json'], captured['source.json'], plan_sha256=plan_sha256)
    if captured != expected:
        _fail('Promptfoo conversion does not recompute byte-for-byte')
    if evaluation_path is not None and rendered(_json(_read(evaluation_path))) != expected['evaluation.json']:
        _fail('downstream evaluation differs from the verified Promptfoo conversion')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau promptfoo-eval', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('plan', type=Path)
    create.add_argument('source', type=Path)
    create.add_argument('--plan-sha256', required=True)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--plan-sha256', required=True)
    verify.add_argument('--evaluation', type=Path)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .promptfoo_demo import create_demo
            create_demo(args.out)
            print('Created constructed Promptfoo-format demo; no exporter or model executed.')
            return 0
        if args.command == 'create':
            create_promptfoo_pack(_read(args.plan), _read(args.source), args.out, plan_sha256=args.plan_sha256)
            report = verify_promptfoo_pack(args.out, plan_sha256=args.plan_sha256)
        else:
            report = verify_promptfoo_pack(args.directory, plan_sha256=args.plan_sha256, evaluation_path=args.evaluation)
        print(f"Promptfoo conversion verified: {report['projected_row_count']} projected of {report['validated_row_count']} checked rows; not score acceptance or approval.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
