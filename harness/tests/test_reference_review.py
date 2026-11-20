from copy import deepcopy
from html.parser import HTMLParser
from itertools import product
import json
import os

import pytest

from aau_harness.agent_bom import AgentBomError, MAX_JSON_BYTES, digest, rendered
from aau_harness.catalog_cli import main
from aau_harness.grader_review import review_grader
from aau_harness.reference_demo import example_inputs
from aau_harness.reference_review import FILES, create_reference_pack, reference_payloads, verify_reference_pack


def convert(plan, ratings, adjudications):
    raw = rendered(plan)
    return reference_payloads(raw, rendered(ratings), rendered(adjudications), plan_sha256=digest(raw))


def bind(ratings, adjudications):
    adjudications['ratings_sha256'] = digest(rendered(ratings))


def scope(report, split='validation', group='overall', criterion='authorization'):
    return next(r for r in report['scopes'] if (r['split'], r['group_id'], r['criterion']) == (split, group, criterion))


def test_disagreement_missing_abstentions_and_original_conflicts_survive_adjudication():
    inputs = example_inputs()
    original = deepcopy(inputs)
    report, files = convert(*inputs)
    assert inputs == original
    rows = report['observations']
    assert [r['reference'] for r in rows] == ['pass', 'fail', 'disputed', 'unreviewed', 'unreviewed', 'fail']
    assert [r['panel_reference'] for r in rows] == ['pass', 'fail', 'disputed', 'unreviewed', 'unreviewed', 'disputed']
    assert rows[2]['rating_counts'] == {'pass': 2, 'fail': 1, 'abstain': 0, 'missing': 0}
    assert rows[3]['ratings'][-1] == {'rater_id': 'reviewer-c', 'verdict': 'missing', 'rationale': None}
    assert rows[5]['flags'] == ['abstained_ratings', 'conflicting_ratings', 'recorded_adjudication', 'panel_reference_changed']
    assert scope(report)['panel_conflict_count'] == 2
    assert scope(report)['adjudicated_count'] == 1
    assert scope(report)['submitted_rating_coverage']['numerator'] == 14
    assert scope(report)['submitted_rating_coverage']['denominator'] == 15
    assert scope(report)['decided_reference_coverage']['value'] == 0.4
    assert scope(report, 'calibration')['reference_counts']['pass'] == 1
    assert scope(report, group='assisted-channel')['reference_counts']['unreviewed'] == 2
    assert len(report['scopes']) == 4
    assert files == convert(*inputs)[1]
    assert set(files) == FILES


def test_all_64_three_rater_patterns_against_independent_consensus_oracle():
    for votes in product(('pass', 'fail', 'abstain', None), repeat=3):
        plan, ratings, adjudications = example_inputs()
        plan['items'] = [plan['items'][1]]
        plan['groups'] = []
        template = ratings['rows'][3]
        ratings['rows'] = [{**template, 'rater_id': rater, 'verdict': vote}
                           for rater, vote in zip(plan['raters'], votes) if vote is not None]
        adjudications['rows'] = []
        bind(ratings, adjudications)
        report, _ = convert(plan, ratings, adjudications)
        expected = ('pass' if votes == ('pass',) * 3 else 'fail' if votes == ('fail',) * 3 else
                    'disputed' if 'pass' in votes and 'fail' in votes else 'unreviewed')
        assert report['observations'][0]['reference'] == expected
        assert scope(report)['reference_counts'][expected] == 1
        assert scope(report)['submitted_rating_coverage']['numerator'] == sum(v is not None for v in votes)
        assert scope(report)['submitted_rating_coverage']['denominator'] == 3
        assert scope(report, 'calibration')['decided_reference_coverage']['value'] is None


