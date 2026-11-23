from copy import deepcopy
from fractions import Fraction
from itertools import product
import json
import math

import pytest

from aau_harness.agent_bom import AgentBomError, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_import import import_observations
from aau_harness.eval_paired import FILES, create_paired_pack, exact_mcnemar, paired_payloads, verify_paired_pack
from aau_harness.paired_demo import example_inputs


def review(plan=None, baseline=None, candidate=None):
    defaults = example_inputs()
    plan, baseline, candidate = [value if value is not None else default
                                 for value, default in zip((plan, baseline, candidate), defaults)]
    raw = rendered(plan)
    return paired_payloads(raw, rendered(baseline), rendered(candidate), plan_sha256=digest(raw))


def test_exact_projection_bundle_not_repeat_unit_and_regression_retention():
    report, files = review()
    overall, subgroup = report['scopes']
    assert (overall['both_pass'], overall['improved'], overall['regressed'], overall['both_fail']) == (1, 10, 1, 0)
    assert overall['scenario_count'] == report['scenario_count'] == 12
    assert overall['discordant_pair_count'] == 11
    assert overall['two_sided_exact_p'] == {'value': .01171875, 'numerator': '3', 'denominator': '256'}
    assert overall['bonferroni_adjusted_p']['value'] == .0234375
    assert overall['inference_status'] == 'difference_detected'
    assert overall['observed_candidate_minus_baseline_failure_fraction'] == -.75
    assert subgroup['regressed'] == 1 and subgroup['improved'] == 0
    case = report['scenario_outcomes'][10]
    assert case['transition'] == 'regressed' and len(case['candidate_failed_repeats']) == 1
    assert case['candidate_failed_repeats'][0]['repeat'] == 0
    assert set(files) == FILES


@pytest.mark.parametrize('i,r,p', [(0, 0, Fraction(1)), (4, 4, Fraction(1)), (6, 0, Fraction(1, 32)),
                                  (10, 1, Fraction(3, 256)), (500, 0, Fraction(1, 2 ** 499))])
def test_exact_known_values_and_symmetry(i, r, p):
    assert exact_mcnemar(i, r) == exact_mcnemar(r, i) == p
    assert float(p) > 0


@pytest.mark.parametrize('n', range(13))
def test_exact_test_is_conservative_for_each_conditional_null(n):
    # Enumerate the exact fair-coin distribution, not another library's rounded p-values.
    for alpha in (Fraction(1, 2), Fraction(1, 20), Fraction(1, 100)):
        rejection_probability = sum(Fraction(math.comb(n, k), 2 ** n) for k in range(n + 1)
                                    if exact_mcnemar(k, n - k) <= alpha)
        assert rejection_probability <= alpha


def test_overlapping_scope_family_null_by_exhaustive_joint_enumeration():
    # Four-valued IID pairs with symmetric discordance; two overlapping declared scopes.
    for probabilities in ((Fraction(1, 4),) * 4, (Fraction(1, 10), Fraction(2, 5), Fraction(2, 5), Fraction(1, 10))):
        for alpha in (Fraction(1, 2), Fraction(1, 4), Fraction(1, 20)):
            false_family = Fraction(0)
            for outcomes in product(range(4), repeat=4):
                weight = math.prod(probabilities[o] for o in outcomes)
                p_values = [exact_mcnemar(sum(outcomes[i] == 1 for i in scope), sum(outcomes[i] == 2 for i in scope))
                            for scope in (range(4), range(3))]
                if any(2 * p <= alpha for p in p_values):
                    false_family += weight
            assert false_family <= alpha


@pytest.mark.parametrize('counts', [(True, 1), (1, False), (-1, 2), (1.0, 1), (501, 0), (250, 251)])
def test_invalid_exact_counts(counts):
    with pytest.raises(AgentBomError):
        exact_mcnemar(*counts)


def test_fixed_benchmark_withholds_all_inference_but_preserves_counts():
    plan, baseline, candidate = example_inputs()
    conditional, _ = review(plan, baseline, candidate)
    plan['sampling_design'] = 'fixed_benchmark'
    fixed, _ = review(plan, baseline, candidate)
    assert fixed['status'] == 'population_inference_withheld'
    for observed, reference in zip(fixed['scopes'], conditional['scopes']):
        assert observed['two_sided_exact_p'] is observed['bonferroni_adjusted_p'] is None
        assert observed['inference_status'] == 'population_inference_withheld'
        for field in ('both_pass', 'improved', 'regressed', 'both_fail', 'scenario_count'):
            assert observed[field] == reference[field]


