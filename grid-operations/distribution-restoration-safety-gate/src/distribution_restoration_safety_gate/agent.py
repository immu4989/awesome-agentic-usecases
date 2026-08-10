"""Domain prompt and deterministic comparison backend."""

from aau_harness.decision_gate import GateMockBackend, build_gate_system_prompt

from .domain import CONFIG

SYSTEM_PROMPT = build_gate_system_prompt(CONFIG)


class MockBackend(GateMockBackend):
    def __init__(self):
        super().__init__(CONFIG)
