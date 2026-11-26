"""Fixed synthetic label provenance and grader-audit handoffs; no human participants or model calls."""

import json
from pathlib import Path
import tempfile

from .agent_bom import digest, rendered
from .evidence_index import create_index, verify_index
from .grader_pack import create_grader_pack
from .reference_demo import example_inputs
from .reference_review import create_reference_pack, reference_payloads


VARIANTS = ('linked-false-passes', 'missing-provenance', 'substituted-reference', 'changed-grader-plan')


def build_inputs(directory, variant):
    if variant not in VARIANTS:
        raise ValueError('unknown synthetic grader handoff')
    plan, ratings, adjudications = map(rendered, example_inputs())
    _, source = reference_payloads(plan, ratings, adjudications, plan_sha256=digest(plan))
    grader_plan = source['grader-plan.json']
    reference = source['reference.json']
    if variant == 'substituted-reference':
        # Valid audit against different, more favorable labels. It must not bind to the delivered panel.
        changed = json.loads(reference)
        for row in changed['rows']:
            row['verdict'] = 'pass'
        reference = rendered(changed)
        changed_plan = json.loads(grader_plan)
        changed_plan['reference_sha256'] = digest(reference)
        grader_plan = rendered(changed_plan)
    elif variant == 'changed-grader-plan':
        # Same labels, different declared partition: label equality cannot prove equal study controls.
        changed_plan = json.loads(grader_plan)
        changed_plan['items'][1]['split'] = 'calibration'
        grader_plan = rendered(changed_plan)
    judgments = {'format_version': 'aau-grader-judgments/1.0',
                 'rubric_sha256': json.loads(reference)['rubric_sha256'], 'grader_id': 'synthetic-all-pass',
                 'rows': [{**row, 'verdict': 'pass'} for row in json.loads(reference)['rows']]}
    delivery = directory / 'delivery'
    delivery.mkdir(parents=True)
    if variant != 'missing-provenance':
        create_reference_pack(plan, ratings, adjudications, delivery / 'panel', plan_sha256=digest(plan))
    create_grader_pack(grader_plan, reference, rendered(judgments), delivery / 'grader',
                      plan_sha256=digest(grader_plan))
    request = {'request_version': 'aau-evidence-index-request/1.0',
               'purpose': 'Synthetic reference-to-grader handoff; no authenticated human judgments or deployment approval.',
               'items': [{'item_id': 'panel', 'profile': 'reference-review',
                          'purpose': 'Retain original disagreement, missing ratings, and explicit adjudication.',
                          'controls': {'plan_sha256': digest(plan)}},
                         {'item_id': 'grader', 'profile': 'grader-review',
                          'purpose': 'Retain false passes and unresolved references, not just a favorable summary.',
                          'controls': {'plan_sha256': digest(grader_plan)}}],
               'bindings': [{'left': {'item_id': 'panel', 'role': left},
                             'right': {'item_id': 'grader', 'role': right}}
                            for left, right in (('reference', 'reference'), ('grader-plan', 'plan'))]}
    return request, delivery


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('grader demo refuses existing output')
    directory.mkdir(parents=True, exist_ok=False)
    commands = []
    for variant in VARIANTS:
        with tempfile.TemporaryDirectory(prefix='aau-grader-handoff-') as temporary:
            request, delivery = build_inputs(Path(temporary), variant)
            raw = rendered(request)
            report = create_index(raw, delivery, directory / variant, request_sha256=digest(raw))
            if verify_index(directory / variant, request_sha256=digest(raw)) != report:
                raise ValueError('synthetic grader handoff does not replay')
            commands.append(f'aau evidence-index verify {variant} --request-sha256 {digest(raw)}  # exit {report["exit_code"]}')
    guide = '''# Which labels did the grader audit actually use?

All ratings, identities, judgments, evidence fingerprints, and examples are synthetic. No human study,
model call, or grader execution took place. Keep outputs local; they do not establish approval.

- linked-false-passes: both packets and both byte bindings verify (exit 0), yet the all-pass grader
  has two false passes in validation. Three of five validation reference labels remain unresolved.
  Exit 0 verifies delivery, not grader quality or truth. Original panel disagreements remain visible.
- missing-provenance: the grader packet verifies, but the requested panel packet is missing (exit 1).
  Merely supplying reference labels cannot replace their separately requested provenance.
- substituted-reference: both packets individually verify, but the grader used different all-pass
  labels. Both cross-packet bindings fail (exit 1). Do not accept a favorable unrelated audit.
- changed-grader-plan: identical labels, but a validation item was moved into calibration in a
  separately valid grader plan. The reference binding matches; the plan binding fails (exit 1).

Open the generated top-level review.html only after inspecting the delivery. Native findings are in
report.json; original bytes are retained under evidence/. No claims of identity, expertise,
independence, genuine execution, label correctness, or government certification follow these checks.

Replay from this directory with the matching trusted harness. Pins here are example-only; real
receiver controls and their hashes must be reviewed and retained independently of supplier evidence.

```bash
''' + '\n'.join(commands) + '\n```\n'
    (directory / 'README.md').write_text(guide, encoding='utf-8')