def test_reversing_roles_preserves_two_sided_test_and_flips_direction():
    plan, baseline, candidate = example_inputs()
    forward, _ = review(plan, baseline, candidate)
    plan['baseline'], plan['candidate'] = plan['candidate'], plan['baseline']
    reverse, _ = review(plan, candidate, baseline)
    for left, right in zip(forward['scopes'], reverse['scopes']):
        assert left['two_sided_exact_p'] == right['two_sided_exact_p']
        assert left['improved'] == right['regressed']
        assert left['observed_candidate_minus_baseline_failure_fraction'] == -right['observed_candidate_minus_baseline_failure_fraction']


def test_zero_discordance_is_not_equivalence_and_keeps_shared_failures():
    plan, baseline, _ = example_inputs()
    same = deepcopy(baseline)
    same['evaluation_context']['config_sha256'] = plan['candidate']['config_sha256']
    report, _ = review(plan, baseline, same)
    assert report['scopes'][0]['two_sided_exact_p']['value'] == 1
    assert report['scopes'][0]['both_fail'] == 10
    assert report['scopes'][0]['inference_status'] == 'difference_not_detected'
    assert report['method']['equivalence_test'] is False


@pytest.mark.parametrize('alpha,status', [(0.0234375, 'difference_detected'), (0.02343749, 'difference_not_detected')])
def test_decision_uses_exact_value_and_inclusive_predeclared_threshold(alpha, status):
    plan, baseline, candidate = example_inputs()
    plan['family_significance_level'] = alpha
    report, _ = review(plan, baseline, candidate)
    assert report['scopes'][0]['inference_status'] == status


def test_replicating_recorded_repeats_does_not_inflate_independent_pairs():
    plan, baseline, candidate = example_inputs()
    original, _ = review(plan, baseline, candidate)
    sources = []
    for source in (baseline, candidate):
        recording = {'format_version': 'aau-recorded-observations/1.0', 'source_label': 'Synthetic duplicated repeats',
                     'scenario_ids': plan['scenario_ids'], 'n_repeats': 6,
                     'observations': [{'scenario_id': row['scenario_id'], 'repeat': row['repeat'] + offset,
                                       'metrics': row['metrics']} for offset in (0, 2, 4) for row in source['results']]}
        copied = import_observations(recording)
        copied['evaluation_context'] = source['evaluation_context']
        sources.append(copied)
    plan['n_repeats'] = 6
    repeated, _ = review(plan, *sources)
    assert repeated['scopes'] == original['scopes']
    assert len(repeated['scenario_outcomes'][10]['candidate_failed_repeats']) == 3


def test_unreviewed_metrics_and_summary_mismatch_are_visible():
    plan, baseline, candidate = example_inputs()
    candidate['results'][0]['metrics']['completion'] = 0
    candidate['results'][0]['metrics']['unused'] = 7
    report, _ = review(plan, baseline, candidate)
    assert report['source_audits']['candidate']['status'] != 'consistent'
    assert report['unreviewed_metrics']['candidate'] == ['unused']


@pytest.mark.parametrize('defect', ['missing-row', 'duplicate-row', 'wrong-repeat', 'missing-metric', 'missing-context',
    'wrong-config', 'wrong-scenario-hash', 'wrong-scorer', 'wrong-ids', 'wrong-repeat-plan', 'nan', 'bad-alpha',
    'bool-alpha', 'duplicate-system-id', 'unknown-field', 'unknown-design', 'empty-group', 'unknown-group-id',
    'reserved-group', 'duplicate-group', 'unknown-group-field', 'duplicate-fingerprint', 'raw-not-bytes'])
