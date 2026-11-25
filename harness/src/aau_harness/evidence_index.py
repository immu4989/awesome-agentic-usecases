"""Receiver-pinned index of distinct review packets, with explicit cross-packet byte bindings."""

import argparse
from html import escape
from pathlib import Path
import re
import sys
import tempfile

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .eval_candidate_bounds import _document
from .inspect_pack import _capture
from .intake_review import _read_request, _sha, review_intake, validate_request as validate_intake
from .report_html import STYLE, table


# Closed role names select known members. No requested path, module, command, or URL is executed.
ROLES = {'policy-review': {'baseline': 'baseline.json', 'candidate': 'candidate.json'},
         'paired-review': {'baseline': 'baseline.json', 'candidate': 'candidate.json'},
         'coverage-review': {'evaluation': 'evaluation.json'},
         'inspect-conversion': {'source': 'source.json', 'plan': 'plan.json', 'evaluation': 'evaluation.json'},
         'promptfoo-conversion': {'source': 'source.json', 'plan': 'plan.json', 'evaluation': 'evaluation.json'},
         'inspect-diagnostic': {'source': 'source.json', 'plan': 'plan.json'},
         'promptfoo-diagnostic': {'source': 'source.json', 'plan': 'plan.json'}}
BOUNDARY = (
    'Receiver-defined evidence index, not an overall quality score, approved system, procurement decision, '
    'risk acceptance, compliance determination, government adoption, or deployment authorization. Verified '
    'means the declared packet recomputes with its required controls; it can still document a failed '
    'policy, coverage gap, or new regression. Those native outcomes remain separate and require human '
    'review. A verified source diagnostic can retain a log rejected by conversion; it cannot replace '
    'a separately requested conversion. Source, mapping-plan, and evaluation byte bindings are distinct; '
    'sharing a source does not imply sharing a mapping, and sharing evaluated scores does not identify '
    'the original log. A complete conversion is not score acceptance. No source code is re-executed for '
    'review. Missing and invalid required packets remain visible; no favorable fallback is substituted. '
    'Only explicit bindings compare exact member bytes, not semantic JSON equality, equivalent tasks, '
    'genuine execution, chronology, or identity. Unbound inputs have no asserted cross-packet association. '
    'Matching bytes do not validate scoring, reference labels, sampling, policy thresholds, or scientific '
    'assumptions. Different whitespace/serialization can fail a byte binding. The independently controlled '
    'request pin binds the complete receiver request, including nested control pins and bindings; it does '
    'not establish authorization, preregistration, signatures, or authenticity. Never derive the expected '
    'request pin from supplier-controlled delivery in the same production job. Capture is bounded and '
    'read-only but not an atomic snapshot of a concurrently changing source. Only trusted installed '
    'allowlisted verifiers run; supplied HTML, scripts, instructions, and modules are never executed. '
    'The output retains all supplied member bytes, including invalid packet contents; keep it private '
    'unless disclosure is separately authorized. Do not open retained HTML before review. No sanitization, '
    'upload, model, network, or external coordination occurs. Keep the full index and matching trusted '
    'harness. This bounded contract covers at most six flat packets, sixty delivered files, and twenty '
    'bindings; it is not a general evidence archive or a complete agency assurance process.'
)


def _fail(reason):
    raise AgentBomError('evidence_index_' + reason)


