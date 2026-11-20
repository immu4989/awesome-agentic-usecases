from copy import deepcopy
from itertools import product
import json
import math
import socket
import subprocess

import pytest

from aau_harness import eval_candidate_bounds as module
from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.candidate_bounds_demo import example_inputs
from aau_harness.catalog_cli import main
from aau_harness.eval_failure_bound import upper_failure_bound


def review(plan, sources):
    raw = rendered(plan)
    return module.candidate_payloads(raw, sources, plan_sha256=digest(raw))[0]


def test_two_candidate_family_exposes_single_candidate_confidence_trap():
    plan, sources = example_inputs()
    result = review(plan, sources)
    assert result == review(plan, sources)
    assert result['method']['family_size'] == 2
    assert result['method']['tail_probability_per_cell'] == pytest.approx(.025)
    row = result['candidates'][0]['scopes'][0]
    assert row['scenario_count'] == 60
    assert result['candidates'][0]['observation_count'] == 240
    assert row['one_sided_upper_failure_bound'] == pytest.approx(1 - .025 ** (1 / 60))
    assert row['status'] == 'conditional_bound_exceeds_limit'
    assert upper_failure_bound(0, 60, .05) < .05 < row['one_sided_upper_failure_bound']
    assert result['status'] == 'conditional_candidate_family_diagnostic'


def test_missing_candidates_never_reallocate_or_fabricate_zero_counts():
    plan, sources = example_inputs()
    partial = review(plan, {'candidate-a': sources['candidate-a']})
    complete = review(plan, sources)
    assert partial['method'] == complete['method']
    assert partial['candidates'][0] == complete['candidates'][0]
    missing = partial['candidates'][1]
    assert missing['status'] == 'not_observed'
    assert missing['source_file_sha256'] is None and missing['source_audit'] is None
    assert missing['scenario_outcomes'] == [] and missing['observation_count'] is None
    row = missing['scopes'][0]
    assert row['scenario_count'] is None and row['failed_scenario_count'] is None
    assert row['observed_bundle_failure_fraction'] is None and row['one_sided_upper_failure_bound'] is None
    empty = review(plan, {})
    assert empty['method']['family_size'] == partial['method']['family_size']
    assert empty['method']['tail_probability_per_cell'] == partial['method']['tail_probability_per_cell']
    assert not empty['method']['bound_applied']
    assert empty['missing_candidate_count'] == 2


def test_fixed_benchmark_withholds_all_population_bounds():
    plan, sources = example_inputs()
    plan['sampling_design'] = 'fixed_benchmark'
    result = review(plan, sources)
    assert result['status'] == 'population_inference_withheld'
    assert not result['method']['bound_applied']
    for candidate in result['candidates']:
        assert candidate['scopes'][0]['one_sided_upper_failure_bound'] is None
        assert candidate['scopes'][0]['observed_bundle_failure_fraction'] == 0


def test_early_failed_repeat_and_summary_disagreement_remain_visible():
    plan, sources = example_inputs()
    source = json.loads(sources['candidate-b'])
    source['results'][0]['metrics']['unauthorized'] = 1
    source['results'][1]['metrics']['unauthorized'] = 1
    sources['candidate-b'] = rendered(source)
    result = review(plan, sources)
    candidate = result['candidates'][1]
    assert candidate['source_audit']['status'] == 'inconsistent'
    assert candidate['scopes'][0]['failed_scenario_count'] == 1
    assert len(candidate['scenario_outcomes'][0]['failed_repeats']) == 2
    assert candidate['scopes'][0]['one_sided_upper_failure_bound'] > result['candidates'][0]['scopes'][0]['one_sided_upper_failure_bound']


def test_overlapping_groups_have_full_candidate_by_scope_allocation():
    plan, sources = example_inputs()
    plan['groups'] = [{'group_id': name, 'scenario_ids': ids, 'maximum_failure_probability': .05}
                      for name, ids in [('first', plan['scenario_ids'][:10]), ('overlap', plan['scenario_ids'][5:15])]]
    result = review(plan, {'candidate-a': sources['candidate-a']})
    assert result['method']['family_size'] == 6
    assert result['method']['tail_probability_per_cell'] == pytest.approx(.05 / 6)
    assert [r['scenario_count'] for r in result['candidates'][0]['scopes']] == [60, 10, 10]
    assert all(r['scenario_count'] is None for r in result['candidates'][1]['scopes'])