def test_rejects_invalid_or_incomparable_evidence_before_writing(tmp_path, defect):
    plan, baseline, candidate = example_inputs()
    if defect == 'missing-row':
        candidate['results'].pop()
    elif defect == 'duplicate-row':
        candidate['results'][-1] = candidate['results'][0]
    elif defect == 'wrong-repeat':
        candidate['results'][0]['repeat'] = 99
    elif defect == 'missing-metric':
        del candidate['results'][0]['metrics']['completion']
    elif defect == 'missing-context':
        del candidate['evaluation_context']
    elif defect == 'wrong-config':
        candidate['evaluation_context']['config_sha256'] = '0' * 64
    elif defect == 'wrong-scenario-hash':
        candidate['evaluation_context']['scenario_sha256'] = {**plan['scenario_sha256'], 'case-00': '0' * 64}
    elif defect == 'wrong-scorer':
        candidate['evaluation_context']['scoring_sha256'] = {'other': '0' * 64}
    elif defect == 'wrong-ids':
        plan['scenario_ids'] = plan['scenario_ids'][:-1]
        plan['scenario_sha256'] = {k: v for k, v in plan['scenario_sha256'].items() if k in plan['scenario_ids']}
        plan['groups'] = []
    elif defect == 'wrong-repeat-plan':
        plan['n_repeats'] = 3
    elif defect in ('bad-alpha', 'bool-alpha'):
        plan['family_significance_level'] = True if defect == 'bool-alpha' else 0
    elif defect == 'duplicate-system-id':
        plan['candidate']['candidate_id'] = plan['baseline']['candidate_id']
    elif defect == 'unknown-field':
        plan['unplanned'] = 'extra'
    elif defect == 'unknown-design':
        plan['sampling_design'] = 'optional_stopping'
    elif defect == 'empty-group':
        plan['groups'][0]['scenario_ids'] = []
    elif defect == 'unknown-group-id':
        plan['groups'][0]['scenario_ids'] = ['unplanned-case']
    elif defect == 'reserved-group':
        plan['groups'][0]['group_id'] = 'overall'
    elif defect == 'duplicate-group':
        plan['groups'].append(deepcopy(plan['groups'][0]))
    elif defect == 'unknown-group-field':
        plan['groups'][0]['extra'] = 1
    elif defect == 'duplicate-fingerprint':
        plan['scenario_sha256']['case-01'] = plan['scenario_sha256']['case-00']
    raw, old, new = rendered(plan), rendered(baseline), rendered(candidate)
    if defect == 'nan':
        new = new.replace(b'"completion": 1', b'"completion": NaN', 1)
    elif defect == 'raw-not-bytes':
        new = candidate
    with pytest.raises((AgentBomError, ValueError)):
        create_paired_pack(raw, old, new, tmp_path / 'out', plan_sha256=digest(raw))
    assert not (tmp_path / 'out').exists()


def test_exact_raw_bytes_plan_pin_manifest_replay_and_no_overwrite(tmp_path):
    plan, baseline, candidate = example_inputs()
    raw = b' ' + rendered(plan)
    old = rendered(baseline).replace(b'\n', b'\r\n')
    new = rendered(candidate)
    packet = tmp_path / 'packet'
    report = create_paired_pack(raw, old, new, packet, plan_sha256=digest(raw))
    assert report == verify_paired_pack(packet, plan_sha256=digest(raw))
    assert (packet / 'baseline.json').read_bytes() == old
    assert (packet / 'plan.json').read_bytes() == raw
    with pytest.raises(AgentBomError):
        verify_paired_pack(packet, plan_sha256=digest(rendered(plan)))
    with pytest.raises(AgentBomError):
        create_paired_pack(raw, old, new, packet, plan_sha256=digest(raw))


@pytest.mark.parametrize('member', sorted(FILES) + ['extra.json', 'directory', 'symlink'])
def test_pack_tampering_inventory_and_links_fail(tmp_path, member):
    plan, baseline, candidate = example_inputs()
    raw = rendered(plan)
    packet = tmp_path / 'packet'
    create_paired_pack(raw, rendered(baseline), rendered(candidate), packet, plan_sha256=digest(raw))
    if member == 'directory':
        (packet / member).mkdir()
    elif member == 'symlink':
        (packet / member).symlink_to(packet / 'baseline.json')
    else:
        with (packet / member).open('ab') as stream:
            stream.write(b' ')
    with pytest.raises((AgentBomError, ValueError)):
        verify_paired_pack(packet, plan_sha256=digest(raw))


def test_html_escapes_identifiers_and_sampling_notes():
    plan, baseline, candidate = example_inputs()
    plan['sampling_basis'] = '<script>alert(1)</script>'
    plan['groups'][0]['group_id'] = '<img src=x onerror=bad>'
    _, files = review(plan, baseline, candidate)
    html = files['review.html'].decode()
    assert '<script>' not in html and '<img src=' not in html
    assert '&lt;script&gt;' in html and '&lt;img src=x onerror=bad&gt;' in html
    assert 'role="group"' in html and 'scope="row"' in html


def test_cli_demo_all_twins_create_verify_and_closed_error(tmp_path, capsys):
    directory = tmp_path / 'demo'
    assert main(['paired-review', 'demo', '--out', str(directory)]) == 0
    assert main(['paired-review', 'demo', '--out', str(directory)]) == 2
    for packet in sorted(p for p in directory.iterdir() if p.is_dir()):
        pin = digest((packet / 'plan.json').read_bytes())
        assert main(['paired-review', 'verify', str(packet), '--plan-sha256', pin]) == 0
        report = json.loads((packet / 'report.json').read_bytes())
        assert report['scenario_count'] == 12
    assert main(['paired-review', 'create', str(packet / 'plan.json'), str(packet / 'baseline.json'),
                 str(packet / 'candidate.json'), '--plan-sha256', pin, '--out', str(tmp_path / 'copy')]) == 0
    assert main(['paired-review', 'verify', str(packet), '--plan-sha256', '0' * 64]) == 2
    assert str(tmp_path) not in capsys.readouterr().err
