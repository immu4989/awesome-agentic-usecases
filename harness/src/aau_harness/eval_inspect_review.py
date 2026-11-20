"""Receiver-pinned Inspect source-to-policy handoff, without executing supplied code."""

import argparse
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .eval_inspect import _json, _read, inspect_payloads
from .eval_pack import pack_payloads
from .inspect_pack import _capture
from .intake_review import _sha


FIELDS = {'request_version', 'baseline_source_sha256', 'baseline_plan', 'candidate_plan',
          'policy', 'diagnostics', 'operating_budget'}
BOUNDARY = (
    'Full recomputation of supplied Inspect scores through a receiver-pinned request, not original '
    'execution, authentic scoring, independent evaluation, government adoption, certification, an ATO, '
    'or deployment approval. The request pin binds the exact request bytes, including the baseline '
    'source hash, both mappings, policy, diagnostics, and optional budget. Keep that expected pin '
    'independently of the delivered evidence; a supplier-controlled pin is not receiver control. '
    'Embedded mappings and review inputs are exported with the harness canonical renderer, not as '
    'pre-existing original files. Both original source logs and request bytes are retained unchanged. '
    'The candidate source is intentionally not pinned by the request; its supplied scores are checked '
    'against the requested policy. Pins do not prove identity, authority, preregistration, independence, '
    'comparable tasks, protected holdouts, or valid rubric mappings. Inspect aggregate metrics are not '
    'copied; the existing AAU methods recompute summaries. No context, operating cost, latency, API-call '
    'count, or measurement validity is inferred. Context remains unavailable even when policy constraints '
    'are met; operating-budget requirements cannot pass without measurements. Review scoring and '
    'comparability separately. No model, adapter, subprocess, task file, attachment, or network request '
    'is executed. Raw logs can contain sensitive data and are not sanitized or authorized for sharing. '
    'Keep the complete handoff: nested conversion or review verification alone does not prove the '
    'cross-folder relationship or independently pinned request. Use a matching trusted harness.'
)


