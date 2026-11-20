"""Construct condition-coverage gaps without treating synthetic scores as public benefit."""

from copy import deepcopy

from .agent_bom import AgentBomError, digest, rendered
from .coverage_review import create_coverage_pack, coverage_payloads, verify_coverage_pack
from .eval_import import import_observations


def example_inputs():
    plan = {'plan_version': 'aau-coverage-plan/1.0',
            'purpose': 'Constructed service-routing coverage across channel and language; no actual service evaluation.',
            'dimensions': {'channel': ['self-service', 'assisted'], 'language': ['english', 'spanish']},
            'minimum_cases': 1, 'minimum_complete_repeats': 2,
            'required_metrics': ['completion', 'authorization'], 'cell_overrides': []}
    items = [{'scenario_id': f'case-{i}', 'scenario_sha256': digest(f'synthetic scenario contents {i}'.encode()),
              'attributes': {'channel': channel, 'language': language}}
             for i, (channel, language) in enumerate((('self-service', 'english'), ('self-service', 'english'),
                  ('assisted', 'english'), ('self-service', 'spanish'), ('assisted', 'spanish')))]
    variants = {}
    for name in ('gap', 'uncertain', 'covered'):
        selected = deepcopy(items[:-1] if name == 'gap' else items)
        if name == 'uncertain':
            selected[-1]['attributes']['language'] = None
        inventory = {'inventory_version': 'aau-coverage-inventory/1.0', 'source_label': 'Constructed cases and annotations',
                     'items': selected}
        recording = {'format_version': 'aau-recorded-observations/1.0', 'source_label': 'Constructed all-one scores',
                     'scenario_ids': [i['scenario_id'] for i in selected], 'n_repeats': 10,
                     'evaluation_context': {'context_version': 'aau-evaluation-context/1.0',
                         'scenario_sha256': {i['scenario_id']: i['scenario_sha256'] for i in selected},
                         'config_sha256': digest(b'constructed configuration'),
                         'scoring_sha256': {'constructed': digest(b'constructed scoring')}},
                     'observations': [{'scenario_id': i['scenario_id'], 'repeat': repeat,
                                       'metrics': {'completion': 1, 'authorization': 1}}
                                      for i in selected for repeat in range(10)]}
        variants[name] = (inventory, import_observations(recording))
    return plan, variants


def create_demo(directory):
    if directory.exists() or directory.is_symlink():
        raise AgentBomError('refusing to overwrite a coverage demo destination')
    plan, variants = example_inputs()
    raw, pin = rendered(plan), digest(rendered(plan))
    for inventory, evaluation in variants.values():
        coverage_payloads(raw, rendered(inventory), rendered(evaluation), plan_sha256=pin)
    directory.mkdir(parents=True, exist_ok=False)
    for name, (inventory, evaluation) in variants.items():
        create_coverage_pack(raw, rendered(inventory), rendered(evaluation), directory / name, plan_sha256=pin)
        verify_coverage_pack(directory / name, plan_sha256=pin)
    lines = ['# Perfect supplied scores can still leave a coverage gap', '',
             'All cases, attributes, fingerprints, and scores here are constructed. No model or public service was tested.', '',
             '| Packet | What the recorded evidence shows | Expected verify exit |', '|---|---|---:|',
             '| gap | 40 all-one observations, but no assisted/Spanish case | 1 |',
             '| uncertain | 50 observations; the added assisted case has unclassified language | 1 |',
             '| covered | The same fifth case is explicitly classified as Spanish; all four declared cells meet their floor | 0 |', '',
             'Open each review.html locally. Ten repeats do not count as ten distinct cases.',
             'Unknown language is not imputed. A counted case still may be synthetic, mislabeled, or semantically duplicated.',
             'Coverage does not assess whether scores pass a performance policy or represent real users.', '',
             'Replay from this directory with the same trusted harness. This pin is demo-only:', '', '```bash',
             f'aau coverage-review verify gap --plan-sha256 {pin}',
             f'aau coverage-review verify uncertain --plan-sha256 {pin}',
             f'aau coverage-review verify covered --plan-sha256 {pin}', '```', '',
             'Exit 1 means a valid report with unmet or unverified coverage, not a broken replay.',
             'Exit 2 means invalid inputs or a pack/pin mismatch. Do not chain the three commands with &&.',
             'For real work, independently review dimensions, floors, exclusions, and the plan pin before evaluation.',
             'Collect authorized, domain-reviewed evidence; do not use this demo as evidence of government adoption,',
             'population coverage, fairness, accessibility conformance, or measured public benefit.', '']
    with (directory / 'README.md').open('xb') as stream:
        stream.write('\n'.join(lines).encode())
