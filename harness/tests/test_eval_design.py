from copy import deepcopy
from fractions import Fraction
import json
import math

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.eval_design import binomial_weights, create_design, design_payloads, search_design, validate_plan, verify_design
from aau_harness.eval_design_demo import create_demo, demo_plan


def payloads(plan):
    raw = rendered(plan)
    return design_payloads(raw, plan_sha256=digest(raw))


def cdf(n, c, p):
    # Independent oracle: direct binomial expansion, not the production recurrence.
    return sum((math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(c + 1)), Fraction(0))


def ratio(row):
    exact = Fraction(int(row['numerator']), int(row['denominator']))
    assert float(exact) == row['decimal']
    return exact


@pytest.mark.parametrize('p', [Fraction(0), Fraction(1, 10), Fraction(1, 3), Fraction(1, 2), Fraction(99, 100)])
def test_integer_weights_against_direct_expansion(p):
    for n in range(1, 16):
        weights, denominator = binomial_weights(n, p)
        assert sum(weights) == denominator
        for k, weight in enumerate(weights):
            assert Fraction(weight, denominator) == math.comb(n, k) * p ** k * (1 - p) ** (n - k)


@pytest.mark.parametrize('bad', [Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)])
@pytest.mark.parametrize('good', [Fraction(0), Fraction(1, 10)])
@pytest.mark.parametrize('alpha', [Fraction(1, 20), Fraction(1, 5)])
def test_exhaustive_small_design_minimality_and_largest_cutoff(bad, good, alpha):
    minimum, maximum = Fraction(4, 5), 24
    expected = None
    for n in range(1, maximum + 1):
        legal = [c for c in range(n + 1) if cdf(n, c, bad) <= alpha]
        if legal and cdf(n, max(legal), good) >= minimum:
            expected = n, max(legal)
            break
    selected, _ = search_design(bad, good, alpha, minimum, maximum)
    assert (None if selected is None else (selected['scenario_count'], selected['maximum_failed_bundles'])) == expected
    if selected:
        n, c = expected
        assert ratio(selected['qualification_probability_at_unacceptable_rate']) == cdf(n, c, bad) <= alpha
        assert ratio(selected['qualification_probability_at_assumed_rate']) == cdf(n, c, good) >= minimum
        assert cdf(n, c + 1, bad) > alpha


def test_exact_equal_boundary_not_float_tolerance():
    selected, _ = search_design(Fraction(1, 2), Fraction(0), Fraction(1, 2), Fraction(1), 5)
    assert (selected['scenario_count'], selected['maximum_failed_bundles']) == (1, 0)
    lower, _ = search_design(Fraction(1, 2), Fraction(0), Fraction('0.499999'), Fraction(1), 5)
    assert lower['scenario_count'] == 2


def test_nist_published_operating_characteristic_example():
    # NIST handbook pmc232: n=52, c=3, p=.01 through .12 (three-place displayed values).
    expected = [.998, .980, .930, .845, .739, .620, .502, .394, .300, .223, .162, .115]
    for percentage, displayed in enumerate(expected, 1):
        weights, denominator = binomial_weights(52, Fraction(percentage, 100))
        calculated = Fraction(sum(weights[:4]), denominator)
        assert calculated == cdf(52, 3, Fraction(percentage, 100))
        # The illustrative .04 and .05 table entries differ from nearest three-place
        # rounding of the published formula. Never use that display as an exact oracle.
        assert abs(float(calculated) - displayed) < .001


def test_zero_failure_reference_is_not_an_eighty_percent_design():
    report, _ = payloads(demo_plan())
    scope = report['scopes'][0]
    zero, selected = scope['zero_failure_reference'], scope['design']
    assert zero['scenario_count'] == 59
    assert zero['meets_requested_probability'] is False
    assert ratio(zero['qualification_probability_at_assumed_rate']) == Fraction(99, 100) ** 59
    assert (selected['scenario_count'], selected['maximum_failed_bundles']) == (124, 2)
    assert selected['attempts_per_candidate'] == 248
    assert report['decision_status'] == 'not_assessed'


