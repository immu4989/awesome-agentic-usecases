"""Tests for the delegation primitive: nested agent runs, cost rollup, brief isolation."""

import json

import pytest

from aau_harness import Block, CostTracker, MockUsage, Specialist, make_delegate_tool, run_crew


def _tool(name, **props):
    return {
        "name": name, "description": name, "strict": True,
        "input_schema": {"type": "object",
                         "properties": {k: {"type": "string", "description": k}
                                        for k in props},
                         "required": list(props), "additionalProperties": False},
    }


class ScriptedBackend:
    """Replays a queue of tool calls, so a crew run is fully deterministic."""

    name = "mock"
    model = "mock"

    def __init__(self, script):
        self.script = list(script)
        self.seen_prompts = []
        self.seen_first_messages = []

    def create(self, system, messages, tools):
        self.seen_prompts.append(system)
        self.seen_first_messages.append(messages[0]["content"])
        name, inp = self.script.pop(0)
        return Block(
            content=[Block(type="tool_use", id=f"t{len(self.seen_prompts)}",
                           name=name, input=inp)],
            stop_reason="tool_use",
            usage=MockUsage(input_tokens=100, output_tokens=10),
        )


def make_specialist(name="checker", submit="report"):
    return Specialist(
        name=name,
        description=f"{name} does a thing",
        system_prompt=f"You are the {name}.",
        tool_schemas=[_tool("look", topic=1), _tool(submit, verdict=1)],
        execute_tool=lambda n, i: json.dumps({"looked_at": i.get("topic")}),
        submit_tool=submit,
    )


def test_delegate_schema_lists_every_specialist():
    specs = {"checker": make_specialist("checker"), "auditor": make_specialist("auditor")}
    schema = make_delegate_tool(specs)
    assert schema["name"] == "delegate"
    assert schema["input_schema"]["properties"]["specialist"]["enum"] == ["auditor", "checker"]
    assert "checker does a thing" in schema["description"]
    assert schema["strict"] is True


def test_delegation_runs_a_full_subagent_and_returns_its_submission():
    specs = {"checker": make_specialist()}
    backend = ScriptedBackend([
        ("delegate", {"specialist": "checker", "brief": "look at the invoice"}),
        ("look", {"topic": "invoice"}),          # sub-agent turn 1
        ("report", {"verdict": "clean"}),        # sub-agent submits
        ("finish", {"answer": "ok"}),            # orchestrator submits
    ])
    cost = CostTracker(model="mock")
    crew = run_crew(
        backend, "You orchestrate.", [make_delegate_tool(specs), _tool("finish", answer=1)],
        "case 1", lambda n, i: "{}", "finish", specs, cost,
    )
    assert crew.submitted and crew.submission == {"answer": "ok"}
    assert crew.n_delegations == 1
    d = crew.delegations[0]
    assert d.specialist == "checker" and d.submitted
    assert d.returned == {"verdict": "clean"}
    assert crew.called("checker") and not crew.called("auditor")


def test_specialist_sees_only_the_brief():
    """A fact the orchestrator omits is genuinely unavailable to the specialist."""
    specs = {"checker": make_specialist()}
    backend = ScriptedBackend([
        ("delegate", {"specialist": "checker", "brief": "ONLY THIS"}),
        ("report", {"verdict": "fine"}),
        ("finish", {"answer": "done"}),
    ])
    run_crew(backend, "orchestrator prompt", [make_delegate_tool(specs), _tool("finish", answer=1)],
             "the full case file the orchestrator can see", lambda n, i: "{}", "finish",
             specs, CostTracker(model="mock"))
    # the sub-agent's opening message is the brief, not the original case
    assert "ONLY THIS" in backend.seen_first_messages[1]
    assert "full case file" not in backend.seen_first_messages[1]
    # and it runs under the specialist's own system prompt
    assert backend.seen_prompts[1] == "You are the checker."


def test_cost_rolls_up_from_subagents():
    """Orchestration cannot look cheap by hiding spend inside sub-agents."""
    specs = {"checker": make_specialist()}
    backend = ScriptedBackend([
        ("delegate", {"specialist": "checker", "brief": "b"}),
        ("look", {"topic": "x"}),
        ("report", {"verdict": "v"}),
        ("finish", {"answer": "a"}),
    ])
    cost = CostTracker(model="mock")
    run_crew(backend, "orch", [make_delegate_tool(specs), _tool("finish", answer=1)],
             "case", lambda n, i: "{}", "finish", specs, cost)
    # 2 orchestrator calls + 2 sub-agent calls, all on one tracker
    assert cost.api_calls == 4
    assert cost.input_tokens == 400


def test_unknown_specialist_is_reported_not_raised():
    specs = {"checker": make_specialist()}
    backend = ScriptedBackend([
        ("delegate", {"specialist": "nobody", "brief": "b"}),
        ("finish", {"answer": "a"}),
    ])
    crew = run_crew(backend, "orch", [make_delegate_tool(specs), _tool("finish", answer=1)],
                    "case", lambda n, i: "{}", "finish", specs, CostTracker(model="mock"))
    assert crew.submitted
    assert crew.delegations[0].error == "unknown specialist"
    assert crew.delegations[0].returned is None


def test_subagent_that_never_submits_is_recorded():
    """A specialist that stalls must surface to the orchestrator, not hang the run."""
    spec = make_specialist()
    spec.max_turns = 2
    specs = {"checker": spec}
    backend = ScriptedBackend([
        ("delegate", {"specialist": "checker", "brief": "b"}),
        ("look", {"topic": "x"}),   # sub turn 1, no submit
        ("look", {"topic": "y"}),   # sub turn 2, budget exhausted
        ("finish", {"answer": "a"}),
    ])
    crew = run_crew(backend, "orch", [make_delegate_tool(specs), _tool("finish", answer=1)],
                    "case", lambda n, i: "{}", "finish", specs, CostTracker(model="mock"))
    assert crew.submitted
    assert crew.delegations[0].submitted is False
    assert crew.delegations[0].returned is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
