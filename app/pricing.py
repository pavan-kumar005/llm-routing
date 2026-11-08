# USD per 1M tokens: (input_price, output_price)
PRICES = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "mock-cheap": (0.05, 0.08),
    "mock-strong": (0.59, 0.79),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = PRICES.get(model, (0.0, 0.0))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000