def _text(value, maximum):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def validate_request(raw, pin):
    if not isinstance(raw, bytes) or not _sha(pin) or digest(raw) != pin:
        _fail('request_byte_pin_mismatch')
    request = _document(raw)
    if (not isinstance(request, dict) or set(request) != {'request_version', 'purpose', 'items', 'bindings'}
            or request['request_version'] != 'aau-evidence-index-request/1.0' or not _text(request['purpose'], 2000)):
        _fail('request_contract_invalid')
    if not isinstance(request['items'], list) or not 1 <= len(request['items']) <= 6:
        _fail('requires_one_to_six_items')
    items = {}
    for item in request['items']:
        if not isinstance(item, dict) or set(item) != {'item_id', 'profile', 'purpose', 'controls'}:
            _fail('item_contract_invalid')
        identity, profile = item['item_id'], item['profile']
        if (not isinstance(identity, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,59}', identity) is None
                or identity in items or not isinstance(profile, str) or profile not in ROLES
                or not _text(item['purpose'], 1000) or not isinstance(item['controls'], dict)):
            _fail('item_identity_profile_or_purpose_invalid')
        controls = item['controls']
        if profile == 'policy-review':
            if set(controls) != {'intake_request'}:
                _fail('policy_controls_invalid')
            nested = rendered(controls['intake_request'])
            validated, _ = validate_intake(nested, digest(nested))
            if validated['profile'] != 'evaluation-review':
                _fail('policy_requires_flat_evaluation_review')
        elif set(controls) != {'plan_sha256'} or not _sha(controls['plan_sha256']):
            _fail('diagnostic_controls_require_exact_plan_pin')
        items[identity] = item
    if not isinstance(request['bindings'], list) or len(request['bindings']) > 20:
        _fail('binding_list_invalid')
    seen = set()
    for binding in request['bindings']:
        if not isinstance(binding, dict) or set(binding) != {'left', 'right'}:
            _fail('binding_contract_invalid')
        endpoints = []
        for side in ('left', 'right'):
            point = binding[side]
            if (not isinstance(point, dict) or set(point) != {'item_id', 'role'}
                    or not isinstance(point['item_id'], str) or point['item_id'] not in items
                    or not isinstance(point['role'], str)
                    or point['role'] not in ROLES[items[point['item_id']]['profile']]):
                _fail('binding_endpoint_invalid')
            endpoints.append((point['item_id'], point['role']))
        key = tuple(sorted(endpoints))
        if endpoints[0][0] == endpoints[1][0] or key in seen:
            _fail('binding_self_reference_or_duplicate')
        seen.add(key)
    return request


def _delivery(files, directories, request):
    allowed = {item['item_id'] for item in request['items']}
    if (len(files) > 60 or len(directories) != len(set(directories))
            or not set(directories) <= allowed):
        _fail('delivery_inventory_invalid')
    for name in files:
        parts = name.split('/')
        if len(parts) != 2 or parts[0] not in directories:
            _fail('delivery_requires_only_declared_flat_packets')
    return {identity: {name.split('/')[1]: raw for name, raw in files.items() if name.startswith(identity + '/')}
            for identity in directories}


def _verify_item(item, path):
    profile, controls = item['profile'], item['controls']
    if profile == 'policy-review':
        raw = rendered(controls['intake_request'])
        native = review_intake(raw, path, request_sha256=digest(raw))
        # Preserve an honestly failed policy, but never accept changed controls/context as a matched delivery.
        matched = not native['unmatched_input_roles'] and not (set(native['failed_constraints']) - {'policy_and_any_candidate_budget'})
        return native, matched, 'supplied_policy', native['pack_inspection']['assessment']['status']
    if profile == 'paired-review':
        from .eval_paired import verify_paired_pack
        native = verify_paired_pack(path, plan_sha256=controls['plan_sha256'])
        return native, True, 'paired_diagnostic_not_a_gate', native['status']
    if profile == 'inspect-conversion':
        from .eval_inspect import verify_inspect_pack
        native = verify_inspect_pack(path, plan_sha256=controls['plan_sha256'])
        return native, True, 'conversion_not_quality', 'complete_projection'
    if profile == 'promptfoo-conversion':
        from .eval_promptfoo import verify_promptfoo_pack
        native = verify_promptfoo_pack(path, plan_sha256=controls['plan_sha256'])
        return native, True, 'conversion_not_quality', 'complete_projection'
    if profile == 'inspect-diagnostic':
        from .inspect_diagnostic import verify_diagnostic
        native = verify_diagnostic(path, plan_sha256=controls['plan_sha256'])
        return native, True, 'source_diagnostic_not_conversion', native['status']
    if profile == 'promptfoo-diagnostic':
        from .promptfoo_diagnostic import verify_diagnostic
        native = verify_diagnostic(path, plan_sha256=controls['plan_sha256'])
        return native, True, 'source_diagnostic_not_conversion', native['status']
    from .coverage_review import verify_coverage_pack
    native = verify_coverage_pack(path, plan_sha256=controls['plan_sha256'])
    return native, True, 'coverage_diagnostic_not_quality', native['status']


