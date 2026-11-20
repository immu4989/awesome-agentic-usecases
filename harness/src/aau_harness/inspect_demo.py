"""Create a no-key constructed Inspect-format conversion and a rejected missing-row example."""

from copy import deepcopy

from .agent_bom import AgentBomError, digest, rendered
from .eval_inspect import create_inspect_pack, inspect_payloads, verify_inspect_pack
from .inspect_diagnostic import create_diagnostic, diagnostic_payloads, verify_diagnostic


def example_inputs():
    plan = {'plan_version': 'aau-inspect-observation-plan/1.0',
            'source_label': 'Constructed service-routing scores, not a model evaluation',
            'sample_map': [{'sample_id': 1, 'scenario_id': 'self-service'},
                           {'sample_id': '1', 'scenario_id': 'assisted'}], 'n_repeats': 2,
            'metrics': {'completion': {'scorer': 'match', 'value_key': None, 'encoding': 'labels',
                                      'labels': {'C': 1, 'I': 0, 'N': None}},
                        'authorization': {'scorer': 'checks', 'value_key': 'authorized', 'encoding': 'number'}}}
    source = {'version': 2, 'status': 'success',
              'eval': {'task': 'constructed-service-example', 'created': '2026-11-19T00:00:00Z',
                       'model': 'constructed-no-model', 'config': {'epochs': 2},
                       'dataset': {'samples': 2, 'sample_ids': [1, '1'], 'shuffled': False},
                       'packages': {'inspect_ai': 'constructed-not-an-Inspect-execution'}},
              'results': {'total_samples': 4, 'completed_samples': 4},
              'samples': [{'id': identity, 'epoch': epoch, 'input': 'Constructed service request', 'target': '',
                           'scores': {'match': {'value': label}, 'checks': {'value': {'authorized': authorized}}}}
                          for identity, epoch, label, authorized in ((1, 1, 'C', 1), (1, 2, 'I', 1),
                                                                     ('1', 1, 'C', None), ('1', 2, 'N', 0))]}
    return plan, source


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite an Inspect demo destination')
    plan, source = example_inputs()
    raw_plan, raw_source = rendered(plan), rendered(source)
    pin = digest(raw_plan)
    inspect_payloads(raw_plan, raw_source, plan_sha256=pin)  # Validate before writing anything.
    incomplete = deepcopy(source)
    incomplete['samples'].pop()
    interrupted = deepcopy(incomplete)
    interrupted['status'] = 'error'
    interrupted['error'] = {'message': 'Constructed interrupted run; no real endpoint.'}
    interrupted['samples'][0]['error'] = {'message': 'Constructed scored error.'}
    interrupted['samples'][1]['error_retries'] = [{'message': 'Constructed earlier error.'}]
    interrupted['samples'][2]['limit'] = {'type': 'time', 'limit': 1}
    interrupted['samples'][2]['invalidation'] = {'reason': 'Constructed review marker.'}
    interrupted['samples'][2]['scores']['audit-only'] = {'value': 0, 'reason': 'zeroed', 'history': [{'value': 1}]}
    interrupted['samples'].append(deepcopy(interrupted['samples'][0]))
    interrupted['samples'].append({'id': 'outside-plan', 'epoch': 1, 'scores': {}})
    diagnostic_payloads(raw_plan, rendered(interrupted), plan_sha256=pin)
    directory.mkdir(parents=True, exist_ok=False)
    files = {'plan.json': raw_plan, 'source.json': raw_source, 'incomplete-source.json': rendered(incomplete),
             'interrupted-source.json': rendered(interrupted)}
    lines = ['# Reuse scores without hiding missing evidence', '',
             'This is a constructed Inspect-format example, not an Inspect or model execution.',
             'The separate repository regression test uses an upstream Inspect mock-model log with documented byte hashes.', '',
             'The integer ID 1 and string ID "1" are different cases. Epochs 1/2 become repeats 0/1.',
             'One completion is zero. One completion label N maps explicitly to missing, not zero.',
             'One authorization score is missing and one is zero. Both metrics cover 3 of 4 observations.',
             'A success run status means the run finished, not that its scores passed a policy.', '',
             'Run from this directory with the same trusted harness; this pin is for the demo only:', '',
             '```bash', f'aau inspect-eval verify converted --plan-sha256 {pin}',
             f'aau inspect-eval create plan.json source.json --plan-sha256 {pin} --out another-conversion',
             '# Expected exit 2: a missing sample/epoch pair must not be silently dropped.',
             f'aau inspect-eval create plan.json incomplete-source.json --plan-sha256 {pin} --out rejected',
             '```', '',
             'Use a new output directory for each create. Review conversion.json and evaluation.json.',
             'No cost, latency, API counts, or context fingerprints are inferred. This conversion is not a gate.',
             'In real reviews, keep the reviewed plan pin independently from the supplier and protect raw logs.',
             'The converted directory retains the complete source bytes: it is not a sanitized sharing artifact.', '']
    lines += ['## Review interrupted evidence without repairing it', '',
              'Open diagnostic/review.html. Five source rows cover only three of four planned pairs:',
              'one pair is duplicated, one is missing, and one row is outside the plan.',
              'Errors, retries, limits, invalidation, and edits on an unmapped scorer remain visible.',
              'A score on an errored row does not erase its error. No evaluation is exported from this diagnostic.', '',
              '```bash', '# Expected exit 1: a valid diagnostic with findings, not a broken packet.',
              f'aau inspect-eval verify-diagnostic diagnostic --plan-sha256 {pin}',
              f'aau inspect-eval diagnose plan.json interrupted-source.json --plan-sha256 {pin} --out another-diagnostic',
              '```', '', 'The strict create command still rejects this source. Do not edit it to force acceptance.', '']
    files['README.md'] = '\n'.join(lines).encode()
    for name, raw in files.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    create_inspect_pack(raw_plan, raw_source, directory / 'converted', plan_sha256=pin)
    verify_inspect_pack(directory / 'converted', plan_sha256=pin)
    create_diagnostic(raw_plan, rendered(interrupted), directory / 'diagnostic', plan_sha256=pin)
    verify_diagnostic(directory / 'diagnostic', plan_sha256=pin)
