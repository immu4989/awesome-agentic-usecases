

def test_provider_cache_split_is_honoured_not_billed_as_misses():
    """A tool loop re-sends its whole conversation every turn, so turns 2..N are almost
    entirely cache hits. Billing those at the miss rate overstated a real DeepSeek call by
    22x, which is the loop this repo spends most of its money on.
    """
    from aau_harness.cost import CostTracker
    from aau_harness.llm_providers import _UsageAdapter

    # verbatim usage block from api.deepseek.com on a repeated prefix
    raw = {"prompt_tokens": 1697, "completion_tokens": 5,
           "prompt_tokens_details": {"cached_tokens": 1664},
           "prompt_cache_hit_tokens": 1664, "prompt_cache_miss_tokens": 33}
    u = _UsageAdapter(raw)
    assert (u.input_tokens, u.cache_read_input_tokens) == (33, 1664)

    c = CostTracker(model="deepseek-v4-flash")
    c.add_usage(u)
    all_miss = 1697 / 1e6 * 0.14 + 5 / 1e6 * 0.28
    assert c.cost_usd < all_miss / 10, "cache hits must not bill at the miss rate"


def test_a_provider_without_a_cache_split_is_unchanged():
    from aau_harness.llm_providers import _UsageAdapter
    u = _UsageAdapter({"prompt_tokens": 1000, "completion_tokens": 10})
    assert (u.input_tokens, u.cache_read_input_tokens) == (1000, 0)


def test_cache_read_multiplier_is_per_provider():
    """One constant would misprice DeepSeek by 5x: it publishes 0.02x, Anthropic 0.1x."""
    from aau_harness.cost import _cache_read_multiplier
    assert _cache_read_multiplier("deepseek-v4-flash") == 0.02
    assert _cache_read_multiplier("deepseek/deepseek-v4-flash-0731") == 0.02
    assert _cache_read_multiplier("claude-opus-4-8") == 0.10
