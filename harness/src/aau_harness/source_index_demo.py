"""Synthetic source-to-diagnostic/conversion links, not authentic execution or agency evidence."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile

from .agent_bom import digest, rendered
from .eval_pack import create_pack
from .evidence_index import create_index, verify_index


EXPORTERS = ('inspect', 'promptfoo')
VARIANTS = ('linked-source', 'policy-context-gap', 'rejected-conversion', 'substituted-source')


def build_inputs(directory, exporter, variant):
    if exporter not in EXPORTERS or variant not in VARIANTS:
        raise ValueError('unknown synthetic source-index example')
    if exporter == 'inspect':
        from .inspect_review_demo import example_inputs
        from .eval_inspect import create_inspect_pack as convert
        from .inspect_diagnostic import create_diagnostic as diagnose
    else:
        from .promptfoo_review_demo import example_inputs
        from .eval_promptfoo import create_promptfoo_pack as convert
        from .promptfoo_diagnostic import create_diagnostic as diagnose
    review_request, baseline, candidate = example_inputs()['unsafe']
    plan = review_request['candidate_plan']
    raw_plan, raw_candidate = rendered(plan), rendered(candidate)
    pin = digest(raw_plan)
    delivery = directory / 'delivery'
    delivery.mkdir(parents=True)
    items = [{'item_id': identity, 'profile': f'{exporter}-{profile}', 'purpose': purpose,
              'controls': {'plan_sha256': pin}} for identity, profile, purpose in (
                  ('conversion', 'conversion', 'Require the full strict source projection, not just a diagnostic.'),
                  ('diagnostic', 'diagnostic', 'Retain source findings independently of conversion and policy.'))]
    bindings = [{'left': {'item_id': 'conversion', 'role': role}, 'right': {'item_id': 'diagnostic', 'role': role}}
                for role in ('source', 'plan')]
    if variant == 'rejected-conversion':
        interrupted = deepcopy(candidate)
        if exporter == 'inspect':
            interrupted['status'] = 'error'
            interrupted['samples'][0]['error'] = {'message': 'Constructed interruption'}
        else:
            interrupted['results']['results'][0].update(failureReason=2, success=False, error='Constructed provider error')
        raw_diagnostic = rendered(interrupted)
    else:
        convert(raw_plan, raw_candidate, delivery / 'conversion', plan_sha256=pin)
        raw_diagnostic = rendered(example_inputs()['repaired'][2]) if variant == 'substituted-source' else raw_candidate
    if variant == 'policy-context-gap':
        # Both source conversion and policy use byte-identical evaluation.json, not independently guessed scores.
        evaluation = json.loads((delivery / 'conversion/evaluation.json').read_bytes())
        if exporter == 'inspect':
            from .eval_inspect import inspect_payloads as projection
        else:
            from .eval_promptfoo import promptfoo_payloads as projection
        baseline_plan = rendered(review_request['baseline_plan'])
        _, base_files = projection(baseline_plan, rendered(baseline), plan_sha256=digest(baseline_plan))
        base_evaluation = json.loads(base_files['evaluation.json'])
        policy = review_request['policy']
        create_pack(policy, base_evaluation, evaluation, delivery / 'policy')
        intake = {'request_version': 'aau-evidence-intake-request/1.0', 'profile': 'evaluation-review',
                  'pack_version': 'aau-evaluation-review-pack/1.0', 'input_format': 'evaluations',
                  'pinned_inputs': {'policy': digest(rendered(policy)), 'baseline': digest(rendered(base_evaluation))}}
        items.append({'item_id': 'policy', 'profile': 'policy-review', 'purpose': 'Keep the failed authorization policy visible.',
                      'controls': {'intake_request': intake}})
        bindings.append({'left': {'item_id': 'conversion', 'role': 'evaluation'},
                         'right': {'item_id': 'policy', 'role': 'candidate'}})
    diagnose(raw_plan, raw_diagnostic, delivery / 'diagnostic', plan_sha256=pin)
    return {'request_version': 'aau-evidence-index-request/1.0',
            'purpose': 'Constructed source-linked delivery; no execution, approval, or measured public benefit.',
            'items': items, 'bindings': bindings}, delivery


def add_examples(directory):
    commands = []
    for exporter in EXPORTERS:
        for variant in VARIANTS:
            with tempfile.TemporaryDirectory(prefix='aau-source-index-') as temporary:
                request, delivery = build_inputs(Path(temporary), exporter, variant)
                raw = rendered(request)
                name = f'{exporter}-{variant}'
                report = create_index(raw, delivery, directory / name, request_sha256=digest(raw))
                if verify_index(directory / name, request_sha256=digest(raw)) != report:
                    raise ValueError('synthetic source-index replay mismatch')
                commands.append(f'aau evidence-index verify {name} --request-sha256 {digest(raw)}  # exit {report["exit_code"]}')
    return commands
