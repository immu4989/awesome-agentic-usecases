"""Explain changed service requirements and optionally rescore one frozen trace collection."""

import argparse
from copy import deepcopy
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered, write_json
from .public_value import PublicValueContract
from .public_value_review import CONTRACT_FLAGS, CONTRACT_LABELS, CONTRACT_LISTS, _label, _parse
from .eval_service_traces import SCORING_FILES, _bounded, service_trace_payloads


KINDS = ('case_added', 'case_removed', 'version_changed', 'terminal_changed', 'channel_changed',
         'protection_required', 'protection_no_longer_required', 'evidence_requirements_changed',
         'held_evidence_changed', 'prohibitions_changed')
TRANSITIONS = ('became_satisfied', 'became_unsatisfied', 'unchanged_satisfied', 'unchanged_unsatisfied')
BOUNDARY = (
    'Comparison of supplied service-owner contract declarations, not legal interpretation, requirement adequacy, '
    'approval, preregistration, or net policy strength. Added and removed cases are not assumed equivalent; no '
    'favorable intersection is scored. Evidence requirements, held-evidence claims, terminal events, and channels '
    'are changed expectations, not automatically improvements or regressions. Ordering of set-like contract lists '
    'and cases is ignored; omitted optional continuity=false is normalized. Version-label changes still request review. '
    'Frozen-trace rescoring, when requested, applies both suites to the same complete supplied observation collection '
    'with the same current scorer; differences therefore reflect changed requirements for these fixed assertions, '
    'not changed agent behavior, measured public benefit, a causal real-world experiment, or population reliability. '
    'A satisfied inapplicable protection is not a performed protection. Requirements can change even when no supplied '
    'trace exposes a score difference. Ordinary context-comparison and service-review gates remain unchanged. '
    'Input hashes identify JSON values, not original file bytes, authentic execution, source timing, or independent '
    'approval. Listed implementation bytes do not cover dependencies or the interpreter. No source is sanitized, '
    'executed, uploaded, or rewritten and no approval pin or workflow setting is changed. Keep original input files '
    'with this report and inspect all labels, source values, and findings before sharing. No-change is not approval.'
)


def _suite(value):
    _bounded(value)
    if (not isinstance(value, dict) or set(value) != {'suite_version', 'cases'}
            or value['suite_version'] != 'aau-public-value-suite/1.0' or not isinstance(value['cases'], list)
            or not 1 <= len(value['cases']) <= 500):
        raise AgentBomError('contract comparison requires a version-1.0 suite with 1 to 500 cases')
    normalized = {}
    for case in value['cases']:
        if (not isinstance(case, dict) or set(case) != {'case_id', 'contract'}
                or not _label(case['case_id']) or case['case_id'] in normalized):
            raise AgentBomError('contract suite requires unique case IDs and separate contracts')
        fields = _parse(case['contract'], CONTRACT_LISTS, CONTRACT_FLAGS, CONTRACT_LABELS,
                        'continuity_preservation_required', True)
        try:
            contract = PublicValueContract(**fields).as_dict()
        except ValueError as exc:
            raise AgentBomError(str(exc)) from exc
        for name in CONTRACT_LISTS:
            contract[name] = sorted(contract[name])
        normalized[case['case_id']] = contract
    return normalized


def _transition(before, after):
    if before == after:
        return 'unchanged_satisfied' if after else 'unchanged_unsatisfied'
    return 'became_satisfied' if after else 'became_unsatisfied'


