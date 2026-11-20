"""Create synthetic agency lifecycle cost scenarios without pricing services or model calls."""

import argparse
from copy import deepcopy
from pathlib import Path
import sys

from .agent_bom import digest, rendered
from .lifecycle_cost import review_costs


def example_inputs():
    items = [
        ('setup', 'implementation', 'one_time', '50000', 'Implementation and migration'),
        ('model', 'model_usage', 'per_case', '0.01', 'Declared all-attempt model allowance per case'),
        ('hosting', 'infrastructure', 'per_month', '1200', 'Infrastructure allowance'),
        ('review', 'human_review', 'per_review', '4.5', 'Human review event allowance, not a staffing model'),
        ('observe', 'monitoring', 'per_month', '800', 'Monitoring and incident preparation'),
        ('assurance', 'security_privacy_accessibility', 'per_month', '500', 'Assurance activities allowance'),
        ('exit', 'transition_exit', 'one_time', '15000', 'Export, transfer, and exit rehearsal'),
    ]
    plan = {'plan_version': 'aau-lifecycle-cost-plan/1.0', 'currency': 'USD',
            'assumptions': 'Synthetic constant-dollar arithmetic only. No market quotes, measured savings, or actual government workload.',
            'cost_items': [{'cost_id': name, 'category': category, 'driver': driver, 'description': description}
                           for name, category, driver, _, description in items],
            'scenarios': [
                {'scenario_id': 'expected', 'months': 12, 'cases': 300000, 'reviews': 60000,
                 'assumptions': 'Constructed annual workload and review-event count; not inferred from benchmark scores.'},
                {'scenario_id': 'review-surge', 'months': 12, 'cases': 300000, 'reviews': 120000,
                 'assumptions': 'Only declared review events double; same supplied rates and other quantities.'},
                {'scenario_id': 'case-surge', 'months': 12, 'cases': 900000, 'reviews': 180000,
                 'assumptions': 'Both case and review quantities triple; not a one-factor sensitivity result.'},
                {'scenario_id': 'shorter-horizon', 'months': 6, 'cases': 300000, 'reviews': 60000,
                 'assumptions': 'Only recurring months change; all one-time and per-event obligations retained.'},
            ]}
    rates = {'format_version': 'aau-lifecycle-cost-rates/1.0', 'currency': 'USD',
             'rates': [{'cost_id': name, 'unit_cost_usd': rate, 'basis': 'synthetic',
                        'source_ref': 'constructed-example', 'assumptions': 'Illustrative input, not observed or quoted pricing.'}
                       for name, _, _, rate, _ in items]}
    missing_exit = deepcopy(rates)
    missing_exit['rates'][-1].update(unit_cost_usd=None, basis='unknown', source_ref='not-supplied',
                                   assumptions='Exit cost has not been obtained. Do not treat it as zero.')
    return plan, {'complete': rates, 'unknown-exit': missing_exit,
                  'no-rates': {'format_version': rates['format_version'], 'currency': 'USD', 'rates': []}}


def create_demo(directory):
    plan, variants = example_inputs()
    raw = rendered(plan)
    pin = digest(raw)
    payloads = {'plan.json': raw}
    lines = ['# An inexpensive model call is not a lifecycle budget', '',
             'Synthetic examples only. No market prices, invoices, agency data, or measured savings.', '',
             '| Rates | Scenario | Known subtotal USD | Declared total USD | Unknown active items |',
             '|---|---|---:|---:|---|']
    commands = []
    for name, rates in variants.items():
        rates_raw = rendered(rates)
        report = review_costs(raw, rates_raw, plan_sha256=pin)
        payloads[f'{name}-rates.json'] = rates_raw
        payloads[f'{name}-report.json'] = rendered(report)
        for scenario in report['scenarios']:
            total = scenario['declared_total_usd'] or 'UNKNOWN'
            unknown = ', '.join(scenario['unknown_active_cost_ids']) or 'none'
            lines.append(f"| {name} | {scenario['scenario_id']} | {scenario['known_subtotal_usd']} | {total} | {unknown} |")
        commands.append(f'aau lifecycle-cost plan.json {name}-rates.json --plan-sha256 {pin} --verify {name}-report.json')
    lines += ['', 'In the complete expected scenario, model usage is $3,000 of the $368,000 declared total.',
              'Doubling only review events adds $270,000 under these supplied assumptions; this is not a workforce forecast.',
              'When exit cost is unknown, $353,000 is only a known subtotal, not a complete estimate.',
              'Changing cases and reviews together is explicitly marked as a multiple-quantity comparison.', '',
              'From this directory, use a matching trusted harness:', '', '```bash', *commands, '```', '',
              'The shown pin is for synthetic reproduction only. Real review requires independently controlled plan pins.',
              'Keep all inputs and reports. Inspect assumptions, rate sources, omissions, double counting, minimums,',
              'and nonlinear prices with qualified acquisition/cost reviewers before any use. Exit 0 means a valid',
              'diagnostic, even with unknown totals; it is not affordability, funding, compliance, or award approval.', '']
    payloads['README.md'] = '\n'.join(lines).encode()
    directory.mkdir(parents=True, exist_ok=False)
    for name, payload in payloads.items():
        with (directory / name).open('xb') as stream:
            stream.write(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='aau lifecycle-cost-demo', description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        create_demo(args.out)
        print('Created three synthetic rate variants across four lifecycle scenarios. Not a government cost estimate.')
        return 0
    except (ValueError, OSError) as exc:
        print(f'error: lifecycle demo could not be created ({type(exc).__name__}).', file=sys.stderr)
        return 2
