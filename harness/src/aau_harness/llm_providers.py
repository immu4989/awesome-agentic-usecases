"""Generic backend for OpenAI-compatible chat-completions APIs with tool calling.

One class covers Mistral, Groq, Gemini (OpenAI-compat endpoint), Cerebras, and
DeepSeek — anything that serves POST {base_url}/chat/completions. Several of
these have free tiers, so the full eval can run at zero dollars while still
reporting measured token usage priced at list rates.

Implementation notes:
- stdlib-only HTTP (urllib) so the package adds no dependencies.
- The agent loop speaks the Anthropic block shape; this backend translates the
  running conversation to OpenAI wire format on every call and adapts the
  response back into duck-typed blocks (.type/.id/.name/.input) so run_agent
  never branches on provider.
- Free tiers rate-limit hard; each provider gets a min-interval throttle plus
  429/5xx retries with exponential backoff honoring Retry-After.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    env_key: str
    default_model: str
    min_interval_s: float  # free-tier RPM throttle


PROVIDERS = {
    "mistral": Provider("mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY",
                        "mistral-small-latest", 1.1),
    "groq": Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
                     "llama-3.3-70b-versatile", 2.1),
    "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                       "GEMINI_API_KEY", "gemini-2.0-flash", 4.1),
    "cerebras": Provider("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY",
                         "zai-glm-4.7", 2.1),
    "deepseek": Provider("deepseek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY",
                         "deepseek-chat", 0.0),
    "together": Provider("together", "https://api.together.xyz/v1", "TOGETHER_API_KEY",
                         "meta-llama/Llama-3.3-70B-Instruct-Turbo", 0.5),
    "fireworks": Provider("fireworks", "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY",
                          "accounts/fireworks/models/gpt-oss-120b", 0.5),
}


class StreamingRequiredError(Exception):
    """The provider rejects non-streaming requests for this model. The backend
    catches this once, latches `_force_stream`, and replays over SSE."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class ToolUseFailedError(Exception):
    """The provider rejected the model's own malformed tool call (e.g. Groq's
    `tool_use_failed`). This is a model failure, not a harness failure — the
    run scores as a miss instead of crashing the eval."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _UsageAdapter:
    """Maps OpenAI usage fields onto the Anthropic names CostTracker reads.

    Provider-reported cached prompt tokens are folded into input_tokens
    (conservative: bills them at the full input rate)."""

    def __init__(self, usage: dict):
        self.input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        self.output_tokens = int(usage.get("completion_tokens", 0) or 0)
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0


def _to_openai_tools(tool_schemas: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tool_schemas
    ]


def _to_openai_messages(system: str, messages: list) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        content = m["content"]
        if m["role"] == "user" and isinstance(content, str):
            out.append({"role": "user", "content": content})
        elif m["role"] == "assistant":
            tool_calls = []
            text_parts = []
            for block in content:
                if getattr(block, "type", None) == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    })
                elif getattr(block, "type", None) == "text":
                    text_parts.append(block.text)
            msg: dict = {"role": "assistant", "content": " ".join(text_parts) or None}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            out.append(msg)
        else:  # user turn carrying tool results
            for block in content:
                out.append({
                    "role": "tool",
                    "tool_call_id": block["tool_use_id"],
                    "content": block["content"],
                })
    return out


class OpenAICompatBackend:
    def __init__(self, provider: str, model: str | None = None):
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; known: {sorted(PROVIDERS)}")
        self.provider = PROVIDERS[provider]
        self.name = provider
        self.model = model or self.provider.default_model
        self.api_key = os.environ.get(self.provider.env_key, "")
        if not self.api_key:
            raise RuntimeError(f"{self.provider.env_key} is not set")
        self._last_call = 0.0
        # Some models (e.g. Together's Qwen3.7 family) reject non-streaming
        # requests outright. Detected on first use, then latched on.
        self._force_stream = False

    # -- HTTP -----------------------------------------------------------
    def _post(self, payload: dict, max_retries: int = 6) -> dict:
        wait = self.provider.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        body = json.dumps(payload).encode()
        last_err: Exception | None = None
        for attempt in range(max_retries):
            req = urllib.request.Request(
                f"{self.provider.base_url}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    # Cloudflare in front of some providers (Groq, Cerebras) bans
                    # urllib's default Python-urllib UA with error 1010
                    "User-Agent": "aau-exception-triage-agent/0.1",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    self._last_call = time.monotonic()
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                self._last_call = time.monotonic()
                detail = e.read().decode(errors="replace")[:500]
                if e.code == 429 or e.code >= 500:
                    retry_after = e.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else min(2**attempt * 2.0, 60)
                    time.sleep(delay)
                    last_err = RuntimeError(f"HTTP {e.code} from {self.provider.name}: {detail}")
                    continue
                if e.code == 400 and "tool_use_failed" in detail:
                    raise ToolUseFailedError(detail) from e
                if e.code == 400 and "streaming" in detail.lower():
                    raise StreamingRequiredError(detail) from e
                raise RuntimeError(f"HTTP {e.code} from {self.provider.name}: {detail}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                time.sleep(min(2**attempt * 2.0, 30))
                last_err = e
        raise RuntimeError(f"giving up after {max_retries} retries: {last_err}")

    def _post_streaming(self, payload: dict) -> dict:
        """Drive an SSE completion and reassemble it into the non-streaming
        response shape, so callers see one uniform object either way."""
        payload = {**payload, "stream": True, "stream_options": {"include_usage": True}}
        wait = self.provider.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            f"{self.provider.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "aau-harness/0.1",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        text_parts: list[str] = []
        calls: dict[int, dict] = {}
        usage: dict = {}
        finish_reason = None
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    chunk_s = line[5:].strip()
                    if chunk_s == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_s)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    for choice in chunk.get("choices") or []:
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            text_parts.append(delta["content"])
                        for tc in delta.get("tool_calls") or []:
                            slot = calls.setdefault(
                                tc.get("index", 0), {"id": None, "name": None, "args": ""}
                            )
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                slot["name"] = fn["name"]
                            if fn.get("arguments"):
                                slot["args"] += fn["arguments"]
        finally:
            self._last_call = time.monotonic()

        tool_calls = [
            {"id": v["id"] or f"call-{i}", "type": "function",
             "function": {"name": v["name"], "arguments": v["args"]}}
            for i, (_, v) in enumerate(sorted(calls.items()))
            if v["name"]
        ]
        return {
            "choices": [{
                "finish_reason": finish_reason,
                "message": {
                    "content": "".join(text_parts) or None,
                    "tool_calls": tool_calls or None,
                },
            }],
            "usage": usage,
        }

    # -- backend interface ------------------------------------------------
    def create(self, system: str, messages: list, tools: list):
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": _to_openai_messages(system, messages),
            "tools": _to_openai_tools(tools),
        }
        try:
            if self._force_stream:
                data = self._post_streaming(payload)
            else:
                try:
                    data = self._post(payload)
                except StreamingRequiredError:
                    self._force_stream = True  # latch: this model is streaming-only
                    data = self._post_streaming(payload)
        except ToolUseFailedError as e:
            return _Block(
                content=[_Block(type="text", text=f"[model emitted malformed tool call] {e.detail[:300]}")],
                stop_reason="tool_use_failed",
                usage=_UsageAdapter({}),
            )
        choice = data["choices"][0]
        msg = choice["message"]
        blocks = []
        if msg.get("content"):
            blocks.append(_Block(type="text", text=msg["content"]))
        for tc in msg.get("tool_calls") or []:
            args = tc["function"].get("arguments") or "{}"
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_unparseable": args}
            blocks.append(
                _Block(type="tool_use", id=tc["id"], name=tc["function"]["name"], input=args)
            )
        return _Block(
            content=blocks,
            stop_reason=choice.get("finish_reason"),
            usage=_UsageAdapter(data.get("usage") or {}),
        )
