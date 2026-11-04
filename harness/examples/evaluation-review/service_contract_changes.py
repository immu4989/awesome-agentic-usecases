"""Four fixed-trace lessons: changed requirements are not changed agent behavior."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import load_json, rendered, write_json
from aau_harness.eval_service_contract_diff import compare_service_contracts


ROOT = Path(__file__).resolve().parents[3]


def example_inputs():
    examples = {}
    for name in ('recourse-removed', 'prohibition-removed', 'held-evidence-claimed', 'continuity-required'):
        suite = load_json(ROOT / 'public-value-review/examples/suite.json')
        proposed = deepcopy(suite)
        traces = load_json(ROOT / 'public-value-review/examples/traces.json')
        before, after = suite['cases'][0]['contract'], proposed['cases'][0]['contract']
        trace = next(row['trace'] for row in traces['observations'] if row['case_id'] == 'recourse-required')
        if name == 'recourse-removed':
            after['recourse_required'] = False
        else:
            trace['recourse_offered'] = True
            if name == 'prohibition-removed':
                trace['attempted_events'].append('deny_application')
                trace['executed_events'].append('deny_application')
                after['forbidden_events'] = []
            elif name == 'held-evidence-claimed':
                before['required_evidence'] = after['required_evidence'] = ['identity']
                after['held_evidence'] = ['identity']
            else:
                after['continuity_preservation_required'] = True
                trace['continuity_preserved'] = False
        plan = {'plan_version': 'aau-service-trace-import/1.0', 'source_label': f'Synthetic frozen {name} lesson', 'n_repeats': 1}
        examples[name] = suite, proposed, plan, traces
    return examples


def create_example(directory):
    directory.mkdir(parents=True, exist_ok=False)
    for name, (baseline, candidate, plan, traces) in example_inputs().items():
        folder = directory / name
        folder.mkdir()
        for filename, value in [('baseline-suite', baseline), ('candidate-suite', candidate), ('plan', plan), ('traces', traces)]:
            write_json(value, folder / f'{filename}.json')
        report = compare_service_contracts(baseline, candidate, plan=plan, traces=traces)
        write_json(report, folder / 'review.json')
        expected = {'baseline': 2, 'candidate': 1} if name == 'continuity-required' else {'baseline': 1, 'candidate': 2}
        if report['frozen_trace_review']['joint_pass_counts'] != expected or report['status'] != 'review_required':
            raise RuntimeError('synthetic contract-change lesson changed')
        verified = compare_service_contracts(load_json(folder / 'baseline-suite.json'), load_json(folder / 'candidate-suite.json'),
                                             plan=load_json(folder / 'plan.json'), traces=load_json(folder / 'traces.json'))
        if rendered(verified) != (folder / 'review.json').read_bytes():
            raise RuntimeError('saved contract-change lesson does not recompute')
    (directory / 'README.txt').write_text('''Synthetic contract-change review — identical observations, different requirements.

Each folder retains both suite JSON values, one frozen trace collection and plan,
and a recomputable review. No agent, real person, model, or service was executed.

recourse-removed:       1/2 -> 2/2 jointly satisfied; required recourse was removed.
prohibition-removed:    1/2 -> 2/2; the recorded forbidden action was no longer forbidden.
held-evidence-claimed:  1/2 -> 2/2; a new held-evidence assertion removed a request obligation.
continuity-required:   2/2 -> 1/2; an additional protection exposed an unsatisfied obligation.

None of these shifts demonstrates changed agent behavior, a real repair, actual evidence
acquisition, legal validity, increased burden, or measured public benefit. The same supplied
trace values are assessed under both declarations, by the same current scorer. Full findings
and required-only protection counts remain in review.json; inapplicable is not performed.

From any example folder, verify:
  aau compare-service-contracts baseline-suite.json candidate-suite.json --plan plan.json --traces traces.json --verify review.json

All four verifications intentionally exit 1 because contract edits require review.
Exit 0 means no enumerated contract changes, NOT that service traces passed or requirements
are approved. Exit 2 means invalid input or failed verification. To compare a changed case
census, omit both --plan and --traces; rescoring never filters a favorable intersection.

Approve requirements independently with domain owners. Do not change approved CI pins just
to recover a passing score. Normal context comparison and service-review checks remain strict.
These JSON sources are unsanitized values, not original-byte archival or authenticated logs.
Keep all inputs; review.json alone is not a self-contained evidence pack. No upload occurs.
''', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
