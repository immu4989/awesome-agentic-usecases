"""Retain incomplete Inspect evidence for review without manufacturing an evaluation."""

from collections import Counter
from html import escape
from pathlib import Path

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .authority_html import STYLE
from .eval_inspect import _identity, _json, _number, _plan, _text, inspect_payloads
from .eval_pack import _table
from .inspect_pack import _capture


FILES = {'plan.json', 'source.json', 'diagnostic.json', 'review.html', 'manifest.json'}
BOUNDARY = (
    'Diagnostic of supplied finite Inspect version-2 JSON, not a converted evaluation, performance '
    'verdict, source authentication, complete schema validation, government adoption, or deployment approval. '
    'Missing log rows do not prove that an attempt never executed. Errors, retry records, limits, '
    'invalidations, and score-edit markers are separate recorded conditions, not inferred causes or '
    'automatic failing scores. Scored rows can also contain errors or limits. Duplicates remain '
    'ambiguous: no row is selected as the authoritative attempt. Recorded positions are zero-based '
    'source-array indexes; epochs remain one-based. Metric availability is not metric validity. '
    'The current strict converter is checked separately without writing its outputs; its first '
    'rejection reason is not an exhaustive schema assessment. Selected markers and mapped score '
    'availability are inspected, not arbitrary events, transcript semantics, attachment contents, '
    'or complete retry lineage. No code, model, network, URL, attachment, or subprocess from the '
    'log is executed or fetched. No repair, rescoring, retries, inferred costs, or synthetic missing '
    'observations are produced. Non-finite JSON, binary .eval files, and oversized evidence remain '
    'unsupported. Retained raw logs can contain sensitive data; this is not sanitization or permission '
    'to disclose. Hashes bind bytes, not identity, chronology, independence, or approval. Retain the '
    'complete packet and an independently reviewed plan pin with a matching trusted implementation.'
)


def _present(value):
    return value is not None and value != []


def _pointer(value):
    return value.replace('~', '~0').replace('/', '~1')


def _metric_state(scores, mapping):
    if scores is None:
        return 'scorer_absent'
    if not isinstance(scores, dict):
        return 'scores_shape_invalid'
    if mapping['scorer'] not in scores:
        return 'scorer_absent'
    score = scores[mapping['scorer']]
    if not isinstance(score, dict) or 'value' not in score:
        return 'score_shape_invalid'
    value = score['value']
    if mapping['value_key'] is not None:
        if not isinstance(value, dict):
            return 'component_shape_invalid'
        if mapping['value_key'] not in value:
            return 'component_absent'
        value = value[mapping['value_key']]
    if value is None:
        return 'value_null'
    if mapping['encoding'] == 'labels':
        if not isinstance(value, str) or value not in mapping['labels']:
            return 'label_unmapped'
        value = mapping['labels'][value]
        if value is None:
            return 'label_maps_to_absent'
    try:
        _number(value)
    except AgentBomError:
        return 'number_invalid'
    return 'available'


