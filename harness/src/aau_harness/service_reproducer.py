"""Create label-minimized service reproducers without claiming anonymization or publication approval."""

import argparse
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_service_traces import FILES as SERVICE_FILES, SCORING_FILES, service_trace_payloads


FILES = {f'service/{name}' for name in SERVICE_FILES} | {'reproduction.json', 'README.txt', 'manifest.json'}
SOURCE_LABEL = 'Label-minimized service reproducer; not original source identity'
CONTRACT_VERSION = 'aau-label-minimized-service/1.0'
BOUNDARY = (
    'Label minimization for reproducing normalized service-scoring behavior, NOT anonymization, de-identification '
    'certification, a privacy guarantee, legal compliance, publication approval, or authenticated service execution. '
    'Case identifiers, contract versions, event/evidence/channel labels, and the source label are replaced. '
    'Cost, latency, and API-call measurements are removed, not zeroed. No private-input hashes, original names, '
    'mapping, or original-source provenance are retained. Counts, ordering, repetitions, equality patterns within '
    'each case and namespace, protection flags, and failures remain and can reveal sensitive facts or enable linkage. '
    'Aliases are deterministic local ordinals, not secret tokens, cryptographic pseudonyms, or a privacy budget. '
    'Cross-case and cross-namespace label identity and label meaning are intentionally not preserved. '
    'Creation checks every original and minimized observation metric and required-protection count; offline '
    'verification without private inputs proves only the minimized profile and its recomputed evidence. '
    'Owner-side source verification checks the same transformation, not exact original identity: changed names, '
    'version labels, or removed measurements can produce the same reproducer. No population inference, operating '
    'comparison, original context equivalence, approval-pin substitution, or deployment approval is supported. '
    'Hashes cover exported values and listed first-party bytes, not dependencies, the interpreter, authenticity, '
    'or independent review. Coordinated replacement can verify. No upload occurs. Independently assess residual '
    'disclosure risk and authority before sharing; use synthetic data when release is not appropriate.'
)
GUIDE = '''Label-minimized service reproducer — NOT approved for publication

This folder reproduces normalized service-scoring failures without copying original
case IDs, source names, contract versions, or event/evidence/channel labels. It is
not anonymized data. Counts, equality patterns, sequence, repeated requests, flags,
and outcomes remain. These can disclose sensitive facts or identify a source.
No statistical privacy protection or disclosure-risk assessment is provided.

  aau service-reproducer verify PATH_TO_THIS_FOLDER

Exit 0 means the ten-file minimized profile recomputes, including failed service
observations. It is NOT a passing-service or publish-approval gate. Exit 2 means
invalid inputs, changed files, or a failed preservation check. No sources are run.

Review service/scoring.json for every obligation and service/evaluation.json for
the derived metrics. The nested seven-file pack uses the normal service interface:

  aau service-trace-eval verify PATH_TO_THIS_FOLDER/service

That separate command exits 1 when supplied service obligations fail, 0 when they
all pass, and 2 for invalid evidence. Operating measurements are absent, not zero.
Do not use the reproducer to compare original cost/latency or replace approved pins.

The owner can verify the transformation locally against private original inputs:

  aau service-reproducer verify-source PATH_TO_THIS_FOLDER PLAN SUITE TRACES

Keep those originals private and separate. They and their hashes are deliberately
absent from this folder; no reversible mapping file is emitted. This check confirms
the same minimized values and scoring preservation, not the identity of originals.
Original name/version/measurement edits can legitimately produce the same export.
An outside reviewer cannot establish source fidelity from this pack alone.

All declared cases and repeats are retained, including failures and non-submission.
Nothing is selected by score. Aliases are per-case, per-namespace ordinals assigned
in contract/trace encounter order. No hash of a private label is used. Event names
stay consistent across expected, forbidden, attempted, executed, and terminal roles.
Evidence labels stay consistent across required, held, and requested roles. Duplicate
requests and multiple terminal/channel events remain duplicates, not collapsed sets.
Contract versions and source descriptions become fixed labels; cross-case name
identity and domain meanings are lost. This is only a normalized scorer reproducer.

Creation compares every original/minimized metric and required-protection count
before writing. Offline verification also requires the alias profile to be a fixed
point of the transformation, so an ordinary source pack with private labels cannot
silently pass as minimized. Tampering plus rehashing does not bypass recomputation;
replacing the whole unsigned folder with a different valid folder can still verify.
Preserve the full folder and use a matching trusted implementation to recompute it.

Before sharing: inspect the whole folder, review unusual counts and outcome patterns,
assess recipient/linkage risks and legal/organizational permissions independently.
If residual disclosure is inappropriate, create an independent synthetic example
instead. This command never uploads or authorizes disclosure. Private input files
are not deleted or modified. Existing destinations are not overwritten.
'''


