"""Bounded offline projection of Inspect JSON sample scores, without loading Inspect."""

import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import stat
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, _parse_json, digest, rendered
from .eval_import import import_observations


FILES = {'source.json', 'plan.json', 'recording.json', 'evaluation.json', 'conversion.json', 'manifest.json'}
BOUNDARY = (
    'Conversion of supplied Inspect version-2 JSON sample scores only; not execution, scoring validation, '
    'source authentication, approval, or government adoption. A success log status is not a passing score. '
    'Only the explicitly mapped scores are projected. Missing scorers, missing selected keys, null selected '
    'values, and labels explicitly mapped to null remain absent, never zero. All planned sample/epoch pairs '
    'must exist. Inspect aggregate metrics and epoch reducers are not copied: AAU recomputes its own summaries '
    'and coverage. No code, imports, attachments, URLs, tools, or models from the log are executed or fetched. '
    'This is a bounded supported subset, not full Inspect schema validation. No costs, latency, API-call counts, '
    'or evaluation-context fingerprints are inferred. Original bytes are retained and may contain sensitive '
    'transcripts or credentials; review before sharing. Hash pins bind bytes, not authenticity or approval. '
    'A pin copied from an untrusted supplier is not independent receiving-team control.'
)


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 200


def _json(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_JSON_BYTES:
        raise AgentBomError('Inspect inputs must contain 1 to 2000000 bytes')
    try:
        value = _parse_json(raw)
        json.dumps(value, allow_nan=False)  # Also rejects overflow such as 1e999 in unused fields.
        if not isinstance(value, dict):
            raise ValueError('object required')
        return value
    except (ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise AgentBomError('Inspect inputs require finite JSON objects without duplicate keys') from exc


def _identity(value):
    if not ((type(value) is int and abs(value) <= 10**15) or _text(value)):
        raise AgentBomError('sample IDs must be bounded integers or nonblank strings; no coercion')
    return type(value).__name__, value


def _number(value):
    if type(value) not in (int, float) or abs(value) > 10**15 or not math.isfinite(value):
        raise AgentBomError('mapped scores must be finite bounded numbers, not booleans or numeric strings')
    return value


def _plan(raw, pin):
    if not isinstance(pin, str) or len(pin) != 64 or set(pin) - set('0123456789abcdef') or digest(raw) != pin:
        raise AgentBomError('Inspect plan does not match the independently supplied SHA-256 pin')
    plan = _json(raw)
    required = {'plan_version', 'source_label', 'sample_map', 'n_repeats', 'metrics'}
    if set(plan) != required or plan['plan_version'] != 'aau-inspect-observation-plan/1.0':
        raise AgentBomError('unsupported Inspect plan version or fields')
    mapping, repeats, metrics = plan['sample_map'], plan['n_repeats'], plan['metrics']
    if (not _text(plan['source_label']) or not isinstance(mapping, list) or not 1 <= len(mapping) <= 500
            or type(repeats) is not int or repeats < 1 or repeats * len(mapping) > 10000):
        raise AgentBomError('plan requires a label, 1 to 500 samples, and at most 10000 sample/epoch pairs')
    ids, scenarios = {}, set()
    for item in mapping:
        if not isinstance(item, dict) or set(item) != {'sample_id', 'scenario_id'} or not _text(item['scenario_id']):
            raise AgentBomError('sample_map entries require sample_id and nonblank scenario_id')
        identity = _identity(item['sample_id'])
        if identity in ids or item['scenario_id'] in scenarios:
            raise AgentBomError('sample and scenario mappings must each be unique')
        ids[identity] = item['scenario_id']
        scenarios.add(item['scenario_id'])
    if not isinstance(metrics, dict) or not 1 <= len(metrics) <= 100 or any(not _text(m) for m in metrics):
        raise AgentBomError('plan requires 1 to 100 named metrics')
    sources = set()
    for config in metrics.values():
        if (not isinstance(config, dict) or set(config) not in (
                {'scorer', 'value_key', 'encoding'}, {'scorer', 'value_key', 'encoding', 'labels'})
                or not _text(config['scorer']) or not (config['value_key'] is None or _text(config['value_key']))):
            raise AgentBomError('metric mappings require scorer, value_key, encoding and optional label map')
        pair = config['scorer'], config['value_key']
        if pair in sources:
            raise AgentBomError('a score component cannot be relabeled as multiple metrics')
        sources.add(pair)
        if config['encoding'] == 'number' and 'labels' not in config:
            continue
        labels = config.get('labels')
        if (config['encoding'] != 'labels' or not isinstance(labels, dict) or not 1 <= len(labels) <= 100
                or any(not _text(label) for label in labels)):
            raise AgentBomError('encoding must be number or labels with an explicit nonempty string-label map')
        for value in labels.values():
            if value is not None:
                _number(value)
    return plan, ids


def _count(obj, field, expected, *, optional=False):
    value = obj.get(field)
    if optional and value is None:
        return
    if type(value) is not int or value != expected:
        raise AgentBomError(f'Inspect {field} disagrees with the complete planned sample/epoch census')


def _no_state(obj, fields):
    for field in fields:
        if obj.get(field) not in (None, []):
            raise AgentBomError(f'Inspect {field} is outside this unedited, uninterrupted import subset')


def inspect_payloads(plan_raw: bytes, raw: bytes, *, plan_sha256: str):
    plan, identities = _plan(plan_raw, plan_sha256)
    source = _json(raw)
    if type(source.get('version')) is not int or source['version'] != 2 or source.get('status') != 'success':
        raise AgentBomError('only successful Inspect version-2 JSON logs are supported; no aborted/header repair')
    _no_state(source, ('error', 'config_updates', 'log_updates'))
    if source.get('invalidated', False) is not False:
        raise AgentBomError('invalidated Inspect logs are unsupported')
    spec, results, samples = source.get('eval'), source.get('results'), source.get('samples')
    if not isinstance(spec, dict) or not isinstance(results, dict) or not isinstance(samples, list):
        raise AgentBomError('Inspect log needs eval, results and full samples, not just a header')
    config, packages = spec.get('config'), spec.get('packages')
    if (not isinstance(config, dict) or not isinstance(packages, dict)
            or not _text(packages.get('inspect_ai'))):
        raise AgentBomError('Inspect configuration and declared package version are required')
    epochs = config.get('epochs')
    if epochs is None:  # Inspect default is one epoch, not inferred from observed rows.
        epochs = 1
    _count({'epochs': epochs}, 'epochs', plan['n_repeats'])
    _no_state(spec, ('shards',))
    _no_state(results, ('early_stopping',))
    total = len(identities) * plan['n_repeats']
    for obj, field, optional in ((source, 'total_samples', True), (results, 'total_samples', False),
                                 (results, 'completed_samples', False), (results, 'logged_samples', True)):
        _count(obj, field, total, optional=optional)
    if len(samples) != total:
        raise AgentBomError('Inspect samples do not cover every planned sample/epoch pair')
    dataset = spec.get('dataset')
    if not isinstance(dataset, dict):
        raise AgentBomError('Inspect dataset metadata is required')
    if dataset.get('sample_ids') is not None:
        declared = dataset['sample_ids']
        if (not isinstance(declared, list) or len(declared) != len(identities)
                or {_identity(item) for item in declared} != set(identities)):
            raise AgentBomError('Inspect selected dataset IDs disagree with the plan')
    rows, seen, used, available, expanded = [], set(), set(), set(), 0
    for sample in samples:
        if not isinstance(sample, dict):
            raise AgentBomError('Inspect samples must be objects')
        identity, epoch = _identity(sample.get('id')), sample.get('epoch')
        if identity not in identities or type(epoch) is not int or not 1 <= epoch <= plan['n_repeats']:
            raise AgentBomError('Inspect sample ID or one-based epoch is outside the plan')
        key = identity, epoch
        if key in seen:
            raise AgentBomError('duplicate Inspect sample/epoch pair')
        seen.add(key)
        _no_state(sample, ('error', 'error_retries', 'invalidation', 'limit'))
        scores = sample.get('scores')
        if scores is None:
            scores = {}
        if not isinstance(scores, dict) or any(not _text(name) for name in scores):
            raise AgentBomError('Inspect sample scores must be a scorer-name object')
        available.update(scores)
        for score in scores.values():
            if not isinstance(score, dict) or 'value' not in score:
                raise AgentBomError('each recorded Inspect score must contain value')
            # Conservatively reject all edits/reasons, even on unmapped scorers.
            _no_state(score, ('history', 'reason'))
        row = {'scenario_id': identities[identity], 'repeat': epoch - 1, 'metrics': {}}
        for metric, mapping in plan['metrics'].items():
            scorer = mapping['scorer']
            if scorer not in scores:
                continue
            used.add(scorer)
            value = scores[scorer]['value']
            if mapping['value_key'] is not None:
                if not isinstance(value, dict):
                    raise AgentBomError('selected Inspect score component requires an object value')
                value = value.get(mapping['value_key'])
            if value is None:
                continue
            if mapping['encoding'] == 'labels':
                if not isinstance(value, str) or value not in mapping['labels']:
                    raise AgentBomError('Inspect score label is not explicitly mapped; no fallback value')
                value = mapping['labels'][value]
            if value is not None:
                row['metrics'][metric] = _number(value)
        expanded += len(rendered(row))
        if expanded > MAX_JSON_BYTES:
            raise AgentBomError('expanded Inspect observations exceed 2 MB')
        rows.append(row)
    recording = {'format_version': 'aau-recorded-observations/1.0', 'source_label': plan['source_label'],
                 'scenario_ids': [item['scenario_id'] for item in plan['sample_map']],
                 'n_repeats': plan['n_repeats'], 'observations': rows}
    evaluation = import_observations(recording)
    report = {'report_version': 'aau-inspect-observation-conversion/1.0',
              'source_json_sha256': digest(raw), 'plan_sha256': digest(plan_raw),
              'declared_inspect_version': packages['inspect_ai'], 'source_log_version': 2,
              'recording_sha256': digest(recording), 'evaluation_sha256': digest(evaluation),
              'observation_count': total, 'scenario_count': len(identities), 'epoch_count': plan['n_repeats'],
              'metric_mapping': deepcopy(plan['metrics']), 'metric_coverage': evaluation['metric_coverage'],
              'unreported_metrics': sorted(set(plan['metrics']) - set(evaluation['metric_coverage'])),
              'unmapped_scorers': sorted(available - used), 'boundary': BOUNDARY}
    payloads = {'source.json': raw, 'plan.json': plan_raw, 'recording.json': rendered(recording),
                'evaluation.json': rendered(evaluation), 'conversion.json': rendered(report)}
    payloads['manifest.json'] = rendered({'pack_version': 'aau-inspect-observation-pack/1.0',
                                        'files': {name: digest(value) for name, value in sorted(payloads.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError('Inspect conversion pack member exceeds 2 MB')
    return report, payloads


def _read(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JSON_BYTES:
        raise AgentBomError('Inspect inputs must be regular non-symlink files within 2 MB')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
            raise AgentBomError('Inspect input changed during capture')
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise AgentBomError('Inspect input exceeds 2 MB')
    return raw


def create_inspect_pack(plan_raw, raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite an existing Inspect conversion destination')
    report, payloads = inspect_payloads(plan_raw, raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in payloads.items():
        with (directory / name).open('xb') as stream:
            stream.write(value)  # Manifest last: interrupted packs do not verify.
    return report


def verify_inspect_pack(directory, *, plan_sha256, evaluation_path=None):
    if directory.is_symlink() or not directory.is_dir():
        raise AgentBomError('Inspect conversion needs a real pack directory')
    captured = {}
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name not in FILES:
                raise AgentBomError('Inspect conversion requires exactly six documented files')
            captured[entry.name] = _read(Path(entry.path))
    if set(captured) != FILES:
        raise AgentBomError('Inspect conversion requires exactly six documented files')
    report, expected = inspect_payloads(captured['plan.json'], captured['source.json'], plan_sha256=plan_sha256)
    if captured != expected:
        raise AgentBomError('Inspect conversion pack does not recompute byte-for-byte')
    if evaluation_path is not None and rendered(_json(_read(evaluation_path))) != expected['evaluation.json']:
        raise AgentBomError('downstream evaluation does not match the verified Inspect conversion')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau inspect-eval', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('plan', type=Path)
    create.add_argument('source', type=Path)
    create.add_argument('--out', type=Path, required=True)
    create.add_argument('--plan-sha256', required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--plan-sha256', required=True)
    verify.add_argument('--evaluation', type=Path)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    diagnose = commands.add_parser('diagnose', help='retain incomplete evidence without converting or repairing scores')
    diagnose.add_argument('plan', type=Path)
    diagnose.add_argument('source', type=Path)
    diagnose.add_argument('--out', type=Path, required=True)
    diagnose.add_argument('--plan-sha256', required=True)
    diagnostic_verify = commands.add_parser('verify-diagnostic')
    diagnostic_verify.add_argument('directory', type=Path)
    diagnostic_verify.add_argument('--plan-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .inspect_demo import create_demo
            create_demo(args.out)
            print('Created constructed Inspect-format demo; no model or Inspect execution.')
            return 0
        if args.command in ('diagnose', 'verify-diagnostic'):
            from .inspect_diagnostic import create_diagnostic, verify_diagnostic
            if args.command == 'diagnose':
                create_diagnostic(_read(args.plan), _read(args.source), args.out, plan_sha256=args.plan_sha256)
                report = verify_diagnostic(args.out, plan_sha256=args.plan_sha256)
            else:
                report = verify_diagnostic(args.directory, plan_sha256=args.plan_sha256)
            print(f"{report['status']}: Inspect evidence diagnostic only; no evaluation exported.")
            return int(report['status'] != 'no_diagnostic_findings')
        if args.command == 'create':
            create_inspect_pack(_read(args.plan), _read(args.source), args.out, plan_sha256=args.plan_sha256)
            report = verify_inspect_pack(args.out, plan_sha256=args.plan_sha256)
        else:
            report = verify_inspect_pack(args.directory, plan_sha256=args.plan_sha256, evaluation_path=args.evaluation)
        print(f"Inspect conversion verified: {report['observation_count']} supplied scores/epochs; not deployment approval.")
        return 0
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
