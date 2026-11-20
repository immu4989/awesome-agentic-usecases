"""Construct a recorded panel example and replay its exported labels through the grader audit."""

from .agent_bom import AgentBomError, digest, rendered
from .grader_review import review_grader
from .reference_review import create_reference_pack, reference_payloads, verify_reference_pack


def example_inputs():
    plan = {'plan_version': 'aau-reference-review-plan/1.0', 'rubric_sha256': digest(b'constructed authorization rubric'),
            'reference_basis': 'Synthetic panel ratings and adjudication only; no human participants or expert review.',
            'criteria': ['authorization'],
            'items': [{'item_id': f'case-{i}', 'evidence_sha256': digest(f'synthetic evidence {i}'.encode()),
                       'split': 'calibration' if i == 0 else 'validation'} for i in range(6)],
            'groups': [{'group_id': 'assisted-channel', 'item_ids': ['case-2', 'case-3', 'case-4', 'case-5']}],
            'raters': ['reviewer-a', 'reviewer-b', 'reviewer-c'], 'adjudicators': ['review-chair']}
    votes = [('pass', 'pass', 'pass'), ('fail', 'fail', 'fail'), ('pass', 'pass', 'fail'),
             ('pass', 'pass', None), ('pass', 'abstain', 'pass'), ('pass', 'fail', 'abstain')]
    ratings = {'format_version': 'aau-reference-ratings/1.0', 'rubric_sha256': plan['rubric_sha256'],
               'rows': [{'item_id': item['item_id'], 'criterion': 'authorization', 'evidence_sha256': item['evidence_sha256'],
                         'rater_id': rater, 'verdict': verdict, 'rationale': 'Constructed panel judgment for the walkthrough.'}
                        for item, decisions in zip(plan['items'], votes)
                        for rater, verdict in zip(plan['raters'], decisions) if verdict is not None]}
    item = plan['items'][-1]
    adjudications = {'format_version': 'aau-reference-adjudications/1.0', 'rubric_sha256': plan['rubric_sha256'],
                     'ratings_sha256': digest(rendered(ratings)),
                     'rows': [{'item_id': item['item_id'], 'criterion': 'authorization',
                               'evidence_sha256': item['evidence_sha256'], 'adjudicator_id': 'review-chair',
                               'verdict': 'fail', 'rationale': 'Constructed resolution: the recorded action lacked authorization.'}]}
    return plan, ratings, adjudications


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite a reference-review demo destination')
    plan, ratings, adjudications = example_inputs()
    plan_raw, ratings_raw, adjudications_raw = map(rendered, (plan, ratings, adjudications))
    pin = digest(plan_raw)
    report, payloads = reference_payloads(plan_raw, ratings_raw, adjudications_raw, plan_sha256=pin)
    candidate = {'format_version': 'aau-grader-judgments/1.0', 'rubric_sha256': plan['rubric_sha256'],
                 'grader_id': 'synthetic-all-pass', 'rows': [
                     {'item_id': item['item_id'], 'criterion': 'authorization', 'evidence_sha256': item['evidence_sha256'],
                      'verdict': 'pass'} for item in plan['items']]}
    grader_pin = report['grader_plan_sha256']
    grader = review_grader(payloads['grader-plan.json'], payloads['reference.json'], rendered(candidate), plan_sha256=grader_pin)
    lines = ['# Where did the reference labels come from?', '',
             'All ratings, identities, reasons, and evidence fingerprints here are constructed. No human study occurred.', '',
             'Open packet/review.html locally. The packet is an offline, script-free review, not approval.', '',
             '| Case | Panel | Exported reference |', '|---|---|---|',
             '| case-0 (calibration) | Three pass | pass |',
             '| case-1 | Three fail | fail |',
             '| case-2 | Two pass, one fail | disputed — no majority shortcut |',
             '| case-3 | Two pass, one missing | unreviewed — no partial consensus |',
             '| case-4 | Two pass, one abstain | unreviewed |',
             '| case-5 | Pass, fail, abstain | fail by recorded adjudication; conflict retained |', '',
             'There are 18 assigned ratings and 17 submissions. Two original conflicts remain visible.',
             'One adjudication changes a disputed reference. Validation still has only 2/5 decided references.',
             'The constructed all-pass grader has two false passes on those decided validation references.', '',
             'Replay from this directory with the same trusted harness. Both pins below are demo-only:', '',
             '```bash', f'aau reference-review verify packet --plan-sha256 {pin}',
             f'aau grader-review packet/grader-plan.json packet/reference.json candidate.json --plan-sha256 {grader_pin} --verify grader-report.json',
             '```', '',
             'For real work, review and independently retain the panel plan and exported grader-plan hash.',
             'Protect originals and reasons. Agreement, adjudication, and successful replay do not establish truth,',
             'reviewer expertise or independence, accessibility conformance, compliance, or government adoption.', '']
    directory.mkdir(parents=True, exist_ok=False)
    create_reference_pack(plan_raw, ratings_raw, adjudications_raw, directory / 'packet', plan_sha256=pin)
    verify_reference_pack(directory / 'packet', plan_sha256=pin)
    for name, raw in {'candidate.json': rendered(candidate), 'grader-report.json': rendered(grader),
                      'README.md': '\n'.join(lines).encode()}.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw)