@pytest.mark.parametrize('state', ['pass', 'fail', 'disputed', 'unreviewed'])
def test_explicit_adjudication_may_preserve_or_change_state_without_erasing_panel(state):
    plan, ratings, adjudications = example_inputs()
    adjudications['rows'][0]['verdict'] = state
    report, _ = convert(plan, ratings, adjudications)
    assert report['observations'][-1]['reference'] == state
    assert report['observations'][-1]['panel_reference'] == 'disputed'
    assert report['observations'][-1]['rating_counts']['abstain'] == 1
    assert scope(report)['panel_conflict_count'] == 2


def test_all_missing_is_unreviewed_not_perfect_agreement():
    plan, ratings, adjudications = example_inputs()
    ratings['rows'] = []
    adjudications['rows'] = []
    bind(ratings, adjudications)
    report, _ = convert(plan, ratings, adjudications)
    assert all(row['reference'] == 'unreviewed' for row in report['observations'])
    assert scope(report)['submitted_rating_coverage'] == {'numerator': 0, 'denominator': 15, 'value': 0}
    assert scope(report)['decided_reference_coverage']['numerator'] == 0
    assert scope(report)['rating_counts']['missing'] == 15


def test_existing_grader_consumer_uses_exact_exported_reference_bytes():
    plan, ratings, adjudications = example_inputs()
    report, files = convert(plan, ratings, adjudications)
    candidate = {'format_version': 'aau-grader-judgments/1.0', 'rubric_sha256': plan['rubric_sha256'],
                 'grader_id': 'all-pass', 'rows': [{**row, 'verdict': 'pass'} for row in json.loads(files['reference.json'])['rows']]}
    result = review_grader(files['grader-plan.json'], files['reference.json'], rendered(candidate),
                           plan_sha256=report['grader_plan_sha256'])
    assert scope(result)['false_passes'] == 2
    assert scope(result)['paired_decision_coverage']['value'] == 0.4
    assert scope(result)['matrix']['disputed']['pass'] == 1
    assert scope(result)['matrix']['unreviewed']['pass'] == 2
    assert json.loads(files['grader-plan.json'])['reference_sha256'] == digest(files['reference.json'])


@pytest.mark.parametrize('defect', ['extra', 'version', 'single-rater', 'duplicate-rater', 'invalid-rater',
    'too-many-raters', 'shared-role', 'no-adjudicator', 'duplicate-adjudicator', 'duplicate-item',
    'duplicate-evidence', 'invalid-split', 'group-outside', 'duplicate-group', 'empty-criterion',
    'bad-rubric', 'empty-basis', 'too-many-assignments'])
def test_plan_rejects_ambiguous_roles_and_census_before_creating(tmp_path, defect):
    plan, ratings, adjudications = example_inputs()
    if defect == 'extra':
        plan['trust'] = True
    elif defect == 'version':
        plan['plan_version'] += '-unknown'
    elif defect == 'single-rater':
        plan['raters'] = ['one']
    elif defect == 'duplicate-rater':
        plan['raters'] = ['one', 'one']
    elif defect == 'invalid-rater':
        plan['raters'] = [False, {}]
    elif defect == 'too-many-raters':
        plan['raters'] = [f'r-{i}' for i in range(11)]
    elif defect == 'shared-role':
        plan['adjudicators'] = [plan['raters'][0]]
    elif defect == 'no-adjudicator':
        plan['adjudicators'] = []
    elif defect == 'duplicate-adjudicator':
        plan['adjudicators'] *= 2
    elif defect == 'duplicate-item':
        plan['items'][1]['item_id'] = plan['items'][0]['item_id']
    elif defect == 'duplicate-evidence':
        plan['items'][1]['evidence_sha256'] = plan['items'][0]['evidence_sha256']
    elif defect == 'invalid-split':
        plan['items'][0]['split'] = 'pooled'
    elif defect == 'group-outside':
        plan['groups'][0]['item_ids'].append('not-planned')
    elif defect == 'duplicate-group':
        plan['groups'] *= 2
    elif defect == 'empty-criterion':
        plan['criteria'] = []
    elif defect == 'bad-rubric':
        plan['rubric_sha256'] = 'not-a-hash'
    elif defect == 'empty-basis':
        plan['reference_basis'] = ' '
    else:
        plan['items'] = [{'item_id': f'case-{i}', 'evidence_sha256': digest(str(i).encode()), 'split': 'validation'} for i in range(500)]
        plan['criteria'] = [f'criterion-{i}' for i in range(10)]
    with pytest.raises(AgentBomError):
        create_reference_pack(*map(rendered, (plan, ratings, adjudications)), tmp_path / 'invalid', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'invalid').exists()


