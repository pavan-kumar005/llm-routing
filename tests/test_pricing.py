from app.pricing import calculate_cost


def test_cost_math():
    # 1M input + 1M output tokens at (0.05, 0.08) = 0.13 USD
    assert calculate_cost("llama-3.1-8b-instant", 1_000_000, 1_000_000) == pytest.approx(0.13)


def test_unknown_model_is_free():
    assert calculate_cost("no-such-model", 1000, 1000) == 0.0


import pytest  # noqa: E402