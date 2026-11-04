"""Repository entry point for the packaged, source-bound failure-bound walkthrough."""

import argparse
from pathlib import Path

from aau_harness.eval_failure_demo import create_demo, example_inputs  # noqa: F401


def create_examples(directory):
    create_demo(directory)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    create_examples(parser.parse_args().out)
