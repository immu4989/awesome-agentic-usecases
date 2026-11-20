from copy import deepcopy
from html.parser import HTMLParser
from itertools import product
import json
import os

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.coverage_demo import example_inputs
from aau_harness.coverage_review import FILES, coverage_payloads, create_coverage_pack, verify_coverage_pack
from aau_harness.eval_import import import_observations


def convert(plan, inventory, evaluation):
    raw = rendered(plan)
    return coverage_payloads(raw, rendered(inventory), rendered(evaluation), plan_sha256=digest(raw))


def rebuild(evaluation):
    return import_observations({'format_version': 'aau-recorded-observations/1.0', 'source_label': 'test only',
        'scenario_ids': sorted({r['scenario_id'] for r in evaluation['results']}),
        'n_repeats': evaluation['n_repeats'], 'observations': evaluation['results'],
        **({'evaluation_context': evaluation['evaluation_context']} if 'evaluation_context' in evaluation else {})})


def cell(report, channel='assisted', language='spanish'):
    return next(r for r in report['cells'] if r['coordinates'] == {'channel': channel, 'language': language})


def test_high_scores_repeats_and_unknown_classification_do_not_hide_missing_conditions():
    plan, variants = example_inputs()
    original = deepcopy((plan, variants))
    reports = {name: convert(plan, *inputs)[0] for name, inputs in variants.items()}
    assert [reports[n]['status'] for n in ('gap', 'uncertain', 'covered')] == [
        'coverage_not_met', 'coverage_not_verified', 'coverage_met']
    assert reports['gap']['recorded_observations'] == 40
    assert cell(reports['gap'])['counted_scenario_ids'] == []
    assert cell(reports['uncertain'])['counted_scenario_ids'] == []
    assert cell(reports['uncertain'])['uncertain_scenario_ids'] == ['case-4']
    assert cell(reports['covered'])['counted_scenario_ids'] == ['case-4']
    assert cell(reports['covered'], 'self-service', 'english')['counted_scenario_ids'] == ['case-0', 'case-1']
    assert reports['covered']['cases'][0]['complete_metric_repeats'] == 10
    assert (plan, variants) == original


def test_zero_performance_scores_can_supply_coverage_but_do_not_become_passes():
    plan, variants = example_inputs()
    inventory, evaluation = variants['covered']
    for row in evaluation['results']:
        row['metrics'] = {'completion': 0, 'authorization': 0}
    report, files = convert(plan, inventory, rebuild(evaluation))
    assert report['status'] == 'coverage_met'
    assert json.loads(files['evaluation.json'])['metric_means'] == {'authorization': 0, 'completion': 0}
    assert 'not model quality' in report['boundary']


def test_inventory_only_case_is_not_counted_as_observed():
    plan, variants = example_inputs()
    report, _ = convert(plan, variants['covered'][0], variants['gap'][1])
    assert report['status'] == 'coverage_not_met'
    case = report['cases'][-1]
    assert case['observed_repeats'] == 0 and case['fingerprint_binding'] == 'not_observed'
    assert 'not_observed' in case['flags']
    assert cell(report)['uncertain_scenario_ids'] == []


def test_metrics_must_be_present_together_on_enough_repeats():
    plan, variants = example_inputs()
    inventory, evaluation = variants['covered']
    for row in evaluation['results']:
        if row['scenario_id'] == 'case-4':
            row['metrics'] = {'authorization': 1} if row['repeat'] % 2 else {'completion': 1}
    report, _ = convert(plan, inventory, rebuild(evaluation))
    assert report['status'] == 'coverage_not_met'
    assert report['cases'][-1]['complete_metric_repeats'] == 0
    assert cell(report)['uncertain_scenario_ids'] == []


def test_unavailable_context_is_uncertain_and_mismatching_context_is_invalid():
    plan, variants = example_inputs()
    inventory, evaluation = variants['covered']
    context = evaluation.pop('evaluation_context')
    report, _ = convert(plan, inventory, evaluation)
    assert report['status'] == 'coverage_not_verified'
    assert all(not r['counted_scenario_ids'] for r in report['cells'])
    assert all(r['fingerprint_binding'] == 'unavailable' for r in report['cases'])
    evaluation['evaluation_context'] = context
    context['scenario_sha256']['case-4'] = '0' * 64
    with pytest.raises(AgentBomError, match='fingerprints disagree'):
        convert(plan, inventory, evaluation)


