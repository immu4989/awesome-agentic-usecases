"""Account for rejected Promptfoo evidence without exporting or repairing evaluation scores."""

from collections import Counter
from html import escape
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .eval_promptfoo import _index, _json, _number, _plan, _single_repeat, _text, promptfoo_payloads
from .inspect_pack import _capture
from .report_html import STYLE, table


FILES = {'plan.json', 'source.json', 'diagnostic.json', 'review.html', 'manifest.json'}
BOUNDARY = (
    'Diagnostic of supplied version-3 Promptfoo JSON, not an evaluation, quality verdict, source '
    'authentication, complete schema validation, government adoption, or deployment approval. '
    'The entire receiver-planned test/column census and every supplied row are retained. Missing '
    'rows do not prove an attempt never ran. Duplicate rows are not resolved into an authoritative '
    'attempt. Repeated tests are not guessed from row order, renamed, averaged, or treated as '
    'independent cases. Recorded outcome categories and mapped score availability do not establish '
    'valid scoring; scores can coexist with execution errors. The unchanged strict converter is '
    'checked separately; its first rejection is not an exhaustive finding list. A diagnostic can '
    'verify while conversion remains rejected. No evaluation.json, repaired scores, retries, inferred '
    'costs, latency, API counts, or execution context are produced. Code, providers, assertions, URLs, '
    'and attachments are never executed or fetched. Unknown fields remain in the original bytes, '
    'not interpreted as complete retry/edit history. Raw evidence may contain sensitive data; this '
    'is not sanitization or permission to disclose. Hashes bind bytes, not identity or chronology. '
    'Retain the independent plan pin and use a matching trusted implementation for replay.'
)


def _metric_state(row, mapping):
    field = mapping['field']
    container = row
    if field == 'namedScores':
        if field not in row:
            return 'absent'
        container, field = row[field], mapping['name']
        if not isinstance(container, dict):
            return 'container_invalid'
    if field not in container:
        return 'absent'
    value = container[field]
    if value is None:
        return 'null'
    if mapping['field'] == 'success':
        return 'available' if type(value) is bool else 'invalid'
    try:
        _number(value)
    except AgentBomError:
        return 'invalid'
    return 'available'


def render_diagnostic(report):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Promptfoo evidence diagnostic</title>'
            f'<style>{STYLE}td{{white-space:pre-line}}table{{min-width:700px}}</style></head><body><main>'
            '<h1>Promptfoo evidence diagnostic</h1>'
            f'<p class="notice">{escape(report["status"])} — not an evaluation or quality verdict.</p>'
            f'<p>Strict converter: {escape(report["conversion_eligibility"]["status"])}. '
            f'{escape(report["conversion_eligibility"]["first_rejection"] or "No rejection; not score acceptance.")}</p>'
            '<p>All columns are inspected. Missing rows remain missing; duplicates remain ambiguous. '
            'Mapped metric availability is not validity. No evaluation scores are exported.</p>'
            '<p>On narrow screens, scroll tables sideways; keyboard users can focus each table region.</p>'
            + table('Export-level findings', ('Finding', 'Source JSON pointer'),
                    [(f['code'], f['pointer']) for f in report['log_findings']])
            + table('Every planned test and column', ('Scenario', 'Test index', 'Column index', 'Presence', 'Source positions'),
                    [(p['scenario_id'], p['test_index'], p['prompt_index'], p['presence'],
                      ', '.join(map(str, p['source_positions'])) or 'None') for p in report['planned_pairs']])
            + table('Every supplied row including malformed and outside-plan rows',
                    ('Position', 'Planned scenario', 'Outcome category', 'Findings', 'Mapped metric availability'),
                    [(r['source_position'], r['scenario_id'] or 'Unassigned', r['outcome'],
                      '\n'.join(f"{f['code']} ({f['pointer']})" for f in r['markers']) or 'None',
                      '\n'.join(f'{name}: {state}' for name, state in r['metric_states'].items())) for r in report['rows']])
            + f'<h2>Boundaries</h2><p>{escape(BOUNDARY)}</p>'
            + f'<p>Plan hash: <code>{report["plan_sha256"]}</code></p></main></body></html>')