def render_review(report):
    rows = [(r['item_id'], r['profile'], r['purpose'], r['verification_status'].replace('_', ' '),
             r['native_outcome_kind'].replace('_', ' ') if r['native_outcome_kind'] else None,
             r['native_outcome_status'].replace('_', ' ') if r['native_outcome_status'] else None) for r in report['items']]
    bindings = [(f'{r["left"]["item_id"]}: {r["left"]["role"]}', f'{r["right"]["item_id"]}: {r["right"]["role"]}',
                 r['status'].replace('_', ' ')) for r in report['bindings']]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Receiver evidence index</title>'
            f'<style>{STYLE}</style></head><body><main><h1>One handoff, separate findings</h1>'
            '<p class="notice">Delivery verification is not approval. A verified packet may document failure. '
            'Native outcomes are not averaged, voted, or converted into an overall pass.</p>'
            f'<p>{escape(report["purpose"])}</p><p>Delivery: {escape(report["delivery_status"].replace("_", " "))}. '
            f'Required items: {len(report["items"])}; verified: {report["verified_count"]}; missing: {report["missing_count"]}. '
            'Human review is always required.</p>'
            '<p>Tab to each table; arrow keys scroll and Tab leaves it. Retained raw HTML is not opened here.</p>'
            + table('Every receiver-required item and its own outcome',
                    ('Item', 'Profile', 'Purpose', 'Verification', 'Outcome kind', 'Native outcome'), rows,
                    missing_text='Not verified')
            + table('Explicit exact-byte relationships only', ('Left evidence member', 'Right evidence member', 'Binding status'), bindings)
            + '<p>With no binding, no association is asserted. Byte equality is not proof of genuine execution '
              'or appropriate scientific assumptions. See report.json for native findings and retained inventories.</p>'
            '<h2>Interpretation and disclosure limits</h2><p>' + escape(BOUNDARY) + '</p></main></body></html>')