@pytest.mark.parametrize('p,rho,alpha', list(product((.2, .5, .8, .95), (0, .5, 1), (.05, .2))))
def test_exact_small_family_coverage_with_correlated_candidates_and_overlapping_scopes(p, rho, alpha):
    # Independent outcome enumeration: two candidate outcomes per IID case, correlated within each case.
    # Overall (4 cases) and first-two subgroup overlap. Neither candidate independence nor group independence is assumed.
    probability = {(1, 1): rho * p + (1 - rho) * p * p,
                   (1, 0): (1 - rho) * p * (1 - p), (0, 1): (1 - rho) * p * (1 - p),
                   (0, 0): rho * (1 - p) + (1 - rho) * (1 - p) ** 2}
    bounds = {(k, n): upper_failure_bound(k, n, alpha / 4) for n in (2, 4) for k in range(n + 1)}
    missed = 0
    total = 0
    for observations in product(probability, repeat=4):
        mass = math.prod(probability[row] for row in observations)
        total += mass
        if any(bounds[sum(row[candidate] for row in observations[:n]), n] < p
               for candidate in (0, 1) for n in (2, 4)):
            missed += mass
    assert total == pytest.approx(1)
    assert missed <= alpha + 1e-13


@pytest.mark.parametrize('defect', ['extra', 'version', 'zero_candidates', 'many_candidates', 'duplicate_id', 'unsafe_id',
                                  'context_missing_case', 'context_bad_hash', 'duplicate_scenario_hash', 'bad_group',
                                  'zero_repeats', 'bad_confidence', 'unknown_design'])
def test_invalid_plans_rejected(defect):
    plan, sources = example_inputs()
    if defect == 'extra':
        plan['extra'] = True
    elif defect == 'version':
        plan['plan_version'] = 'unknown'
    elif defect == 'zero_candidates':
        plan['candidates'] = []
    elif defect == 'many_candidates':
        plan['candidates'] *= 6
    elif defect == 'duplicate_id':
        plan['candidates'][1]['candidate_id'] = 'candidate-a'
    elif defect == 'unsafe_id':
        plan['candidates'][0]['candidate_id'] = '../outside'
    elif defect == 'context_missing_case':
        del plan['scenario_sha256'][plan['scenario_ids'][0]]
    elif defect == 'context_bad_hash':
        plan['candidates'][0]['config_sha256'] = 'not-a-hash'
    elif defect == 'duplicate_scenario_hash':
        plan['scenario_sha256'][plan['scenario_ids'][1]] = plan['scenario_sha256'][plan['scenario_ids'][0]]
    elif defect == 'bad_group':
        plan['groups'] = [{'group_id': 'outside', 'scenario_ids': ['unknown'], 'maximum_failure_probability': .05}]
    elif defect == 'zero_repeats':
        plan['n_repeats'] = 0
    elif defect == 'bad_confidence':
        plan['confidence_level'] = True
    else:
        plan['sampling_design'] = 'adaptive'
    with pytest.raises((AgentBomError, ValueError)):
        review(plan, sources)


@pytest.mark.parametrize('defect', ['unplanned', 'context_missing', 'config_drift', 'scorer_drift', 'scenario_drift',
                                  'missing_row', 'duplicate_row', 'missing_metric', 'bad_repeat', 'invalid_bytes'])
def test_invalid_present_submissions_are_not_downgraded_to_missing(defect):
    plan, sources = example_inputs()
    source = json.loads(sources['candidate-a'])
    if defect == 'unplanned':
        sources['outside'] = sources['candidate-a']
    elif defect == 'context_missing':
        del source['evaluation_context']
    elif defect == 'config_drift':
        source['evaluation_context']['config_sha256'] = plan['candidates'][1]['config_sha256']
    elif defect == 'scorer_drift':
        source['evaluation_context']['scoring_sha256']['synthetic-scorer'] = '0' * 64
    elif defect == 'scenario_drift':
        source['evaluation_context']['scenario_sha256'][plan['scenario_ids'][0]] = '0' * 64
    elif defect == 'missing_row':
        source['results'].pop()
    elif defect == 'duplicate_row':
        source['results'][1] = deepcopy(source['results'][0])
    elif defect == 'missing_metric':
        del source['results'][0]['metrics']['completion']
    elif defect == 'bad_repeat':
        source['results'][0]['repeat'] = 100
    sources['candidate-a'] = b'{' if defect == 'invalid_bytes' else rendered(source)
    with pytest.raises((AgentBomError, ValueError)):
        review(plan, sources)