def test_independent_oracle_for_36_classification_binding_measurement_patterns():
    plan, variants = example_inputs()
    base_inventory, base_evaluation = variants['covered']
    for channel, language, context, complete in product(('self-service', 'assisted', None), ('english', 'spanish', None), (False, True), (False, True)):
        inventory, evaluation = deepcopy(base_inventory), deepcopy(base_evaluation)
        inventory['items'] = inventory['items'][:1]
        inventory['items'][0]['attributes'] = {'channel': channel, 'language': language}
        evaluation['results'] = [r for r in evaluation['results'] if r['scenario_id'] == 'case-0']
        evaluation['evaluation_context']['scenario_sha256'] = {'case-0': inventory['items'][0]['scenario_sha256']}
        if not context:
            del evaluation['evaluation_context']
        if not complete:
            for row in evaluation['results']:
                row['metrics'].pop('completion')
        report, _ = convert(plan, inventory, rebuild(evaluation))
        for current in report['cells']:
            matches = (channel is None or channel == current['coordinates']['channel']) and (language is None or language == current['coordinates']['language'])
            counted = matches and complete and context and channel is not None and language is not None
            uncertain = matches and complete and not counted
            assert current['counted_scenario_ids'] == (['case-0'] if counted else [])
            assert current['uncertain_scenario_ids'] == (['case-0'] if uncertain else [])
            assert current['status'] == ('coverage_met' if counted else 'coverage_not_verified' if uncertain else 'coverage_not_met')


def test_unknown_case_possibilities_are_not_added_across_cells():
    plan, variants = example_inputs()
    inventory, evaluation = variants['covered']
    for item in inventory['items']:
        item['attributes'] = {'channel': None, 'language': None}
    report, _ = convert(plan, inventory, evaluation)
    assert report['status'] == 'coverage_not_verified'
    assert sum(len(c['uncertain_scenario_ids']) for c in report['cells']) == 20
    assert report['recorded_cases'] == 5
    assert all(len(c['counted_scenario_ids']) == 0 for c in report['cells'])


def test_explicit_exclusion_remains_visible_and_requires_changed_plan_pin(tmp_path):
    plan, variants = example_inputs()
    old_pin = digest(rendered(plan))
    plan['cell_overrides'] = [{'coordinates': {'channel': 'assisted', 'language': 'spanish'}, 'minimum_cases': 0,
                               'rationale': 'Constructed example of an explicit scope exclusion, not an approval.'}]
    report, _ = convert(plan, *variants['gap'])
    assert report['status'] == 'coverage_met'
    assert cell(report)['status'] == 'excluded' and cell(report)['override_rationale']
    assert report['cell_counts']['excluded'] == 1
    create_coverage_pack(rendered(plan), *map(rendered, variants['gap']), tmp_path / 'pack', plan_sha256=digest(rendered(plan)))
    with pytest.raises(AgentBomError, match='pin'):
        verify_coverage_pack(tmp_path / 'pack', plan_sha256=old_pin)


@pytest.mark.parametrize('defect', ['version', 'extra', 'no-dimensions', 'bad-dimension', 'too-many-dimensions',
    'duplicate-level', 'invalid-level', 'empty-levels', 'grid-too-large', 'bool-minimum', 'zero-minimum',
    'bool-repeats', 'too-many-repeats', 'empty-metrics', 'duplicate-metric', 'bad-purpose', 'override-extra',
    'override-partial', 'override-unknown', 'override-duplicate', 'override-no-reason', 'override-bool', 'all-excluded'])
def test_invalid_plan_is_rejected_before_output(tmp_path, defect):
    plan, variants = example_inputs()
    override = {'coordinates': {'channel': 'assisted', 'language': 'spanish'}, 'minimum_cases': 0, 'rationale': 'Example only'}
    if defect == 'version':
        plan['plan_version'] += '-unknown'
    elif defect == 'extra':
        plan['approve'] = True
    elif defect == 'no-dimensions':
        plan['dimensions'] = {}
    elif defect == 'bad-dimension':
        plan['dimensions']['bad name'] = ['one']
    elif defect == 'too-many-dimensions':
        plan['dimensions'] = {f'd-{i}': ['one'] for i in range(6)}
    elif defect == 'duplicate-level':
        plan['dimensions']['channel'] = ['one', 'one']
    elif defect == 'invalid-level':
        plan['dimensions']['channel'] = [False]
    elif defect == 'empty-levels':
        plan['dimensions']['channel'] = []
    elif defect == 'grid-too-large':
        plan['dimensions'] = {f'd-{i}': [f'l-{j}' for j in range(10)] for i in range(3)}
    elif defect in ('bool-minimum', 'zero-minimum'):
        plan['minimum_cases'] = True if defect == 'bool-minimum' else 0
    elif defect in ('bool-repeats', 'too-many-repeats'):
        plan['minimum_complete_repeats'] = True if defect == 'bool-repeats' else 10001
    elif defect == 'empty-metrics':
        plan['required_metrics'] = []
    elif defect == 'duplicate-metric':
        plan['required_metrics'] *= 2
    elif defect == 'bad-purpose':
        plan['purpose'] = ' '
    else:
        plan['cell_overrides'] = [override]
        if defect == 'override-extra':
            override['hidden'] = True
        elif defect == 'override-partial':
            del override['coordinates']['language']
        elif defect == 'override-unknown':
            override['coordinates']['language'] = 'unplanned'
        elif defect == 'override-duplicate':
            plan['cell_overrides'] *= 2
        elif defect == 'override-no-reason':
            override['rationale'] = ''
        elif defect == 'override-bool':
            override['minimum_cases'] = False
        else:
            plan['cell_overrides'] = [{**override, 'coordinates': {'channel': channel, 'language': language}}
                                     for channel, language in product(plan['dimensions']['channel'], plan['dimensions']['language'])]
    with pytest.raises(AgentBomError):
        create_coverage_pack(rendered(plan), *map(rendered, variants['covered']), tmp_path / 'invalid', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'invalid').exists()


