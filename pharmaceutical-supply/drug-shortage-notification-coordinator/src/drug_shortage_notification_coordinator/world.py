"""Domain configuration and synthetic world wrapper."""

from aau_harness.decision_gate import (
    GateScenario,
    generate_gate_scenarios,
    load_gate_scenarios,
    save_gate_scenarios,
    search_gate_policy as shared_search_gate_policy,
)

from .domain import CONFIG

Scenario = GateScenario


def generate_scenarios(n: int = 32, seed: int = CONFIG["seed"]):
    return generate_gate_scenarios(CONFIG, n=n, seed=seed)


def save_scenarios(scenarios, path: str) -> None:
    save_gate_scenarios(scenarios, path)


def load_scenarios(path: str):
    return load_gate_scenarios(path)


def search_policy(query: str, top_k: int = 4):
    return shared_search_gate_policy(CONFIG, query, top_k=top_k)
