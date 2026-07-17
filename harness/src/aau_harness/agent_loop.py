"""The generic tool-use agent loop shared by every use case.

A use case supplies the domain: a system prompt, tool schemas, a tool executor,
and the name of its terminal submit tool. The loop owns turn-taking, usage
accounting, refusal handling, and the no-submission failure path. Backends are
duck-typed: anything with `.create(system, messages, tools)` returning an
object with `.content` blocks, `.stop_reason`, and `.usage` works — the real
SDK, the OpenAI-compat adapter, or a use case's deterministic mock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .cost import CostTracker


class Block:
    """Duck-typed content block for mock backends (mirrors SDK block attrs)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class MockUsage:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0


@dataclass
class AgentRun:
    submitted: bool
    submission: dict | None
    n_turns: int
    tool_calls: list = field(default_factory=list)
    refused: bool = False
    error: str | None = None


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8"):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model

    def create(self, system: str, messages: list, tools: list):
        return self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=tools,
            messages=messages,
        )


def run_tool_agent(
    backend,
    system_prompt: str,
    tool_schemas: list[dict],
    user_message: str,
    execute_tool: Callable[[str, dict], str],
    submit_tool: str,
    cost: CostTracker,
    max_turns: int = 8,
) -> AgentRun:
    messages: list = [{"role": "user", "content": user_message}]
    tool_calls: list = []

    for turn in range(1, max_turns + 1):
        response = backend.create(system_prompt, messages, tool_schemas)
        cost.add_usage(response.usage)

        if getattr(response, "stop_reason", None) == "refusal":
            return AgentRun(False, None, turn, tool_calls, refused=True)

        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            return AgentRun(False, None, turn, tool_calls,
                            error="ended turn without submitting a decision")

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for tu in tool_uses:
            tool_calls.append({"name": tu.name, "input": tu.input})
            if tu.name == submit_tool:
                return AgentRun(True, tu.input, turn, tool_calls)
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": execute_tool(tu.name, tu.input),
            })
        messages.append({"role": "user", "content": results})

    return AgentRun(False, None, max_turns, tool_calls,
                    error=f"no submission within {max_turns} turns")


def make_backend(kind: str, model: str | None = None, mock_factory: Callable | None = None):
    """Resolve a backend by name: 'mock' (use case supplies the factory),
    'anthropic', or any provider in llm_providers.PROVIDERS."""
    if kind == "mock":
        if mock_factory is None:
            raise ValueError("this use case has no mock backend registered")
        return mock_factory()
    if kind == "anthropic":
        return AnthropicBackend(model=model or "claude-opus-4-8")
    from .llm_providers import PROVIDERS, OpenAICompatBackend

    if kind in PROVIDERS:
        return OpenAICompatBackend(kind, model=model)
    raise ValueError(f"unknown backend {kind!r}")
