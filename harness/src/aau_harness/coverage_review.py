"""Review declared condition coverage without treating repeated runs as new cases."""

import argparse
from collections import Counter
from html import escape
from itertools import product
from pathlib import Path
import re
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .report_html import STYLE
from .eval_audit import audit_evaluation
from .eval_pack import _table
from .evaluation_context import validate_context
from .inspect_pack import _capture
from .intake_review import _read_request, _sha
from .reference_review import _document


FILES = {'plan.json', 'inventory.json', 'evaluation.json', 'review.json', 'review.html', 'manifest.json'}
BOUNDARY = (
    'Coverage of supplied recorded evidence against a declared condition grid, not model quality, '
    'population representativeness, fairness, statistical power, independence, authentic execution, '
    'government adoption, compliance, or deployment approval. Every declared dimension combination '
    'is reported, including explicitly excluded cells. A counted case has enough repeats with all '
    'required metrics present together, matching declared scenario fingerprints, and fully classified '
    'attributes. Score values are not compared with performance thresholds: failing scores can provide '
    'coverage. Repeats do not create additional cases. Duplicate declared scenario fingerprints are '
    'rejected, but different hashes do not establish semantic diversity or independent cases. '
    'Missing attributes and unavailable context fingerprints remain uncertain, never assigned to a '
    'favorable cell. Uncertain cases can appear in multiple cells; those per-cell possibilities cannot '
    'be added or assumed simultaneously attainable. Insufficient supplied measurements cannot count '
    'as coverage. Inventory-only cases remain unobserved. Classifications and hashes are supplied '
    'assertions; no underlying scenario is read and no authenticity or annotation correctness is proven. '
    'The evaluator and its summaries are not rerun against live systems; only supplied numeric rows '
    'are audited. No model, network, adapter, or subprocess is invoked. Bounds are engineering resource '
    'limits, not scientifically recommended sample sizes. Preserve the independently reviewed plan pin '
    'and all inputs; pins do not prove preregistration or authority. Raw evidence can be sensitive and '
    'is not sanitized or authorized for sharing. Condition coverage cannot substitute for independent '
    'validation, protected holdouts, operational monitoring, or domain review.'
)


def _fail(message):
    raise AgentBomError('coverage review: ' + message)


def _object(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        _fail('fields differ from the documented contract')


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value) is not None


def _text(value, maximum=200):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _plan(raw, pin):
    if not isinstance(raw, bytes) or not _sha(pin) or digest(raw) != pin:
        _fail('plan byte pin mismatch')
    plan = _document(raw)
    _object(plan, ('plan_version', 'purpose', 'dimensions', 'minimum_cases', 'minimum_complete_repeats',
                   'required_metrics', 'cell_overrides'))
    if plan['plan_version'] != 'aau-coverage-plan/1.0' or not _text(plan['purpose'], 2000):
        _fail('unsupported plan version or missing purpose')
    dimensions = plan['dimensions']
    if not isinstance(dimensions, dict) or not 1 <= len(dimensions) <= 5:
        _fail('require 1 to 5 named dimensions')
    total = 1
    for name, levels in dimensions.items():
        if (not _id(name) or not isinstance(levels, list) or not 1 <= len(levels) <= 10
                or not all(_id(v) for v in levels) or len(set(levels)) != len(levels)):
            _fail('each dimension requires 1 to 10 unique named levels')
        total *= len(levels)
    if total > 200:
        _fail('condition grid exceeds 200 cells')
    if not _integer(plan['minimum_cases'], 1, 500) or not _integer(plan['minimum_complete_repeats'], 1, 10000):
        _fail('invalid case or complete-repeat floor')
    metrics = plan['required_metrics']
    if (not isinstance(metrics, list) or not 1 <= len(metrics) <= 100 or not all(_text(m) for m in metrics)
            or len(set(metrics)) != len(metrics)):
        _fail('require 1 to 100 unique metric names')
    names = sorted(dimensions)
    cells = [dict(zip(names, values)) for values in product(*(dimensions[name] for name in names))]
    overrides = plan['cell_overrides']
    if not isinstance(overrides, list) or len(overrides) > total:
        _fail('invalid cell overrides')
    indexed = {}
    for override in overrides:
        _object(override, ('coordinates', 'minimum_cases', 'rationale'))
        coordinates = override['coordinates']
        _object(coordinates, names)
        if any(coordinates[name] not in dimensions[name] for name in names):
            _fail('override coordinates outside declared grid')
        key = tuple(coordinates[name] for name in names)
        if key in indexed or not _integer(override['minimum_cases'], 0, 500) or not _text(override['rationale'], 1000):
            _fail('duplicate or invalid cell override; exclusions require a rationale')
        indexed[key] = override
    if all(indexed.get(tuple(cell[n] for n in names), {}).get('minimum_cases', plan['minimum_cases']) == 0 for cell in cells):
        _fail('at least one condition cell must remain required')
    return plan, cells, indexed


