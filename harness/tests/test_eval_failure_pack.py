from copy import deepcopy
from html.parser import HTMLParser
import json
import math
from pathlib import Path

import pytest

from aau_harness.agent_bom import AgentBomError, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness import eval_failure_demo, eval_failure_pack
from aau_harness.eval_failure_bound import review_failure_bounds
from aau_harness.eval_failure_pack import FILES, create_failure_bound_pack, failure_bound_payloads, verify_failure_bound_pack
from aau_harness.runner import ScenarioResult, run_eval


def inputs(design='declared_iid_fixed_horizon', unsafe=False, label='synthetic-case'):
    plan = {'plan_version': 'aau-failure-bound-plan/1.0', 'scenario_ids': [label], 'n_repeats': 2,
            'criteria': [{'metric': 'completion', 'direction': 'higher', 'limit': 1}],
            'sampling_design': design, 'sampling_basis': 'Synthetic fixture, not sampled people.',
            'confidence_level': .95, 'maximum_failure_probability': .05, 'groups': []}
    source = run_eval([label], lambda scenario, repeat: ScenarioResult(
        scenario, repeat, {'completion': int(not (unsafe and repeat == 0))}, 0, .1, 0), repeats=2).as_dict()
    source['retained_detail'] = {'note': 'SYNTHETIC-DO-NOT-UPLOAD'}
    return plan, source


@pytest.mark.parametrize('design', ['fixed_benchmark', 'declared_iid_fixed_horizon'])
@pytest.mark.parametrize('unsafe', [False, True])
def test_complete_pack_recomputes_and_preserves_supplied_source_values(tmp_path, design, unsafe):
    plan, source = inputs(design, unsafe)
    originals = deepcopy((plan, source))
    report, payloads = failure_bound_payloads(plan, source)
    assert (report, payloads) == failure_bound_payloads(plan, source)
    assert (plan, source) == originals
    assert set(payloads) == FILES
    assert list(payloads)[-1] == 'manifest.json'
    destination = tmp_path / 'pack'
    assert create_failure_bound_pack(plan, source, destination) == verify_failure_bound_pack(destination) == report
    assert load_json(destination / 'evaluation.json') == source
    assert 'SYNTHETIC-DO-NOT-UPLOAD' not in payloads['review.html'].decode()
    manifest = load_json(destination / 'manifest.json')
    assert manifest['files'] == {name: digest(payload) for name, payload in sorted(payloads.items()) if name != 'manifest.json'}
    assert len(list(destination.iterdir())) == 5


@pytest.mark.parametrize('name', sorted(FILES))
def test_every_member_must_recompute_even_when_only_whitespace_changes(tmp_path, name):
    destination = tmp_path / 'pack'
    create_failure_bound_pack(*inputs(), destination)
    path = destination / name
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(AgentBomError, match='does not recompute'):
        verify_failure_bound_pack(destination)


@pytest.mark.parametrize('member', ['review.html', 'report.json', 'plan.json', 'evaluation.json'])
def test_updating_manifest_does_not_authorize_changed_evidence(tmp_path, member):
    destination = tmp_path / 'pack'
    create_failure_bound_pack(*inputs(), destination)
    path = destination / member
    if member == 'review.html':
        path.write_bytes(path.read_bytes().replace(b'Conditional numeric limits exceeded', b'Approved for deployment'))
    else:
        value = load_json(path)
        if member == 'report.json':
            value['scopes'][0]['one_sided_upper_failure_bound'] = 0
        elif member == 'plan.json':
            value['maximum_failure_probability'] = .99
        else:
            value['retained_detail']['note'] = 'replaced evidence'
        path.write_bytes(rendered(value))
    manifest = load_json(destination / 'manifest.json')
    manifest['files'][member] = digest(path.read_bytes())
    (destination / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError, match='does not recompute'):
        verify_failure_bound_pack(destination)


