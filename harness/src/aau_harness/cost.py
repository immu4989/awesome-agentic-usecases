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
    "llama-3.3-70b": (0.85, 1.20),  # Cerebras
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "deepseek-chat": (0.27, 1.10),
    "zai-glm-4.7": (2.25, 2.50),  # Cerebras-hosted GLM; approximate list rate
    "gpt-oss-120b": (0.35, 0.75),  # Cerebras-hosted; approximate list rate
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": (0.88, 0.88),  # Together
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),  # Fireworks; approximate list rate
    "accounts/fireworks/models/kimi-k2p6": (1.00, 3.00),  # Fireworks; approximate list rate
    "accounts/fireworks/models/deepseek-v4-pro": (1.20, 1.20),  # Fireworks; approximate list rate
    "mock": (0.0, 0.0),
}

CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


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
            + self.cache_read_input_tokens * in_rate * CACHE_READ_MULTIPLIER
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
