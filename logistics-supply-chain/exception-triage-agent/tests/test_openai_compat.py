import json

import pytest

from aau_harness import CostTracker
from exception_triage_agent.agent import run_agent
from exception_triage_agent.openai_compat import (
    PROVIDERS,
    OpenAICompatBackend,
    _to_openai_messages,
    _to_openai_tools,
)
from exception_triage_agent.tools import TOOL_SCHEMAS
from exception_triage_agent.world import generate_scenarios


def make_backend(monkeypatch, replies):
    """OpenAICompatBackend with a scripted transport instead of HTTP."""
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    backend = OpenAICompatBackend("mistral")
    calls = []

    def fake_post(payload, max_retries=6):
        calls.append(payload)
        return replies[len(calls) - 1]

    backend._post = fake_post
    backend.provider = PROVIDERS["mistral"]
    return backend, calls


def reply_tool_call(name, args, call_id="call-1"):
    return {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }],
            },
        }],
        "usage": {"prompt_tokens": 500, "completion_tokens": 40},
    }


def test_tools_convert_without_anthropic_fields():
    tools = _to_openai_tools(TOOL_SCHEMAS)
    assert all(t["type"] == "function" for t in tools)
    assert all("strict" not in t["function"] for t in tools)
    assert tools[0]["function"]["parameters"]["additionalProperties"] is False


def test_full_agent_loop_over_scripted_transport(monkeypatch):
    sc = generate_scenarios(n=1, seed=7)[0]
    replies = [
        reply_tool_call("lookup_shipment", {"tracking_id": sc.tracking_id}, "c1"),
        reply_tool_call("search_policy", {"query": "escalation"}, "c2"),
        reply_tool_call(
            "submit_triage",
            {"queue": sc.gold_queue, "action": sc.gold_action, "reasoning": "test"},
            "c3",
        ),
    ]
    backend, calls = make_backend(monkeypatch, replies)
    cost = CostTracker(model="mistral-small-latest")
    outcome = run_agent(backend, sc, cost)

    assert outcome.submitted and outcome.queue == sc.gold_queue
    assert cost.api_calls == 3
    assert cost.cost_usd == pytest.approx((3 * 500 * 0.10 + 3 * 40 * 0.30) / 1e6)

    # third request must carry the full translated history
    msgs = calls[2]["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": sc.ticket_text}
    assert msgs[2]["role"] == "assistant" and msgs[2]["tool_calls"][0]["id"] == "c1"
    assert msgs[3]["role"] == "tool" and msgs[3]["tool_call_id"] == "c1"
    tool_reply = json.loads(msgs[3]["content"])
    assert tool_reply["exception_code"] == sc.shipment["exception_code"]


def test_message_translation_handles_text_blocks():
    class B:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [
            B(type="text", text="thinking out loud"),
            B(type="tool_use", id="x", name="lookup_shipment", input={"tracking_id": "T1"}),
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "x", "content": "{}"},
        ]},
    ]
    out = _to_openai_messages("sys", messages)
    assert out[2]["content"] == "thinking out loud"
    assert out[2]["tool_calls"][0]["function"]["name"] == "lookup_shipment"
    assert out[3] == {"role": "tool", "tool_call_id": "x", "content": "{}"}


def test_unknown_provider_and_missing_key(monkeypatch):
    with pytest.raises(ValueError):
        OpenAICompatBackend("nonexistent")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OpenAICompatBackend("groq")
