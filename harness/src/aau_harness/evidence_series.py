"""Review an explicitly ordered evidence history without erasing failed or missing checkpoints."""

import argparse
import os
from pathlib import Path
import re
import stat
import sys

from .agent_bom import MAX_JSON_BYTES, _parse_json, digest, load_json, rendered, write_json
from .inspect_pack import InspectionError
from .intake_review import _read_request, _sha, review_intake, validate_request


MAX_CHECKPOINTS = 10
STATES = ('request_constraints_met', 'request_constraints_not_met', 'missing', 'invalid')
RESERVED_NAMES = {'con', 'prn', 'aux', 'nul', *(f'{prefix}{i}' for prefix in ('com', 'lpt') for i in range(1, 10))}
BOUNDARY = (
    'Offline review of a declared ordered checkpoint census against one fixed receiving-team request. '
    'This is not a production monitor, scheduler, deployment decision, incident closure, recovery proof, '
    'statistical trend, availability estimate, source authentication, signature, or compliance result. '
    'Order comes only from the separately pinned plan, not filenames, timestamps, repeat indices, or '
    'filesystem modification times. The plan contains no authenticated time or cadence, so no elapsed '
    'duration, freshness, uptime, or time-to-repair is calculated. Missing and invalid checkpoints are '
    'retained; later passing evidence never erases earlier failed or unavailable evidence. Changes in '
    'requirement outcomes are not necessarily changes in agent performance. One common request pins '
    'the baseline, controls, exact profile/version/format, and any required budget throughout; no rolling '
    'rebaseline or silent requirement replacement is allowed. Independently review and protect BOTH '
    'expected plan and request byte hashes; computing them from candidate-controlled files in the same '
    'production job defeats this boundary. Matching pins do not establish reviewer identity or authority, '
    'preregistration, complete external history, or independence of observations. Identical pack inventories '
    'identify the same retained bytes, not fresh executions; different bytes do not prove independent runs '
    'either. No statistical pooling, success weighting, model calls, adapters, subprocesses, uploads, or '
    'network requests occur. Each checkpoint is individually captured and verified, not an atomic snapshot '
    'of the whole live history. Root membership is checked before and after review. Keep the plan, request, '
    'all complete checkpoint packs, and report, and reverify with a matching trusted harness. Reports '
    'include supplied checkpoint IDs and hashes that may disclose information; no sanitization or permission '
    'to share is implied. Source authenticity, scoring validity, actual conditions, affected users, and '
    'unreported incidents need separate investigation.'
)


def validate_plan(raw, expected_sha256):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise InspectionError('series_plan_bytes_invalid_or_oversized')
    if not _sha(expected_sha256) or digest(raw) != expected_sha256:
        raise InspectionError('series_plan_byte_pin_mismatch')
    plan = _parse_json(raw)
    if (not isinstance(plan, dict) or set(plan) != {'plan_version', 'checkpoint_ids'}
            or plan['plan_version'] != 'aau-evidence-series-plan/1.0'):
        raise InspectionError('invalid_series_plan')
    ids = plan['checkpoint_ids']
    if (not isinstance(ids, list) or not 2 <= len(ids) <= MAX_CHECKPOINTS
            or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', name)
                   or name in RESERVED_NAMES for name in ids)
            or len(set(ids)) != len(ids)):
        raise InspectionError('invalid_series_checkpoint_ids')
    return plan


def _entries(root, expected):
    if root.is_symlink() or not root.is_dir():
        raise InspectionError('series_directory_required')
    entries = {}
    with os.scandir(root) as stream:
        for entry in stream:
            if entry.name not in expected or len(entries) >= MAX_CHECKPOINTS:
                raise InspectionError('unexpected_series_member')
            info = entry.stat(follow_symlinks=False)
            # Remember identity and kind for root-membership recheck, never expose inode/device in reports.
            entries[entry.name] = (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))
    return entries


