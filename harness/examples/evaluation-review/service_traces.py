"""Synthetic service traces to recomputed scores and complete policy/budget dossiers."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import load_json, write_json
from aau_harness.eval_pack import create_pack, verify_pack
from aau_harness.eval_service_traces import create_service_trace_pack, verify_service_trace_pack


ROOT = Path(__file__).resolve().parents[3]


def example_inputs():
    fixture = ROOT / 'public-value-review/examples'
    existing_suite, existing_traces = [load_json(fixture / f'{name}.json') for name in ('suite', 'traces')]
    standard_contract = next(case['contract'] for case in existing_suite['cases'] if case['case_id'] == 'recourse-not-required')
    standard_trace = next(row['trace'] for row in existing_traces['observations'] if row['case_id'] == 'recourse-not-required')
    suite = {'suite_version': 'aau-public-value-suite/1.0', 'cases': [
        {'case_id': 'assisted-service', 'contract': load_json(fixture / 'contract.json')},
        {'case_id': 'standard-service', 'contract': standard_contract}]}
    plan = {'plan_version': 'aau-service-trace-import/1.0', 'source_label': 'Synthetic service trace lesson', 'n_repeats': 2}
    baseline = {'trace_version': 'aau-public-value-traces/1.1', 'observations': [
        {'case_id': case_id, 'repeat': repeat, 'trace': deepcopy(trace), 'cost_usd': .1, 'latency_s': 2, 'n_api_calls': 1}
        for case_id, trace in [('assisted-service', load_json(fixture / 'exact-trace.json')), ('standard-service', standard_trace)]
        for repeat in range(2)]}
    burden = deepcopy(baseline)
    burden['observations'][0]['trace'] = load_json(fixture / 'burden-trace.json')
    policy = {'policy_version': 'aau-evaluation-review-policy/1.0',
              'scenario_ids': ['assisted-service', 'standard-service'], 'minimum_repeats': 2,
              'metrics': [{'metric': metric, 'direction': 'higher', 'candidate_observation_limit': 1,
                           'max_mean_regression': 0, 'max_regressed_scenarios': 0}
                          for metric in ('service_completion', 'public_value_exact')]}
    criteria = [{'metric': 'public_value_exact', 'direction': 'higher', 'limit': 1}]
    diagnostics = {'plan_version': 'aau-evaluation-diagnostics/1.0', 'criteria': criteria, 'draw_sizes': [1, 2],
                   'cost_basis': {'baseline': 'synthetic', 'candidate': 'synthetic'}}
    budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': policy['scenario_ids'], 'minimum_repeats': 2,
              'criteria': criteria, 'cost_basis': 'synthetic', 'groups': [],
              'limits': {'cost_per_passing_attempt_usd': .12, 'p95_latency_s': 3}}
    return plan, suite, baseline, burden, policy, diagnostics, budget


def create_example(directory):
    plan, suite, baseline, burden, policy, diagnostics, budget = example_inputs()
    directory.mkdir(parents=True, exist_ok=False)
    for name, traces in [('baseline', baseline), ('burden', burden), ('repaired', baseline)]:
        report = create_service_trace_pack({**plan, 'source_label': f'Synthetic {name} service traces'},
                                           suite, traces, directory / name)
        expected = 'evidence_failed' if name == 'burden' else 'evidence_passed'
        if report['status'] != expected:
            raise RuntimeError('synthetic service scoring changed')
    base = load_json(directory / 'baseline/evaluation.json')
    for name in ('burden', 'repaired'):
        candidate = load_json(directory / name / 'evaluation.json')
        if candidate['metric_means']['service_completion'] != 1:
            raise RuntimeError('synthetic completion contrast changed')
        review = directory / f'{name}-review'
        create_pack(policy, base, candidate, review, diagnostics=diagnostics, operating_budget=budget)
        gate = verify_pack(review, require_diagnostics=True, require_budget=True)
        expected = 'constraints_not_met' if name == 'burden' else 'constraints_met'
        if gate['status'] != expected:
            raise RuntimeError('synthetic service policy/budget outcome changed')
        verify_service_trace_pack(directory / 'baseline', evaluation_path=review / 'baseline.json')
        verify_service_trace_pack(directory / name, evaluation_path=review / 'candidate.json')
    for name, value in [('policy', policy), ('diagnostics', diagnostics), ('budget', budget)]:
        write_json(value, directory / f'{name}.json')
    (directory / 'README.txt').write_text('''Synthetic service trace scoring lesson — no real people, service actions, or billing.

All versions complete their declared terminal action. The burden candidate asks
for already-held identity twice and an out-of-contract password, misses the
required evidence, uses the wrong channel, and omits required recourse in one
of four observations. Completion is 100%, but public_value_exact is 75%.
The same synthetic $0.40 across all attempts becomes about $0.133 per jointly
passing observation, above the illustrative $0.12 limit. The repaired fixture
is constructed, not an observed repair or demonstrated public benefit.

Open burden-review/review.html and repaired-review/review.html. Retain the
source-scoring folders with them. Run these commands separately: a valid
failed-scoring pack or failed gate intentionally exits 1, not 0.

  aau service-trace-eval verify baseline --evaluation burden-review/baseline.json
  aau service-trace-eval verify burden --evaluation burden-review/candidate.json
  aau evaluation-pack verify burden-review --require-diagnostics --require-budget
  aau service-trace-eval verify repaired --evaluation repaired-review/candidate.json
  aau evaluation-pack verify repaired-review --require-diagnostics --require-budget

Expected exit codes: 0, 1, 1, 0, 0. Exit 2 means invalid evidence or failed
verification. Original contract and trace JSON values are retained; scores
are computed by the current first-party scorer. Inputs are not authenticated
and no legal requirements, actual protections, or deployment approval are
inferred. Missing operating measurements stay unknown. Required-only counts
distinguish a satisfied inapplicable obligation from a performed protection.
Review and independently approve your own contracts and scoring definitions;
do not copy these synthetic thresholds or claim this fixture measures people.
''', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