def _inventory(raw, plan):
    inventory = _document(raw)
    _object(inventory, ('inventory_version', 'source_label', 'items'))
    if inventory['inventory_version'] != 'aau-coverage-inventory/1.0' or not _text(inventory['source_label']):
        _fail('unsupported inventory version or label')
    items = inventory['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        _fail('inventory requires 1 to 500 cases')
    indexed, hashes = {}, set()
    for item in items:
        _object(item, ('scenario_id', 'scenario_sha256', 'attributes'))
        if not _text(item['scenario_id']) or item['scenario_id'] in indexed:
            _fail('duplicate or invalid scenario ID')
        if not _sha(item['scenario_sha256']) or item['scenario_sha256'] in hashes:
            _fail('duplicate or invalid scenario fingerprint')
        attributes = item['attributes']
        _object(attributes, plan['dimensions'])
        for name, value in attributes.items():
            if value is not None and value not in plan['dimensions'][name]:
                _fail('unknown attribute value; use null for an unclassified attribute')
        indexed[item['scenario_id']] = item
        hashes.add(item['scenario_sha256'])
    return inventory, indexed


def render_review(report):
    table = _table
    cells = [('\n'.join(f'{k}: {v}' for k, v in r['coordinates'].items()), r['minimum_cases'],
              len(r['counted_scenario_ids']), len(r['uncertain_scenario_ids']), r['status'], r['override_rationale'] or 'Default floor')
             for r in report['cells']]
    cases = [(r['scenario_id'], '\n'.join(f'{k}: {v if v is not None else "unclassified"}' for k, v in r['attributes'].items()),
              r['observed_repeats'], r['complete_metric_repeats'], r['fingerprint_binding'], ', '.join(r['flags']) or 'None')
             for r in report['cases']]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Declared evaluation coverage</title>'
            f'<style>{STYLE}p,h1{{overflow-wrap:anywhere}}td{{white-space:pre-line;overflow-wrap:break-word}}'
            'table{min-width:750px}.scroll:focus-visible{outline:3px solid #355c70;outline-offset:3px}'
            '@media print{table{min-width:0}}</style></head><body><main><h1>Declared evaluation coverage</h1>'
            f'<p class="notice">{escape(report["status"])} — coverage only, not performance or deployment approval.</p>'
            f'<p>{escape(report["purpose"])}</p>'
            '<p>Counted cases have matching declared fingerprints, known attributes, and enough repeats with all '
            'required metrics recorded together. Repeats are not new cases. Uncertain cases may appear in more than '
            'one row and must not be added. Excluded cells remain visible.</p>'
            '<p>On narrow screens, scroll tables sideways. Keyboard users can focus a table region and use arrow keys.</p>'
            + table('Every declared condition combination', ('Condition', 'Required cases', 'Counted cases',
                'Uncertain cases', 'Coverage status', 'Override rationale'), cells)
            + '<h2>Case-level evidence and gaps</h2>'
            + table('Every inventory case, including unobserved cases', ('Scenario', 'Attributes', 'Recorded repeats',
                'Complete-metric repeats', 'Declared fingerprint binding', 'Review flags'), cases)
            + f'<h2>Boundaries</h2><p>{escape(report["boundary"])}</p>'
            + f'<p>Plan hash: <code>{report["input_sha256"]["plan.json"]}</code></p></main></body></html>')