def render_diagnostic(report):
    def table(caption, headers, rows):
        return _table(caption, headers, rows).replace('<div class="scroll">',
            f'<div class="scroll" tabindex="0" role="region" aria-label="{escape(caption, quote=True)}">', 1)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Inspect evidence diagnostic</title>'
            f'<style>{STYLE}p,h1{{overflow-wrap:anywhere}}td{{white-space:pre-line;overflow-wrap:anywhere}}'
            'table{min-width:700px}.scroll:focus-visible{outline:3px solid #355c70;outline-offset:3px}'
            '@media print{table{min-width:0}}</style></head><body><main><h1>Inspect evidence diagnostic</h1>'
            f'<p class="notice">{escape(report["status"])} — diagnostic only, not an evaluation result.</p>'
            f'<p>Strict converter: {escape(report["conversion_eligibility"]["status"])}. '
            f'{escape(report["conversion_eligibility"]["first_rejection"] or "No rejection; this is not a quality pass.")}</p>'
            '<p>Missing rows remain missing. Duplicates remain ambiguous. Errors and limits can coexist with scores. '
            'No scores are repaired or exported. Positions below are zero-based source-array indexes; epochs are one-based.</p>'
            '<p>On narrow screens, scroll tables sideways; keyboard users can focus each table region.</p>'
            + table('Log-level findings', ('Finding', 'Source JSON pointer'),
                    [(r['code'], r['pointer']) for r in report['log_findings']])
            + table('Every planned sample and epoch', ('Scenario', 'Typed sample ID', 'Epoch', 'Presence', 'Source positions'),
                    [(r['scenario_id'], f"{r['sample_id_type']}: {r['sample_id']}", r['epoch'], r['presence'],
                      ', '.join(map(str, r['source_positions'])) or 'None') for r in report['planned_pairs']])
            + '<h2>Every supplied row, including duplicates and out-of-plan rows</h2>'
            + table('Recorded evidence markers and mapped metric availability', ('Position', 'Scenario', 'Markers', 'Mapped metrics'),
                    [(r['source_position'], r['scenario_id'] or 'Outside plan',
                      '\n'.join(f"{f['code']} ({f['pointer']})" for f in r['markers']) or 'None',
                      '\n'.join(f'{m}: {s}' for m, s in r['metric_states'].items())) for r in report['rows']])
            + f'<h2>Boundaries</h2><p>{escape(report["boundary"])}</p>'
            + f'<p>Plan hash: <code>{report["plan_sha256"]}</code></p></main></body></html>')


