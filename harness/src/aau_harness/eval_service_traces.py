"""Recompute public-service scores from separate contracts and normalized recorded traces."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_import import import_observations
from .eval_operations import validate_operating_measurements
from .evaluation_context import capture_context
from .public_value_review import _label, assess_public_value


FILES = {'plan.json', 'suite.json', 'traces.json', 'scoring.json', 'recording.json', 'evaluation.json', 'manifest.json'}
SCORING_FILES = ('eval_service_traces.py', 'public_value.py', 'public_value_review.py', 'eval_import.py',
                 'eval_audit.py', 'eval_operations.py', 'runner.py', 'evaluation_context.py', 'agent_bom.py')
PROTECTIONS = {'recourse_preserved': 'recourse_required', 'deadline_protected': 'deadline_preservation_required',
               'service_continuity_preserved': 'continuity_preservation_required'}
BOUNDARY = (
    'Offline rescoring of supplied normalized public-service traces against separately supplied contracts. '
    'Contracts are service-owner declarations, not inferred law or independently approved requirements. '
    'Trace events, submission flags, channels, and protections are supplied assertions, not authenticated tool logs; '
    'no model prose is interpreted and no tool or service is executed. Complete declared case/repeat coverage does '
    'not prove complete external activity or population representativeness. Input scores and per-observation '
    'contract overrides are not accepted. Inapplicable protections score as satisfied, not as performed protections; '
    'required-only coverage counts remain separate. Operating fields are copied when supplied, never measured, '
    'priced, or inferred; omitted values stay unknown. Scoring context binds supplied contract values and listed '
    'first-party source bytes, not an interpreter/dependency closure, authentic execution, or approval. Retained '
    'JSON values are not original file bytes. No sanitization, uploads, eligibility decisions, compliance '
    'certification, public-benefit claims, or deployment approval occurs. Inspect all labels and source values before sharing.'
)


def _bounded(value):
    try:
        json.dumps(value, allow_nan=False, ensure_ascii=False).encode('utf-8')
        if len(rendered(value)) > MAX_JSON_BYTES:
            raise AgentBomError('service-trace input exceeds 2 MB')
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise AgentBomError('service-trace inputs must be bounded finite UTF-8 JSON') from exc


def service_trace_payloads(plan: dict, suite: dict, traces: dict):
    for value in (plan, suite, traces):
        _bounded(value)
    if (not isinstance(plan, dict) or set(plan) != {'plan_version', 'source_label', 'n_repeats'}
            or plan['plan_version'] != 'aau-service-trace-import/1.0' or not _label(plan['source_label'])
            or type(plan['n_repeats']) is not int or not 1 <= plan['n_repeats'] <= 500):
        raise AgentBomError('service-trace plan requires version 1.0, a source label, and 1 to 500 repeats')
    if (not isinstance(suite, dict) or set(suite) != {'suite_version', 'cases'}
            or suite['suite_version'] != 'aau-public-value-suite/1.0' or not isinstance(suite['cases'], list)
            or not 1 <= len(suite['cases']) <= 500 or len(suite['cases']) * plan['n_repeats'] > 500):
        raise AgentBomError('service suite requires 1 to 500 cases and at most 500 planned observations')
    contracts = {}
    for case in suite['cases']:
        if (not isinstance(case, dict) or set(case) != {'case_id', 'contract'}
                or not _label(case['case_id']) or case['case_id'] in contracts):
            raise AgentBomError('service suite requires unique case IDs and separate contracts')
        contracts[case['case_id']] = case['contract']
    if (not isinstance(traces, dict) or set(traces) != {'trace_version', 'observations'}
            or traces['trace_version'] not in ('aau-public-value-traces/1.0', 'aau-public-value-traces/1.1')
            or not isinstance(traces['observations'], list)
            or len(traces['observations']) != len(contracts) * plan['n_repeats']):
        raise AgentBomError('service traces must cover the complete declared observation count')
    repeated = traces['trace_version'] == 'aau-public-value-traces/1.1'
    if not repeated and plan['n_repeats'] != 1:
        raise AgentBomError('legacy single-trace input requires exactly one planned repeat')
    required = {'case_id', 'trace'} | ({'repeat'} if repeated else set())
    optional = {'cost_usd', 'latency_s', 'n_api_calls'} if repeated else set()
    indexed = {}
    for row in traces['observations']:
        if not isinstance(row, dict) or not required <= set(row) or set(row) - required - optional:
            raise AgentBomError('trace observation has missing or unexpected fields; scores and contract overrides are not accepted')
        case_id, repeat = row['case_id'], row['repeat'] if repeated else 0
        if (not isinstance(case_id, str) or case_id not in contracts or type(repeat) is not int
                or not 0 <= repeat < plan['n_repeats'] or (case_id, repeat) in indexed):
            raise AgentBomError('every declared case/repeat requires exactly one trace; no filtering or imputation')
        indexed[case_id, repeat] = row
    validate_operating_measurements(list(indexed.values()))
    observations, assessments = [], []
    protection_counts = {name: {'required_observation_count': 0, 'satisfied_required_observation_count': 0,
                               'not_required_observation_count': 0} for name in PROTECTIONS}
    for (case_id, repeat), row in sorted(indexed.items()):
        assessment = assess_public_value(contracts[case_id], row['trace'])
        observations.append({'scenario_id': case_id, 'repeat': repeat, 'metrics': assessment['metrics'],
                             **{field: row[field] for field in sorted(optional) if field in row}})
        assessments.append({'case_id': case_id, 'repeat': repeat, 'assessment': assessment})
        for metric, flag in PROTECTIONS.items():
            counts = protection_counts[metric]
            if contracts[case_id].get(flag, False):
                counts['required_observation_count'] += 1
                counts['satisfied_required_observation_count'] += int(assessment['metrics'][metric])
            else:
                counts['not_required_observation_count'] += 1
    context = capture_context([{'scenario_id': name, 'contract': contracts[name]} for name in sorted(contracts)],
                              {'scoring_profile': 'aau-public-value-normalized-traces/1.0'},
                              {name: Path(__file__).with_name(name).read_bytes() for name in SCORING_FILES})
    recording = {'format_version': 'aau-recorded-observations/1.1', 'source_label': plan['source_label'],
                 'scenario_ids': sorted(contracts), 'n_repeats': plan['n_repeats'], 'evaluation_context': context,
                 'observations': observations}
    evaluation = import_observations(recording)
    failed = [{'case_id': row['case_id'], 'repeat': row['repeat']} for row in assessments
              if row['assessment']['status'] == 'evidence_failed']
    report = {'report_version': 'aau-service-trace-scoring/1.0', 'plan_sha256': digest(plan),
              'suite_sha256': digest(suite), 'traces_sha256': digest(traces),
              'recording_sha256': digest(recording), 'evaluation_sha256': digest(evaluation),
              'scenario_count': len(contracts), 'repeat_count': plan['n_repeats'], 'observation_count': len(observations),
              'failed_observations': failed, 'failed_observation_count': len(failed),
              'status': 'evidence_failed' if failed else 'evidence_passed',
              'required_protection_coverage': protection_counts, 'observations': assessments,
              'scoring_context': deepcopy(context), 'boundary': BOUNDARY}
    files = {name: rendered(value) for name, value in (('plan.json', plan), ('suite.json', suite), ('traces.json', traces),
             ('scoring.json', report), ('recording.json', recording), ('evaluation.json', evaluation))}
    files['manifest.json'] = rendered({'pack_version': 'aau-service-trace-pack/1.0',
                                      'files': {name: digest(value) for name, value in sorted(files.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in files.values()):
        raise AgentBomError('service-trace pack member exceeds 2 MB; no findings are truncated')
    return report, files


def create_service_trace_pack(plan, suite, traces, directory: Path):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite service-trace pack destination')
    report, files = service_trace_payloads(plan, suite, traces)
    directory.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(value)
    return report


def verify_service_trace_pack(directory: Path, *, evaluation_path: Path | None = None):
    if directory.is_symlink() or not directory.is_dir() or {path.name for path in directory.iterdir()} != FILES:
        raise AgentBomError('service-trace pack requires its exact seven-file set in a real directory')
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError('service-trace pack members must be bounded regular non-symlink files')
    report, files = service_trace_payloads(*(load_json(directory / name) for name in ('plan.json', 'suite.json', 'traces.json')))
    for name, value in files.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f'service-trace pack member does not recompute: {name}')
    if evaluation_path is not None and rendered(load_json(evaluation_path)) != files['evaluation.json']:
        raise AgentBomError('downstream evaluation does not match verified service-trace scoring')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau service-trace-eval', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    for name in ('plan', 'suite', 'traces'):
        create.add_argument(name, type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--evaluation', type=Path, help='also bind the normalized evaluation in a downstream review')
    args = parser.parse_args(argv)
    try:
        report = (create_service_trace_pack(load_json(args.plan), load_json(args.suite), load_json(args.traces), args.out)
                  if args.command == 'create' else verify_service_trace_pack(args.directory, evaluation_path=args.evaluation))
        print(f"Service-trace scoring: {report['status']}; {report['failed_observation_count']} failed observations. No service was executed.")
        return int(report['status'] != 'evidence_passed')
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
