from app.config import CHEAP_MODEL, STRONG_MODEL
from app.routing.rules import route


def test_simple_question_goes_cheap():
    assert route("What is the capital of France?").model == CHEAP_MODEL


def test_greeting_goes_cheap():
    assert route("hello").model == CHEAP_MODEL


def test_long_prompt_goes_strong():
    assert route("word " * 200).model == STRONG_MODEL


def test_hard_keyword_goes_strong():
    assert route("Prove that the square root of 2 is irrational").model == STRONG_MODEL


def test_code_goes_strong():
    assert route("Fix this:\n```python\ndef f(:\n  pass\n```").model == STRONG_MODEL


def test_math_goes_strong():
    assert route("What is 17 * 23?").model == STRONG_MODEL


def test_reason_is_never_empty():
    assert route("hello").reason
    assert route("analyze this").reason