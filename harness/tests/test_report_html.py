from html.parser import HTMLParser

import pytest

from aau_harness.eval_diagnostics import _table as diagnostic_table
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_pack import pack_payloads
from aau_harness.report_html import STYLE, table


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, value):
        self.text.append(value)


@pytest.mark.parametrize('renderer', [table, diagnostic_table])
def test_shared_tables_have_named_keyboard_groups_and_semantic_headers(renderer):
    html = renderer('One <caption>', ['Case', 'Observed'], [('first', 0), ('second', 1)])
    parsed = Structure()
    parsed.feed(html)
    group = parsed.elements[0]
    assert group == ('div', {'class': 'scroll', 'tabindex': '0', 'role': 'group', 'aria-label': 'Scrollable table: One <caption>'})
    assert [attrs['scope'] for tag, attrs in parsed.elements if tag == 'th'] == ['col', 'col', 'row', 'row']
    assert '<tbody><tr><th scope="row">first</th><td>0</td></tr>' in html
    assert not any(tag == 'script' or name.startswith('on') for tag, attrs in parsed.elements for name in attrs)


@pytest.mark.parametrize('value', ['<script>alert(1)</script>', '\" onfocus=\"alert(1)', '</td><img src=x>', '&amp;'])
def test_all_supplied_captions_headers_and_cells_are_escaped(value):
    parsed = Structure()
    parsed.feed(table(value, [value, 'Value'], [(value, value)]))
    assert {tag for tag, _ in parsed.elements} <= {'div', 'table', 'caption', 'thead', 'tbody', 'tr', 'th', 'td'}
    assert parsed.elements[0][1]['aria-label'] == 'Scrollable table: ' + value
    assert value in parsed.text
    assert not any(name.startswith('on') for _, attrs in parsed.elements for name in attrs)


def test_empty_and_unavailable_values_are_not_silent_or_rounded_into_zero():
    assert '<td colspan="2">None recorded.</td>' in table('Empty', ['A', 'B'], [])
    assert '<td>None</td>' in table('Null', ['A', 'B'], [('a', None)])
    assert '<td>Not available</td>' in diagnostic_table('Null', ['A', 'B'], [('a', None)])
    assert '<td>0.123457</td>' in diagnostic_table('Rounded display only', ['A', 'B'], [('a', 0.123456789)], compact_numbers=True)
    assert '<td>0.123456789</td>' in table('Exact display', ['A', 'B'], [('a', 0.123456789)])


def test_policy_navigation_targets_exist_without_changing_evidence_verdicts():
    policy, baseline, candidate, diagnostics = demo_inputs()
    for source, expected in ((baseline, 'constraints_not_met'), (candidate, 'constraints_met')):
        report, files = pack_payloads(policy, baseline, source, recordings=True, diagnostics=diagnostics)
        assert report['status'] == expected
        parsed = Structure()
        parsed.feed(files['review.html'].decode())
        ids = [attrs['id'] for _, attrs in parsed.elements if 'id' in attrs]
        assert len(ids) == len(set(ids))
        fragments = [attrs['href'][1:] for tag, attrs in parsed.elements if tag == 'a' and attrs.get('href', '').startswith('#')]
        assert {'policy-checks', 'evidence-consistency', 'diagnostics'} <= set(fragments) <= set(ids)
        assert any(tag == 'nav' and attrs.get('aria-label') == 'Review sections' for tag, attrs in parsed.elements)
        assert all(attrs.get('scope') in ('col', 'row') for tag, attrs in parsed.elements if tag == 'th')
        assert b'<script' not in files['review.html']


def test_shared_styles_keep_focus_reflow_and_forced_color_support():
    assert 'body{overflow-wrap:anywhere}' in STYLE
    assert '.scroll:focus-visible' in STYLE and 'outline:3px solid' in STYLE
    assert '@media(forced-colors:active)' in STYLE and 'outline-color:Highlight' in STYLE
    assert 'min-width:0!important' in STYLE