def review_series(plan_raw, request_raw, directory: Path, *, plan_sha256, request_sha256):
    try:
        plan = validate_plan(plan_raw, plan_sha256)
        validate_request(request_raw, request_sha256)  # Both pinned controls must validate before reading evidence.
        entries = _entries(directory, set(plan['checkpoint_ids']))
        checkpoints, inventories = [], {}
        for position, name in enumerate(plan['checkpoint_ids'], 1):
            row = {'checkpoint_id': name, 'position': position, 'status': 'missing', 'intake': None, 'reason': None}
            if name not in entries:
                row['reason'] = 'expected_checkpoint_not_supplied'
            else:
                try:
                    if entries[name][2] != stat.S_IFDIR:
                        raise InspectionError('checkpoint_directory_required')
                    intake = review_intake(request_raw, directory / name, request_sha256=request_sha256)
                    row.update(status=intake['status'], intake=intake)
                    inventory_hash = intake['pack_inspection']['captured_inventory_sha256']
                    inventories.setdefault(inventory_hash, []).append(name)
                except InspectionError:
                    # Keep other checkpoints, but never promote invalid evidence or copy untrusted error text.
                    row.update(status='invalid', reason='checkpoint_verification_failed')
            checkpoints.append(row)
        if _entries(directory, set(plan['checkpoint_ids'])) != entries:
            raise InspectionError('series_membership_changed_during_review')
        counts = {state: sum(row['status'] == state for row in checkpoints) for state in STATES}
        if counts['invalid']:
            status, code = 'series_not_fully_verified', 2
        elif counts['missing']:
            status, code = 'series_evidence_missing', 1
        elif counts['request_constraints_not_met']:
            status, code = 'series_constraints_not_met', 1
        else:
            status, code = 'series_constraints_met', 0
        transitions = []
        for previous, current in zip(checkpoints, checkpoints[1:]):
            before, after = previous['status'], current['status']
            relation = ('not_comparable_missing_or_invalid' if before in ('missing', 'invalid') or after in ('missing', 'invalid')
                        else 'unchanged_requirement_outcome' if before == after
                        else 'requirements_started_failing' if after == 'request_constraints_not_met'
                        else 'requirements_met_after_failure')
            transitions.append({'from_checkpoint': previous['checkpoint_id'], 'to_checkpoint': current['checkpoint_id'],
                                'before': before, 'after': after, 'relationship': relation})
        report = {'report_version': 'aau-evidence-series-review/1.0', 'status': status, 'exit_code': code,
                  'plan_file_sha256': plan_sha256, 'request_file_sha256': request_sha256,
                  'control_byte_pins_matched': True, 'checkpoint_count': len(checkpoints), 'counts': counts,
                  'latest_checkpoint': {key: checkpoints[-1][key] for key in ('checkpoint_id', 'position', 'status')},
                  'historical_issue_checkpoint_ids': [row['checkpoint_id'] for row in checkpoints
                                                      if row['status'] != 'request_constraints_met'],
                  'distinct_verified_pack_inventory_count': len(inventories),
                  'repeated_pack_inventories': [{'inventory_sha256': key, 'checkpoint_ids': names}
                                               for key, names in sorted(inventories.items()) if len(names) > 1],
                  'checkpoints': checkpoints, 'transitions': transitions,
                  'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                                            for name in ('evidence_series.py', 'intake_review.py', 'inspect_pack.py',
                                                         'evaluation_context.py', 'agent_bom.py')},
                  'boundary': BOUNDARY}
        if len(rendered(report)) > MAX_JSON_BYTES:
            raise InspectionError('series_report_exceeds_limit')
        return report
    except InspectionError:
        raise
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        raise InspectionError('series_input_or_evidence_invalid') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau review-series', description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('request', type=Path)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--plan-sha256', required=True, help='independently controlled SHA-256 of exact ordered-plan bytes')
    parser.add_argument('--request-sha256', required=True, help='independently controlled SHA-256 of exact common request bytes')
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--out', type=Path)
    output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out and (args.out.resolve() == args.directory.resolve() or args.directory.resolve() in args.out.resolve().parents):
            raise InspectionError('series_output_must_be_outside_evidence')
        report = review_series(_read_request(args.plan), _read_request(args.request), args.directory,
                               plan_sha256=args.plan_sha256, request_sha256=args.request_sha256)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise InspectionError('series_report_does_not_recompute')
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {report['checkpoint_count']} expected checkpoints; "
              f"{len(report['historical_issue_checkpoint_ids'])} non-passing checkpoints. Not recovery or deployment approval.")
        return report['exit_code']
    except (ValueError, OSError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'series_input_or_output_rejected'
        print(f'error: {reason}; no new series report produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