def _minimized_inputs(plan, suite, traces):
    """Transform already validated inputs, keeping the private case correspondence in memory only."""
    indexed = {(row['case_id'], row.get('repeat', 0)): row['trace'] for row in traces['observations']}
    cases, rows, correspondence = [], [], []
    for number, case in enumerate(suite['cases'], 1):
        alias = f'case-{number:04d}'
        contract = case['contract']
        maps = {name: {} for name in ('event', 'evidence', 'channel')}

        def rename(namespace, value):
            labels = maps[namespace]
            if value not in labels:
                labels[value] = f'{namespace}-{len(labels) + 1:04d}'
            return labels[value]

        def renamed(namespace, values):
            return [rename(namespace, value) for value in values]

        transformed = {
            'version': CONTRACT_VERSION,
            'expected_terminal': rename('event', contract['expected_terminal']),
            'required_evidence': renamed('evidence', contract['required_evidence']),
            'held_evidence': renamed('evidence', contract['held_evidence']),
            'required_channel': rename('channel', contract['required_channel']),
            'recourse_required': contract['recourse_required'],
            'deadline_preservation_required': contract['deadline_preservation_required'],
            'continuity_preservation_required': contract.get('continuity_preservation_required', False),
            'forbidden_events': renamed('event', contract['forbidden_events']),
        }
        cases.append({'case_id': alias, 'contract': transformed})
        for repeat in range(plan['n_repeats']):
            trace = indexed[case['case_id'], repeat]
            minimized = {
                'terminal_events': renamed('event', trace['terminal_events']),
                'requested_evidence': renamed('evidence', trace['requested_evidence']),
                'delivery_channels': renamed('channel', trace['delivery_channels']),
                'recourse_offered': trace['recourse_offered'], 'deadline_preserved': trace['deadline_preserved'],
                'continuity_preserved': trace.get('continuity_preserved', False),
                'attempted_events': renamed('event', trace['attempted_events']),
                'executed_events': renamed('event', trace['executed_events']), 'submitted': trace['submitted'],
            }
            rows.append({'case_id': alias, 'repeat': repeat, 'trace': minimized})
            correspondence.append((case['case_id'], alias, repeat))
    return ({'plan_version': 'aau-service-trace-import/1.0', 'source_label': SOURCE_LABEL, 'n_repeats': plan['n_repeats']},
            {'suite_version': 'aau-public-value-suite/1.0', 'cases': cases},
            {'trace_version': 'aau-public-value-traces/1.1', 'observations': rows}, correspondence)


