# backend/app/agent/pricing.py
"""LLM pricing for cost tracking."""

# USD per 1M tokens (input, output)
PRICING: dict[tuple[str, str], tuple[float, float]] = {
    # Anthropic models
    ("anthropic", "claude-sonnet-4-20250514"): (3.00, 15.00),
    ("anthropic", "claude-3-5-sonnet-20241022"): (3.00, 15.00),
    ("anthropic", "claude-3-sonnet-20240229"): (3.00, 15.00),
    ("anthropic", "claude-3-haiku-20240307"): (0.25, 1.25),
    # OpenAI models
    ("openai", "gpt-4o"): (2.50, 10.00),
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("openai", "gpt-4-turbo"): (10.00, 30.00),
}

# Fallback pricing for unknown models
DEFAULT_PRICING = (5.00, 15.00)


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Calculate cost in USD for an LLM call.

    Args:
        provider: LLM provider name (anthropic, openai)
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    key = (provider.lower(), model)
    if key not in PRICING:
        input_rate, output_rate = DEFAULT_PRICING
    else:
        input_rate, output_rate = PRICING[key]

    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
