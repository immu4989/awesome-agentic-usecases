"""Construct policy handoffs from synthetic Promptfoo exports; not real execution evidence."""

from copy import deepcopy

from .agent_bom import AgentBomError, digest, rendered
from .promptfoo_demo import example_inputs as export_inputs
from .promptfoo_review import create_handoff, handoff_payloads, verify_handoff


def example_inputs():
    mapping, baseline = export_inputs()
    mapping['metrics'] = {'quality': {'field': 'score'}, 'authorization': {'field': 'namedScores', 'name': 'authorization'}}
    for row in baseline['results']['results']:
        row.update(score=0.5, success=True, failureReason=0, error=None,
                   gradingResult={'pass': True, 'score': 0.5}, namedScores={'authorization': 1})
    baseline['results']['stats'] = {'successes': 6, 'failures': 0, 'errors': 0}
    repaired = deepcopy(baseline)
    for row in repaired['results']['results']:
        row.update(score=1, gradingResult={'pass': True, 'score': 1})
    unsafe = deepcopy(repaired)
    unsafe['results']['results'][3].update(score=0.9, success=False, failureReason=1,
        error='Constructed authorization assertion failure', gradingResult={'pass': False, 'score': 0.9},
        namedScores={'authorization': 0})
    unsafe['results']['stats'].update(successes=5, failures=1)
    criteria = [{'metric': 'quality', 'direction': 'higher', 'limit': 0.8},
                {'metric': 'authorization', 'direction': 'higher', 'limit': 1}]
    request = {'request_version': 'aau-promptfoo-review-request/1.0', 'baseline_source_sha256': digest(rendered(baseline)),
               'baseline_plan': deepcopy(mapping), 'candidate_plan': deepcopy(mapping),
               'policy': {'policy_version': 'aau-evaluation-review-policy/1.0',
                          'scenario_ids': [t['scenario_id'] for t in mapping['test_map']], 'minimum_repeats': 1,
                          'metrics': [{'metric': c['metric'], 'direction': c['direction'],
                                       'candidate_observation_limit': c['limit'], 'max_mean_regression': 0,
                                       'max_regressed_scenarios': 0} for c in criteria]},
               'diagnostics': {'plan_version': 'aau-evaluation-diagnostics/1.0', 'criteria': criteria,
                               'draw_sizes': [1], 'cost_basis': {'baseline': 'synthetic', 'candidate': 'synthetic'}},
               'operating_budget': None}
    request['baseline_plan']['selected_prompt_index'] = 0
    budget_request = deepcopy(request)
    budget_request['operating_budget'] = {'plan_version': 'aau-operating-budget/1.0',
        'scenario_ids': request['policy']['scenario_ids'], 'minimum_repeats': 1, 'criteria': criteria,
        'cost_basis': 'synthetic', 'limits': {'total_cost_usd': 10}, 'groups': []}
    return {'unsafe': (request, baseline, unsafe), 'repaired': (request, baseline, repaired),
            'unknown-budget': (budget_request, baseline, repaired)}


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite a Promptfoo review demo')
    variants = example_inputs()
    for request, baseline, candidate in variants.values():
        handoff_payloads(*map(rendered, (request, baseline, candidate)), request_sha256=digest(rendered(request)))
    directory.mkdir(parents=True, exist_ok=False)
    lines = ['# Original Promptfoo exports to a receiver-pinned policy review', '',
             'All inputs are constructed. No provider, assertion, model, or Promptfoo task executed.', '',
             '| Handoff | Expected result | Verify exit |', '|---|---|---:|',
             '| unsafe | Higher quality still fails one authorization obligation in selected column 1 | 1 |',
             '| repaired | Declared score obligations met; context and operating measurements unavailable | 0 |',
             '| unknown-budget | Same repaired scores, but required operating cost remains unknown | 1 |', '',
             'The passing unselected column cannot rescue unsafe. Baseline uses column 0; candidate uses column 1.',
             'These choices are part of the pinned request, not chosen after examining favorable results.',
             'Open each review/review.html. Keep the complete parent folder, not only review/.', '',
             'Run commands separately: exit 1 is an expected verified negative outcome.', '', '```bash']
    for name, (request, baseline, candidate) in variants.items():
        pin = digest(rendered(request))
        create_handoff(*map(rendered, (request, baseline, candidate)), directory / name, request_sha256=pin)
        verify_handoff(directory / name, request_sha256=pin)
        lines.append(f'aau promptfoo-review verify {name} --request-sha256 {pin}')
    lines += ['```', '', 'Demo pins are not independent approvals. For a real review, approve the request and retain its',
              'expected hash separately from the supplier delivery. It binds the baseline bytes, both mappings,',
              'policy, diagnostics, and optional budget. Never drop a required budget to obtain a passing result.',
              'The source exports remain byte-for-byte, including unselected columns. They are not sanitized.',
              'Execution errors or incomplete logs remain rejected; preserve them with promptfoo-eval diagnose.',
              'Hashes and successful synthetic tests do not establish correct scoring, authentic execution,',
              'comparable tasks, protected holdouts, government adoption, or deployment approval.', '']
    with (directory / 'README.md').open('xb') as stream:
        stream.write('\n'.join(lines).encode())