def test_power_is_not_monotone_across_discrete_sample_sizes():
    # At 124 bundles c=2 first becomes allowed; at 125 c is still 2 and power falls.
    assert cdf(124, 2, Fraction(1, 100)) > cdf(125, 2, Fraction(1, 100))
    assert cdf(123, 2, Fraction(1, 20)) > Fraction(1, 20)
    assert cdf(124, 2, Fraction(1, 20)) <= Fraction(1, 20)


def test_family_and_repeat_accounting_do_not_pool_probability_or_sample_size():
    plan = demo_plan()
    plan['candidate_count'] = 3
    plan['scopes'].append({**plan['scopes'][0], 'scope_id': 'assisted'})
    report, _ = payloads(plan)
    assert report['family_size'] == 6 and ratio(report['cell_error_probability']) == Fraction(1, 120)
    assert all(s['design']['scenario_count'] == 203 for s in report['scopes'])
    plan['repeats_per_scenario'] = 20
    repeated, _ = payloads(plan)
    for before, after in zip(report['scopes'], repeated['scopes']):
        assert after['design']['scenario_count'] == before['design']['scenario_count']
        assert after['design']['attempts_per_candidate'] == 4060
        assert after['design']['qualification_probability_at_assumed_rate'] == before['design']['qualification_probability_at_assumed_rate']
    assert 'total_attempts' not in report


def test_search_failure_is_bounded_not_impossibility_or_approval():
    plan = demo_plan()
    plan['maximum_scenarios_per_scope'] = 100
    report, _ = payloads(plan)
    assert report['status'] == 'design_search_incomplete'
    assert report['scopes'][0]['status'] == 'no_design_within_search_limit'
    assert report['scopes'][0]['design'] is None
    assert report['scopes'][0]['zero_failure_reference']['scenario_count'] == 59
    plan['maximum_scenarios_per_scope'] = 10
    report, _ = payloads(plan)
    assert report['scopes'][0]['zero_failure_reference'] is None


