"""Run fixed offline smoke checks from an installed harness, without a checkout or user evidence."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .agent_bom import AgentBomError, digest, rendered
from .inspect_pack import _capture
from .runtime_info import runtime_info


CASES = {
    'policy-met': 'A complete synthetic policy pass verifies without changing its outcome.',
    'policy-unmet': 'A complete synthetic authorization failure verifies but remains a policy failure.',
    'required-budget-unknown': 'Met score requirements cannot pass an unmeasured required operating budget.',
    'inspect-missing-score': 'Inspect import preserves missing metrics and original source bytes.',
    'promptfoo-missing-score': 'Promptfoo import preserves missing metrics, selected-column failures, and source bytes.',
    'missing-conversion': 'A verified source diagnostic cannot fill a separately required conversion slot.',
    'wrong-pin-rejected': 'A wrong independently supplied mapping pin is rejected.',
    'changed-derived-file-rejected': 'A changed derived policy report fails complete replay.',
    'transfer-tamper-rejected': 'A synthetic BagIt transfer verifies and a changed payload is rejected.',
}
FILES = {'checks.json', 'runtime.json', 'README.txt', 'manifest.json'}
BOUNDARY = (
    'Fixed synthetic installed-package smoke checks only, not the complete test suite, actual model '
    'performance, independent reproduction, interpreter/dependency attestation, source authenticity, '
    'OS-enforced air-gap proof, government adoption, compliance, an ATO, or deployment approval. '
    'Expected negative outcomes are successful checks; a check failure is not a model-policy verdict. '
    'Only trusted installed first-party code and fixed fixtures execute. No user cases, received '
    'tasks, model SDKs, provider credentials, subprocesses, package installers, or network requests '
    'are used. Synthetic working files are created in temporary directories and removed afterward. '
    'Only this receipt is retained. It contains on-disk first-party source hashes, Python/distribution '
    'versions, fixed check descriptions, and closed result/error codes; no local installation paths, hostnames, environment '
    'variables, timings, timestamps, exception messages, or user evidence are collected. On-disk hashes '
    'do not prove which code was loaded or executed. Replay requires the same receipt-producing '
    'implementation and runtime metadata and reruns the fixed checks; it does not authenticate a '
    'previous run or inspect arbitrary evidence. A receipt can be fabricated; no signatures or '
    'independent execution attestation are provided. Review before sharing; nothing is uploaded.'
)


def _rejected(operation, phrase):
    try:
        operation()
    except AgentBomError as exc:
        return phrase in str(exc)
    return False


def _execute(case, root):
    """Closed dispatch of trusted fixed fixtures; never called with a received script or task."""
    if case in ('policy-met', 'policy-unmet', 'changed-derived-file-rejected'):
        from .eval_demo import demo_inputs
        from .eval_pack import create_pack, verify_pack
        policy, baseline, candidate, diagnostics = demo_inputs()
        if case == 'policy-unmet':
            candidate = baseline
        packet = root / 'policy'
        create_pack(policy, baseline, candidate, packet, recordings=True, diagnostics=diagnostics)
        result = verify_pack(packet, require_recordings=True, require_diagnostics=True)
        expected = 'constraints_not_met' if case == 'policy-unmet' else 'constraints_met'
        if result['status'] != expected:
            return False
        if case == 'changed-derived-file-rejected':
            with (packet / 'review.json').open('ab') as stream:
                stream.write(b' ')
            return _rejected(lambda: verify_pack(packet, require_recordings=True, require_diagnostics=True), 'does not recompute')
        return True
    if case == 'required-budget-unknown':
        from .promptfoo_review_demo import example_inputs
        from .promptfoo_review import create_handoff, verify_handoff
        values = tuple(map(rendered, example_inputs()['unknown-budget']))
        packet = root / 'handoff'
        report = create_handoff(*values, packet, request_sha256=digest(values[0]))
        return (verify_handoff(packet, request_sha256=digest(values[0])) == report
                and report['policy_status'] == 'constraints_met' and report['status'] == 'constraints_not_verified'
                and report['candidate_budget_status'] == 'constraints_not_verified'
                and report['declared_context']['status'] == 'unavailable')
    if case == 'inspect-missing-score':
        from .inspect_demo import example_inputs
        from .eval_inspect import create_inspect_pack, verify_inspect_pack
        plan, source = map(rendered, example_inputs())
        packet = root / 'conversion'
        created = create_inspect_pack(plan, source, packet, plan_sha256=digest(plan))
        rows = json.loads((packet / 'evaluation.json').read_bytes())['results']
        return (verify_inspect_pack(packet, plan_sha256=digest(plan)) == created
                and (packet / 'source.json').read_bytes() == source and len(rows) == 4
                and sum('completion' in row['metrics'] for row in rows) == 3
                and sum('authorization' in row['metrics'] for row in rows) == 3)
    if case in ('promptfoo-missing-score', 'wrong-pin-rejected'):
        from .promptfoo_demo import example_inputs
        from .eval_promptfoo import create_promptfoo_pack, verify_promptfoo_pack
        plan, source = map(rendered, example_inputs())
        packet = root / 'conversion'
        created = create_promptfoo_pack(plan, source, packet, plan_sha256=digest(plan))
        if verify_promptfoo_pack(packet, plan_sha256=digest(plan)) != created:
            return False
        if case == 'wrong-pin-rejected':
            return _rejected(lambda: verify_promptfoo_pack(packet, plan_sha256='0' * 64), 'independently supplied')
        rows = json.loads((packet / 'evaluation.json').read_bytes())['results']
        return ((packet / 'source.json').read_bytes() == source and len(rows) == 3
                and sum('authorization' in row['metrics'] for row in rows) == 2
                and sum(row['metrics']['passed'] for row in rows) == 2)
    if case == 'missing-conversion':
        from .source_index_demo import build_inputs
        from .evidence_index import create_index, verify_index
        request, delivery = build_inputs(root, 'promptfoo', 'rejected-conversion')
        raw = rendered(request)
        packet = root / 'index'
        report = create_index(raw, delivery, packet, request_sha256=digest(raw))
        return (verify_index(packet, request_sha256=digest(raw)) == report and report['exit_code'] == 1
                and report['items'][0]['verification_status'] == 'missing'
                and report['items'][1]['verification_status'] == 'verified'
                and report['items'][1]['native_report']['conversion_eligibility']['status'] == 'rejected_by_current_converter')
    if case == 'transfer-tamper-rejected':
        from .evidence_bag import create_bag, verify_bag
        source, packet = root / 'source', root / 'bag'
        source.mkdir()
        (source / 'example.txt').write_bytes(b'Fixed synthetic transfer; no user evidence.\n')
        create_bag(source, packet)
        pin = digest((packet / 'tagmanifest-sha256.txt').read_bytes())
        verify_bag(packet, tagmanifest_sha256=pin)
        (packet / 'data/example.txt').write_bytes(b'Changed synthetic payload.\n')
        return _rejected(lambda: verify_bag(packet, tagmanifest_sha256=pin), 'canonical_inventory_or_checksums_mismatch')
    raise ValueError('unknown fixed self-check case')


def _error_code(exc):
    if isinstance(exc, ImportError):
        return 'required_module_unavailable'
    if isinstance(exc, OSError):
        return 'filesystem_operation_failed'
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return 'fixture_or_behavior_contract_failed'
    return 'unexpected_exception'


def check_payloads():
    before = runtime_info()
    checks = []
    for case, description in CASES.items():
        try:
            with tempfile.TemporaryDirectory(prefix='aau-self-check-') as temporary:
                matched = _execute(case, Path(temporary)) is True
            code = None if matched else 'expected_behavior_not_observed'
        except Exception as exc:
            # Do not serialize exception messages: they can expose paths or environment details.
            matched, code = False, _error_code(exc)
        checks.append({'case_id': case, 'expected': description,
                       'status': 'matched_expected' if matched else 'failed', 'error_code': code})
    after = runtime_info()
    if before != after:
        raise AgentBomError('self-check runtime inventory changed during collection; no stable receipt produced')
    report = {'report_version': 'aau-self-check/1.0', 'suite_version': 'aau-offline-smoke/1.0',
              'status': 'expected_behavior_observed' if all(c['status'] == 'matched_expected' for c in checks) else 'self_check_failed',
              'runtime_receipt_sha256': digest(rendered(before)), 'checks': checks, 'boundary': BOUNDARY}
    guide = '''AAU installed-package self-check

Read checks.json for each fixed expectation and its result. A retained policy failure, missing
conversion, or rejected tamper is expected behavior, not a failing self-check.

Replay using the matching trusted installed package and Python metadata:
  aau self-check verify PATH_TO_THIS_RECEIPT

Verification reruns the fixed synthetic checks in temporary directories. It does not execute
anything from this receipt. Exit 0: all expectations matched. Exit 1: a complete receipt records
one or more failed checks. Exit 2: invalid input, overwrite refusal, runtime drift, or replay mismatch.
No existing output is overwritten. If interrupted, preserve any partial output and use a new path.

Failure codes deliberately omit exception messages, paths, and environment variables:
- required_module_unavailable: confirm the reviewed wheel and documented Python dependencies.
- filesystem_operation_failed: check permission and space for temporary/output directories.
- fixture_or_behavior_contract_failed or expected_behavior_not_observed: preserve this receipt;
  reproduce from a new approved environment using the same reviewed implementation.
- unexpected_exception: preserve the receipt for a separately authorized investigation.

Compare runtime.json source_tree_sha256 independently of the distribution version. Use the offline
kit's source audit and installed-runtime comparison for provenance checks; this smoke test does not
replace them. A different Python/source receipt requires a fresh run, not editing the old receipt.
Only share after review and permission. Nothing is collected remotely or published automatically.

''' + BOUNDARY + '\n'
    files = {'checks.json': rendered(report), 'runtime.json': rendered(before), 'README.txt': guide.encode()}
    files['manifest.json'] = rendered({'pack_version': 'aau-self-check-receipt/1.0',
                                      'files': {name: digest(raw) for name, raw in sorted(files.items())}})
    return report, files


def create_check(directory):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('self-check refuses to overwrite an existing destination')
    report, files = check_payloads()
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_check(directory):
    files, dirs = _capture(directory)
    if dirs or set(files) != FILES:
        raise AgentBomError('self-check receipt requires exactly four documented regular files')
    report, expected = check_payloads()
    if files != expected:
        raise AgentBomError('self-check receipt differs from current runtime or rerun results')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau self-check', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    try:
        report = create_check(args.out) if args.command == 'run' else verify_check(args.directory)
        passed = sum(c['status'] == 'matched_expected' for c in report['checks'])
        print(f'{report["status"]}: {passed}/{len(CASES)} fixed offline checks matched; not deployment approval.')
        return int(report['status'] != 'expected_behavior_observed')
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError):
        print('error: self_check_input_runtime_or_replay_rejected; no verified result claimed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
