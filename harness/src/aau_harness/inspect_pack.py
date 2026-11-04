"""Recognize and fully verify supported recorded-evidence packs without running pack-supplied code."""

import argparse
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .eval_pack import verify_pack
from .eval_csv import verify_csv_pack
from .eval_csv_review import verify_handoff as verify_csv_review
from .eval_retries import verify_retry_pack
from .eval_retry_review import verify_handoff as verify_retry_review
from .eval_otlp import verify_otlp_pack
from .eval_otlp_review import verify_handoff as verify_otlp_review
from .eval_service_traces import verify_service_trace_pack
from .eval_service_review import verify_handoff as verify_service_review
from .eval_failure_pack import verify_failure_bound_pack
from .service_challenge import verify_challenge
from .service_reproducer import verify_reproducer


# Only trusted installed implementations appear here; no module/command is imported from a manifest.
PROFILES = {
    'evaluation-review': ('aau-evaluation-review-pack', ('1.0', '1.1', '2.0', '3.0'), verify_pack, 'review', 'evaluation-pack', 'review.html'),
    'csv-review': ('aau-csv-evaluation-handoff-pack', ('1.0', '1.1'), verify_csv_review, 'review', 'csv-review', 'review/review.html'),
    'retry-review': ('aau-retry-evaluation-handoff-pack', ('1.0', '1.1'), verify_retry_review, 'review', 'retry-review', 'review/review.html'),
    'otlp-review': ('aau-otlp-evaluation-handoff-pack', ('1.0', '1.1'), verify_otlp_review, 'review', 'otlp-review', 'review/review.html'),
    'service-review': ('aau-service-evaluation-handoff-pack', ('1.0', '1.1'), verify_service_review, 'review', 'service-review', 'review/review.html'),
    'csv-source': ('aau-csv-observation-pack', ('1.0',), verify_csv_pack, 'conversion', 'csv-eval', 'conversion.json'),
    'retry-source': ('aau-retry-accounting-pack', ('1.0',), verify_retry_pack, 'conversion', 'retry-eval', 'accounting.json'),
    'otlp-source': ('aau-otlp-retry-pack', ('1.0',), verify_otlp_pack, 'conversion', 'otlp-retries', 'projection.json'),
    'service-traces': ('aau-service-trace-pack', ('1.0',), verify_service_trace_pack, 'service', 'service-trace-eval', 'scoring.json'),
    'service-challenge': ('aau-service-obligation-challenge-pack', ('1.0',), verify_challenge, 'challenge', 'service-challenge', 'README.txt'),
    'service-reproducer': ('aau-label-minimized-service-pack', ('1.0',), verify_reproducer, 'minimized_service', 'service-reproducer', 'README.txt'),
    'failure-bounds': ('aau-failure-bound-pack', ('1.0',), verify_failure_bound_pack, 'diagnostic', 'failure-bound-pack', 'review.html'),
}
MAX_FILES = 64
MAX_DIRECTORIES = 16
MAX_TOTAL_BYTES = MAX_FILES * MAX_JSON_BYTES
BOUNDARY = (
    'Intake of a bounded local copy using an explicitly allowlisted installed verifier, not a generic manifest '
    'trust check. A recognized version is only a routing hint until full source-to-output recomputation succeeds. '
    'Integrity, supplied policy/budget outcomes, service obligations, and non-decision diagnostics remain distinct. '
    'A valid conversion or challenge is not a passed policy or a tested adapter. No fallback to a nested or weaker '
    'pack occurs after failure. The supplied path is the scope: inspecting a nested pack cannot establish its '
    'relationship to an omitted parent handoff. Require the expected profile and budget layer independently. '
    'The local copy is not an atomic capture of a concurrently changing source; hashes identify the inspected '
    'copied bytes, not later directory contents, signatures, approved requirements, source authenticity, scoring '
    'validity, population effectiveness, or deployment approval. No adapter, model, subprocess, pack-provided '
    'instruction, or network request is executed. HTML and raw sources are not opened automatically. '
    'Summary hashes and retained source patterns can disclose information; this is not sanitization or permission '
    'to share. First-party verifier code comes from the current installed harness, not from the pack. Use a '
    'matching trusted version, retain the complete pack, and independently review full findings and limitations.'
)


class InspectionError(AgentBomError):
    """Closed reason codes only: do not expose untrusted labels or local paths."""


