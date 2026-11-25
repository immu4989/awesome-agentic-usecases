"""Replay original Promptfoo exports through a receiver-pinned policy review, without execution."""

import argparse
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .eval_promptfoo import _json, _read, promptfoo_payloads
from .eval_pack import pack_payloads
from .inspect_pack import _capture
from .intake_review import _sha


FIELDS = {'request_version', 'baseline_source_sha256', 'baseline_plan', 'candidate_plan',
          'policy', 'diagnostics', 'operating_budget'}
BOUNDARY = (
    'Receiver-pinned source-to-policy replay, not original execution, authentic scoring, comparable '
    'tasks, independent evaluation, government adoption, certification, an ATO, or deployment approval. '
    'The independently retained request hash binds exact request bytes: baseline-source hash, both '
    'test/column/score mappings, policy, diagnostics, and optional budget. A supplier-controlled pin '
    'does not establish receiver control. Embedded plans are canonically rendered, not represented '
    'as separately supplied original files. Original request and both complete source exports remain '
    'unchanged. The candidate source is not predetermined by the request; its scores are assessed '
    'against the pinned requirements. The selected columns cannot be replaced with more favorable '
    'columns without changing the request. All columns undergo strict import validation. Failed '
    'assertions remain evidence; execution errors, unsupported repetition, and incomplete census '
    'remain rejected. Aggregate export scores are not used. No cost, latency, API-call count, or '
    'execution-context fingerprint is inferred; required operating measurements remain unknown. '
    'No supplied provider, assertion, code, URL, or attachment is executed or fetched. Raw evidence '
    'may contain sensitive data and is not sanitized or authorized for disclosure. Keep the entire '
    'handoff: separately valid nested packs do not establish their cross-folder relationship. '
    'Use a matching trusted implementation; hashes bind bytes, not authority or correctness.'
)