def test_fixed_benchmark_never_runs_population_design(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('fixed benchmark must not perform population planning')
    monkeypatch.setattr('aau_harness.eval_design.search_design', forbidden)
    plan = demo_plan()
    plan['sampling_design'] = 'fixed_benchmark'
    report, _ = payloads(plan)
    assert report['status'] == 'population_design_withheld'
    assert all(s['design'] is None and s['zero_failure_reference'] is None for s in report['scopes'])


@pytest.mark.parametrize('field,value', [('candidate_count', True), ('candidate_count', 11), ('candidate_count', 0),
    ('repeats_per_scenario', 21), ('repeats_per_scenario', 1.0), ('maximum_scenarios_per_scope', 501),
    ('family_error_probability', '0'), ('family_error_probability', '0.500001'),
    ('minimum_qualification_probability', '0'), ('minimum_qualification_probability', '1.1'),
    ('sampling_design', 'iid'), ('purpose', ''), ('sampling_basis', ' '), ('extra', 1)])
def test_invalid_contracts(field, value):
    plan = demo_plan()
    plan[field] = value
    with pytest.raises(AgentBomError):
        payloads(plan)


@pytest.mark.parametrize('value', [0.05, True, None, 'NaN', '1e-2', ' 0.05', '0.1234567', '-0.1', '.1'])
def test_probabilities_are_bounded_exact_decimal_strings(value):
    plan = demo_plan()
    plan['scopes'][0]['assumed_failure_probability'] = value
    with pytest.raises(AgentBomError):
        payloads(plan)


@pytest.mark.parametrize('change', ['missing_overall', 'duplicate', 'empty', 'too_many', 'bad_id', 'equal_rates', 'zero_bad', 'one_bad', 'extra_field'])
def test_bad_scopes(change):
    plan = demo_plan()
    if change == 'missing_overall':
        plan['scopes'][0]['scope_id'] = 'other'
    elif change == 'duplicate':
        plan['scopes'] *= 2
    elif change == 'empty':
        plan['scopes'] = []
    elif change == 'too_many':
        plan['scopes'] += [{**plan['scopes'][0], 'scope_id': f'g{i}'} for i in range(20)]
    elif change == 'bad_id':
        plan['scopes'][0]['scope_id'] = '../outside'
    elif change == 'equal_rates':
        plan['scopes'][0]['assumed_failure_probability'] = '0.05'
    elif change in ('zero_bad', 'one_bad'):
        plan['scopes'][0]['unacceptable_failure_probability'] = '0' if change == 'zero_bad' else '1'
    else:
        plan['scopes'][0]['ignore'] = True
    with pytest.raises(AgentBomError):
        payloads(plan)


def test_full_resource_boundary_and_exact_six_place_arithmetic():
    # Exercise the largest n and denominator without overflowing JSON integer conversion.
    weights, denominator = binomial_weights(500, Fraction('0.999999'))
    assert sum(weights) == denominator
    assert len(str(denominator)) == 3001
    plan = demo_plan()
    plan['candidate_count'] = 10
    plan['maximum_scenarios_per_scope'] = 1
    plan['family_error_probability'] = '0.000001'
    plan['scopes'] += [{**plan['scopes'][0], 'scope_id': f'g{i}'} for i in range(19)]
    report, _ = payloads(plan)
    assert report['family_size'] == 200
    assert ratio(report['cell_error_probability']) == Fraction(1, 200_000_000)


def test_pins_raw_bytes_replay_and_no_mutation(tmp_path):
    plan = demo_plan()
    before = deepcopy(plan)
    raw = rendered(plan)
    pin = digest(raw)
    directory = tmp_path / 'packet'
    report = create_design(raw, directory, plan_sha256=pin)
    assert verify_design(directory, plan_sha256=pin) == report
    assert (directory / 'plan.json').read_bytes() == raw
    assert plan == before
    with pytest.raises(AgentBomError):
        validate_plan(raw + b' ', pin)
    with pytest.raises(AgentBomError):
        create_design(raw, directory, plan_sha256=pin)
    with pytest.raises(AgentBomError):
        validate_plan(b'x' * (MAX_JSON_BYTES + 1), pin)


@pytest.mark.parametrize('member', ['plan.json', 'report.json', 'review.html', 'manifest.json', 'extra.json'])
def test_all_members_bound_and_recomputed(tmp_path, member):
    raw = rendered(demo_plan())
    pin = digest(raw)
    directory = tmp_path / 'packet'
    create_design(raw, directory, plan_sha256=pin)
    path = directory / member
    path.write_bytes((path.read_bytes() if path.exists() else b'') + b' ')
    with pytest.raises(AgentBomError):
        verify_design(directory, plan_sha256=pin)


def test_escaped_html_and_no_scripts():
    plan = demo_plan()
    plan['purpose'] = '<script>alert("untrusted")</script>'
    _, files = payloads(plan)
    html = files['review.html'].decode()
    assert '<script' not in html and '&lt;script&gt;' in html
    assert html.count('<table>') == 3
    assert 'role="group"' in html and 'tabindex="0"' in html


def test_demo_cli_and_diagnostic_exits(tmp_path, capsys):
    demo = tmp_path / 'demo'
    create_demo(demo)
    for name in ('planned', 'limited', 'family', 'fixed-benchmark'):
        directory = demo / name
        pin = digest((directory / 'plan.json').read_bytes())
        assert main(['evaluation-design', 'verify', str(directory), '--plan-sha256', pin]) == 0
        assert main(['evaluation-design', 'verify', str(directory), '--plan-sha256', '0' * 64]) == 2
    assert main(['evaluation-design', 'demo', '--out', str(demo)]) == 2
    assert main(['evaluation-design', 'demo', '--out', str(tmp_path / 'other')]) == 0
    pin = digest((demo / 'planned/plan.json').read_bytes())
    assert main(['evaluation-design', 'create', str(demo / 'planned/plan.json'), '--plan-sha256', pin,
                 '--out', str(tmp_path / 'created')]) == 0
    assert 'not_assessed' == json.loads((tmp_path / 'created/report.json').read_bytes())['decision_status']
    assert str(tmp_path) not in capsys.readouterr().err
