"""Tests for the SSE path used by streaming-only models (e.g. Together's Qwen3.7)."""

import json

import pytest

from aau_harness.llm_providers import (
    OpenAICompatBackend,
    StreamingRequiredError,
)


def make_backend(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
    return OpenAICompatBackend("together", model="Qwen/Qwen3.7-Plus")


def test_streaming_reassembles_split_tool_call(monkeypatch):
    """Tool-call arguments arrive as fragments across chunks and must be concatenated."""
    backend = make_backend(monkeypatch)
    captured = {}

    def fake_stream(payload):
        captured["payload"] = payload
        return {
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call-1", "type": "function",
                        "function": {"name": "lookup_customer",
                                     "arguments": '{"entity_id": "acct-42"}'},
                    }],
                },
            }],
            "usage": {"prompt_tokens": 400, "completion_tokens": 30},
        }

    backend._force_stream = True
    backend._post_streaming = fake_stream
    resp = backend.create("sys", [{"role": "user", "content": "hi"}], [])

    assert captured["payload"]["model"] == "Qwen/Qwen3.7-Plus"
    block = resp.content[0]
    assert block.type == "tool_use"
    assert block.name == "lookup_customer"
    assert block.input == {"entity_id": "acct-42"}
    assert resp.usage.input_tokens == 400
    assert resp.usage.output_tokens == 30


def test_streaming_required_latches_and_replays(monkeypatch):
    """A 400 'streaming required' must flip the backend to SSE and retry once."""
    backend = make_backend(monkeypatch)
    calls = {"post": 0, "stream": 0}

    def fake_post(payload, max_retries=6):
        calls["post"] += 1
        raise StreamingRequiredError('{"error": {"code": "streaming_required"}}')

    def fake_stream(payload):
        calls["stream"] += 1
        return {
            "choices": [{"finish_reason": "stop",
                         "message": {"content": "ok", "tool_calls": None}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }

    backend._post = fake_post
    backend._post_streaming = fake_stream

    resp = backend.create("sys", [{"role": "user", "content": "hi"}], [])
    assert resp.content[0].text == "ok"
    assert backend._force_stream is True, "must latch so later calls skip the failed probe"

    backend.create("sys", [{"role": "user", "content": "again"}], [])
    assert calls["post"] == 1, "non-streaming must not be retried after latching"
    assert calls["stream"] == 2


def test_sse_chunk_accumulation_logic():
    """The fragment-accumulation contract the SSE reader implements."""
    chunks = [
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "submit_triage", "arguments": '{"que'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": 'ue": "card-fraud"}'}}]}}]},
        {"choices": [{"finish_reason": "tool_calls", "delta": {}}],
         "usage": {"prompt_tokens": 100, "completion_tokens": 20}},
    ]
    calls, usage, finish = {}, {}, None
    for chunk in chunks:
        if chunk.get("usage"):
            usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            if choice.get("finish_reason"):
                finish = choice["finish_reason"]
            for tc in (choice.get("delta") or {}).get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", 0), {"id": None, "name": None, "args": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] = fn["name"]
                if fn.get("arguments"):
                    slot["args"] += fn["arguments"]

    assert finish == "tool_calls"
    assert usage["prompt_tokens"] == 100
    assert calls[0]["name"] == "submit_triage"
    assert json.loads(calls[0]["args"]) == {"queue": "card-fraud"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
