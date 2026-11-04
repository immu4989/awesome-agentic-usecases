"""Synthetic reviewer-request contrasts; local fixture hashes are not independent approval."""

import argparse
from copy import deepcopy
from pathlib import Path

from aau_harness.agent_bom import digest, rendered, write_json
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_pack import create_pack
from aau_harness.intake_review import review_intake


def create_example(directory):
    policy, baseline, repaired, diagnostics = demo_inputs()
    # Defined from known fixture control inputs BEFORE any delivered candidate pack is inspected.
    # In production a separate authorized reviewer must choose these values and protect the expected pin.
    request = {'request_version': 'aau-evidence-intake-request/1.0', 'profile': 'evaluation-review',
               'pack_version': 'aau-evaluation-review-pack/2.0', 'input_format': 'recordings',
               'pinned_inputs': {name: digest(rendered(value)) for name, value in (
                   ('policy', policy), ('baseline', baseline), ('diagnostics', diagnostics))}}
    raw = rendered(request)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(request, directory / 'request.json')
    relaxed = deepcopy(policy)
    relaxed['metrics'][1]['candidate_observation_limit'] = 1
    expected = {'repaired': ('request_constraints_met', [], []),
                'failed': ('request_constraints_not_met', [], ['policy_and_any_candidate_budget']),
                'relaxed-policy': ('request_constraints_not_met', ['policy'], [])}
    for name, supplied_policy, candidate in (('repaired', policy, repaired), ('failed', policy, baseline),
                                             ('relaxed-policy', relaxed, baseline)):
        folder = directory / name
        create_pack(supplied_policy, baseline, candidate, folder, recordings=True, diagnostics=diagnostics)
        result = review_intake(raw, folder, request_sha256=digest(raw))
        if (result['status'], result['unmatched_input_roles'], result['failed_constraints']) != expected[name]:
            raise RuntimeError('synthetic intake outcome differs from its contract')
        write_json(result, directory / f'{name}-intake.json')
    guide = f'''AAU synthetic receiving-team request walkthrough

All inputs and measurements are constructed. No real service or model was run.
The request is assembled from known fixture controls before creating the candidate packs.
This local hash illustrates plumbing, NOT independent approval or reviewer identity:

{digest(raw)}

From this directory, using the same trusted harness:

aau review-intake request.json repaired --request-sha256 {digest(raw)} --verify repaired-intake.json
aau review-intake request.json failed --request-sha256 {digest(raw)} --verify failed-intake.json
aau review-intake request.json relaxed-policy --request-sha256 {digest(raw)} --verify relaxed-policy-intake.json

Expected exits: repaired=0, failed=1, relaxed-policy=1. Exit 2 means invalid input or verification.
The relaxed-policy pack fully verifies and passes its supplied policy, but does not satisfy
the receiver's pinned policy. The failed pack matches all control pins but fails its policy.
All three outcomes are preserved. Open each pack's review.html AFTER verification for details.

For real intake, independently select the exact profile, version, source format, and every
control input. Pin the exact exported member bytes, which may differ from original JSON
formatting. Protect the reviewed request's expected hash separately from delivered evidence.
Never compute that expected approval hash from candidate-controlled input in the same job.
Do not copy synthetic context hashes or thresholds onto real observations. Missing context
fails this intake gate, even if a legacy descriptive pack otherwise verifies successfully.

Keep the request, all three complete packs, and reports. A report alone cannot reverify itself.
No signatures, source authenticity, procurement compliance, population effectiveness,
privacy permission, or deployment approval are established. Inspect sensitive data before sharing.
This guide is written last; interrupted output must not be treated as completed evidence.
'''
    (directory / 'README.txt').write_text(guide, encoding='utf-8')
    print('Created three synthetic intake contrasts: matched, failed policy, and substituted policy.')
    return expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
