"""Exact Public Value Contract scoring and evaluation wrapper."""

from aau_harness.evidence_service import (
    evaluate_service,
    save_service_results,
    score_service_run,
)

from .agent import MockBackend
from .domain import CONFIG


def score_run(scenario, run, session):
    return score_service_run(scenario, run, session)


def evaluate(scenarios, backend_kind="mock", model=None, repeats=3, progress=None):
    return evaluate_service(
        CONFIG,
        scenarios,
        MockBackend,
        backend_kind=backend_kind,
        model=model,
        repeats=repeats,
        progress=progress,
    )


def save_results(aggregate, backend_kind: str, model: str, out_dir: str):
    return save_service_results(aggregate, backend_kind, model, out_dir)