def reproducer_payloads(plan, suite, traces):
    original, _ = service_trace_payloads(plan, suite, traces)
    minimized_plan, minimized_suite, minimized_traces, correspondence = _minimized_inputs(plan, suite, traces)
    minimized, source_files = service_trace_payloads(minimized_plan, minimized_suite, minimized_traces)
    before = {(row['case_id'], row['repeat']): row['assessment']['metrics'] for row in original['observations']}
    after = {(row['case_id'], row['repeat']): row['assessment']['metrics'] for row in minimized['observations']}
    if (len(before) != len(after) or len(correspondence) != len(before)
            or any(before[source, repeat] != after[alias, repeat] for source, alias, repeat in correspondence)
            or original['required_protection_coverage'] != minimized['required_protection_coverage']):
        raise AgentBomError('label minimization did not preserve every supplied service metric and protection count')
    report = {'reproduction_version': 'aau-label-minimized-service-reproducer/1.0',
              'status': 'label_minimized_reproduction', 'service_status': minimized['status'],
              'scenario_count': minimized['scenario_count'], 'repeat_count': minimized['repeat_count'],
              'observation_count': minimized['observation_count'], 'failed_observation_count': minimized['failed_observation_count'],
              'minimized_evaluation_sha256': minimized['evaluation_sha256'],
              'source_relationship': 'not_verifiable_without_private_inputs; transformation_equivalence_not_source_identity',
              'removed': ['original_case_ids', 'original_contract_versions', 'original_source_label',
                          'original_event_evidence_channel_labels', 'cost_usd', 'latency_s', 'n_api_calls',
                          'original_input_hashes_and_identity_mapping'],
              'retained': ['complete_case_repeat_census', 'within_case_namespace_equality', 'list_order_and_multiplicity',
                           'required_and_observed_flags', 'per_observation_metrics_and_findings', 'required_protection_counts'],
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                                        for name in sorted((*SCORING_FILES, Path(__file__).name))}, 'boundary': BOUNDARY}
    files = {f'service/{name}': value for name, value in source_files.items()}
    files.update({'reproduction.json': rendered(report), 'README.txt': GUIDE.encode('utf-8')})
    files['manifest.json'] = rendered({'pack_version': 'aau-label-minimized-service-pack/1.0',
                                      'files': {name: digest(value) for name, value in sorted(files.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in files.values()):
        raise AgentBomError('service reproducer member exceeds 2 MB; nothing is truncated')
    return report, files


def create_reproducer(plan, suite, traces, directory: Path):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite service reproducer destination')
    report, files = reproducer_payloads(plan, suite, traces)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'service').mkdir()
    for name, value in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(value)
    return report


def verify_reproducer(directory: Path):
    if (directory.is_symlink() or not directory.is_dir()
            or {path.name for path in directory.iterdir()} != {'service', 'reproduction.json', 'README.txt', 'manifest.json'}):
        raise AgentBomError('service reproducer requires its exact directory structure')
    service = directory / 'service'
    if service.is_symlink() or not service.is_dir() or {path.name for path in service.iterdir()} != SERVICE_FILES:
        raise AgentBomError('service reproducer requires its exact nested service pack')
    for name in FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise AgentBomError('service reproducer members must be bounded regular non-symlink files')
    report, expected = reproducer_payloads(*(load_json(service / f'{name}.json') for name in ('plan', 'suite', 'traces')))
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError('service reproducer does not match the minimized profile and recomputed evidence')
    return report


def verify_source(directory: Path, plan, suite, traces):
    report = verify_reproducer(directory)
    expected_report, expected = reproducer_payloads(plan, suite, traces)
    if report != expected_report or any((directory / name).read_bytes() != value for name, value in expected.items()):
        raise AgentBomError('service reproducer differs from the supplied private-input transformation')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau service-reproducer', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    verify = sub.add_parser('verify')
    verify.add_argument('directory', type=Path)
    source = sub.add_parser('verify-source')
    source.add_argument('directory', type=Path)
    for command in (create, source):
        for name in ('plan', 'suite', 'traces'):
            command.add_argument(name, type=Path)
    create.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            report = verify_reproducer(args.directory)
        else:
            inputs = [load_json(getattr(args, name)) for name in ('plan', 'suite', 'traces')]
            report = (create_reproducer(*inputs, args.out) if args.command == 'create'
                      else verify_source(args.directory, *inputs))
        print(f"Label-minimized reproducer verified: {report['observation_count']} observations; "
              f"{report['failed_observation_count']} service failures retained. NOT anonymized or approved for sharing.")
        return 0
    except (ValueError, OSError, RecursionError) as exc:
        # Private labels can appear in upstream parser errors and paths; never echo them.
        print(f'error: service reproducer rejected input ({type(exc).__name__}); no sharing approval.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
