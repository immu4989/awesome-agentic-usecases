"""Generate fixed synthetic reports for browser checks; accepts no user evidence."""

import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path

from aau_harness.coverage_demo import create_demo as coverage_demo
from aau_harness.candidate_bounds_demo import create_demo as candidate_bounds_demo
from aau_harness.eval_demo import demo_inputs
from aau_harness.eval_pack import create_pack, verify_pack
from aau_harness.grader_compare_demo import create_demo as grader_comparison_demo
from aau_harness.inspect_demo import create_demo as inspect_demo
from aau_harness.paired_demo import create_demo as paired_demo
from aau_harness.evidence_index_demo import create_demo as evidence_index_demo
from aau_harness.reference_demo import create_demo as reference_demo


def create_fixtures(directory):
    if directory.exists() or directory.is_symlink():
        raise ValueError('refusing to overwrite browser fixtures')
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('aau_browser_public_fixtures', root / 'docs/make_evaluation_review_demo.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assets = module.build_assets()
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in assets.items():
        target = directory / 'public' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    reference_demo(directory / 'reference')
    coverage_demo(directory / 'coverage')
    inspect_demo(directory / 'inspect')
    grader_comparison_demo(directory / 'grader-comparison')
    candidate_bounds_demo(directory / 'candidate-bounds')
    paired_demo(directory / 'paired-review')
    evidence_index_demo(directory / 'evidence-index')
    policy, baseline, candidate, diagnostics = deepcopy(demo_inputs())
    # Long supplied identifiers must wrap in prose while tables retain their own scroll area.
    old = 'completion'
    long_metric = '<script>not executable</script>-' + 'long-metric-' * 12
    policy['metrics'][0]['metric'] = long_metric
    diagnostics['criteria'][0]['metric'] = long_metric
    for recording in (baseline, candidate):
        recording.pop('evaluation_context', None)
        for row in recording['observations']:
            row['metrics'][long_metric] = row['metrics'].pop(old)
    create_pack(policy, baseline, candidate, directory / 'stress', recordings=True, diagnostics=diagnostics)
    verify_pack(directory / 'stress', require_recordings=True, require_diagnostics=True)
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    create_fixtures(args.out)
    print('Created fixed synthetic browser fixtures; no user data or external execution.')


if __name__ == '__main__':
    main()