def diagnostic_payloads(plan_raw, source_raw, *, plan_sha256):
    plan, tests = _plan(plan_raw, plan_sha256)
    source = _json(source_raw)
    summary, metadata, config = source.get('results'), source.get('metadata'), source.get('config')
    if (not isinstance(summary, dict) or type(summary.get('version')) is not int or summary['version'] != 3
            or not isinstance(metadata, dict) or not _text(metadata.get('promptfooVersion')) or not isinstance(config, dict)):
        raise AgentBomError('Promptfoo diagnostic requires a version-3 OutputFile envelope, config, and declared producer')
    supplied = summary.get('results')
    rows_state = 'unavailable' if supplied is None else 'present'
    if supplied is None:
        supplied = []
    if not isinstance(supplied, list) or len(supplied) > 10000:
        raise AgentBomError('Promptfoo diagnostic requires at most 10000 supplied rows')
    findings = []
    def finding(code, pointer):
        findings.append({'code': code, 'pointer': pointer})
    if rows_state == 'unavailable':
        finding('rows_unavailable', '/results/results')
    for options, pointer in ((config.get('evaluateOptions'), '/config/evaluateOptions'),
                             (source.get('runtimeOptions'), '/runtimeOptions')):
        try:
            _single_repeat(options)
        except AgentBomError:
            finding('repeat_options_unsupported', pointer)
    columns, prompts = plan['columns'], summary.get('prompts')
    if not isinstance(prompts, list) or len(prompts) != len(columns):
        finding('prompt_inventory_mismatch', '/results/prompts')
    if isinstance(prompts, list):
        for i, column in enumerate(columns):
            if i < len(prompts) and (not isinstance(prompts[i], dict) or prompts[i].get('id') != column['prompt_id']
                                    or prompts[i].get('provider') != column['provider_id']):
                finding('prompt_identity_mismatch', f'/results/prompts/{i}')
    rows, positions, ids, expanded = [], {}, {}, 0
    counts = Counter()
    for position, original in enumerate(supplied):
        base, markers = f'/results/results/{position}', []
        def mark(code, field=''):
            markers.append({'code': code, 'pointer': base + field})
        row = original if isinstance(original, dict) else {}
        if not isinstance(original, dict):
            mark('row_shape_invalid')
        test, column_index = row.get('testIdx'), row.get('promptIdx')
        valid_indices = _index(test) and _index(column_index)
        planned = valid_indices and test in tests and column_index < len(columns)
        if valid_indices:
            positions.setdefault((test, column_index), []).append(position)
        else:
            mark('row_indices_invalid')
        if not planned:
            mark('outside_plan')
        if 'id' in row:
            if not _text(row['id']):
                mark('result_id_invalid', '/id')
            else:
                ids.setdefault(row['id'], []).append(position)
        if planned:
            column, provider = columns[column_index], row.get('provider')
            if (row.get('promptId') != column['prompt_id'] or not isinstance(provider, dict)
                    or provider.get('id') != column['provider_id']):
                mark('row_identity_mismatch')
        variables = row.get('vars', {})
        if not isinstance(variables, dict):
            mark('variables_shape_invalid', '/vars')
            variables = {}
        for container, field, pointer in ((variables, '__repeatIndex', '/vars/__repeatIndex'), (row, 'repeatIndex', '/repeatIndex')):
            if field in container and (type(container[field]) is not int or container[field] != 0):
                mark('repeat_marker_unsupported', pointer)
        reason, success = row.get('failureReason'), row.get('success')
        outcome = {0: 'none', 1: 'assertion_failure', 2: 'execution_error'}.get(reason, 'unknown') if type(reason) is int else 'unknown'
        counts[outcome] += 1
        if outcome == 'execution_error':
            mark('execution_error_recorded', '/failureReason')
        if outcome == 'unknown':
            mark('failure_category_unknown', '/failureReason')
        if type(success) is not bool or outcome == 'unknown' or success != (reason == 0):
            mark('success_state_inconsistent', '/success')
        error, response = row.get('error'), row.get('response')
        if error is not None and not isinstance(error, str):
            mark('error_shape_invalid', '/error')
        elif success is True and error:
            mark('successful_row_error_text', '/error')
        if response is not None:
            if not isinstance(response, dict):
                mark('response_shape_invalid', '/response')
            elif response.get('error') not in (None, ''):
                mark('response_error_recorded', '/response/error')
        grading = row.get('gradingResult')
        try:
            score = _number(row.get('score'))
            if ((reason == 1 and not isinstance(grading, dict)) or (grading is not None and (
                    not isinstance(grading, dict) or type(grading.get('pass')) is not bool
                    or grading['pass'] != success or _number(grading.get('score')) != score))):
                raise AgentBomError('inconsistent grading')
        except AgentBomError:
            mark('score_or_grading_invalid', '/gradingResult')
        named = row.get('namedScores', {})
        try:
            if not isinstance(named, dict) or any(not _text(name) for name in named):
                raise AgentBomError('invalid named scores')
            for value in named.values():
                if value is not None:
                    _number(value)
        except AgentBomError:
            mark('named_scores_invalid', '/namedScores')
        record = {'source_position': position, 'source_pointer': base, 'test_index': test if _index(test) else None,
                  'prompt_index': column_index if _index(column_index) else None,
                  'scenario_id': tests[test] if planned else None, 'planned': planned,
                  'selected_column': planned and column_index == plan['selected_prompt_index'], 'outcome': outcome,
                  'error_text_recorded': isinstance(error, str) and bool(error), 'markers': markers,
                  'metric_states': {name: _metric_state(row, mapping) for name, mapping in sorted(plan['metrics'].items())}}
        expanded += len(rendered(record))
        if expanded > MAX_JSON_BYTES:
            raise AgentBomError('expanded Promptfoo diagnostic exceeds 2 MB')
        rows.append(record)
    for group in (positions, ids):
        for found in group.values():
            if len(found) > 1:
                for position in found:
                    rows[position]['markers'].append({'code': 'duplicate_pair' if group is positions else 'duplicate_result_id',
                                                     'pointer': rows[position]['source_pointer']})
    pairs = []
    for item in plan['test_map']:
        for column in columns:
            found = positions.get((item['test_index'], column['prompt_index']), [])
            pairs.append({'scenario_id': item['scenario_id'], 'test_index': item['test_index'],
                          'prompt_index': column['prompt_index'], 'source_positions': found,
                          'presence': 'missing' if not found else 'unique' if len(found) == 1 else 'duplicate'})
    stats = summary.get('stats')
    if not isinstance(stats, dict):
        finding('summary_counts_unavailable', '/results/stats')
    else:
        for field, outcome in (('successes', 'none'), ('failures', 'assertion_failure'), ('errors', 'execution_error')):
            if type(stats.get(field)) is not int or stats[field] != counts[outcome]:
                finding('summary_count_mismatch', '/results/stats/' + field)
        if counts['unknown'] or any(any(m['code'] == 'success_state_inconsistent' for m in r['markers']) for r in rows):
            finding('summary_outcomes_ambiguous', '/results/stats')
    eligibility = {'status': 'accepted_by_current_converter', 'first_rejection': None}
    try:
        promptfoo_payloads(plan_raw, source_raw, plan_sha256=plan_sha256)
    except AgentBomError as exc:
        eligibility = {'status': 'rejected_by_current_converter', 'first_rejection': str(exc)}
    presence = Counter(p['presence'] for p in pairs)
    needs_review = (bool(findings) or eligibility['first_rejection'] is not None
                    or any(p['presence'] != 'unique' for p in pairs)
                    or any(r['markers'] or any(s != 'available' for s in r['metric_states'].values()) for r in rows))
    report = {'report_version': 'aau-promptfoo-evidence-diagnostic/1.0',
              'status': 'review_required' if needs_review else 'no_diagnostic_findings',
              'source_json_sha256': digest(source_raw), 'plan_sha256': digest(plan_raw),
              'declared_promptfoo_version': metadata['promptfooVersion'], 'rows_state': rows_state,
              'recorded_rows': len(rows), 'planned_pair_count': len(pairs),
              'pair_counts': {k: presence[k] for k in ('missing', 'unique', 'duplicate')},
              'outcome_category_counts': {k: counts[k] for k in ('none', 'assertion_failure', 'execution_error', 'unknown')},
              'row_marker_counts': dict(sorted(Counter(m['code'] for r in rows for m in r['markers']).items())),
              'log_findings': findings, 'planned_pairs': pairs, 'rows': rows, 'conversion_eligibility': eligibility,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'promptfoo_diagnostic.py', 'eval_promptfoo.py', 'eval_import.py', 'eval_audit.py', 'runner.py',
                  'agent_bom.py', 'report_html.py', 'authority_html.py')}, 'boundary': BOUNDARY}
    diagnostic = rendered(report)
    if len(diagnostic) > MAX_JSON_BYTES:
        raise AgentBomError('expanded Promptfoo diagnostic exceeds 2 MB')
    files = {'plan.json': plan_raw, 'source.json': source_raw, 'diagnostic.json': diagnostic,
             'review.html': render_diagnostic(report).encode()}
    files['manifest.json'] = rendered({'pack_version': 'aau-promptfoo-diagnostic-pack/1.0',
                                      'files': {name: digest(raw) for name, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        raise AgentBomError('Promptfoo diagnostic pack member exceeds 2 MB')
    return report, files


def create_diagnostic(plan_raw, source_raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite a Promptfoo diagnostic destination')
    report, files = diagnostic_payloads(plan_raw, source_raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_diagnostic(directory, *, plan_sha256):
    files, directories = _capture(directory)
    if directories or set(files) != FILES:
        raise AgentBomError('Promptfoo diagnostic requires exactly five documented files')
    report, expected = diagnostic_payloads(files['plan.json'], files['source.json'], plan_sha256=plan_sha256)
    if files != expected:
        raise AgentBomError('Promptfoo diagnostic does not recompute byte-for-byte')
    return report
