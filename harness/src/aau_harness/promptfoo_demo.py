"""No-key native-format example: assertion failures are evidence, execution errors are not scores."""

from copy import deepcopy

from .agent_bom import AgentBomError, digest, rendered
from .eval_promptfoo import create_promptfoo_pack, promptfoo_payloads, verify_promptfoo_pack


def example_inputs():
    plan = {'plan_version': 'aau-promptfoo-observation-plan/1.0',
            'source_label': 'Constructed routing example; not a Promptfoo execution',
            'test_map': [{'test_index': i, 'scenario_id': name} for i, name in enumerate(('routing', 'delegation', 'unmeasured'))],
            'columns': [{'prompt_index': i, 'prompt_id': 'constructed-prompt', 'provider_id': f'constructed-provider-{i}'} for i in range(2)],
            'selected_prompt_index': 1, 'metrics': {'quality': {'field': 'score'}, 'passed': {'field': 'success'},
                                                  'authorization': {'field': 'namedScores', 'name': 'authorization'}}}
    rows = []
    for test in range(3):
        for column in range(2):
            failed = test == 1 and column == 1
            score = 0.9 if failed else 1
            rows.append({'id': f'constructed-{test}-{column}', 'testIdx': test, 'promptIdx': column,
                         'promptId': 'constructed-prompt', 'provider': {'id': f'constructed-provider-{column}'},
                         'failureReason': int(failed), 'success': not failed, 'score': score,
                         'error': 'Constructed authorization assertion failure' if failed else None,
                         'gradingResult': {'pass': not failed, 'score': score},
                         'namedScores': {'authorization': None if test == 2 and column == 1 else int(not failed)},
                         'response': {'output': 'Synthetic result; no model call'}, 'vars': {}})
    source = {'evalId': 'constructed-no-execution', 'shareableUrl': None,
              'metadata': {'promptfooVersion': 'constructed-not-an-exporter-run'},
              'config': {'evaluateOptions': {'repeat': 1}}, 'results': {'version': 3,
                  'prompts': [{'id': c['prompt_id'], 'provider': c['provider_id']} for c in plan['columns']],
                  'results': rows, 'stats': {'successes': 5, 'failures': 1, 'errors': 0}}}
    return plan, source


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite a Promptfoo demo destination')
    plan, source = example_inputs()
    plan_raw, source_raw = rendered(plan), rendered(source)
    pin = digest(plan_raw)
    promptfoo_payloads(plan_raw, source_raw, plan_sha256=pin)
    missing = deepcopy(source)
    missing['results']['results'].pop()
    error = deepcopy(source)
    error['results']['results'][0].update(failureReason=2, success=False, error='Constructed provider failure')
    error['results']['stats'].update(successes=4, errors=1)
    incomplete = deepcopy(error)
    incomplete['results']['results'].pop()
    incomplete['results']['results'].append(deepcopy(incomplete['results']['results'][1]))
    incomplete['results']['results'].append({'testIdx': 99, 'promptIdx': 0, 'failureReason': 2, 'success': False})
    guide = f'''# A failed assertion is still a result

This is a constructed Promptfoo-format example, not a Promptfoo or model execution.
Six rows cover three tests and two prompt/provider columns. Column 1 is explicitly selected.
Its average quality is high, but one authorization score is zero and another is unknown.
The passing column 0 cannot replace column 1 just because its scores look better.

Run from this folder with the trusted harness. The following pin is for this demo only:

```bash
aau promptfoo-eval verify converted --plan-sha256 {pin}
aau promptfoo-eval create plan.json source.json --plan-sha256 {pin} --out another-conversion
# Both commands below must exit 2; use a new destination each time.
aau promptfoo-eval create plan.json missing-row.json --plan-sha256 {pin} --out rejected-missing
aau promptfoo-eval create plan.json execution-error.json --plan-sha256 {pin} --out rejected-error
# Both diagnostic commands exit 1: a verified packet with findings, not invalid input.
aau promptfoo-eval verify-diagnostic diagnostic --plan-sha256 {pin}
aau promptfoo-eval diagnose plan.json incomplete-source.json --plan-sha256 {pin} --out another-diagnostic
```

Inspect converted/conversion.json for row pointers, selected/unprojected columns, and metric coverage.
Inspect converted/evaluation.json: authorization covers only two of three projected observations.
The original assertion failure is retained even though its error field contains text. The separate
execution-error source is rejected even though its error occurs in the unselected column.
No unknown score becomes zero, no aggregate score is trusted, and no provider/config code runs.
Exit 0 means faithful conversion, not that supplied scores meet a policy or justify deployment.

The six-file conversion preserves full raw source bytes. It is not a sanitized sharing artifact.
For a real review, approve the mappings independently and retain that plan hash outside the delivery.
Use the existing evaluation-review workflow for policy checks; verification with --evaluation can
check that a downstream evaluation.json still matches this converted source. Context and operating
measurements remain unavailable. Hashes do not authenticate the log or establish reference correctness.

Open diagnostic/review.html for a separate deliberately incomplete delivery: one missing pair,
one duplicate pair, four unique pairs, and an outside-plan row. An execution error in column 0
coexists with recorded scores. All seven supplied rows remain visible; none is selected as a
replacement attempt. Stale summary counts remain findings. This packet contains no evaluation.json.
Diagnostic exit codes are 0 for no findings (not quality acceptance), 1 for retained review findings,
and 2 for invalid inputs or failed verification. Original data is retained, not sanitized.
'''
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in {'plan.json': plan_raw, 'source.json': source_raw, 'missing-row.json': rendered(missing),
                      'execution-error.json': rendered(error), 'incomplete-source.json': rendered(incomplete),
                      'README.md': guide.encode()}.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
    create_promptfoo_pack(plan_raw, source_raw, directory / 'converted', plan_sha256=pin)
    verify_promptfoo_pack(directory / 'converted', plan_sha256=pin)
    from .promptfoo_diagnostic import create_diagnostic, verify_diagnostic
    create_diagnostic(plan_raw, rendered(incomplete), directory / 'diagnostic', plan_sha256=pin)
    verify_diagnostic(directory / 'diagnostic', plan_sha256=pin)
