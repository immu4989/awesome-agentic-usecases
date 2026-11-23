"""Construct a source-linked review handoff; no real agency evidence or public benefit measured."""

from copy import deepcopy
from pathlib import Path
import tempfile

from .agent_bom import digest, rendered
from .coverage_review import create_coverage_pack
from .eval_import import import_observations
from .eval_pack import create_pack
from .eval_paired import create_paired_pack
from .evidence_index import create_index, verify_index
from .inspect_pack import _capture
from .paired_demo import example_inputs


def build_inputs(directory):
    """Fixed test fixture only; never infer receiving-team pins from production deliveries."""
    paired, baseline, candidate = example_inputs()
    delivery = directory / 'delivery'
    delivery.mkdir(parents=True)
    paired_raw = rendered(paired)
    create_paired_pack(paired_raw, rendered(baseline), rendered(candidate), delivery / 'comparison',
                       plan_sha256=digest(paired_raw))
    # The policy baseline is a historical reference under the candidate's configuration,
    # not the different system used in the paired comparison. Only candidate data is bound across all three.
    recording = {'format_version': 'aau-recorded-observations/1.0', 'source_label': 'Synthetic historical reference',
                 'scenario_ids': paired['scenario_ids'], 'n_repeats': paired['n_repeats'],
                 'observations': [{'scenario_id': row['scenario_id'], 'repeat': row['repeat'],
                                   'metrics': {'completion': 1, 'unauthorized': 0}} for row in candidate['results']]}
    historical = import_observations(recording)
    historical['evaluation_context'] = candidate['evaluation_context']
    policy = {'policy_version': 'aau-evaluation-review-policy/1.0', 'scenario_ids': paired['scenario_ids'],
              'minimum_repeats': paired['n_repeats'], 'metrics': [
                  {'metric': r['metric'], 'direction': r['direction'], 'candidate_observation_limit': r['limit'],
                   'max_mean_regression': 0, 'max_regressed_scenarios': 0} for r in paired['criteria']]}
    create_pack(policy, historical, candidate, delivery / 'policy')
    coverage = {'plan_version': 'aau-coverage-plan/1.0', 'purpose': 'Synthetic channel census, not a real population.',
                'dimensions': {'channel': ['self-service', 'assisted']}, 'minimum_cases': 1,
                'minimum_complete_repeats': 2, 'required_metrics': ['completion', 'unauthorized'], 'cell_overrides': []}
    inventory = {'inventory_version': 'aau-coverage-inventory/1.0', 'source_label': 'Constructed classifications',
                 'items': [{'scenario_id': s, 'scenario_sha256': paired['scenario_sha256'][s],
                            'attributes': {'channel': 'assisted' if i >= 10 else 'self-service'}}
                           for i, s in enumerate(paired['scenario_ids'])]}
    coverage_raw = rendered(coverage)
    create_coverage_pack(coverage_raw, rendered(inventory), rendered(candidate), delivery / 'coverage',
                         plan_sha256=digest(coverage_raw))
    intake = {'request_version': 'aau-evidence-intake-request/1.0', 'profile': 'evaluation-review',
              'pack_version': 'aau-evaluation-review-pack/1.0', 'input_format': 'evaluations',
              'pinned_inputs': {'policy': digest(rendered(policy)), 'baseline': digest(rendered(historical))}}
    request = {'request_version': 'aau-evidence-index-request/1.0',
               'purpose': 'Synthetic acquisition-review handoff: separate findings, no agency approval or field evidence.',
               'items': [{'item_id': 'policy', 'profile': 'policy-review', 'purpose': 'Check every authorization obligation.',
                          'controls': {'intake_request': intake}},
                         {'item_id': 'comparison', 'profile': 'paired-review', 'purpose': 'Retain newly introduced failures.',
                          'controls': {'plan_sha256': digest(paired_raw)}},
                         {'item_id': 'coverage', 'profile': 'coverage-review', 'purpose': 'Expose missing declared conditions.',
                          'controls': {'plan_sha256': digest(coverage_raw)}}],
               'bindings': [{'left': {'item_id': 'policy', 'role': 'candidate'},
                             'right': {'item_id': other, 'role': role}}
                            for other, role in (('comparison', 'candidate'), ('coverage', 'evaluation'))]}
    return request, delivery, coverage_raw, inventory, candidate


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite evidence-index demo')
    directory.mkdir(parents=True, exist_ok=False)
    commands = []
    for variant in ('complete-with-failed-policy', 'missing-coverage', 'mismatched-evaluation', 'invalid-comparison', 'changed-controls'):
        with tempfile.TemporaryDirectory(prefix='aau-index-example-') as temporary:
            root = Path(temporary)
            request, delivery, coverage_raw, inventory, candidate = build_inputs(root)
            if variant == 'missing-coverage':
                # Construct a separate delivery, preserving the original inputs; no deletion of evidence.
                files, _ = _capture(delivery)
                selected = root / 'selected'
                for name, raw in files.items():
                    if not name.startswith('coverage/'):
                        target = selected / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(raw)
                delivery = selected
            elif variant == 'mismatched-evaluation':
                # A valid coverage packet for a different synthetic evaluation is not the paired input.
                files, _ = _capture(delivery)
                selected = root / 'selected'
                for name, raw in files.items():
                    if not name.startswith('coverage/'):
                        target = selected / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(raw)
                different = import_observations({'format_version': 'aau-recorded-observations/1.0',
                    'source_label': 'Constructed different evaluation; not the reviewed candidate output',
                    'scenario_ids': [r['scenario_id'] for r in inventory['items']], 'n_repeats': candidate['n_repeats'],
                    'observations': [{'scenario_id': r['scenario_id'], 'repeat': r['repeat'],
                                      'metrics': {'completion': 1, 'unauthorized': 0}} for r in candidate['results']]})
                different['evaluation_context'] = candidate['evaluation_context']
                create_coverage_pack(coverage_raw, rendered(inventory), rendered(different), selected / 'coverage',
                                     plan_sha256=digest(coverage_raw))
                delivery = selected
            elif variant == 'invalid-comparison':
                with (delivery / 'comparison/report.json').open('ab') as stream:
                    stream.write(b' ')
            elif variant == 'changed-controls':
                request = deepcopy(request)
                request['items'][0]['controls']['intake_request']['pinned_inputs']['baseline'] = '0' * 64
            raw = rendered(request)
            pin = digest(raw)
            report = create_index(raw, delivery, directory / variant, request_sha256=pin)
            if report != verify_index(directory / variant, request_sha256=pin):
                raise ValueError('synthetic index replay differs from creation')
            commands.append(f'aau evidence-index verify {variant} --request-sha256 {pin}  # exit {report["exit_code"]}')
    lines = ['# One handoff does not mean one approval', '',
             'Fixed synthetic packets only. No model, agency data, or measured public benefit.', '',
             '- complete-with-failed-policy: every packet verifies and candidate bytes match, but the policy fails.',
             '  Paired improvement and coverage cannot cancel that failure. Exit 0 concerns delivery verification only.',
             '- missing-coverage: the required slot remains missing; its binding is not checked. Exit 1.',
             '- mismatched-evaluation: coverage verifies over a different synthetic evaluation with no failures,',
             '  but its evaluation bytes do not match the reviewed candidate. The binding fails. Exit 1.',
             '  Bindings are deliberately byte-exact; even whitespace-only export changes also fail them.',
             '- invalid-comparison: a modified derived report remains in the retained evidence and fails verification. Exit 1.',
             '- changed-controls: a valid policy packet does not match the independently requested baseline pin. Exit 1.', '',
             'Only candidate data is bound across the three reviews. The policy uses a historical same-configuration',
             'baseline; the paired comparison uses a different system. No association between those baselines is asserted.', '',
             'Open only the generated top-level review.html after inspecting the files. Complete original member bytes,',
             'including invalid contents, are retained under evidence/. Native findings are in report.json.',
             'Keep outputs local; an index does not sanitize evidence or authorize sharing.', '',
             'Replay with the matching trusted harness (these pins are example-only):', '', '```bash', *commands, '```', '',
             'For real work, protect the reviewed request and its expected hash independently of the delivery.',
             'Exit 2 means invalid request/inventory or failed replay. No automatic approval follows any exit code.', '']
    (directory / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
