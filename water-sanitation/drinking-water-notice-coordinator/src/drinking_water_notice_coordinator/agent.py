"""Domain prompt and deterministic comparison backend."""

from aau_harness.evidence_service import (
    ServiceMockBackend,
    build_system_prompt,
)

from .domain import CONFIG

SYSTEM_PROMPT = build_system_prompt(CONFIG)


class MockBackend(ServiceMockBackend):
    def __init__(self):
        super().__init__(CONFIG)
