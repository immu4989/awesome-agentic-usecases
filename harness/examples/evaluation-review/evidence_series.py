"""Construct offline evidence histories; no production monitoring or recovery claim."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import digest, rendered, write_json
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_pack import create_pack
from aau_harness.evidence_series import review_series


def create_example(directory):
    policy, baseline, repaired, diagnostics = demo_inputs()
    budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': policy['scenario_ids'], 'minimum_repeats': 4,
              'criteria': diagnostics['criteria'], 'cost_basis': 'synthetic', 'groups': [], 'limits': {'total_cost_usd': 2}}
    # Both controls are assembled before delivery from known synthetic inputs; this is not independent approval.
    plan = {'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ['before', 'during', 'after']}
    request = {'request_version': 'aau-evidence-intake-request/1.0', 'profile': 'evaluation-review',
               'pack_version': 'aau-evaluation-review-pack/3.0', 'input_format': 'recordings',
               'pinned_inputs': {role: digest(rendered(value)) for role, value in (
                   ('policy', policy), ('baseline', baseline), ('diagnostics', diagnostics), ('operating_budget', budget))}}
    plan_raw, request_raw = rendered(plan), rendered(request)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(plan, directory / 'plan.json')
    write_json(request, directory / 'request.json')
    expected = {'all-met': ('series_constraints_met', 0), 'later-met': ('series_constraints_not_met', 1),
                'missing': ('series_evidence_missing', 1), 'invalid': ('series_not_fully_verified', 2),
                'changed-policy': ('series_constraints_not_met', 1)}
    for name, outcome in expected.items():
        root = directory / name
        root.mkdir()
        for checkpoint in plan['checkpoint_ids']:
            if name == 'missing' and checkpoint == 'during':
                continue
            supplied_policy = deepcopy(policy)
            candidate = baseline if checkpoint == 'during' and name in ('later-met', 'changed-policy') else repaired
            if checkpoint == 'during' and name == 'changed-policy':
                supplied_policy['metrics'][1]['candidate_observation_limit'] = 1
            create_pack(supplied_policy, baseline, candidate, root / checkpoint,
                        recordings=True, diagnostics=diagnostics, operating_budget=budget)
            if name == 'invalid' and checkpoint == 'during':
                (root / checkpoint / 'review.json').write_bytes(b'{}')  # Deliberate invalid-evidence negative control.
        result = review_series(plan_raw, request_raw, root, plan_sha256=digest(plan_raw), request_sha256=digest(request_raw))
        if (result['status'], result['exit_code']) != outcome or result['latest_checkpoint']['status'] != 'request_constraints_met':
            raise RuntimeError('synthetic evidence-series outcome differs from its contract')
        write_json(result, directory / f'{name}-series.json')
    commands = '\n'.join(
        f'aau review-series plan.json request.json {name} --plan-sha256 {digest(plan_raw)} '
        f'--request-sha256 {digest(request_raw)} --verify {name}-series.json  # expected exit {outcome[1]}'
        for name, outcome in expected.items())
    guide = f'''AAU synthetic evidence history walkthrough

Every latest checkpoint passes. Only all-met has no earlier issue in the declared history.
later-met retains the earlier policy failure; missing retains an absent checkpoint; invalid
retains an unverifiable pack; changed-policy retains a passing but substituted policy.
All examples use the SAME pinned baseline, diagnostic plan, budget, and expected policy.

From this directory, using the matching trusted harness:

{commands}

These hashes are synthetic plumbing, NOT independent approval. In production, separately review
and protect both the ordered plan and the common request. Candidate-controlled files must not
define their own expected approval hashes. Changed plans or requirements need independent review.
The declared scope is not an append-only log and cannot prove absence of omitted external events.

The invalid example deliberately contains an altered review.json. Exit 2 retains a diagnostic
series report but does not verify that checkpoint. Unexpected root members or invalid control
files are rejected without a new report. Reports and controls stay outside each history folder.

Pack inventories repeat in these constructed examples. Identical retained bytes do not prove
fresh executions; different bytes do not prove independence either. Order is explicitly declared,
not measured time, so no freshness, uptime, duration, or time-to-repair can be inferred. This is
not a scheduler, production monitor, automated incident closure, or recovery/deployment approval.
No real service, model, or adapter was executed. A later pass never erases earlier evidence.
Keep all controls, reports, and complete checkpoint packs; inspect sensitive data before sharing.
This guide is written last, after expected outcomes have been checked.
'''
    (directory / 'README.txt').write_text(guide, encoding='utf-8')
    print('Created five synthetic evidence histories; every latest checkpoint passes, but four histories retain issues.')
    return expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
