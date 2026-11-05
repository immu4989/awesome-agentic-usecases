"""Six offline CI-reporting contrasts, using constructed evidence and no hosted CI service."""

import argparse
from copy import deepcopy
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET

from aau_harness.agent_bom import digest, rendered, write_json
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_pack import create_pack
from aau_harness.evidence_ci import export_ci


def create_example(directory):
    policy, baseline, repaired, diagnostics = demo_inputs()
    budget = {'plan_version': 'aau-operating-budget/1.0', 'scenario_ids': policy['scenario_ids'], 'minimum_repeats': 4,
              'criteria': diagnostics['criteria'], 'cost_basis': 'synthetic', 'groups': [], 'limits': {'total_cost_usd': 2}}
    # Chosen fixture controls BEFORE delivered packs exist; not independent production approval.
    request = {'request_version': 'aau-evidence-intake-request/1.0', 'profile': 'evaluation-review',
               'pack_version': 'aau-evaluation-review-pack/3.0', 'input_format': 'recordings',
               'pinned_inputs': {role: digest(rendered(value)) for role, value in (
                   ('policy', policy), ('baseline', baseline), ('diagnostics', diagnostics), ('operating_budget', budget))}}
    plan = {'plan_version': 'aau-evidence-series-plan/1.0', 'checkpoint_ids': ['before', 'gap', 'after']}
    raw, plan_raw = rendered(request), rendered(plan)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(request, directory / 'request.json')
    write_json(plan, directory / 'plan.json')
    unknown = deepcopy(repaired)
    del unknown['observations'][0]['cost_usd']
    relaxed = deepcopy(policy)
    relaxed['metrics'][1]['candidate_observation_limit'] = 1
    for name, supplied_policy, candidate in [('passed', policy, repaired), ('failed', policy, baseline),
                                             ('unknown', policy, unknown), ('substituted', relaxed, baseline)]:
        create_pack(supplied_policy, baseline, candidate, directory / 'sources' / name,
                    recordings=True, diagnostics=diagnostics, operating_budget=budget)
    shutil.copytree(directory / 'sources/passed', directory / 'sources/invalid')
    (directory / 'sources/invalid/review.json').write_bytes(b'{}')  # Deliberate invalid-evidence control.
    shutil.copytree(directory / 'sources/failed', directory / 'history/before')
    shutil.copytree(directory / 'sources/passed', directory / 'history/after')
    expected = {'passed': 0, 'failed': 1, 'unknown': 1, 'substituted': 1, 'invalid': 2, 'history': 1}
    commands = []
    for name, code in expected.items():
        is_series = name == 'history'
        source = directory / ('history' if is_series else f'sources/{name}')
        kwargs = {'plan_raw': plan_raw, 'plan_sha256': digest(plan_raw)} if is_series else {}
        bundle = directory / 'reports' / name
        report = export_ci(raw, source, request_sha256=digest(raw), out=bundle, **kwargs)
        replay = export_ci(raw, source, request_sha256=digest(raw), verify=bundle, **kwargs)
        xml = ET.fromstring((bundle / 'junit.xml').read_bytes())
        if report != replay or report['exit_code'] != code or len(xml.findall('.//testcase')) != report['counts']['tests']:
            raise RuntimeError('synthetic CI review differs from its expected outcome')
        mode = f'series plan.json request.json history --plan-sha256 {digest(plan_raw)}' if is_series else f'intake request.json sources/{name}'
        commands.append(f'aau review-ci {mode} --request-sha256 {digest(raw)} --verify reports/{name}  # expected exit {code}')
    guide = '''AAU synthetic evidence CI walkthrough

All measurements are constructed, not real agent runs or independent production approval.
passed meets the request; failed retains the policy failure; unknown retains unavailable cost;
substituted passes its own changed policy but fails the pinned request; invalid retains an
error diagnostic without claiming to bind invalid bytes. history retains an earlier failure
AND a gap even though its latest checkpoint passes.

Every reports/ subfolder contains report.json, junit.xml, summary.md, and manifest.json.
Open summary.md for the overview. JUnit counts are mechanical review checks, NOT scenarios,
model executions, independent observations, statistical confidence, or deployment approval.
No elapsed times are fabricated. No CI service, adapter, model, or network request is run.

From this directory with the matching trusted harness, reverify against original evidence:

''' + '\n'.join(commands) + '''

Production reviewers must separately choose and protect expected request and plan hashes;
never compute an expected approval hash from candidate-controlled files in the same job.
Keep complete sources and controls, not just the four-file presentation. Invalid evidence
has no verified inventory; the same error diagnostic cannot prove its original byte identity.
Do not suppress nonzero CLI exits. Unknown/gap/error results are not skipped or passed.
Inspect data and artifact access rules before publishing: JSON retains checkpoint IDs/hashes,
and even ordinal outcomes disclose review structure. No anonymization or sharing approval.
The guide is written last, after all expected outcomes and XML structure have been checked.
'''
    (directory / 'README.txt').write_text(guide, encoding='utf-8')
    print('Created six recomputable CI presentation examples, including unknown, invalid, and gap evidence.')
    return expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