def handoff_payloads(request_raw, baseline_raw, candidate_raw, *, request_sha256):
    if not isinstance(request_raw, bytes) or not _sha(request_sha256) or digest(request_raw) != request_sha256:
        raise AgentBomError('Promptfoo review request byte pin mismatch')
    request = _json(request_raw)
    if set(request) != FIELDS or request['request_version'] != 'aau-promptfoo-review-request/1.0':
        raise AgentBomError('Promptfoo review requires exactly the documented request fields and version')
    if not _sha(request['baseline_source_sha256']) or digest(baseline_raw) != request['baseline_source_sha256']:
        raise AgentBomError('Promptfoo baseline bytes differ from the receiving request')
    if not isinstance(request['policy'], dict) or not isinstance(request['diagnostics'], dict):
        raise AgentBomError('Promptfoo review requires explicit policy and diagnostics objects')
    if request['operating_budget'] is not None and not isinstance(request['operating_budget'], dict):
        raise AgentBomError('Promptfoo operating budget must be an object or explicit null')
    files, recordings, sources = {}, [], {}
    for side, source_raw in (('baseline', baseline_raw), ('candidate', candidate_raw)):
        plan_raw = rendered(request[side + '_plan'])
        conversion, converted = promptfoo_payloads(plan_raw, source_raw, plan_sha256=digest(plan_raw))
        files.update({f'{side}/{name}': raw for name, raw in converted.items()})
        recordings.append(json.loads(converted['recording.json']))
        sources[side] = {key: conversion[key] for key in (
            'source_json_sha256', 'plan_sha256', 'recording_sha256', 'evaluation_sha256',
            'declared_promptfoo_version', 'selected_column', 'validated_row_count', 'projected_row_count', 'metric_coverage')}
    outcome, review_files = pack_payloads(request['policy'], *recordings, recordings=True,
                                         diagnostics=request['diagnostics'], operating_budget=request['operating_budget'])
    files.update({f'review/{name}': raw for name, raw in review_files.items()})
    review = json.loads(review_files['review.json'])
    report = {'report_version': 'aau-promptfoo-review-handoff/1.0', 'status': outcome['status'],
              'request_sha256': request_sha256, 'baseline_source_pin_matched': True,
              'policy_status': review['status'], 'budget_required': request['operating_budget'] is not None,
              'candidate_budget_status': outcome.get('candidate_budget_status'),
              'declared_context': review['comparisons'][0]['context_match'], 'sources': sources,
              'review_json_sha256': digest(review_files['review.json']),
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'promptfoo_review.py', 'eval_promptfoo.py', 'eval_import.py', 'eval_pack.py', 'eval_policy.py',
                  'eval_compare.py', 'eval_diagnostics.py', 'eval_budget_gate.py')}, 'boundary': BOUNDARY}
    files['request.json'], files['handoff.json'] = request_raw, rendered(report)
    files['README.txt'] = f'''AAU Promptfoo source-to-policy handoff

Open review/review.html. HTML does not verify itself. Read handoff.json for source bindings.
Keep the whole folder, including both original source.json exports, not just review/.
Use the receiver's independently retained expected request hash:

  aau promptfoo-review verify PATH_TO_THIS_FOLDER --request-sha256 RECEIVER_REQUEST_SHA256

Exit 0: source chain verifies and supplied policy/budget constraints are met; not approval.
Exit 1: source chain verifies but constraints are not met or not verified.
Exit 2: invalid inputs, wrong expected pins, missing files, or failed recomputation.

The request pins baseline bytes, both selected columns and mappings, policy, diagnostics,
and optional budget. Candidate bytes are assessed, not predetermined. Plans are canonically
rendered from this request. Every nested file and source-to-review relationship is recomputed.
Individually valid but unrelated nested components cannot replace the complete chain.

Context and operating costs remain unavailable. Do not drop a required budget to get a pass.
Execution errors, repetitions, and incomplete logs remain rejected by the strict converter.
Retain those separately with promptfoo-eval diagnose; do not repair them to enter this handoff.

{BOUNDARY}
'''.encode()
    files['manifest.json'] = rendered({'pack_version': 'aau-promptfoo-review-handoff-pack/1.0',
                                      'files': {name: digest(raw) for name, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        raise AgentBomError('Promptfoo handoff member exceeds 2 MB')
    return report, files


def create_handoff(request_raw, baseline_raw, candidate_raw, directory, *, request_sha256):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite a Promptfoo handoff destination')
    report, files = handoff_payloads(request_raw, baseline_raw, candidate_raw, request_sha256=request_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name in ('baseline', 'candidate', 'review'):
        (directory / name).mkdir()
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_handoff(directory, *, request_sha256):
    files, directories = _capture(directory)
    if set(directories) != {'baseline', 'candidate', 'review'}:
        raise AgentBomError('Promptfoo handoff requires exactly its three documented directories')
    if not {'request.json', 'baseline/source.json', 'candidate/source.json'} <= set(files):
        raise AgentBomError('Promptfoo handoff is missing source inputs')
    report, expected = handoff_payloads(files['request.json'], files['baseline/source.json'], files['candidate/source.json'],
                                      request_sha256=request_sha256)
    if files != expected:
        raise AgentBomError('Promptfoo handoff does not recompute byte-for-byte')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau promptfoo-review', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('request', 'baseline_source', 'candidate_source'):
        create.add_argument(name, type=Path)
    create.add_argument('--request-sha256', required=True)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--request-sha256', required=True)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .promptfoo_review_demo import create_demo
            create_demo(args.out)
            print('Created synthetic Promptfoo handoffs; no exporter or model executed.')
            return 0
        if args.command == 'create':
            create_handoff(_read(args.request), _read(args.baseline_source), _read(args.candidate_source), args.out,
                           request_sha256=args.request_sha256)
            report = verify_handoff(args.out, request_sha256=args.request_sha256)
        else:
            report = verify_handoff(args.directory, request_sha256=args.request_sha256)
        print(f"{report['status']}: receiver-pinned Promptfoo source-to-policy replay, not deployment approval.")
        return int(report['status'] != 'constraints_met')
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
