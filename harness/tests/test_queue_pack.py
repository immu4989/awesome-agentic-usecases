from html.parser import HTMLParser
import os
import runpy

import pytest

from aau_harness import queue_pack as module
from aau_harness.agent_bom import MAX_JSON_BYTES, digest, load_json, rendered
from aau_harness.catalog_cli import main
from aau_harness.inspect_pack import InspectionError

from test_review_queue import EXAMPLE, inputs as inputs


def create(inputs, directory):
    plan, routing, source, timing = inputs
    raw = rendered(plan)
    return module.create_pack(raw, routing, source, timing, directory, queue_plan_sha256=digest(raw))


@pytest.mark.parametrize('name', ['one-slot', 'two-slots', 'break-window', 'blocked-head', 'unknown-deadlines'])
def test_every_constructed_outcome_recomputes_complete_pack(tmp_path, name):
    inputs = runpy.run_path(str(EXAMPLE))['example_inputs']()[name]
    report = create(inputs, tmp_path / 'pack')
    assert module.verify_pack(tmp_path / 'pack', queue_plan_sha256=digest(rendered(inputs[0]))) == report
    assert {p.name for p in (tmp_path / 'pack').iterdir()} == module.FILES
    assert load_json(tmp_path / 'pack/report.json') == report
    assert report['counts']['deferred_observations'] == 4
    assert not report['human_resolution_measured']
    assert report['routing_review']['recorded_joint_failures'] == 4


@pytest.mark.parametrize('member', sorted(module.FILES))
def test_rehashed_manifest_cannot_bless_altered_sources_or_presentation(tmp_path, inputs, member):
    folder = tmp_path / 'pack'
    create(inputs, folder)
    path = folder / member
    path.write_bytes(path.read_bytes() + b' ')
    if member != 'manifest.json':
        manifest = load_json(folder / 'manifest.json')
        manifest['files_sha256'][member] = digest(path.read_bytes())
        (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(ValueError):
        module.verify_pack(folder, queue_plan_sha256=digest(rendered(inputs[0])))


@pytest.mark.parametrize('defect', ['extra', 'missing', 'directory', 'link', 'fifo', 'oversized', 'root_link'])
def test_exact_bounded_regular_members_required(tmp_path, inputs, defect):
    folder = tmp_path / 'pack'
    create(inputs, folder)
    if defect == 'extra':
        (folder / 'unreviewed.txt').write_text('not a pack member')
    elif defect == 'directory':
        (folder / 'empty').mkdir()
    elif defect == 'root_link':
        (tmp_path / 'link').symlink_to(folder, target_is_directory=True)
        folder = tmp_path / 'link'
    else:
        (folder / 'review.html').unlink()
        if defect == 'link':
            (folder / 'review.html').symlink_to(folder / 'README.txt')
        elif defect == 'fifo':
            if not hasattr(os, 'mkfifo'):
                pytest.skip('FIFO unavailable')
            os.mkfifo(folder / 'review.html')
        elif defect == 'oversized':
            (folder / 'review.html').write_bytes(b'x' * (MAX_JSON_BYTES + 1))
    with pytest.raises(InspectionError):
        module.verify_pack(folder, queue_plan_sha256=digest(rendered(inputs[0])))


def test_raw_control_bytes_are_retained_but_expected_pin_stays_independent(tmp_path, inputs):
    plan, routing, source, timing = inputs
    routing += b'\n '
    plan['routing_plan_sha256'] = digest(routing)
    raw = rendered(plan) + b' \n'
    module.create_pack(raw, routing, source, timing, tmp_path / 'pack', queue_plan_sha256=digest(raw))
    assert (tmp_path / 'pack/queue-plan.json').read_bytes() == raw
    assert (tmp_path / 'pack/routing-plan.json').read_bytes() == routing
    with pytest.raises(InspectionError, match='pin_mismatch'):
        module.verify_pack(tmp_path / 'pack', queue_plan_sha256='0' * 64)
    assert module.verify_pack(tmp_path / 'pack', queue_plan_sha256=digest(raw))['counts']['known_deadline_failures'] == 2


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.links, self.attributes = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)
        if tag == 'a':
            self.links.append(dict(attrs)['href'])


def test_html_is_script_free_escaped_accessible_and_source_linked(tmp_path, inputs):
    inputs[0]['workers'][0]['worker_id'] = '<script>alert("PRIVATE")</script>'
    report = create(inputs, tmp_path / 'pack')
    html = (tmp_path / 'pack/review.html').read_text()
    doc = Document()
    doc.feed(html)
    assert not {'script', 'iframe', 'img', 'object', 'embed', 'form'} & set(doc.tags)
    assert not any(name.startswith('on') for name, _ in doc.attributes)
    assert set(doc.links) == module.FILES - {'review.html'}
    assert 'Content-Security-Policy' in html and 'default-src &#39;none&#39;' in html
    assert 'aria-labelledby="queue-title queue-desc"' in html
    assert '<caption>Exact timeline after same-time events</caption>' in html
    assert '<th scope="col">' in html and '<figcaption>' in html
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert 'Not measured' in html and 'Unknown or unresolved deadline outcomes' in html
    assert str(report['maximum_scheduled_wait_s']) in html
    assert str(tmp_path) not in html


def test_cli_verifies_diagnostics_with_deadline_failures_without_promoting_them(tmp_path, inputs):
    plan, routing, source, timing = inputs
    for name, raw in [('queue', rendered(plan)), ('routing', routing), ('evaluation', rendered(source)), ('timing', rendered(timing))]:
        (tmp_path / f'{name}.json').write_bytes(raw)
    command = ['queue-pack', 'create', *[str(tmp_path / f'{name}.json') for name in ('queue', 'routing', 'evaluation', 'timing')],
               '--queue-plan-sha256', digest(rendered(plan)), '--out', str(tmp_path / 'pack')]
    assert main(command) == 0
    assert main(command) == 2
    assert main(['queue-pack', 'verify', str(tmp_path / 'pack'), '--queue-plan-sha256', digest(rendered(plan))]) == 0
    assert main(['queue-pack', 'verify', str(tmp_path / 'pack'), '--queue-plan-sha256', '0' * 64]) == 2


def test_html_member_bound_is_checked_before_writing_any_output(tmp_path, inputs, monkeypatch):
    monkeypatch.setattr(module, 'render_review', lambda _: 'x' * (MAX_JSON_BYTES + 1))
    with pytest.raises(InspectionError, match='member_exceeds_limit'):
        create(inputs, tmp_path / 'pack')
    assert not (tmp_path / 'pack').exists()
