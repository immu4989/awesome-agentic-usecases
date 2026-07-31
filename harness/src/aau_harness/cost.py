"""Dollar-cost accounting from API usage blocks.

Prices are USD per million tokens, from the published Anthropic price list
(cached 2026-07). Cache writes bill at 1.25x input (5-minute TTL) and cache
reads at 0.1x input on every listed model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# model id -> (input $/MTok, output $/MTok)
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5": (10.00, 50.00),
    # OpenAI-compatible providers (list price; several have free tiers where the
    # actual spend is $0 — the report still prices measured tokens at list rate)
    "mistral-small-latest": (0.10, 0.30),
    "llama-3.3-70b-versatile": (0.59, 0.79),  # Groq
    "qwen/qwen3.6-27b": (0.29, 0.59),  # Groq free tier; approximate list rate
    "llama-3.3-70b": (0.85, 1.20),  # Cerebras
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    # DeepSeek's direct API addresses models by rolling, undated names: `deepseek-chat`
    # and `deepseek-reasoner` both resolve to `deepseek-v4-flash`, and that name itself
    # rolls forward to the newest snapshot (OpenRouter exposes the dated one, currently
    # `deepseek-v4-flash-0731`). None of these is a pinned identifier; use the OpenRouter
    # dated id when a result needs to be reproducible.
    # These were priced at the V3 rate (0.27, 1.10) while the API was already serving V4
    # Flash, which overstated every deepseek cost in this repo by roughly 2x until 2026-07-31.
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.14, 0.28),
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek/deepseek-v4-flash-0731": (0.14, 0.28),
    "zai-glm-4.7": (2.25, 2.50),  # Cerebras-hosted GLM; approximate list rate
    "gpt-oss-120b": (0.35, 0.75),  # Cerebras-hosted; approximate list rate
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": (0.88, 0.88),  # Together
    "openai/gpt-oss-20b": (0.05, 0.20),  # Together
    "Qwen/Qwen3-Next-80B-A3B-Thinking": (0.15, 1.50),  # Together
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": (0.18, 0.59),  # Together
    "zai-org/GLM-4.5-Air-FP8": (0.20, 1.10),  # Together
    "meta-llama/Llama-3.2-3B-Instruct": (0.06, 0.06),  # Together
    "Qwen/Qwen3.5-9B": (0.17, 0.25),  # Together
    "accounts/fireworks/models/glm-5p2": (0.60, 2.20),  # Fireworks; approximate
    "Qwen/Qwen3.7-Plus": (0.32, 1.28),  # Together; live list rate 2026-07
    "Qwen/Qwen3.7-Max": (1.25, 3.75),  # Together; live list rate 2026-07
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),  # Fireworks; approximate list rate
    "accounts/fireworks/models/kimi-k2p6": (1.00, 3.00),  # Fireworks; approximate list rate
    "accounts/fireworks/models/deepseek-v4-pro": (1.20, 1.20),  # Fireworks; approximate list rate
    "mock": (0.0, 0.0),
}

CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

# Anthropic reads cache at 0.1x input. Other providers differ enough that using one
# constant would misprice them: DeepSeek publishes $0.0028/MTok against a $0.14 miss,
# i.e. 0.02x. Keyed by model id prefix; anything unlisted keeps the 0.1x default.
CACHE_READ_MULTIPLIER_BY_MODEL: dict[str, float] = {
    "deepseek": 0.02,
}


def _cache_read_multiplier(model: str) -> float:
    for prefix, mult in CACHE_READ_MULTIPLIER_BY_MODEL.items():
        if model.startswith(prefix) or f"/{prefix}" in model:
            return mult
    return CACHE_READ_MULTIPLIER


@dataclass
class CostTracker:
    """Accumulates usage across the API calls of one agent run."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    api_calls: int = 0
    _rates: tuple[float, float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.model not in PRICING_PER_MTOK:
            _lazy_price(self.model)
        if self.model not in PRICING_PER_MTOK:
            raise ValueError(
                f"No pricing for model {self.model!r}; add it to PRICING_PER_MTOK"
            )
        self._rates = PRICING_PER_MTOK[self.model]

    def add_usage(self, usage) -> None:
        """Accept a `usage` object from an API response (or any object/dict
        with the same field names) and accumulate it."""
        get = usage.get if isinstance(usage, dict) else lambda k, d=0: getattr(usage, k, d) or 0
        self.input_tokens += int(get("input_tokens", 0) or 0)
        self.output_tokens += int(get("output_tokens", 0) or 0)
        self.cache_creation_input_tokens += int(get("cache_creation_input_tokens", 0) or 0)
        self.cache_read_input_tokens += int(get("cache_read_input_tokens", 0) or 0)
        self.api_calls += 1

    @property
    def total_input_tokens(self) -> int:
        """Full prompt size: uncached + cache-written + cache-read."""
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )

    @property
    def cost_usd(self) -> float:
        in_rate, out_rate = self._rates
        return (
            self.input_tokens * in_rate
            + self.cache_creation_input_tokens * in_rate * CACHE_WRITE_MULTIPLIER
            + self.cache_read_input_tokens * in_rate * _cache_read_multiplier(self.model)
            + self.output_tokens * out_rate
        ) / 1_000_000

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "api_calls": self.api_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


def register_pricing(model: str, input_per_mtok: float, output_per_mtok: float) -> None:
    """Record a model's published rate so measured tokens can be priced.

    The table above is a hand-maintained cache of published list prices. Aggregators serve
    hundreds of models and publish exact per-token rates over their API, so for those the
    honest move is to read the rate rather than hardcode or guess it — the invariant this
    repo keeps is that every reported dollar comes from a published rate applied to
    measured tokens, never from an estimate.
    """
    PRICING_PER_MTOK[model] = (float(input_per_mtok), float(output_per_mtok))


def _lazy_price(model: str) -> None:
    """Fetch a rate from OpenRouter for models served through it (ids look like `a/b`)."""
    import json as _json
    import os as _os
    import urllib.request as _u

    if "/" not in model:
        return
    key = _os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return
    try:
        req = _u.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {key}",
                     "User-Agent": "aau-harness/0.1"},
        )
        with _u.urlopen(req, timeout=30) as resp:
            for m in _json.loads(resp.read())["data"]:
                if m["id"] == model:
                    p = m["pricing"]
                    # OpenRouter quotes USD per token; the table is per million.
                    register_pricing(model, float(p["prompt"]) * 1e6,
                                     float(p["completion"]) * 1e6)
                    return
    except Exception:
        return  # leave it unpriced; CostTracker will raise with a clear message