def compare_service_contracts(baseline, candidate, *, plan=None, traces=None):
    before, after = _suite(baseline), _suite(candidate)
    if (plan is None) != (traces is None):
        raise AgentBomError('frozen-trace rescoring requires both an import plan and trace collection')
    changes, requests = [], []

    def add(case_id, field, kind, old, new):
        change = {'case_id': case_id, 'field': field, 'kind': kind,
                  'baseline': deepcopy(old), 'candidate': deepcopy(new)}
        if field in CONTRACT_LISTS:
            change.update(added=sorted(set(new) - set(old)), removed=sorted(set(old) - set(new)))
        changes.append(change)

    for case_id in sorted(before.keys() | after.keys()):
        old, new = before.get(case_id), after.get(case_id)
        if old is None or new is None:
            add(case_id, 'contract', 'case_added' if old is None else 'case_removed', old, new)
            continue
        for field, kind in (('version', 'version_changed'), ('expected_terminal', 'terminal_changed'),
                            ('required_channel', 'channel_changed'), ('required_evidence', 'evidence_requirements_changed'),
                            ('held_evidence', 'held_evidence_changed'), ('forbidden_events', 'prohibitions_changed')):
            if old[field] != new[field]:
                add(case_id, field, kind, old[field], new[field])
        for flag in sorted(CONTRACT_FLAGS):
            if old[flag] != new[flag]:
                add(case_id, flag, 'protection_required' if new[flag] else 'protection_no_longer_required', old[flag], new[flag])
        if any(old[field] != new[field] for field in ('required_evidence', 'held_evidence')):
            requests.append({'case_id': case_id,
                             'baseline_missing_evidence': sorted(set(old['required_evidence']) - set(old['held_evidence'])),
                             'candidate_missing_evidence': sorted(set(new['required_evidence']) - set(new['held_evidence'])),
                             'boundary': 'Derived request sets under changed declarations, not proof that evidence was acquired or burden reduced.'})
    impact = {'status': 'not_requested'}
    if plan is not None:
        if before.keys() != after.keys():
            raise AgentBomError('frozen-trace rescoring requires identical case censuses; no intersection filtering; request a structural comparison without probes')
        old_report, _ = service_trace_payloads(plan, baseline, traces)
        new_report, _ = service_trace_payloads(plan, candidate, traces)
        observations = []
        for old, new in zip(old_report['observations'], new_report['observations']):
            left, right = old['assessment'], new['assessment']
            observations.append({'case_id': old['case_id'], 'repeat': old['repeat'],
                                 'joint_transition': _transition(left['metrics']['public_value_exact'], right['metrics']['public_value_exact']),
                                 'changed_metrics': [{'metric': name, 'baseline': left['metrics'][name], 'candidate': right['metrics'][name]}
                                                     for name in sorted(left['metrics']) if left['metrics'][name] != right['metrics'][name]],
                                 'baseline_assessment': left, 'candidate_assessment': right})
        impact = {'status': 'rescored_same_observations', 'plan_sha256': digest(plan), 'traces_sha256': digest(traces),
                  'scenario_count': old_report['scenario_count'], 'repeat_count': old_report['repeat_count'],
                  'observation_count': old_report['observation_count'],
                  'joint_transition_counts': {name: sum(row['joint_transition'] == name for row in observations) for name in TRANSITIONS},
                  'joint_pass_counts': {side: sum(int(row[f'{side}_assessment']['metrics']['public_value_exact']) for row in observations)
                                        for side in ('baseline', 'candidate')},
                  'required_protection_coverage': {'baseline': old_report['required_protection_coverage'],
                                                   'candidate': new_report['required_protection_coverage']},
                  'scoring_contexts': {'baseline': old_report['scoring_context'], 'candidate': new_report['scoring_context']},
                  'observations': observations}
    report = {'report_version': 'aau-service-contract-diff/1.0',
              'baseline_sha256': digest(baseline), 'candidate_sha256': digest(candidate),
              'status': 'review_required' if changes else 'no_contract_change_detected',
              'case_census': {'baseline': sorted(before), 'candidate': sorted(after),
                              'added': sorted(after.keys() - before.keys()), 'removed': sorted(before.keys() - after.keys())},
              'changes': changes, 'change_counts': {kind: sum(c['kind'] == kind for c in changes) for kind in KINDS},
              'evidence_request_sets': requests, 'frozen_trace_review': impact,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                                        for name in sorted((*SCORING_FILES, Path(__file__).name))},
              'boundary': BOUNDARY}
    if len(rendered(report)) > MAX_JSON_BYTES:
        raise AgentBomError('service contract comparison exceeds 2 MB; no changes or findings are truncated')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau compare-service-contracts', description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--plan', type=Path, help='optional frozen-trace import plan; requires --traces')
    parser.add_argument('--traces', type=Path, help='same trace values rescored under both suites; requires --plan')
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument('--out', type=Path)
    destination.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_service_contracts(load_json(args.baseline), load_json(args.candidate),
                                           plan=load_json(args.plan) if args.plan else None,
                                           traces=load_json(args.traces) if args.traces else None)
        if args.verify:
            if rendered(load_json(args.verify)) != rendered(report):
                raise AgentBomError('service contract comparison does not recompute')
        else:
            write_json(report, args.out)
        print(f"{report['status']}: {len(report['changes'])} contract changes; frozen traces: {report['frozen_trace_review']['status']}. Not approval or an agent improvement.")
        return int(bool(report['changes']))
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
