"""Delegation: one agent invoking another as a tool.

A multi-agent system is, mechanically, a nested agent loop. The orchestrator holds a
`delegate` tool; calling it runs a *complete* sub-agent conversation with its own system
prompt, its own tool set, and its own turn budget, and returns that sub-agent's final
submission as the tool result.

Two properties this design keeps, because they are what make the comparison honest:

- **Cost rolls up.** Sub-agent tokens accumulate into the same CostTracker as the
  orchestrator's, so a multi-agent run reports the true total rather than only the
  coordination layer. Orchestration that "wins" by hiding its spend is not winning.
- **The transcript is inspectable.** Every delegation records the brief the orchestrator
  wrote and the payload the specialist returned, so failures at the seam (a brief that
  omitted the deciding fact, a specialist that over-claimed) can be read off the run
  rather than inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .agent_loop import AgentRun, run_tool_agent
from .cost import CostTracker


@dataclass
class Specialist:
    """A sub-agent the orchestrator may call by name."""

    name: str
    description: str          # shown to the orchestrator in the delegate tool schema
    system_prompt: str
    tool_schemas: list
    execute_tool: Callable[[str, dict], str]
    submit_tool: str
    max_turns: int = 8


@dataclass
class DelegationRecord:
    specialist: str
    brief: str
    returned: dict | None
    submitted: bool
    turns: int
    error: str | None = None


@dataclass
class CrewRun:
    """An orchestrator run plus every delegation it made."""

    orchestrator: AgentRun
    delegations: list[DelegationRecord] = field(default_factory=list)

    @property
    def submitted(self) -> bool:
        return self.orchestrator.submitted

    @property
    def submission(self) -> dict | None:
        return self.orchestrator.submission

    @property
    def n_delegations(self) -> int:
        return len(self.delegations)

    def called(self, specialist: str) -> bool:
        return any(d.specialist == specialist for d in self.delegations)


def make_delegate_tool(specialists: dict[str, Specialist]) -> dict:
    """Tool schema the orchestrator sees. One entry per registered specialist."""
    roster = "\n".join(f"- {s.name}: {s.description}" for s in specialists.values())
    return {
        "name": "delegate",
        "description": (
            "Hand a task to a specialist teammate and get their finding back. The "
            "specialist has its own tools and does its own work, but it only knows what "
            "you put in the brief, so state the case and what you need decided.\n\n"
            f"Available specialists:\n{roster}"
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "specialist": {
                    "type": "string",
                    "enum": sorted(specialists),
                    "description": "Which teammate to hand this to",
                },
                "brief": {
                    "type": "string",
                    "description": "What they need to know and what you want decided. They see only this.",
                },
            },
            "required": ["specialist", "brief"],
            "additionalProperties": False,
        },
    }


def run_crew(
    backend,
    orchestrator_prompt: str,
    orchestrator_tools: list,
    user_message: str,
    execute_orchestrator_tool: Callable[[str, dict], str],
    submit_tool: str,
    specialists: dict[str, Specialist],
    cost: CostTracker,
    max_turns: int = 12,
) -> CrewRun:
    """Run an orchestrator that can delegate to sub-agents.

    `execute_orchestrator_tool` handles the orchestrator's own (non-delegate,
    non-submit) tools; `delegate` is intercepted here and turned into a nested run.
    """
    crew = CrewRun(orchestrator=AgentRun(False, None, 0, []))

    def execute(name: str, tool_input: dict) -> str:
        if name != "delegate":
            return execute_orchestrator_tool(name, tool_input)

        import json

        who = tool_input.get("specialist", "")
        brief = tool_input.get("brief", "")
        spec = specialists.get(who)
        if spec is None:
            crew.delegations.append(
                DelegationRecord(who, brief, None, False, 0, error="unknown specialist")
            )
            return json.dumps({"error": f"no specialist named {who!r}",
                               "available": sorted(specialists)})

        # The specialist sees only the brief. That is the point: a fact the
        # orchestrator failed to pass along is genuinely unavailable to it.
        sub = run_tool_agent(
            backend, spec.system_prompt, spec.tool_schemas, brief,
            spec.execute_tool, spec.submit_tool, cost, max_turns=spec.max_turns,
        )
        crew.delegations.append(
            DelegationRecord(
                specialist=who, brief=brief, returned=sub.submission,
                submitted=sub.submitted, turns=sub.n_turns, error=sub.error,
            )
        )
        if not sub.submitted:
            return json.dumps({
                "specialist": who, "returned_finding": False,
                "note": "the specialist did not reach a conclusion; decide without it "
                        "or delegate again with a clearer brief",
            })
        return json.dumps({"specialist": who, "returned_finding": True, **(sub.submission or {})})

    crew.orchestrator = run_tool_agent(
        backend, orchestrator_prompt, orchestrator_tools, user_message,
        execute, submit_tool, cost, max_turns=max_turns,
    )
    return crew