def coverage_payloads(plan_raw, inventory_raw, evaluation_raw, *, plan_sha256):
    plan, grid, overrides = _plan(plan_raw, plan_sha256)
    inventory, indexed = _inventory(inventory_raw, plan)
    evaluation = _document(evaluation_raw)
    audit = audit_evaluation(evaluation)
    if audit['status'] != 'consistent':
        _fail('evaluation summaries are inconsistent; inspect with audit-eval before coverage review')
    observed = {}
    for row in evaluation['results']:
        if row['scenario_id'] not in indexed:
            _fail('evaluation contains a scenario outside the inventory')
        observed.setdefault(row['scenario_id'], []).append(row)
    context = evaluation.get('evaluation_context')
    if 'evaluation_context' in evaluation:
        validate_context(context, observed)
        for identity in observed:
            if context['scenario_sha256'][identity] != indexed[identity]['scenario_sha256']:
                _fail('evaluation and inventory scenario fingerprints disagree')
    cases = []
    for identity, item in sorted(indexed.items()):
        rows = observed.get(identity, [])
        complete = sum(set(plan['required_metrics']) <= set(row['metrics']) for row in rows)
        binding = 'matched' if rows and context is not None else 'unavailable' if rows else 'not_observed'
        flags = ([] if rows else ['not_observed'])
        if complete < plan['minimum_complete_repeats']:
            flags.append('insufficient_complete_metric_repeats')
        if rows and binding == 'unavailable':
            flags.append('scenario_fingerprint_unavailable')
        if any(value is None for value in item['attributes'].values()):
            flags.append('unclassified_attributes')
        cases.append({**item, 'observed_repeats': len(rows), 'complete_metric_repeats': complete,
                      'fingerprint_binding': binding, 'flags': flags})
    cells, expanded = [], len(rendered(cases))
    for coordinates in grid:
        override = overrides.get(tuple(coordinates[name] for name in sorted(coordinates)), {})
        floor = override.get('minimum_cases', plan['minimum_cases'])
        counted, uncertain = [], []
        for case in cases:
            if (case['complete_metric_repeats'] < plan['minimum_complete_repeats']
                    or any(case['attributes'][name] is not None and case['attributes'][name] != value
                           for name, value in coordinates.items())):
                continue
            if case['fingerprint_binding'] == 'matched' and all(v is not None for v in case['attributes'].values()):
                counted.append(case['scenario_id'])
            else:
                uncertain.append(case['scenario_id'])
        status = ('excluded' if floor == 0 else 'coverage_met' if len(counted) >= floor else
                  'coverage_not_met' if len(counted) + len(uncertain) < floor else 'coverage_not_verified')
        cell = {'coordinates': coordinates, 'minimum_cases': floor, 'counted_scenario_ids': counted,
                'uncertain_scenario_ids': uncertain, 'status': status, 'override_rationale': override.get('rationale')}
        expanded += len(rendered(cell))
        if expanded > MAX_JSON_BYTES:
            _fail('expanded coverage report exceeds 2 MB')
        cells.append(cell)
    counts = Counter(cell['status'] for cell in cells)
    status = ('coverage_not_met' if counts['coverage_not_met'] else
              'coverage_not_verified' if counts['coverage_not_verified'] else 'coverage_met')
    report = {'report_version': 'aau-coverage-review/1.0', 'status': status, 'purpose': plan['purpose'],
              'source_label': inventory['source_label'],
              'input_sha256': {'plan.json': digest(plan_raw), 'inventory.json': digest(inventory_raw),
                               'evaluation.json': digest(evaluation_raw)},
              'required_metrics': plan['required_metrics'], 'minimum_complete_repeats': plan['minimum_complete_repeats'],
              'inventory_cases': len(cases), 'recorded_cases': len(observed), 'recorded_observations': len(evaluation['results']),
              'cell_counts': {s: counts[s] for s in ('coverage_met', 'coverage_not_met', 'coverage_not_verified', 'excluded')},
              'cells': cells, 'cases': cases, 'summary_audit_status': audit['status'],
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'coverage_review.py', 'eval_audit.py', 'runner.py', 'evaluation_context.py', 'reference_review.py',
                  'agent_bom.py', 'intake_review.py', 'inspect_pack.py', 'eval_pack.py', 'authority_html.py')},
              'boundary': BOUNDARY}
    payloads = {'plan.json': plan_raw, 'inventory.json': inventory_raw, 'evaluation.json': evaluation_raw,
                'review.json': rendered(report), 'review.html': render_review(report).encode()}
    payloads['manifest.json'] = rendered({'pack_version': 'aau-coverage-review-pack/1.0',
                                        'files': {name: digest(raw) for name, raw in sorted(payloads.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in payloads.values()):
        _fail('generated coverage pack member exceeds 2 MB')
    return report, payloads


def create_coverage_pack(plan_raw, inventory_raw, evaluation_raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('refusing to overwrite an existing destination')
    report, files = coverage_payloads(plan_raw, inventory_raw, evaluation_raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_coverage_pack(directory, *, plan_sha256):
    files, directories = _capture(directory)
    if directories or set(files) != FILES:
        _fail('pack requires the exact six-file inventory')
    report, expected = coverage_payloads(files['plan.json'], files['inventory.json'], files['evaluation.json'], plan_sha256=plan_sha256)
    if files != expected:
        _fail('pack does not recompute byte-for-byte')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau coverage-review', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('plan', 'inventory', 'evaluation'):
        create.add_argument(name, type=Path)
    create.add_argument('--plan-sha256', required=True)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--plan-sha256', required=True)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .coverage_demo import create_demo
            create_demo(args.out)
            print('Created synthetic missing, uncertain, and covered evidence examples; not deployment approval.')
            return 0
        if args.command == 'create':
            create_coverage_pack(_read_request(args.plan), _read_request(args.inventory), _read_request(args.evaluation),
                                 args.out, plan_sha256=args.plan_sha256)
            report = verify_coverage_pack(args.out, plan_sha256=args.plan_sha256)
        else:
            report = verify_coverage_pack(args.directory, plan_sha256=args.plan_sha256)
        print(f"{report['status']}: declared condition coverage only, not performance or deployment approval.")
        return int(report['status'] != 'coverage_met')
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, AgentBomError) else 'coverage input or output rejected'
        print(f'error: {reason}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
