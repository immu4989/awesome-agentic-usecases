"""Retain and replay a complete recorded grader audit without executing a grader."""

import argparse
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from .grader_review import review_grader, validate_plan
from .inspect_pack import _capture
from .intake_review import _read_request


FILES = {'plan.json', 'reference.json', 'judgments.json', 'report.json', 'README.txt', 'manifest.json'}
GUIDE = '''Recorded grader audit packet

Retain this complete six-file directory with the matching trusted harness. Independently review and
protect the expected SHA-256 of plan.json; do not derive a production pin from a supplier delivery.
The plan also pins the exact reference.json bytes. Original plan/reference/judgment bytes are retained.

Replay: aau grader-pack verify DIRECTORY --plan-sha256 INDEPENDENTLY_RETAINED_PLAN_SHA256

Exit 0 means the diagnostic recomputes, NOT that the grader passed. Exit 2 means invalid evidence,
wrong controls, existing output, or replay mismatch. False passes, false failures, missing judgments,
abstentions, disputed references, and unreviewed references remain in report.json. Calibration and
validation scopes remain separate; overlapping groups must not be pooled. No threshold is invented.

To connect label provenance, request reference-review and grader-review items in an evidence index.
Bind reference-review/reference to grader-review/reference, and reference-review/grader-plan to
grader-review/plan. Both bindings are explicit exact-byte comparisons, not semantic equivalence.
A missing reference-review item remains missing even when the grader packet has reference labels.

This packet executes no grader, model, received script, subprocess, or network request. The source
judgments are declarations, not genuine-execution evidence. A correct recomputation does not establish
reference truth, reviewer identity/expertise/independence, rubric validity, hidden validation data,
grader certification, compliance, government adoption, or deployment approval. Hashes do not prove
authenticity or prevent coordinated replacement. These files can contain sensitive IDs and labels;
keep them private unless disclosure is separately authorized. Nothing is uploaded or sanitized.
'''


def grader_payloads(plan_raw, reference_raw, judgments_raw, *, plan_sha256):
    report = review_grader(plan_raw, reference_raw, judgments_raw, plan_sha256=plan_sha256)
    files = {'plan.json': plan_raw, 'reference.json': reference_raw, 'judgments.json': judgments_raw,
             'report.json': rendered(report), 'README.txt': GUIDE.encode()}
    files['manifest.json'] = rendered({'pack_version': 'aau-grader-review-pack/1.0',
                                      'files': {name: digest(raw) for name, raw in sorted(files.items())}})
    if any(len(raw) > MAX_JSON_BYTES for raw in files.values()):
        raise AgentBomError('grader_pack_output_exceeds_limit')
    return report, files


def create_grader_pack(plan_raw, reference_raw, judgments_raw, directory, *, plan_sha256):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('grader_pack_output_already_exists')
    report, files = grader_payloads(plan_raw, reference_raw, judgments_raw, plan_sha256=plan_sha256)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    return report


def verify_grader_pack(directory, *, plan_sha256):
    files, dirs = _capture(directory)
    if dirs or set(files) != FILES:
        raise AgentBomError('grader_pack_inventory_invalid')
    report, expected = grader_payloads(files['plan.json'], files['reference.json'], files['judgments.json'],
                                      plan_sha256=plan_sha256)
    if files != expected:
        raise AgentBomError('grader_pack_does_not_recompute')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau grader-pack', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('plan', 'reference', 'judgments'):
        create.add_argument(name, type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    for command in (create, verify):
        command.add_argument('--plan-sha256', required=True)
    demo = commands.add_parser('demo')
    demo.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .grader_pack_demo import create_demo
            create_demo(args.out)
            print('Created four synthetic label-to-grader handoffs. No grader or human study executed.')
            return 0
        if args.command == 'create':
            plan = _read_request(args.plan)
            validate_plan(plan, args.plan_sha256)
            report = create_grader_pack(plan, _read_request(args.reference), _read_request(args.judgments),
                                       args.out, plan_sha256=args.plan_sha256)
        else:
            report = verify_grader_pack(args.directory, plan_sha256=args.plan_sha256)
        print(f'Recorded grader diagnostic: {report["review_item_count"]} pairs need review. Not grader approval.')
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError, RecursionError):
        print('error: grader_pack_input_or_replay_rejected; no verified diagnostic claimed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