@pytest.mark.parametrize('defect', ['missing', 'extra', 'directory', 'symlink', 'oversized', 'root_symlink'])
def test_pack_shape_errors_fail_closed(tmp_path, defect):
    destination = tmp_path / 'pack'
    create_failure_bound_pack(*inputs(), destination)
    page = destination / 'review.html'
    if defect == 'extra':
        (destination / 'extra.txt').write_text('unexpected')
    elif defect == 'root_symlink':
        link = tmp_path / 'link'
        link.symlink_to(destination, target_is_directory=True)
        destination = link
    elif defect == 'oversized':
        page.write_bytes(b'x' * 2_000_001)
    else:
        page.unlink()
        if defect == 'directory':
            page.mkdir()
        elif defect == 'symlink':
            page.symlink_to(destination / 'report.json')
    with pytest.raises(AgentBomError):
        verify_failure_bound_pack(destination)


class Document(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.elements = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_untrusted_identifiers_notes_metrics_and_mismatches_are_only_text():
    payload = '<img src="https://invalid.example/collect" onerror="alert(1)"><script>bad()</script>'
    plan, source = inputs(unsafe=True, label=payload)
    plan['sampling_basis'] = payload
    plan['criteria'][0]['metric'] = payload
    for row in source['results']:
        row['metrics'] = {payload: row['metrics']['completion']}
    source['metric_means']['completion'] = payload
    report, files = failure_bound_payloads(plan, source)
    assert report['source_audit']['status'] == 'inconsistent'
    page = files['review.html'].decode()
    parsed = Document(page)
    assert '&lt;script&gt;' in page and '&lt;img' in page
    assert not any(tag in {'script', 'img', 'iframe', 'object', 'embed', 'input', 'form', 'link'} for tag, _ in parsed.elements)
    assert not any(name.startswith('on') for _, attrs in parsed.elements for name in attrs)
    assert all(attrs['href'].startswith('#') or attrs['href'] in {'plan.json', 'evaluation.json', 'report.json', 'manifest.json'}
               for _, attrs in parsed.elements if 'href' in attrs)
    assert 'Content-Security-Policy' in page and 'default-src &#39;none&#39;' in page
    assert 'Not sanitized' in page and 'aau failure-bound-pack verify PATH' in page


def test_fixed_benchmark_draws_only_observed_fraction_and_never_a_population_bound():
    report, files = failure_bound_payloads(*inputs('fixed_benchmark'))
    page = files['review.html'].decode()
    parsed = Document(page)
    assert '<h1>Population inference withheld</h1>' in page
    assert 'Population bounds applied: No' in page
    assert not [attrs for tag, attrs in parsed.elements if tag == 'line']
    assert len([attrs for tag, attrs in parsed.elements if tag == 'rect']) == 2
    assert report['scopes'][0]['one_sided_upper_failure_bound'] is None


def test_conditional_chart_and_full_precision_table_come_from_computed_values():
    plan, source = inputs()
    bound = review_failure_bounds(plan, source)['scopes'][0]['one_sided_upper_failure_bound']
    plan['maximum_failure_probability'] = math.nextafter(bound, 0)
    report, files = failure_bound_payloads(plan, source)
    page = files['review.html'].decode()
    parsed = Document(page)
    bars = [attrs for tag, attrs in parsed.elements if tag == 'rect' and attrs.get('fill') == '#a17b38']
    assert bars[0]['width'] == f'{600 * bound:.10f}'
    assert str(bound) in page and str(plan['maximum_failure_probability']) in page
    assert '<h1>Conditional numeric limits exceeded</h1>' in page
    assert report['status'] == 'conditional_bounds_exceed_limits'
    assert 'Status is computed from unrounded values' in page
    assert all('aria-labelledby' in attrs for tag, attrs in parsed.elements if tag == 'svg')
    assert all(attrs.get('tabindex') == '0' for tag, attrs in parsed.elements if attrs.get('class') == 'scroll')


def test_all_criterion_failures_remain_readable_and_unreviewed_metrics_visible():
    plan, source = inputs(unsafe=True)
    source['results'][0]['metrics']['extra-metric'] = .4
    report, files = failure_bound_payloads(plan, source)
    page = files['review.html'].decode()
    assert report['scenario_outcomes'][0]['bundle_failed']
    assert 'Every recorded criterion failure' in page and 'extra-metric' in page
    assert '<td>synthetic-case</td><td>0</td><td>completion</td><td>0</td>' in page
    assert 'Stored-summary consistency: inconsistent' in page


@pytest.mark.parametrize('kind', ['file', 'directory', 'symlink'])
def test_existing_output_is_never_overwritten(tmp_path, kind):
    destination = tmp_path / 'existing'
    if kind == 'file':
        destination.write_text('keep')
    elif kind == 'directory':
        destination.mkdir()
        (destination / 'keep.txt').write_text('keep')
    else:
        target = tmp_path / 'target'
        target.mkdir()
        destination.symlink_to(target, target_is_directory=True)
    with pytest.raises(AgentBomError, match='overwrite'):
        create_failure_bound_pack(*inputs(), destination)
    if kind == 'file':
        assert destination.read_text() == 'keep'
    elif kind == 'directory':
        assert list(destination.iterdir()) == [destination / 'keep.txt']
    else:
        assert not list(destination.iterdir())


def test_expanded_html_is_bounded_before_any_output_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr(eval_failure_pack, 'render_failure_review', lambda report: 'x' * 2_000_001)
    destination = tmp_path / 'too-large'
    with pytest.raises(AgentBomError, match='no evidence is truncated'):
        create_failure_bound_pack(*inputs(), destination)
    assert not destination.exists()


def test_interrupted_write_cannot_produce_a_verifiable_pack(tmp_path, monkeypatch):
    original = Path.open
    def interrupted(path, *args, **kwargs):
        if path.name == 'manifest.json' and args == ('xb',):
            raise OSError('synthetic interruption')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', interrupted)
    destination = tmp_path / 'partial'
    with pytest.raises(OSError):
        create_failure_bound_pack(*inputs(), destination)
    assert (destination / 'review.html').is_file() and not (destination / 'manifest.json').exists()
    with pytest.raises(AgentBomError):
        verify_failure_bound_pack(destination)


def test_cli_creates_and_verifies_a_diagnostic_not_a_release_gate(tmp_path):
    plan, source = inputs()
    for name, value in [('plan', plan), ('evaluation', source)]:
        (tmp_path / f'{name}.json').write_text(json.dumps(value))
    out = tmp_path / 'review'
    assert main(['failure-bound-pack', 'create', str(tmp_path / 'plan.json'), str(tmp_path / 'evaluation.json'), '--out', str(out)]) == 0
    assert main(['failure-bound-pack', 'verify', str(out)]) == 0
    assert load_json(out / 'report.json')['status'] == 'conditional_bounds_exceed_limits'
    (out / 'review.html').write_text('tampered page')
    assert main(['failure-bound-pack', 'verify', str(out)]) == 2


def test_installed_demo_shape_is_deterministic_and_has_all_three_interpretations(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    assert main(['failure-bound-demo', '--out', str(first)]) == 0
    assert main(['failure-bound-demo', '--out', str(first)]) == 2
    eval_failure_demo.create_demo(second)
    files = [p.relative_to(first) for p in first.rglob('*') if p.is_file()]
    assert len(files) == 21
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in files)
    for name, expected in eval_failure_demo.EXPECTED.items():
        assert verify_failure_bound_pack(first / name)['status'] == expected
    assert '13.911%' in (first / 'README.txt').read_text()


def test_demo_completion_guide_is_absent_if_a_result_is_not_verified(tmp_path, monkeypatch):
    original = eval_failure_demo.verify_failure_bound_pack
    def incorrect(directory):
        report = original(directory)
        report['status'] = 'incorrect'
        return report
    monkeypatch.setattr(eval_failure_demo, 'verify_failure_bound_pack', incorrect)
    root = tmp_path / 'partial-demo'
    assert main(['failure-bound-demo', '--out', str(root)]) == 2
    assert not (root / 'README.txt').exists()


def test_synthetic_demo_does_not_capture_ambient_execution_provenance(monkeypatch):
    from aau_harness import provenance

    def forbidden_snapshot():
        raise AssertionError('Synthetic examples must not claim the current time or an ambient provider execution')

    monkeypatch.setattr(provenance, 'snapshot', forbidden_snapshot)
    for plan, source in eval_failure_demo.example_inputs().values():
        assert source['provenance']['evidence_kind'] == 'imported_unverified_observations'
        assert source['provenance']['source_label'] == 'Constructed failure-bound arithmetic lesson; no real sampling'
        assert len(source['results']) == len(plan['scenario_ids']) * 4
        assert all(row['cost_usd'] == 0 and row['latency_s'] == .1 and row['n_api_calls'] == 0
                   for row in source['results'])