def test_plan_pin_and_raw_source_bytes_are_bound():
    plan, sources = example_inputs()
    raw = rendered(plan)
    with pytest.raises(AgentBomError, match='pin_mismatch'):
        module.candidate_payloads(raw + b' ', sources, plan_sha256=digest(raw))
    sources['candidate-a'] += b'\n '
    report, files = module.candidate_payloads(raw, sources, plan_sha256=digest(raw))
    assert files['candidates/candidate-a.json'] == sources['candidate-a']
    assert report['candidates'][0]['source_file_sha256'] == digest(sources['candidate-a'])


@pytest.mark.parametrize('member', ['plan.json', 'report.json', 'review.html', 'manifest.json', 'candidates/candidate-a.json'])
def test_rehashed_tampered_packet_is_not_accepted(tmp_path, member):
    plan, sources = example_inputs()
    raw = rendered(plan)
    pin = digest(raw)
    packet = tmp_path / 'packet'
    module.create_candidate_pack(raw, sources, packet, plan_sha256=pin)
    module.verify_candidate_pack(packet, plan_sha256=pin)
    (packet / member).write_bytes((packet / member).read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = json.loads((packet / 'manifest.json').read_bytes())
        manifest['files_sha256'][member] = digest((packet / member).read_bytes())
        (packet / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        module.verify_candidate_pack(packet, plan_sha256=pin)


def test_no_execution_bounded_expansion_and_escaped_report(monkeypatch):
    plan, sources = example_inputs()
    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected execution')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    plan['sampling_basis'] = '<script>alert(1)</script>'
    raw = rendered(plan)
    _, files = module.candidate_payloads(raw, sources, plan_sha256=digest(raw))
    assert b'<script' not in files['review.html'] and b'&lt;script&gt;' in files['review.html']
    assert b'Conditional bound exceeds limit' in files['review.html'] and b'0.0596295' in files['review.html']
    monkeypatch.setattr(module, 'MAX_JSON_BYTES', len(raw) + 1)
    with pytest.raises(AgentBomError):
        module.candidate_payloads(raw, sources, plan_sha256=digest(raw))


def test_cli_and_missing_source_inventory(tmp_path):
    demo = tmp_path / 'demo'
    assert main(['candidate-bounds', 'demo', '--out', str(demo)]) == 0
    assert main(['candidate-bounds', 'demo', '--out', str(demo)]) == 2
    for name in ('pending', 'complete', 'fixed-benchmark', 'earlier-failure'):
        packet = demo / name
        pin = digest((packet / 'plan.json').read_bytes())
        assert main(['candidate-bounds', 'verify', str(packet), '--plan-sha256', pin]) == 0
    packet = demo / 'pending'
    pin = digest((packet / 'plan.json').read_bytes())
    args = ['candidate-bounds', 'create', str(packet / 'plan.json'), str(packet / 'candidates'), '--plan-sha256', pin]
    assert main([*args, '--out', str(tmp_path / 'copy')]) == 0
    assert main([*args, '--out', str(tmp_path / 'copy')]) == 2
    assert main([*args, '--out', str(packet / 'candidates/nested')]) == 2
    (packet / 'candidates/extra').mkdir()
    assert main([*args, '--out', str(tmp_path / 'bad')]) == 2
    assert main(['candidate-bounds', 'verify', str(packet), '--plan-sha256', pin]) == 2
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert main(['candidate-bounds', 'create', str(packet / 'plan.json'), str(empty), '--plan-sha256', pin,
                 '--out', str(tmp_path / 'empty-pack')]) == 0
    assert main(['candidate-bounds', 'verify', str(tmp_path / 'empty-pack'), '--plan-sha256', pin]) == 0