@pytest.mark.parametrize('defect', ['extra', 'version', 'empty', 'duplicate-id', 'duplicate-hash', 'bad-hash',
    'unknown-value', 'missing-attribute', 'extra-attribute', 'unplanned-evaluation-id', 'summary', 'duplicate-row',
    'missing-row', 'context-null', 'context-incomplete'])
def test_invalid_inventory_or_evaluation_is_not_treated_as_coverage(defect):
    plan, variants = example_inputs()
    inventory, evaluation = variants['covered']
    if defect == 'extra':
        inventory['extra'] = True
    elif defect == 'version':
        inventory['inventory_version'] += '-unknown'
    elif defect == 'empty':
        inventory['items'] = []
    elif defect == 'duplicate-id':
        inventory['items'][1]['scenario_id'] = inventory['items'][0]['scenario_id']
    elif defect == 'duplicate-hash':
        inventory['items'][1]['scenario_sha256'] = inventory['items'][0]['scenario_sha256']
    elif defect == 'bad-hash':
        inventory['items'][0]['scenario_sha256'] = 'bad'
    elif defect == 'unknown-value':
        inventory['items'][0]['attributes']['language'] = 'not-declared'
    elif defect == 'missing-attribute':
        del inventory['items'][0]['attributes']['language']
    elif defect == 'extra-attribute':
        inventory['items'][0]['attributes']['extra'] = 'english'
    elif defect == 'unplanned-evaluation-id':
        inventory['items'].pop()
    elif defect == 'summary':
        evaluation['metric_means']['completion'] = 0.5
    elif defect == 'duplicate-row':
        evaluation['results'][-1] = deepcopy(evaluation['results'][0])
    elif defect == 'missing-row':
        evaluation['results'].pop()
    elif defect == 'context-null':
        evaluation['evaluation_context'] = None
    else:
        del evaluation['evaluation_context']['scenario_sha256']['case-4']
    with pytest.raises(AgentBomError):
        convert(plan, inventory, evaluation)