def handoff_payloads(request_raw, baseline_raw, candidate_raw, *, request_sha256):
    if not isinstance(request_raw, bytes) or not _sha(request_sha256) or digest(request_raw) != request_sha256:
        raise AgentBomError('Inspect review request byte pin mismatch')
    request = _json(request_raw)
    if set(request) != FIELDS or request['request_version'] != 'aau-inspect-review-request/1.0':
        raise AgentBomError('Inspect review request requires exactly the documented fields and version')
    if not _sha(request['baseline_source_sha256']) or digest(baseline_raw) != request['baseline_source_sha256']:
        raise AgentBomError('Inspect baseline bytes do not match the receiving request')
    if not isinstance(request['policy'], dict) or not isinstance(request['diagnostics'], dict):
        raise AgentBomError('Inspect review requires an explicit policy and diagnostics plan')
    if request['operating_budget'] is not None and not isinstance(request['operating_budget'], dict):
        raise AgentBomError('Inspect operating budget must be a plan object or explicit null')
    files, recordings, sources = {}, [], {}
    for side, source_raw in (('baseline', baseline_raw), ('candidate', candidate_raw)):
        plan_raw = rendered(request[side + '_plan'])
        conversion, converted = inspect_payloads(plan_raw, source_raw, plan_sha256=digest(plan_raw))
        files.update({f'{side}/{name}': raw for name, raw in converted.items()})
        recordings.append(json.loads(converted['recording.json']))
        sources[side] = {key: conversion[key] for key in ('source_json_sha256', 'plan_sha256', 'recording_sha256',
                         'evaluation_sha256', 'declared_inspect_version', 'observation_count', 'metric_coverage')}
    outcome, review_files = pack_payloads(request['policy'], *recordings, recordings=True,
        diagnostics=request['diagnostics'], operating_budget=request['operating_budget'])
    files.update({f'review/{name}': raw for name, raw in review_files.items()})
    review = json.loads(review_files['review.json'])
    report = {'report_version': 'aau-inspect-review-handoff/1.0', 'status': outcome['status'],
              'request_sha256': request_sha256, 'baseline_source_pin_matched': True,
              'policy_status': review['status'], 'budget_required': request['operating_budget'] is not None,
              'candidate_budget_status': outcome.get('candidate_budget_status'),
              'declared_context': review['comparisons'][0]['context_match'], 'sources': sources,
              'review_json_sha256': digest(review_files['review.json']),
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in (
                  'eval_inspect_review.py', 'eval_inspect.py', 'eval_import.py', 'eval_pack.py', 'eval_policy.py',
                  'eval_compare.py', 'eval_diagnostics.py', 'eval_budget_gate.py')}, 'boundary': BOUNDARY}
    files['request.json'] = request_raw
    files['handoff.json'] = rendered(report)
    count = len(files) + 2
    guide = f'''AAU Inspect source-to-policy handoff

Open review/review.html for policy, repeatability, and operating diagnostics.
Read handoff.json for the request binding and limitations. HTML does not verify itself.
Keep all {count} files, including the original baseline/source.json and candidate/source.json.

Use the receiver's independently retained request hash with a matching trusted harness:

  aau inspect-review verify PATH_TO_THIS_FOLDER --request-sha256 RECEIVER_REQUEST_SHA256

Exit 0: source chain and request pin verify; supplied policy and any budget constraints are met.
Exit 1: source chain and request pin verify; constraints are not met or not verified.
Exit 2: invalid inputs, wrong request/baseline pin, incomplete pack, or failed replay.
Do not delete failure evidence or fall back to a favorable nested review.

The request fixes the baseline bytes, both score mappings, policy, diagnostics, and optional budget.
Verification reparses both logs and recomputes every recording, evaluation, review, diagnostic,
HTML file, report, and manifest. It rejects individually valid but unrelated nested components.
Nested plans are rendered from the pinned request; no independently supplied mapping file is assumed.

Context is unavailable, not matched. Costs, latency, and API-call counts remain unknown.
A met quality policy is not proof of comparable tasks, correct scoring, or operational suitability.
If an operating budget is requested, missing measurements prevent a passing combined outcome.
Interrupted, edited, or incomplete logs remain rejected by the strict converter. Preserve them
separately with inspect-eval diagnose; never repair a log into a success just to make this work.

{BOUNDARY}
'''
    files['README.txt'] = guide.encode()
    files['manifest.json'] = rendered({'pack_version': 'aau-inspect-review-handoff-pack/1.0',
                                      'files': {name: digest(raw) for name, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        raise AgentBomError('Inspect handoff member exceeds 2 MB')
    return report, files


def create_handoff(request_raw, baseline_raw, candidate_raw, directory, *, request_sha256):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite an Inspect handoff destination')
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
        raise AgentBomError('Inspect handoff requires its exact directory set')
    if not {'request.json', 'baseline/source.json', 'candidate/source.json'} <= set(files):
        raise AgentBomError('Inspect handoff is missing source inputs')
    report, expected = handoff_payloads(files['request.json'], files['baseline/source.json'], files['candidate/source.json'],
                                      request_sha256=request_sha256)
    if files != expected:
        raise AgentBomError('Inspect handoff does not recompute byte-for-byte')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau inspect-review', description=__doc__)
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
            from .inspect_review_demo import create_demo
            create_demo(args.out)
            print('Created synthetic Inspect source-to-policy examples; no model or Inspect execution.')
            return 0
        if args.command == 'create':
            create_handoff(_read(args.request), _read(args.baseline_source), _read(args.candidate_source), args.out,
                           request_sha256=args.request_sha256)
            report = verify_handoff(args.out, request_sha256=args.request_sha256)
        else:
            report = verify_handoff(args.directory, request_sha256=args.request_sha256)
        print(f"{report['status']}: pinned source-to-policy handoff, not deployment approval.")
        return int(report['status'] != 'constraints_met')
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
