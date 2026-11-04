"""Recompute service traces through a strict all-obligations policy and optional budget gate."""

import argparse
import json
from pathlib import Path
import sys

from .agent_bom import AgentBomError, MAX_JSON_BYTES, digest, load_json, rendered
from .eval_budget import validate_budget
from .eval_csv_review import BUDGET_FILES, REVIEW_FILES, ROOT_FILES
from .eval_pack import pack_payloads
from .eval_policy import validate_policy
from .eval_repeatability import _criteria
from .eval_service_traces import FILES as SOURCE_FILES, service_trace_payloads


GROUPS = {'baseline': SOURCE_FILES, 'candidate': SOURCE_FILES, 'review': REVIEW_FILES}
GUIDE = """AAU service trace review handoff

Open review/review.html for the policy verdict and repeated-run/operating diagnostics.
The page is script-free and offline, but it does not verify itself. With the same
trusted harness source version, verify all 30 files together:

  aau service-review verify PATH_TO_THIS_FOLDER

Exit 0: complete source chain verifies and supplied policy constraints are met.
Exit 1: complete source chain verifies but constraints are NOT met.
Exit 2: invalid input, incomplete evidence, changed scoring code, or failed verification.
Keep valid failed evidence. Interrupted folders cannot serve as verified handoffs.

Baseline and candidate retain separate plans and normalized traces, identical
contract-suite values, recomputed findings, recordings, evaluations, and manifests.
Review retains policy, diagnostic definitions, both recordings, and derived reports.
Verification starts with the traces and contracts, not caller-supplied scores.
A valid but unrelated nested pack cannot substitute for the complete source chain.

This strict service profile requires public_value_exact >= 1 for EVERY candidate
observation in the global policy and in joint diagnostic success criteria. A passing
completion metric cannot compensate for an unsatisfied declared obligation. Baseline
failures remain reviewable. Requirements are never silently added to supplied plans.
Required-only protection counts distinguish satisfied inapplicable obligations from
performed protections. Inspect baseline/scoring.json and candidate/scoring.json.

The common suite is a service-owner declaration, not inferred law or independently
approved policy. The GitHub Action requires its independent byte-hash approval as
well as pinned policy, baseline, both import plans, and diagnostics. Pin trusted
Action code separately. CLI hashes are not approvals or signatures: coordinated
replacement of all sources can verify. Do not derive approval pins from the candidate
change under review. Source fingerprints do not authenticate execution or dependencies.

NOT SANITIZED: all contract and trace JSON values are retained, not original file
bytes. Inspect every file before sharing. No model, service, upload, eligibility
decision, legal certification, population claim, or deployment approval occurs.
Supplied operating measurements are not verified invoices; missing values stay unknown.
"""


def _require_joint_success(rules, limit_field, label):
    if not any(rule.get('metric') == 'public_value_exact' and rule.get('direction') == 'higher'
               and type(rule.get(limit_field)) in (int, float) and rule[limit_field] == 1 for rule in rules):
        raise AgentBomError(f'service review requires public_value_exact >= 1 in {label}; obligations cannot be omitted or relaxed')


