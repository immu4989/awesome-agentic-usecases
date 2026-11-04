"""Demonstrate label minimization on synthetic service inputs; never a publication approval."""

import argparse
from pathlib import Path

from aau_harness.agent_bom import load_json
from aau_harness.eval_service_traces import verify_service_trace_pack
from aau_harness.service_reproducer import create_reproducer, verify_reproducer, verify_source


ROOT = Path(__file__).resolve().parents[3]


def create_example(directory):
    suite = load_json(ROOT / 'public-value-review/examples/suite.json')
    traces = load_json(ROOT / 'public-value-review/examples/traces.json')
    plan = {'plan_version': 'aau-service-trace-import/1.0',
            'source_label': 'SYNTHETIC-SOURCE-NAME-NOT-FOR-EXPORT', 'n_repeats': 1}
    report = create_reproducer(plan, suite, traces, directory)
    if report['observation_count'] != 2 or report['failed_observation_count'] != 1:
        raise RuntimeError('synthetic reproducer changed its expected coverage or failures')
    if verify_reproducer(directory) != report or verify_source(directory, plan, suite, traces) != report:
        raise RuntimeError('synthetic reproducer does not recompute')
    if verify_service_trace_pack(directory / 'service')['status'] != 'evidence_failed':
        raise RuntimeError('synthetic service failure was hidden')
    print('Created ten-file synthetic reproducer: 2 observations, 1 service failure; no sharing approval.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_example(parser.parse_args().out)