def diagnostic_payloads(plan_raw, source_raw, *, plan_sha256):
    plan, identities = _plan(plan_raw, plan_sha256)
    source = _json(source_raw)
    if type(source.get('version')) is not int or source['version'] != 2:
        raise AgentBomError('Inspect diagnostic requires a version-2 JSON object')
    status = source.get('status')
    if status not in ('started', 'success', 'error', 'cancelled'):
        raise AgentBomError('Inspect diagnostic requires a documented run status')
    samples = source.get('samples')
    samples_state = 'absent' if samples is None else 'present'
    if samples is None:
        samples = []
    if not isinstance(samples, list) or len(samples) > 10000:
        raise AgentBomError('Inspect diagnostic requires at most 10000 supplied sample rows')
    findings = []
    def finding(code, pointer):
        findings.append({'code': code, 'pointer': pointer})
    if status != 'success':
        finding('run_not_success', '/status')
    if samples_state == 'absent':
        finding('samples_unavailable', '/samples')
    for field in ('error', 'config_updates', 'log_updates'):
        if _present(source.get(field)):
            finding('log_' + field + '_recorded', '/' + field)
    if source.get('invalidated', False) is not False:
        finding('log_invalidation_marker', '/invalidated')
    for parent, field in (('eval', 'shards'), ('results', 'early_stopping')):
        obj = source.get(parent)
        if isinstance(obj, dict) and _present(obj.get(field)):
            finding(field + '_recorded', '/' + parent + '/' + field)
    rows, positions, expanded = [], {}, 0
    for position, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise AgentBomError('Inspect diagnostic sample rows must be objects')
        identity, epoch = _identity(sample.get('id')), sample.get('epoch')
        if type(epoch) is not int or not 1 <= epoch <= 10000:
            raise AgentBomError('Inspect diagnostic epochs must be integers from 1 to 10000')
        key = identity, epoch
        positions.setdefault(key, []).append(position)
        planned = identity in identities and epoch <= plan['n_repeats']
        markers, base = [], f'/samples/{position}'
        if not planned:
            markers.append({'code': 'outside_plan', 'pointer': base})
        for field in ('error', 'error_retries', 'invalidation', 'limit'):
            if _present(sample.get(field)):
                markers.append({'code': field + '_recorded', 'pointer': base + '/' + field})
        scores = sample.get('scores')
        if isinstance(scores, dict):
            for scorer, score in sorted(scores.items()):
                if not _text(scorer):
                    raise AgentBomError('Inspect diagnostic scorer names must be bounded nonblank strings')
                if isinstance(score, dict):
                    for field in ('history', 'reason'):
                        if _present(score.get(field)):
                            markers.append({'code': 'score_' + field + '_recorded',
                                            'pointer': base + '/scores/' + _pointer(scorer) + '/' + field})
        row = {'source_position': position, 'sample_id': sample['id'], 'sample_id_type': identity[0],
               'epoch': epoch, 'scenario_id': identities[identity] if planned else None, 'markers': markers,
               'metric_states': {name: _metric_state(scores, mapping) for name, mapping in sorted(plan['metrics'].items())}}
        expanded += len(rendered(row))
        if expanded > MAX_JSON_BYTES:
            raise AgentBomError('expanded Inspect diagnostic exceeds 2 MB')
        rows.append(row)
    pairs = []
    for item in plan['sample_map']:
        identity = _identity(item['sample_id'])
        for epoch in range(1, plan['n_repeats'] + 1):
            found = positions.get((identity, epoch), [])
            pair = {'scenario_id': item['scenario_id'], 'sample_id': item['sample_id'], 'sample_id_type': identity[0],
                    'epoch': epoch, 'presence': 'missing' if not found else 'unique' if len(found) == 1 else 'duplicate',
                    'source_positions': found}
            expanded += len(rendered(pair))
            if expanded > MAX_JSON_BYTES:
                raise AgentBomError('expanded Inspect diagnostic exceeds 2 MB')
            pairs.append(pair)
    # Check the exact existing projection contract; never relax it or write a partial evaluation.
    eligibility = {'status': 'accepted_by_current_converter', 'first_rejection': None}
    try:
        inspect_payloads(plan_raw, source_raw, plan_sha256=plan_sha256)
    except AgentBomError as exc:
        eligibility = {'status': 'rejected_by_current_converter', 'first_rejection': str(exc)}
    presence_counts = Counter(p['presence'] for p in pairs)
    marker_counts = Counter(code for r in rows for code in {marker['code'] for marker in r['markers']})
    needs_review = (bool(findings) or eligibility['first_rejection'] is not None
                    or any(p['presence'] != 'unique' for p in pairs)
                    or any(r['markers'] or any(v != 'available' for v in r['metric_states'].values()) for r in rows))
    report = {'report_version': 'aau-inspect-evidence-diagnostic/1.0',
              'status': 'review_required' if needs_review else 'no_diagnostic_findings',
              'source_json_sha256': digest(source_raw), 'plan_sha256': digest(plan_raw),
              'source_status': status, 'samples_state': samples_state, 'recorded_rows': len(rows),
              'planned_pair_count': len(pairs),
              'pair_counts': {k: presence_counts[k] for k in ('missing', 'unique', 'duplicate')},
              'row_marker_counts': dict(sorted(marker_counts.items())),
              'metric_state_counts': {name: dict(sorted(Counter(r['metric_states'][name] for r in rows).items()))
                                      for name in sorted(plan['metrics'])},
              'conversion_eligibility': eligibility, 'log_findings': findings, 'planned_pairs': pairs, 'rows': rows,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'inspect_diagnostic.py', 'eval_inspect.py', 'eval_import.py', 'eval_audit.py', 'runner.py',
                  'agent_bom.py', 'eval_pack.py', 'authority_html.py')}, 'boundary': BOUNDARY}
    files = {'plan.json': plan_raw, 'source.json': source_raw, 'diagnostic.json': rendered(report),
             'review.html': render_diagnostic(report).encode()}
    files['manifest.json'] = rendered({'pack_version': 'aau-inspect-diagnostic-pack/1.0',
                                      'files': {name: digest(raw) for name, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        raise AgentBomError('Inspect diagnostic pack member exceeds 2 MB')
    return report, files


def create_diagnostic(plan_raw, source_raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite an Inspect diagnostic destination')
    report, files = diagnostic_payloads(plan_raw, source_raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_diagnostic(directory, *, plan_sha256):
    files, directories = _capture(directory)
    if directories or set(files) != FILES:
        raise AgentBomError('Inspect diagnostic requires exactly five documented files')
    report, expected = diagnostic_payloads(files['plan.json'], files['source.json'], plan_sha256=plan_sha256)
    if files != expected:
        raise AgentBomError('Inspect diagnostic does not recompute byte-for-byte')
    return report