def index_payloads(request_raw, delivered_files, delivered_directories, *, request_sha256):
    request = validate_request(request_raw, request_sha256)
    # Public APIs accept the same bounded, regular-byte inventory as filesystem capture.
    if (not isinstance(delivered_files, dict) or not isinstance(delivered_directories, list)
            or any(not isinstance(n, str) or not isinstance(raw, bytes) or len(raw) > MAX_JSON_BYTES
                   for n, raw in delivered_files.items())
            or any(not isinstance(n, str) for n in delivered_directories)):
        _fail('delivery_bytes_invalid')
    supplied = _delivery(delivered_files, delivered_directories, request)
    if any(re.fullmatch(r'[A-Za-z0-9_.-]+', name) is None or name in ('.', '..')
           for files in supplied.values() for name in files):
        _fail('delivery_member_name_invalid')
    rows = []
    with tempfile.TemporaryDirectory(prefix='aau-evidence-index-') as temporary:
        for item in request['items']:
            identity = item['item_id']
            row = {**{k: item[k] for k in ('item_id', 'profile', 'purpose')}, 'verification_status': 'missing',
                   'native_outcome_kind': None, 'native_outcome_status': None, 'native_report': None,
                   'captured_files_sha256': None}
            if identity in supplied:
                files = supplied[identity]
                row['captured_files_sha256'] = {n: digest(raw) for n, raw in sorted(files.items())}
                folder = Path(temporary) / identity
                folder.mkdir()
                for name, raw in files.items():
                    with (folder / name).open('xb') as stream:
                        stream.write(raw)
                try:
                    native, matched, kind, status = _verify_item(item, folder)
                    row.update(verification_status='verified' if matched else 'receiver_controls_not_matched',
                               native_outcome_kind=kind, native_outcome_status=status, native_report=native)
                except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError):
                    # Closed classification: retain original inputs, never reflect exception text from supplied data.
                    row['verification_status'] = 'verification_failed'
            rows.append(row)
    by_id = {r['item_id']: r for r in rows}
    bindings = []
    for binding in request['bindings']:
        hashes = []
        for side in ('left', 'right'):
            point = binding[side]
            row = by_id[point['item_id']]
            member = ROLES[row['profile']][point['role']]
            hashes.append(row['captured_files_sha256'].get(member) if row['verification_status'] == 'verified' else None)
        bindings.append({**binding, 'left_file_sha256': hashes[0], 'right_file_sha256': hashes[1],
                         'status': 'not_checked_unverified_item' if None in hashes else
                         'matched' if hashes[0] == hashes[1] else 'mismatched'})
    verified = sum(r['verification_status'] == 'verified' for r in rows)
    complete = verified == len(rows) and all(r['status'] == 'matched' for r in bindings)
    report = {'report_version': 'aau-evidence-index/1.0', 'request_file_sha256': request_sha256,
              'purpose': request['purpose'], 'delivery_status': 'declared_evidence_verified_and_bound' if complete else
              'declared_evidence_incomplete_or_unverified', 'exit_code': 0 if complete else 1,
              'decision_status': 'not_assessed', 'human_review_required': True,
              'verified_count': verified, 'missing_count': sum(r['verification_status'] == 'missing' for r in rows),
              'items': rows, 'bindings': bindings,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'evidence_index.py', 'inspect_pack.py', 'intake_review.py', 'eval_candidate_bounds.py',
                  'agent_bom.py', 'report_html.py', 'authority_html.py')}, 'boundary': BOUNDARY}
    files = {'request.json': request_raw, 'report.json': rendered(report), 'review.html': render_review(report).encode(),
             **{f'evidence/{name}': raw for name, raw in delivered_files.items()}}
    directories = ['evidence', *[f'evidence/{name}' for name in sorted(delivered_directories)]]
    files['manifest.json'] = rendered({'pack_version': 'aau-evidence-index-pack/1.0', 'directories': directories,
                                      'files_sha256': {n: digest(raw) for n, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        _fail('output_member_exceeds_limit')
    return report, files, directories


def create_index(request_raw, delivery, directory, *, request_sha256):
    if directory.exists() or directory.is_symlink():
        _fail('output_already_exists')
    validate_request(request_raw, request_sha256)
    if directory.resolve() == delivery.resolve() or delivery.resolve() in directory.resolve().parents:
        _fail('output_must_be_outside_delivery')
    captured, dirs = _capture(delivery)
    report, files, directories = index_payloads(request_raw, captured, dirs, request_sha256=request_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name in directories:
        (directory / name).mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_index(directory, *, request_sha256):
    files, directories = _capture(directory)
    if 'request.json' not in files:
        _fail('request_missing')
    delivered = {name.removeprefix('evidence/'): raw for name, raw in files.items() if name.startswith('evidence/')}
    dirs = [name.removeprefix('evidence/') for name in directories if name.startswith('evidence/')]
    report, expected, expected_dirs = index_payloads(files['request.json'], delivered, dirs, request_sha256=request_sha256)
    if files != expected or set(directories) != set(expected_dirs):
        _fail('index_does_not_recompute')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau evidence-index', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('request', type=Path)
    create.add_argument('delivery', type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    for command in (create, verify):
        command.add_argument('--request-sha256', required=True)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .evidence_index_demo import create_demo
            create_demo(args.out)
            print('Created synthetic evidence-index examples; a complete delivery can still contain a failed policy.')
            return 0
        if args.command == 'create':
            report = create_index(_read_request(args.request), args.delivery, args.out, request_sha256=args.request_sha256)
            verify_index(args.out, request_sha256=args.request_sha256)
        else:
            report = verify_index(args.directory, request_sha256=args.request_sha256)
        print(report['delivery_status'] + '; human review required, not approval.')
        return report['exit_code']
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError):
        print('error: evidence_index_input_or_replay_rejected; no verified index produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
