"""Exact Decision Gate Contract scoring and evaluation wrapper."""

from aau_harness.decision_gate import evaluate_gate, save_gate_results, score_gate_run

from .agent import MockBackend
from .domain import CONFIG


def score_run(scenario, run, session):
    return score_gate_run(scenario, run, session)


def evaluate(scenarios, backend_kind="mock", model=None, repeats=3, progress=None):
    return evaluate_gate(
        CONFIG,
        scenarios,
        MockBackend,
        backend_kind=backend_kind,
        model=model,
        repeats=repeats,
        progress=progress,
    )


def save_results(aggregate, backend_kind: str, model: str, out_dir: str):
    return save_gate_results(aggregate, backend_kind, model, out_dir)
