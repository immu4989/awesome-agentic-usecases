"""Present pinned evidence reviews in CI without turning integrity or unknowns into approval."""

import argparse
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

from .agent_bom import MAX_JSON_BYTES, digest, rendered
from .evidence_series import review_series, validate_plan
from .inspect_pack import InspectionError, _capture
from .intake_review import _read_request, review_intake, validate_request


BOUNDARY = (
    'CI presentation of a recomputed pinned intake or ordered-series review, not agent execution, '
    'independent test samples, deployment approval, source authentication, or compliance. Counts are '
    'mechanical review checks, some related, not scenarios or statistical observations. A failure means '
    'a known unmet requirement; an error means evidence or a required check is unavailable or invalid. '
    'Neither is skipped or promoted. Preserve the native review exit: 0 all requirements met, '
    '1 valid non-passing or missing evidence, 2 invalid evidence or inputs. JUnit errors do not necessarily '
    'mean CLI exit 2: an unknown budget is valid non-passing evidence. Report dashboards are not gates. '
    'Fixed ordinal names avoid copying source labels into XML and Markdown; report.json retains the '
    'native review including checkpoint IDs and hashes. None of these artifacts is anonymized or '
    'approved for sharing. No execution times or timestamps are invented. Protect both expected control '
    'hashes independently of candidate evidence. Retain the request, any ordered plan, all complete '
    'source packs, and this four-file presentation bundle with a matching trusted harness. Verification '
    'recomputes from those original inputs, not from manifest hashes or a supplied report. Invalid '
    'evidence has no verified inventory: a repeated invalid diagnostic does NOT identify or bind its '
    'original bytes. Preserve invalid sources separately for investigation. Capture is bounded, not an '
    'atomic snapshot or an authenticated history. No model, adapter, subprocess, upload, network request, '
    'CI configuration change, or approval-setting change is executed.'
)
OUTCOMES = ('passed', 'failure', 'error')
MESSAGES = {'passed': 'Requirement met.', 'failure': 'Known requirement not met.',
            'error': 'Evidence or required check unavailable or invalid.'}


def _case(name, outcome):
    if outcome not in OUTCOMES:
        raise InspectionError('unexpected_ci_check_outcome')
    return {'name': name, 'outcome': outcome, 'message': MESSAGES[outcome]}


def _constraint_outcome(value):
    if value not in (None, 'constraints_met', 'constraints_not_met', 'constraints_not_verified'):
        raise InspectionError('unexpected_ci_constraint_status')
    return {'constraints_met': 'passed', 'constraints_not_met': 'failure'}.get(value, 'error')


def _intake_cases(intake, request):
    cases = [_case('complete-pack-verification', 'passed')]
    for row in intake['checks']:
        # Split the composite outcome so a known policy failure cannot hide an unknown budget.
        if row['constraint'] == 'policy_and_any_candidate_budget':
            continue
        outcome = 'passed' if row['passed'] else 'error' if row['constraint'] == 'matching_declared_context' else 'failure'
        cases.append(_case('requirement-' + row['constraint'], outcome))
    assessment = intake['pack_inspection']['assessment']
    cases.append(_case('policy-outcome', _constraint_outcome(assessment['policy_status'])))
    if assessment['candidate_budget_status'] is not None or 'operating_budget' in request['pinned_inputs']:
        cases.append(_case('candidate-budget-outcome', _constraint_outcome(assessment['candidate_budget_status'])))
    for index, row in enumerate(intake['control_input_checks'], 1):
        if row['status'] not in ('matched', 'mismatched', 'not_checked_profile_mismatch'):
            raise InspectionError('unexpected_ci_control_status')
        outcome = {'matched': 'passed', 'mismatched': 'failure', 'not_checked_profile_mismatch': 'error'}[row['status']]
        cases.append(_case(f'control-input-{index:02d}', outcome))
    return cases


def _counts(cases):
    return {'tests': len(cases), 'failures': sum(row['outcome'] == 'failure' for row in cases),
            'errors': sum(row['outcome'] == 'error' for row in cases), 'skipped': 0}


def review_ci(request_raw, directory: Path, *, request_sha256, plan_raw=None, plan_sha256=None):
    """Only original controls and full evidence are accepted, never a precomputed review JSON."""
    if (plan_raw is None) != (plan_sha256 is None):
        raise InspectionError('ci_series_requires_plan_and_pin')
    if plan_raw is not None:
        validate_plan(plan_raw, plan_sha256)
    request, _ = validate_request(request_raw, request_sha256)  # Before evidence, including error artifacts.
    input_error = None
    if plan_raw is None:
        try:
            native = review_intake(request_raw, directory, request_sha256=request_sha256)
        except InspectionError:
            native, input_error = None, 'complete_evidence_verification_failed'
        rows = [{'intake': native}]
        status = native['status'] if native else 'evidence_invalid'
        code = int(status != 'request_constraints_met') if native else 2
    else:
        native = review_series(plan_raw, request_raw, directory, plan_sha256=plan_sha256, request_sha256=request_sha256)
        rows, status, code = native['checkpoints'], native['status'], native['exit_code']
    suites = []
    for index, row in enumerate(rows, 1):
        cases = _intake_cases(row['intake'], request) if row['intake'] else [_case('required-checkpoint-evidence', 'error')]
        suites.append({'name': f'checkpoint-{index:04d}', 'counts': _counts(cases), 'cases': cases})
    counts = _counts([case for suite in suites for case in suite['cases']])
    if (code == 0) != (counts['failures'] + counts['errors'] == 0):
        raise InspectionError('ci_presentation_disagrees_with_native_outcome')
    report = {'report_version': 'aau-evidence-ci-review/1.0', 'mode': 'series' if plan_raw is not None else 'intake',
              'status': status, 'exit_code': code, 'request_file_sha256': request_sha256,
              'plan_file_sha256': plan_sha256, 'native_review': native, 'input_error': input_error,
              'invalid_evidence_bytes_bound': False, 'suites': suites, 'counts': counts,
              'implementation_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
                                        ('evidence_ci.py', 'evidence_series.py', 'intake_review.py', 'inspect_pack.py', 'agent_bom.py')},
              'boundary': BOUNDARY}
    if len(rendered(report)) > MAX_JSON_BYTES:
        raise InspectionError('ci_report_exceeds_limit')
    return report


