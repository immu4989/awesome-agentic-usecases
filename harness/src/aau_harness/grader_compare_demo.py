"""Construct paired grader examples with corrections, concealed gaps, and a net-score trap."""

from copy import deepcopy

from .agent_bom import digest, rendered
from .grader_compare import create_comparison, verify_comparison
from .grader_demo import example_inputs


def comparison_inputs():
    plan, reference, graders = example_inputs()
    baseline = graders['group-blind']
    abstained = deepcopy(baseline)
    abstained['grader_id'] = 'synthetic-abstention-trap'
    for row in abstained['rows'][6:8]:
        row['verdict'] = 'abstain'
    missing = deepcopy(abstained)
    missing['grader_id'] = 'synthetic-omission-trap'
    missing['rows'] = missing['rows'][:6] + missing['rows'][8:]
    net = deepcopy(graders['exact-on-decided'])
    net['grader_id'] = 'synthetic-net-gain-with-regression'
    net['rows'][2]['verdict'] = 'fail'
    return plan, reference, baseline, {'corrected': graders['exact-on-decided'], 'abstention-trap': abstained,
                                        'omission-trap': missing, 'net-gain-with-regression': net}


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite grader comparison demo')
    plan, reference, baseline, candidates = comparison_inputs()
    plan_raw, baseline_raw = rendered(plan), rendered(baseline)
    pins = {'plan_sha256': digest(plan_raw), 'baseline_sha256': digest(baseline_raw)}
    directory.mkdir(parents=True, exist_ok=False)
    commands = []
    for name, candidate in candidates.items():
        create_comparison(plan_raw, rendered(reference), baseline_raw, rendered(candidate), directory / name, **pins)
        verify_comparison(directory / name, **pins)
        commands.append(f'aau grader-compare verify {name} --plan-sha256 {pins["plan_sha256"]} '
                        f'--baseline-sha256 {pins["baseline_sha256"]}')
    lines = ['# Did the new grader fix errors or stop judging?', '',
             'Constructed labels only: no model execution, expert study, or observed public benefit.', '',
             '| Candidate | Validation agreement on own decided pairs | Coverage | Paired change |',
             '|---|---:|---:|---|',
             '| Baseline | 4/6 | 6/8 | Two false passes on assisted-channel cases |',
             '| corrected | 6/6 | 6/8 | Both errors corrected |',
             '| abstention-trap | 4/4 | 4/8 | Both errors become abstentions, not corrections |',
             '| omission-trap | 4/4 | 4/8 | Both errors become missing judgments, not corrections |',
             '| net-gain-with-regression | 5/6 | 6/8 | Two corrections AND one new false failure |', '',
             'Disputed/unreviewed references remain unresolved in every packet. Calibration is not pooled with validation.',
             'Open each review.html offline; review.json includes every 4-by-4 verdict transition for each reference state.',
             'The browser report is a diagnostic, not an approval screen. Exit 0 means it computed, even for the traps.', '',
             'From this directory using the matching trusted harness (example-only pins):', '', '```bash', *commands, '```', '',
             'For real evidence, keep plan and baseline pins under independent receiving-team control.',
             'Retain all seven files, obtain permission before sharing, and protect validation data from tuning.', '']
    with (directory / 'README.md').open('xb') as stream:
        stream.write('\n'.join(lines).encode())