def _capture(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise InspectionError('pack_directory_required')
    files, pending, directories, total = {}, [(directory, '', 0)], [], 0
    while pending:
        folder, prefix, depth = pending.pop()
        if folder.is_symlink() or not folder.is_dir():
            raise InspectionError('non_regular_member')
        with os.scandir(folder) as entries:
            for entry in entries:
                if not re.fullmatch(r'[A-Za-z0-9_.-]+', entry.name):
                    raise InspectionError('unsupported_member_name')
                path, name = Path(entry.path), prefix + entry.name
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    directories.append(name)
                    if depth >= 3 or len(directories) >= MAX_DIRECTORIES:
                        raise InspectionError('pack_resource_limit')
                    pending.append((path, name + '/', depth + 1))
                elif stat.S_ISREG(info.st_mode):
                    if len(files) >= MAX_FILES or info.st_size > MAX_JSON_BYTES:
                        raise InspectionError('pack_resource_limit')
                    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
                    with os.fdopen(os.open(path, flags), 'rb') as stream:
                        opened = os.fstat(stream.fileno())
                        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                            raise InspectionError('member_changed_during_capture')
                        payload = stream.read(MAX_JSON_BYTES + 1)
                    total += len(payload)
                    if len(payload) > MAX_JSON_BYTES or total > MAX_TOTAL_BYTES:
                        raise InspectionError('pack_resource_limit')
                    files[name] = payload
                else:
                    raise InspectionError('non_regular_member')
    return files, directories


def _outcome(kind, native):
    policy = budget = service = None
    if kind == 'review':
        status = native['status']
        policy = native.get('policy_status', status)
        budget = native.get('candidate_budget_status')
        outcome = 'supplied_policy_and_candidate_budget' if budget is not None else 'supplied_policy'
        allowed = {'constraints_met', 'constraints_not_met', 'constraints_not_verified'}
        if status not in allowed or policy not in allowed or (budget is not None and budget not in allowed):
            raise InspectionError('unexpected_verifier_outcome')
        exit_code = int(status != 'constraints_met')
    elif kind in ('service', 'minimized_service'):
        service = native['service_status'] if kind == 'minimized_service' else native['status']
        if service not in {'evidence_passed', 'evidence_failed'}:
            raise InspectionError('unexpected_verifier_outcome')
        outcome, status, exit_code = 'supplied_service_obligations', service, int(service != 'evidence_passed')
    elif kind == 'diagnostic':
        outcome, status, exit_code = 'diagnostic_not_a_gate', native['status'], 0
        if status not in {'population_inference_withheld', 'conditional_bounds_within_limits', 'conditional_bounds_exceed_limits'}:
            raise InspectionError('unexpected_verifier_outcome')
    else:
        outcome, status, exit_code = 'not_assessed', 'adapter_responses_not_supplied' if kind == 'challenge' else 'conversion_only', 0
    return {'kind': outcome, 'status': status, 'policy_status': policy, 'candidate_budget_status': budget,
            'service_status': service}, exit_code


def inspect_pack(directory: Path, *, expect=None, require_budget=False):
    if expect is not None and expect not in PROFILES:
        raise InspectionError('unsupported_expected_profile')
    if type(require_budget) is not bool:
        raise InspectionError('invalid_budget_requirement')
    try:
        captured, directories = _capture(directory)
        if 'manifest.json' not in captured:
            raise InspectionError('root_manifest_required')
        with tempfile.TemporaryDirectory(prefix='aau-pack-inspection-') as temporary:
            snapshot = Path(temporary)
            for name in directories:
                (snapshot / name).mkdir(parents=True, exist_ok=True)
            for name, payload in captured.items():
                path = snapshot / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            version = load_json(snapshot / 'manifest.json').get('pack_version')
            matches = [name for name, (base, versions, *_) in PROFILES.items() if version in {f'{base}/{v}' for v in versions}]
            if len(matches) != 1:
                raise InspectionError('unsupported_pack_version')
            profile = matches[0]
            if expect is not None and profile != expect:
                raise InspectionError('unexpected_pack_profile')
            _, _, verifier, kind, command, document = PROFILES[profile]
            if require_budget and kind != 'review':
                raise InspectionError('budget_layer_not_supported')
            # The route is provisional until this exact established verifier succeeds.
            try:
                native = verifier(snapshot, require_budget=require_budget) if kind == 'review' else verifier(snapshot)
            except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
                raise InspectionError('full_verification_failed') from exc
            assessment, exit_code = _outcome(kind, native)
            argv = ['aau', command, 'verify', 'PATH_TO_PACK']
            if assessment['candidate_budget_status'] is not None:
                argv.append('--require-budget')
            inventory = {name: digest(raw) for name, raw in sorted(captured.items())}
            return {'inspection_version': 'aau-recorded-pack-inspection/1.0', 'verification_status': 'verified',
                    'profile': profile, 'pack_version': version, 'assessment': assessment, 'exit_code': exit_code,
                    'requirements': {'expected_profile': expect, 'require_budget': require_budget},
                    'file_count': len(captured), 'total_bytes': sum(len(raw) for raw in captured.values()),
                    'captured_files_sha256': inventory, 'captured_inventory_sha256': digest(inventory),
                    'verified_report_sha256': digest(native), 'inspector_sha256': digest(Path(__file__).read_bytes()),
                    'read_after_verification': document, 'specific_verification_argv': argv,
                    'boundary': BOUNDARY}
    except InspectionError:
        raise
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        raise InspectionError('invalid_or_unreadable_pack') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau inspect-pack', description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--expect', choices=sorted(PROFILES), help='independently require a specific supported profile')
    parser.add_argument('--require-budget', action='store_true', help='reject any pack lacking a candidate operating-budget gate')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--out', type=Path, help='save the compact inspection outside the input pack; never overwrite')
    output.add_argument('--verify', type=Path, help='recompute a saved inspection with these same requirements')
    args = parser.parse_args(argv)
    try:
        if args.out and (args.out.resolve() == args.directory.resolve() or args.directory.resolve() in args.out.resolve().parents):
            raise InspectionError('output_must_be_outside_pack')
        report = inspect_pack(args.directory, expect=args.expect, require_budget=args.require_budget)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise InspectionError('inspection_report_does_not_recompute')
        elif args.out:
            write_json(report, args.out)
        else:
            print(rendered(report).decode(), end='')
        if args.out or args.verify:
            print(f"Verified {report['profile']}: {report['assessment']['kind']} / {report['assessment']['status']}. Not deployment approval.")
        return report['exit_code']
    except (ValueError, OSError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'inspection_input_or_output_rejected'
        print(f'error: {reason}; no verified inspection produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