@pytest.mark.parametrize('member', sorted(FILES))
def test_source_retention_and_every_derived_member_recompute(tmp_path, member):
    plan, variants = example_inputs()
    inventory, evaluation = variants['uncertain']
    raws = (b' ' + rendered(plan), b'\xef\xbb\xbf' + rendered(inventory), rendered(evaluation).replace(b'\n', b'\r\n'))
    pin, folder = digest(raws[0]), tmp_path / 'pack'
    create_coverage_pack(*raws, folder, plan_sha256=pin)
    assert verify_coverage_pack(folder, plan_sha256=pin)['status'] == 'coverage_not_verified'
    for name, raw in zip(('plan.json', 'inventory.json', 'evaluation.json'), raws):
        assert (folder / name).read_bytes() == raw
    with pytest.raises(AgentBomError, match='overwrite'):
        create_coverage_pack(*raws, folder, plan_sha256=pin)
    with (folder / member).open('ab') as stream:
        stream.write(b' ')
    if member != 'manifest.json':
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        manifest['files'][member] = digest((folder / member).read_bytes())
        (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_coverage_pack(folder, plan_sha256=pin)


@pytest.mark.parametrize('raw', [b'', b'[]', b'{"x":NaN}', b'{"x":1e999}', b'{"x":1,"x":2}',
                               b'{"x":"\xff"}', b'[' * 2000, b'x' * (MAX_JSON_BYTES + 1)])
def test_malformed_input_bytes_are_rejected(raw):
    plan, variants = example_inputs()
    with pytest.raises(AgentBomError):
        coverage_payloads(rendered(plan), raw, rendered(variants['covered'][1]), plan_sha256=digest(rendered(plan)))


def test_html_is_structured_script_free_and_escapes_supplied_text():
    plan, variants = example_inputs()
    plan['purpose'] = '<script>alert(1)</script><img src="https://do-not-fetch.invalid">'
    plan['cell_overrides'] = [{'coordinates': {'channel': 'assisted', 'language': 'spanish'}, 'minimum_cases': 1,
                               'rationale': plan['purpose']}]
    _, files = convert(plan, *variants['covered'])
    class Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag not in ('script', 'img', 'iframe', 'link')
            assert not any(name in ('src', 'href', 'onclick', 'onerror') for name, _ in attrs)
            if tag == 'th':
                assert dict(attrs).get('scope') in ('col', 'row')
            if ('class', 'scroll') in attrs:
                assert ('tabindex', '0') in attrs
    html = files['review.html'].decode()
    Parser().feed(html)
    assert '&lt;script&gt;' in html
    assert html.count('<caption>') == 2


def test_demo_and_cli_distinguish_valid_gaps_from_invalid_packets(tmp_path):
    root = tmp_path / 'demo'
    assert main(['coverage-review', 'demo', '--out', str(root)]) == 0
    assert main(['coverage-review', 'demo', '--out', str(root)]) == 2
    for name, expected in [('gap', 1), ('uncertain', 1), ('covered', 0)]:
        pin = digest((root / name / 'plan.json').read_bytes())
        assert main(['coverage-review', 'verify', str(root / name), '--plan-sha256', pin]) == expected
    pack = root / 'covered'
    pin = digest((pack / 'plan.json').read_bytes())
    assert main(['coverage-review', 'create', str(pack / 'plan.json'), str(pack / 'inventory.json'),
                 str(pack / 'evaluation.json'), '--plan-sha256', pin, '--out', str(tmp_path / 'copy')]) == 0
    assert main(['coverage-review', 'verify', str(pack), '--plan-sha256', '0' * 64]) == 2


@pytest.mark.parametrize('defect', ['extra', 'missing', 'symlink', 'directory-link', 'fifo'])
def test_pack_inventory_and_file_types_are_checked(tmp_path, defect):
    plan, variants = example_inputs()
    pin, folder = digest(rendered(plan)), tmp_path / 'pack'
    create_coverage_pack(rendered(plan), *map(rendered, variants['covered']), folder, plan_sha256=pin)
    if defect == 'extra':
        (folder / 'extra').write_text('extra')
    elif defect == 'directory-link':
        alias = tmp_path / 'alias'
        alias.symlink_to(folder, target_is_directory=True)
        folder = alias
    else:
        (folder / 'inventory.json').unlink()
        if defect == 'symlink':
            (folder / 'inventory.json').symlink_to(folder / 'plan.json')
        elif defect == 'fifo':
            if not hasattr(os, 'mkfifo'):
                pytest.skip('FIFO unavailable')
            os.mkfifo(folder / 'inventory.json')
    with pytest.raises(AgentBomError):
        verify_coverage_pack(folder, plan_sha256=pin)


def test_expanded_unknown_case_grid_is_bounded_before_output(tmp_path):
    plan, _ = example_inputs()
    plan['dimensions'] = {'first': [f'v-{i}' for i in range(10)],
                          'second': [f'v-{i}' for i in range(10)], 'third': ['one', 'two']}
    plan['minimum_complete_repeats'] = 1
    items = [{'scenario_id': str(i).zfill(200), 'scenario_sha256': digest(str(i).encode()),
              'attributes': dict.fromkeys(plan['dimensions'])} for i in range(100)]
    inventory = {'inventory_version': 'aau-coverage-inventory/1.0', 'source_label': 'Expansion test only', 'items': items}
    evaluation = import_observations({'format_version': 'aau-recorded-observations/1.0', 'source_label': 'Expansion test only',
        'scenario_ids': [i['scenario_id'] for i in items], 'n_repeats': 1,
        'observations': [{'scenario_id': i['scenario_id'], 'repeat': 0,
                          'metrics': {'completion': 1, 'authorization': 1}} for i in items]})
    assert len(rendered(inventory)) < MAX_JSON_BYTES and len(rendered(evaluation)) < MAX_JSON_BYTES
    with pytest.raises(AgentBomError, match='expanded coverage report'):
        create_coverage_pack(rendered(plan), rendered(inventory), rendered(evaluation), tmp_path / 'large',
                             plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'large').exists()


def test_no_external_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution attempted')
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)
    plan, variants = example_inputs()
    assert convert(plan, *variants['covered'])[0]['status'] == 'coverage_met'