def _render_junit(report):
    root = ET.Element('testsuites', **{key: str(value) for key, value in report['counts'].items()})
    for suite in report['suites']:
        tests = ET.SubElement(root, 'testsuite', name='aau.review.' + suite['name'],
                              **{key: str(value) for key, value in suite['counts'].items()})
        properties = ET.SubElement(tests, 'properties')
        for name, value in (('mode', report['mode']), ('native_exit_code', report['exit_code']),
                            ('report_sha256', digest(rendered(report))), ('count_unit', 'mechanical-review-check')):
            ET.SubElement(properties, 'property', name=name, value=str(value))
        for case in suite['cases']:
            # Unique even for consumers that ignore suite/class names. No untrusted labels or source paths.
            test = ET.SubElement(tests, 'testcase', classname='aau.review.' + suite['name'],
                                 name=suite['name'] + '/' + case['name'])
            if case['outcome'] != 'passed':
                finding = ET.SubElement(test, case['outcome'], type='aau.review.' + case['outcome'], message=case['message'])
                finding.text = case['message'] + ' See the corresponding ordinal suite in report.json. Not deployment approval.'
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


def _render_summary(report):
    lines = ['# Recorded evidence CI review', '', f"Native outcome: `{report['status']}`. Exit: **{report['exit_code']}**.", '',
             'These counts are mechanical review checks, not scenarios, agent runs, or independent samples.', '',
             '| Ordinal checkpoint | Checks | Failures | Errors |', '|---|---:|---:|---:|']
    for suite in report['suites']:
        counts = suite['counts']
        lines.append(f"| {suite['name']} | {counts['tests']} | {counts['failures']} | {counts['errors']} |")
    lines.extend(['', 'Failure = known unmet requirement. Error = unavailable or invalid evidence/check. Nothing is skipped.', '',
                  'Keep the native command exit status; a rendered dashboard alone is not a gate.', '',
                  'Read `report.json` for every check and the original review, in the same ordinal order.', '', BOUNDARY, ''])
    return '\n'.join(lines).encode('utf-8')


def _payloads(report):
    files = {'report.json': rendered(report), 'junit.xml': _render_junit(report), 'summary.md': _render_summary(report)}
    files['manifest.json'] = rendered({'presentation_version': 'aau-evidence-ci-bundle/1.0',
                                       'files_sha256': {name: digest(value) for name, value in sorted(files.items())}})
    if any(len(value) > MAX_JSON_BYTES for value in files.values()):
        raise InspectionError('ci_bundle_member_exceeds_limit')
    return files


def export_ci(request_raw, directory: Path, *, request_sha256, out=None, verify=None, plan_raw=None, plan_sha256=None):
    if (out is None) == (verify is None):
        raise InspectionError('ci_choose_output_or_verification')
    target = out if out is not None else verify
    if target.resolve() == directory.resolve() or directory.resolve() in target.resolve().parents:
        raise InspectionError('ci_output_must_be_outside_evidence')
    if out is not None and (out.exists() or out.is_symlink()):
        raise InspectionError('ci_output_already_exists')
    report = review_ci(request_raw, directory, request_sha256=request_sha256, plan_raw=plan_raw, plan_sha256=plan_sha256)
    files = _payloads(report)
    if verify is not None:
        actual, folders = _capture(verify)
        if folders or actual != files:
            raise InspectionError('ci_bundle_does_not_recompute')
    else:
        out.mkdir(parents=True, exist_ok=False)
        # Manifest last; interrupted output is not a complete bundle. Never overwrite partial output.
        for name, value in files.items():
            with (out / name).open('xb') as stream:
                stream.write(value)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau review-ci', description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    for mode in ('intake', 'series'):
        command = commands.add_parser(mode)
        if mode == 'series':
            command.add_argument('plan', type=Path)
            command.add_argument('--plan-sha256', required=True, help='independently controlled ordered-plan byte hash')
        command.add_argument('request', type=Path)
        command.add_argument('directory', type=Path)
        command.add_argument('--request-sha256', required=True, help='independently controlled request byte hash')
        output = command.add_mutually_exclusive_group(required=True)
        output.add_argument('--out', type=Path)
        output.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        report = export_ci(_read_request(args.request), args.directory, request_sha256=args.request_sha256,
                           plan_raw=_read_request(args.plan) if args.mode == 'series' else None,
                           plan_sha256=args.plan_sha256 if args.mode == 'series' else None, out=args.out, verify=args.verify)
        print(f"{report['status']}: exit {report['exit_code']}; {report['counts']['failures']} failed checks; "
              f"{report['counts']['errors']} unavailable/invalid checks. Not deployment approval.")
        return report['exit_code']
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        reason = str(exc) if isinstance(exc, InspectionError) else 'ci_input_or_output_rejected'
        print(f'error: {reason}; no verified CI presentation produced.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