@pytest.mark.parametrize('adjudication', [False, True])
@pytest.mark.parametrize('defect', ['version', 'rubric', 'duplicate', 'extra-field', 'unknown-item', 'unknown-criterion',
    'wrong-evidence', 'unknown-role', 'bad-verdict', 'explicit-missing', 'no-rationale', 'long-rationale', 'non-object'])
def test_rating_and_adjudication_inputs_are_closed_and_bound(adjudication, defect):
    plan, ratings, adjudications = example_inputs()
    document = adjudications if adjudication else ratings
    row = document['rows'][0]
    if defect == 'version':
        document['format_version'] += '-unknown'
    elif defect == 'rubric':
        document['rubric_sha256'] = '0' * 64
    elif defect == 'duplicate':
        document['rows'].append(deepcopy(row))
    elif defect == 'extra-field':
        row['priority'] = 'high'
    elif defect == 'unknown-item':
        row['item_id'] = 'not-planned'
    elif defect == 'unknown-criterion':
        row['criterion'] = 'not-planned'
    elif defect == 'wrong-evidence':
        row['evidence_sha256'] = '0' * 64
    elif defect == 'unknown-role':
        row['adjudicator_id' if adjudication else 'rater_id'] = 'undeclared'
    elif defect == 'bad-verdict':
        row['verdict'] = True
    elif defect == 'explicit-missing':
        row['verdict'] = 'missing'
    elif defect == 'no-rationale':
        row['rationale'] = ' '
    elif defect == 'long-rationale':
        row['rationale'] = 'x' * 1001
    else:
        document['rows'][0] = []
    bind(ratings, adjudications)
    with pytest.raises(AgentBomError):
        convert(plan, ratings, adjudications)


def test_changed_ratings_including_reason_or_whitespace_invalidate_adjudication():
    plan, ratings, adjudications = example_inputs()
    raw_plan = rendered(plan)
    with pytest.raises(AgentBomError, match='exact rating bytes'):
        reference_payloads(raw_plan, rendered(ratings) + b' ', rendered(adjudications), plan_sha256=digest(raw_plan))
    ratings['rows'][0]['rationale'] = 'Changed after the decision'
    with pytest.raises(AgentBomError, match='exact rating bytes'):
        convert(plan, ratings, adjudications)


def test_incomplete_panel_cannot_be_declared_resolved_by_adjudicator():
    plan, ratings, adjudications = example_inputs()
    missing = plan['items'][3]
    adjudications['rows'][0].update(item_id=missing['item_id'], evidence_sha256=missing['evidence_sha256'])
    with pytest.raises(AgentBomError, match='incomplete panel'):
        convert(plan, ratings, adjudications)


@pytest.mark.parametrize('member', sorted(FILES))
def test_every_member_and_manifest_is_recomputed_not_merely_rehashed(tmp_path, member):
    plan, ratings, adjudications = example_inputs()
    pin, folder = digest(rendered(plan)), tmp_path / 'pack'
    originals = tuple(map(rendered, (plan, ratings, adjudications)))
    create_reference_pack(*originals, folder, plan_sha256=pin)
    assert verify_reference_pack(folder, plan_sha256=pin)['status'] == 'recorded_reference_diagnostic'
    with pytest.raises(AgentBomError, match='overwrite'):
        create_reference_pack(*originals, folder, plan_sha256=pin)
    with (folder / member).open('ab') as stream:
        stream.write(b' ')
    if member != 'manifest.json':
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        manifest['files'][member] = digest((folder / member).read_bytes())
        (folder / 'manifest.json').write_bytes(rendered(manifest))
    with pytest.raises(AgentBomError):
        verify_reference_pack(folder, plan_sha256=pin)


