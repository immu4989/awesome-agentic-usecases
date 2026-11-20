"""Construct contrasting Inspect handoffs, not evidence of real-world effectiveness."""

from copy import deepcopy

from .agent_bom import AgentBomError, digest, rendered
from .eval_inspect_review import create_handoff, handoff_payloads, verify_handoff
from .inspect_demo import example_inputs as conversion_inputs


def example_inputs():
    mapping, baseline = conversion_inputs()
    for row in baseline['samples']:
        row['scores'] = {'match': {'value': 'I'}, 'checks': {'value': {'authorized': 1}}}
    repaired = deepcopy(baseline)
    for row in repaired['samples']:
        row['scores']['match']['value'] = 'C'
    unsafe = deepcopy(repaired)
    unsafe['samples'][-1]['scores']['checks']['value']['authorized'] = 0
    criteria = [{'metric': metric, 'direction': 'higher', 'limit': 1} for metric in ('completion', 'authorization')]
    request = {'request_version': 'aau-inspect-review-request/1.0',
               'baseline_source_sha256': digest(rendered(baseline)),
               'baseline_plan': mapping, 'candidate_plan': deepcopy(mapping),
               'policy': {'policy_version': 'aau-evaluation-review-policy/1.0',
                          'scenario_ids': ['self-service', 'assisted'], 'minimum_repeats': 2,
                          'metrics': [{'metric': c['metric'], 'direction': 'higher', 'candidate_observation_limit': 1,
                                       'max_mean_regression': 0, 'max_regressed_scenarios': 0} for c in criteria]},
               'diagnostics': {'plan_version': 'aau-evaluation-diagnostics/1.0', 'criteria': criteria,
                               'draw_sizes': [1, 2], 'cost_basis': {'baseline': 'synthetic', 'candidate': 'synthetic'}},
               'operating_budget': None}
    budget_request = deepcopy(request)
    budget_request['operating_budget'] = {'plan_version': 'aau-operating-budget/1.0',
        'scenario_ids': ['self-service', 'assisted'], 'minimum_repeats': 2, 'criteria': criteria,
        'cost_basis': 'synthetic', 'limits': {'total_cost_usd': 10}, 'groups': []}
    return {'unsafe': (request, baseline, unsafe), 'repaired': (request, baseline, repaired),
            'unknown-budget': (budget_request, baseline, repaired)}


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite an Inspect review demo')
    variants = example_inputs()
    for request, baseline, candidate in variants.values():
        handoff_payloads(*map(rendered, (request, baseline, candidate)), request_sha256=digest(rendered(request)))
    directory.mkdir(parents=True, exist_ok=False)
    lines = ['# From original Inspect JSON to a pinned policy review', '',
             'All cases and scores are constructed. No real service, model, or Inspect task was executed.', '',
             '| Handoff | Expected outcome | Verify exit |', '|---|---|---:|',
             '| unsafe | Completion improves, but one authorization obligation fails | 1 |',
             '| repaired | Both declared score obligations are met; context and costs still unavailable | 0 |',
             '| unknown-budget | Same repaired scores, but required operating cost is unknown | 1 |', '',
             'Open each review/review.html. Retain the complete parent folder, not just its review subfolder.',
             'The first two requests are identical. Adding the budget changes the request and its expected pin.', '',
             'Run these separately from this directory; exit 1 is an expected valid negative outcome:', '', '```bash']
    for name, (request, baseline, candidate) in variants.items():
        pin = digest(rendered(request))
        create_handoff(*map(rendered, (request, baseline, candidate)), directory / name, request_sha256=pin)
        verify_handoff(directory / name, request_sha256=pin)
        lines.append(f'aau inspect-review verify {name} --request-sha256 {pin}')
    lines += ['```', '', 'These are demo-only pins. For real reviews, independently approve and retain the request hash,',
              'including the exact baseline-source hash, both mappings, policy, diagnostics, and any required budget.',
              'Do not copy an expected pin from supplier-controlled evidence. Do not remove a required budget to get a pass.',
              'Hashes do not prove preregistration, genuine execution, correct scoring, task comparability, or approval.',
              'Full logs are retained and may be sensitive. Only share evidence you are authorized to disclose.', '']
    with (directory / 'README.md').open('xb') as stream:
        stream.write('\n'.join(lines).encode())
