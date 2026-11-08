from evals.scorers import score


def test_number_takes_last_number():
    item = {"type": "number", "answer": 391}
    assert score(item, "The answer is 391.")
    assert not score(item, "I am not sure")


def test_number_handles_commas():
    assert score({"type": "number", "answer": 10000}, "10,000")


def test_contains_ignores_case():
    assert score({"type": "contains", "answer": ["tokyo"]}, "It is TOKYO.")


def test_exact_needs_full_match():
    item = {"type": "exact", "answer": ["au"]}
    assert score(item, "Au")
    assert not score(item, "The symbol is Au")