@pytest.mark.parametrize('raw', [b'', b'[]', b'{"x":NaN}', b'{"x":1e999}', b'{"x":1,"x":2}',
                               b'{"x":"\xff"}', b'[' * 2000, b'x' * (MAX_JSON_BYTES + 1)])
def test_malformed_ratings_are_not_accepted(raw):
    plan, _, adjudications = example_inputs()
    adjudications['ratings_sha256'] = digest(raw)
    with pytest.raises(AgentBomError):
        reference_payloads(rendered(plan), raw, rendered(adjudications), plan_sha256=digest(rendered(plan)))


def test_structured_html_escapes_all_supplied_rationales_and_basis():
    plan, ratings, adjudications = example_inputs()
    attack = '<img src="https://do-not-fetch.invalid" onerror="alert(1)"><script>alert(1)</script>'
    plan['reference_basis'] = attack
    ratings['rows'][0]['rationale'] = attack
    adjudications['rows'][0]['rationale'] = attack
    bind(ratings, adjudications)
    _, files = convert(plan, ratings, adjudications)
    class Structure(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []
        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
            assert not any(k in ('src', 'href', 'onclick', 'onerror') for k, _ in attrs)
            if tag == 'th':
                assert ('scope', 'col') in attrs
            if ('class', 'scroll') in attrs:
                assert ('tabindex', '0') in attrs and ('role', 'region') in attrs
    parser = Structure()
    html = files['review.html'].decode()
    parser.feed(html)
    assert not {'img', 'script', 'iframe', 'link'} & set(parser.tags)
    assert parser.tags.count('caption') == 7
    assert parser.tags.count('section') == 6
    assert parser.tags.count('main') == 1
    assert '&lt;script&gt;' in html
    assert 'conflicting_ratings' in html


def test_html_expansion_is_bounded_before_destination_is_created(tmp_path):
    plan, ratings, adjudications = example_inputs()
    plan['items'] = [{'item_id': f'case-{i}', 'evidence_sha256': digest(str(i).encode()), 'split': 'validation'} for i in range(300)]
    plan['groups'] = []
    plan['raters'] = ['rater-a', 'rater-b']
    ratings['rows'] = [{'item_id': item['item_id'], 'criterion': 'authorization', 'evidence_sha256': item['evidence_sha256'],
                        'rater_id': rater, 'verdict': 'pass', 'rationale': '"' * 900}
                       for item in plan['items'] for rater in plan['raters']]
    adjudications['rows'] = []
    bind(ratings, adjudications)
    assert len(rendered(ratings)) < MAX_JSON_BYTES
    with pytest.raises(AgentBomError, match='exceeds 2 MB'):
        create_reference_pack(*map(rendered, (plan, ratings, adjudications)), tmp_path / 'invalid', plan_sha256=digest(rendered(plan)))
    assert not (tmp_path / 'invalid').exists()


def test_demo_replays_existing_grader_and_cli_refuses_wrong_pin(tmp_path):
    folder = tmp_path / 'demo'
    assert main(['reference-review', 'demo', '--out', str(folder)]) == 0
    assert main(['reference-review', 'demo', '--out', str(folder)]) == 2
    pack = folder / 'packet'
    pin = digest((pack / 'plan.json').read_bytes())
    assert main(['reference-review', 'verify', str(pack), '--plan-sha256', pin]) == 0
    assert main(['reference-review', 'verify', str(pack), '--plan-sha256', '0' * 64]) == 2
    assert main(['reference-review', 'create', str(pack / 'plan.json'), str(pack / 'ratings.json'),
                 str(pack / 'adjudications.json'), '--plan-sha256', pin, '--out', str(tmp_path / 'copy')]) == 0
    grader_pin = digest((pack / 'grader-plan.json').read_bytes())
    assert main(['grader-review', str(pack / 'grader-plan.json'), str(pack / 'reference.json'), str(folder / 'candidate.json'),
                 '--plan-sha256', grader_pin, '--verify', str(folder / 'grader-report.json')]) == 0
    assert pin in (folder / 'README.md').read_text()


@pytest.mark.parametrize('defect', ['extra', 'missing', 'linked-file', 'linked-directory', 'fifo'])
def test_noncanonical_pack_inventory_is_rejected(tmp_path, defect):
    plan, ratings, adjudications = example_inputs()
    pin, folder = digest(rendered(plan)), tmp_path / 'pack'
    create_reference_pack(*map(rendered, (plan, ratings, adjudications)), folder, plan_sha256=pin)
    if defect == 'extra':
        (folder / 'extra').write_text('extra')
    elif defect == 'linked-directory':
        alias = tmp_path / 'alias'
        alias.symlink_to(folder, target_is_directory=True)
        folder = alias
    else:
        (folder / 'ratings.json').unlink()
        if defect == 'linked-file':
            (folder / 'ratings.json').symlink_to(folder / 'plan.json')
        elif defect == 'fifo':
            if not hasattr(os, 'mkfifo'):
                pytest.skip('FIFO unavailable on this platform')
            os.mkfifo(folder / 'ratings.json')
    with pytest.raises(AgentBomError):
        verify_reference_pack(folder, plan_sha256=pin)


def test_no_network_model_or_subprocess_is_invoked(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution attempted')
    monkeypatch.setattr('subprocess.run', forbidden)
    monkeypatch.setattr('socket.create_connection', forbidden)
    assert convert(*example_inputs())[0]['status'] == 'recorded_reference_diagnostic'


def test_criteria_and_splits_are_not_pooled_and_unsubmitted_criterion_stays_unknown():
    plan, ratings, adjudications = example_inputs()
    plan['criteria'].append('task-completion')
    report, files = convert(plan, ratings, adjudications)
    assert len(report['observations']) == 12
    assert len(report['scopes']) == 8
    assert scope(report, criterion='task-completion')['reference_counts']['unreviewed'] == 5
    assert scope(report, criterion='task-completion')['rating_counts']['missing'] == 15
    assert scope(report)['reference_counts']['fail'] == 2
    assert len(json.loads(files['reference.json'])['rows']) == 12


def test_input_bytes_retained_and_replacement_plan_cannot_use_receivers_pin(tmp_path):
    plan, ratings, adjudications = example_inputs()
    plan_raw, rating_raw = rendered(plan) + b' ', b'\xef\xbb\xbf' + rendered(ratings).replace(b'\n', b'\r\n')
    adjudications['ratings_sha256'] = digest(rating_raw)
    adjudication_raw = rendered(adjudications) + b'\n'
    pin = digest(plan_raw)
    folder = tmp_path / 'packet'
    create_reference_pack(plan_raw, rating_raw, adjudication_raw, folder, plan_sha256=pin)
    assert (folder / 'plan.json').read_bytes() == plan_raw
    assert (folder / 'ratings.json').read_bytes() == rating_raw
    assert (folder / 'adjudications.json').read_bytes() == adjudication_raw
    assert verify_reference_pack(folder, plan_sha256=pin)['input_sha256']['ratings.json'] == digest(rating_raw)
    # A supplier can build another valid pack; it still cannot match the receiver's expected plan.
    plan['reference_basis'] = 'Replacement basis'
    create_reference_pack(rendered(plan), rating_raw, adjudication_raw, tmp_path / 'replacement',
                          plan_sha256=digest(rendered(plan)))
    with pytest.raises(AgentBomError, match='pin'):
        verify_reference_pack(tmp_path / 'replacement', plan_sha256=pin)