def handoff_payloads(policy, baseline_plan, baseline_traces, candidate_plan, candidate_traces,
                     diagnostics, *, service_suite, operating_budget=None):
    validate_policy(policy)
    _require_joint_success(policy['metrics'], 'candidate_observation_limit', 'global policy')
    if not isinstance(diagnostics, dict):
        raise AgentBomError('service review requires an explicit diagnostics plan')
    _require_joint_success(_criteria(diagnostics.get('criteria')), 'limit', 'diagnostic criteria')
    if operating_budget is not None:
        validate_budget(operating_budget)
        _require_joint_success(operating_budget['criteria'], 'limit', 'operating budget criteria')
    payloads, recordings, sources = {}, [], {}
    for side, plan, traces in (('baseline', baseline_plan, baseline_traces), ('candidate', candidate_plan, candidate_traces)):
        scoring, files = service_trace_payloads(plan, service_suite, traces)
        payloads.update({f'{side}/{name}': value for name, value in files.items()})
        recordings.append(json.loads(files['recording.json']))
        sources[side] = {key: scoring[key] for key in (
            'plan_sha256', 'suite_sha256', 'traces_sha256', 'recording_sha256', 'evaluation_sha256',
            'status', 'scenario_count', 'repeat_count', 'observation_count', 'failed_observation_count',
            'failed_observations', 'required_protection_coverage')}
    outcome, files = pack_payloads(policy, *recordings, recordings=True, diagnostics=diagnostics,
                                   operating_budget=operating_budget)
    payloads.update({f'review/{name}': value for name, value in files.items()})
    report = {'report_version': 'aau-service-evaluation-handoff/1.0', 'status': outcome['status'],
              'service_suite_sha256': digest(service_suite), 'policy_sha256': digest(policy),
              'diagnostics_sha256': digest(diagnostics), 'review_sha256': digest(json.loads(files['review.json'])),
              'sources': sources, 'profile': 'all_declared_obligations_per_candidate_observation',
              'boundary': 'Recomputed supplied normalized traces against one common declared contract suite. Global policy and joint success criteria require public_value_exact >= 1; no inferred requirements, independently approved policy, authentic execution, real-world effectiveness, source sanitization, or deployment approval. Supplied measurements stay supplied; absent measurements stay unknown. Coordinated replacement can verify; hashes are not signatures.'}
    guide = GUIDE
    if operating_budget is not None:
        report.update(report_version='aau-service-evaluation-handoff/1.1', gate_sha256=digest(outcome),
                      operating_budget_sha256=digest(operating_budget), policy_status=outcome['policy_status'],
                      candidate_budget_status=outcome['candidate_budget_status'])
        guide = (GUIDE.replace('30 files', '33 files').replace('supplied policy constraints', 'combined policy and candidate budget constraints')
                 + '\nThe optional budget is present and independently gated. Budget success criteria also\n'
                 'require public_value_exact >= 1. Missing required measurements cannot pass.\n'
                 'Reject a removed budget layer with:\n'
                 '  aau service-review verify PATH_TO_THIS_FOLDER --require-budget\n')
    payloads['handoff.json'] = rendered(report)
    payloads['README.txt'] = guide.encode('utf-8')
    payloads['manifest.json'] = rendered({
        'pack_version': 'aau-service-evaluation-handoff-pack/1.1' if operating_budget is not None else 'aau-service-evaluation-handoff-pack/1.0',
        'files': {name: digest(value) for name, value in sorted(payloads.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in payloads.values()):
        raise AgentBomError('service handoff member exceeds 2 MB; no evidence is truncated')
    return report, payloads


def create_handoff(policy, baseline_plan, baseline_traces, candidate_plan, candidate_traces,
                   diagnostics, directory: Path, *, service_suite, operating_budget=None):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite service handoff destination')
    report, files = handoff_payloads(policy, baseline_plan, baseline_traces, candidate_plan, candidate_traces,
                                     diagnostics, service_suite=service_suite, operating_budget=operating_budget)
    directory.mkdir(parents=True, exist_ok=False)
    for group in GROUPS:
        (directory / group).mkdir()
    for name, value in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(value)  # Root manifest last: partial folders cannot verify.
    return report


def _regular(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise AgentBomError('service handoff members must be bounded regular non-symlink files')


def verify_handoff(directory: Path, *, require_budget=False):
    if (directory.is_symlink() or not directory.is_dir()
            or {p.name for p in directory.iterdir()} != ROOT_FILES | set(GROUPS)):
        raise AgentBomError('service handoff requires its exact root file and directory set')
    for name in ROOT_FILES:
        _regular(directory / name)
    version = load_json(directory / 'manifest.json').get('pack_version')
    if version not in ('aau-service-evaluation-handoff-pack/1.0', 'aau-service-evaluation-handoff-pack/1.1'):
        raise AgentBomError('unsupported service handoff version')
    budget = version == 'aau-service-evaluation-handoff-pack/1.1'
    if require_budget and not budget:
        raise AgentBomError('operating budget gate required; ungated service handoff refused')
    for group, names in GROUPS.items():
        folder = directory / group
        if budget and group == 'review':
            names = names | BUDGET_FILES
        if folder.is_symlink() or not folder.is_dir() or {p.name for p in folder.iterdir()} != names:
            raise AgentBomError(f'service handoff requires exact member set: {group}')
        for name in names:
            _regular(folder / name)
    report, expected = handoff_payloads(
        load_json(directory / 'review/policy.json'), load_json(directory / 'baseline/plan.json'),
        load_json(directory / 'baseline/traces.json'), load_json(directory / 'candidate/plan.json'),
        load_json(directory / 'candidate/traces.json'), load_json(directory / 'review/diagnostics.json'),
        service_suite=load_json(directory / 'baseline/suite.json'),
        operating_budget=load_json(directory / 'review/operating-budget.json') if budget else None)
    for name, value in expected.items():
        if (directory / name).read_bytes() != value:
            raise AgentBomError(f'service handoff member does not recompute: {name}')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau service-review', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    for name in ('policy', 'suite', 'baseline_plan', 'baseline_traces', 'candidate_plan', 'candidate_traces'):
        create.add_argument(name, type=Path)
    create.add_argument('--diagnostics', type=Path, required=True)
    create.add_argument('--operating-budget', type=Path)
    create.add_argument('--out', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    verify.add_argument('--require-budget', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            create_handoff(load_json(args.policy), load_json(args.baseline_plan), load_json(args.baseline_traces),
                           load_json(args.candidate_plan), load_json(args.candidate_traces), load_json(args.diagnostics), args.out,
                           service_suite=load_json(args.suite),
                           operating_budget=load_json(args.operating_budget) if args.operating_budget else None)
            report = verify_handoff(args.out, require_budget=bool(args.operating_budget))
        else:
            report = verify_handoff(args.directory, require_budget=args.require_budget)
        count = 33 if 'operating_budget_sha256' in report else 30
        print(f"Service handoff verified: {report['status']}; all {count} files recomputed. Not deployment approval.")
        return int(report['status'] != 'constraints_met')
    except (AgentBomError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
