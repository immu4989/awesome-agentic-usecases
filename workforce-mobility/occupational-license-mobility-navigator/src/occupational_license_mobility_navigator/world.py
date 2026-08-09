"""Domain configuration and synthetic world wrapper."""

from aau_harness.evidence_service import (
    ServiceScenario,
    generate_service_scenarios,
    gold_contract as shared_gold_contract,
    load_service_scenarios,
    save_service_scenarios,
    search_policy as shared_search_policy,
)

from .domain import CONFIG

Scenario = ServiceScenario


def generate_scenarios(n: int = 32, seed: int = CONFIG["seed"]):
    return generate_service_scenarios(CONFIG, n=n, seed=seed)


def save_scenarios(scenarios, path: str) -> None:
    save_service_scenarios(scenarios, path)


def load_scenarios(path: str):
    return load_service_scenarios(path)


def gold_contract(record: dict, evidence_vault: dict, service_preference: dict, policy_snapshot: dict):
    return shared_gold_contract(CONFIG, record, evidence_vault, service_preference, policy_snapshot)


def search_policy(query: str, top_k: int = 3):
    return shared_search_policy(CONFIG, query, top_k=top_k)
