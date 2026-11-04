"""Review complete evidence against a separately byte-pinned receiving-team request."""

import argparse
from pathlib import Path
import re
import sys

from .agent_bom import MAX_JSON_BYTES, _parse_json, digest, load_json, rendered, write_json
from .evaluation_context import compare_contexts
from .inspect_pack import PROFILES, InspectionError, _capture, inspect_pack


FORMATS = {'csv-review': 'csv', 'retry-review': 'retry-ledger', 'otlp-review': 'otlp', 'service-review': 'service-traces'}
BOUNDARY = (
    'Mechanical comparison with a separately supplied request-byte pin, not verification of reviewer identity, '
    'authority, independent approval, preregistration, signatures, procurement suitability, legal compliance, '
    'source authenticity, scoring validity, population effectiveness, or deployment approval. Protect the request '
    'and its expected hash independently of the delivered evidence. Computing that expected hash from a '
    'candidate-controlled request in the same job defeats the boundary. Pins identify exact EXPORTED member '
    'bytes, not canonical JSON or original pre-export file bytes; serialized JSON may differ from original files. '
    'Every required control-input role must be pinned. Candidate observations are intentionally not pinned: '
    'they are checked by the supplied policy/budget after matching declared benchmark context. Fingerprint '
    'equality is not authentic execution or proof of identical operating conditions. Unexpected profiles, '
    'versions, source formats, changed control inputs, unavailable context, failed policy, and unknown/failed '
    'budget outcomes cannot satisfy the request. No pins, requirements, branch protections, or CI settings are '
    'updated. The full pack is verified, never a favorable nested fallback. A second bounded capture must match '
    'the inspected inventory; this is not an atomic snapshot of a live directory. Keep the request, complete '
    'pack, and report together and reverify with a matching trusted harness. Hashes and source patterns may '
    'disclose information; no sanitization or permission to share is implied. No model, adapter, subprocess, '
    'upload, or network request is executed.'
)


def required_inputs(profile, pack_version, input_format):
    """Closed role-to-member mapping; never accept arbitrary paths supplied by a request."""
    if profile not in PROFILES or PROFILES[profile][3] != 'review':
        raise InspectionError('request_requires_supported_review_profile')
    base, versions, *_ = PROFILES[profile]
    if pack_version not in {f'{base}/{version}' for version in versions}:
        raise InspectionError('request_pack_version_not_supported')
    if profile == 'evaluation-review':
        version = pack_version.rsplit('/', 1)[1]
        formats = {'evaluations'} if version == '1.0' else {'recordings'} if version == '1.1' else {'evaluations', 'recordings'}
        if input_format not in formats:
            raise InspectionError('request_source_format_not_supported')
        roles = {'policy': ['policy.json'], 'baseline': ['baseline-recording.json' if input_format == 'recordings' else 'baseline.json']}
        if version in ('2.0', '3.0'):
            roles['diagnostics'] = ['diagnostics.json']
        if version == '3.0':
            roles['operating_budget'] = ['operating-budget.json']
        return roles
    if input_format != FORMATS[profile]:
        raise InspectionError('request_source_format_not_supported')
    source_file = {'csv-review': 'source.csv', 'retry-review': 'ledger.json', 'otlp-review': 'source.otlp',
                   'service-review': 'traces.json'}[profile]
    plan_file = 'mapping.json' if profile == 'otlp-review' else 'plan.json'
    roles = {'policy': ['review/policy.json'], 'baseline': [f'baseline/{source_file}'],
             'baseline_plan': [f'baseline/{plan_file}'], 'candidate_plan': [f'candidate/{plan_file}'],
             'diagnostics': ['review/diagnostics.json']}
    if profile == 'service-review':
        roles['service_suite'] = ['baseline/suite.json', 'candidate/suite.json']
    if pack_version.endswith('/1.1'):
        roles['operating_budget'] = ['review/operating-budget.json']
    return roles


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def validate_request(raw, expected_sha256):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise InspectionError('request_bytes_invalid_or_oversized')
    if not _sha(expected_sha256) or digest(raw) != expected_sha256:
        raise InspectionError('request_byte_pin_mismatch')
    request = _parse_json(raw)
    if (not isinstance(request, dict) or set(request) != {'request_version', 'profile', 'pack_version', 'input_format', 'pinned_inputs'}
            or request['request_version'] != 'aau-evidence-intake-request/1.0'
            or any(not isinstance(request[name], str) for name in ('profile', 'pack_version', 'input_format'))):
        raise InspectionError('invalid_intake_request')
    roles = required_inputs(request['profile'], request['pack_version'], request['input_format'])
    pins = request['pinned_inputs']
    if not isinstance(pins, dict) or set(pins) != set(roles) or not all(_sha(value) for value in pins.values()):
        raise InspectionError('request_requires_exact_control_input_pins')
    return request, roles


def review_intake(request_raw, directory: Path, *, request_sha256):
    try:
        request, roles = validate_request(request_raw, request_sha256)
        inspection = inspect_pack(directory)
        files, directories = _capture(directory)
        inventory = {name: digest(value) for name, value in sorted(files.items())}
        expected_directories = {parent.as_posix() for name in files for parent in Path(name).parents if parent != Path('.')}
        if inventory != inspection['captured_files_sha256'] or set(directories) != expected_directories:
            raise InspectionError('pack_changed_after_inspection')
        profile = inspection['profile']
        actual_format = (('recordings' if 'baseline-recording.json' in files else 'evaluations')
                         if profile == 'evaluation-review' else FORMATS.get(profile))
        checks = [{'constraint': name, 'expected': request[name], 'observed': observed, 'passed': request[name] == observed}
                  for name, observed in (('profile', profile), ('pack_version', inspection['pack_version']), ('input_format', actual_format))]
        shape_matches = all(check['passed'] for check in checks)
        input_checks = []
        for role, paths in sorted(roles.items()):
            for path in paths:
                observed = inventory.get(path) if shape_matches else None
                input_checks.append({'role': role, 'member': path, 'expected_sha256': request['pinned_inputs'][role],
                                     'observed_sha256': observed,
                                     'status': 'not_checked_profile_mismatch' if not shape_matches else
                                               'matched' if observed == request['pinned_inputs'][role] else 'mismatched'})
        context = {'status': 'not_checked_profile_mismatch', 'missing_sources': []}
        if shape_matches:
            prefix = '' if profile == 'evaluation-review' else 'review/'
            context = compare_contexts(*(_parse_json(files[f'{prefix}{side}.json']) for side in ('baseline', 'candidate')))
        checks.append({'constraint': 'matching_declared_context', 'expected': 'matched',
                       'observed': context['status'], 'passed': context['status'] == 'matched'})
        assessment = inspection['assessment']
        outcome_met = (assessment['kind'] in {'supplied_policy', 'supplied_policy_and_candidate_budget'}
                       and assessment['status'] == 'constraints_met')
        checks.append({'constraint': 'policy_and_any_candidate_budget', 'expected': 'constraints_met',
                       'observed': assessment['status'], 'passed': outcome_met})
        failed = [check['constraint'] for check in checks if not check['passed']]
        changed_roles = sorted({row['role'] for row in input_checks if row['status'] != 'matched'})
        return {'report_version': 'aau-evidence-intake-review/1.0',
                'status': 'request_constraints_not_met' if failed or changed_roles else 'request_constraints_met',
                'request_file_sha256': request_sha256, 'request_byte_pin_matched': True,
                'expected_profile': request['profile'], 'expected_pack_version': request['pack_version'],
                'expected_input_format': request['input_format'], 'checks': checks, 'control_input_checks': input_checks,
                'failed_constraints': failed, 'unmatched_input_roles': changed_roles, 'declared_context': context,
                'pack_inspection': inspection,
                'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                                          for name in ('intake_review.py', 'inspect_pack.py', 'evaluation_context.py', 'agent_bom.py')},
                'boundary': BOUNDARY}
    except InspectionError:
        raise
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        raise InspectionError('intake_inputs_or_evidence_invalid') from exc


def _read_request(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise InspectionError('request_file_invalid_or_oversized')
    with path.open('rb') as stream:
        return stream.read(MAX_JSON_BYTES + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau review-intake', description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--request-sha256', required=True, help='independently controlled SHA-256 of exact request file bytes')
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out and (args.out.resolve() == args.directory.resolve() or args.directory.resolve() in args.out.resolve().parents):
            raise InspectionError('output_must_be_outside_pack')
        report = review_intake(_read_request(args.request), args.directory, request_sha256=args.request_sha256)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise InspectionError('intake_report_does_not_recompute')
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {len(report['failed_constraints'])} failed requirements; "
              f"{len(report['unmatched_input_roles'])} unmatched input roles. Not approval or authenticated identity.")
        return int(report['status'] != 'request_constraints_met')
    except (ValueError, OSError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'intake_input_or_output_rejected'
        print(f'error: {reason}; no verified intake review produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
