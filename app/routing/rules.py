import re
from dataclasses import dataclass

from app.config import CHEAP_MODEL, STRONG_MODEL

LONG_PROMPT_CHARS = 400    # longer than this: strong
SHORT_PROMPT_CHARS = 200   # at or below this with no signals: cheap

HARD_KEYWORDS = [
    "prove", "analyze", "analyse", "step by step", "compare", "trade-off",
    "tradeoff", "explain why", "derive", "evaluate", "debug", "optimize",
    "optimise", "algorithm", "architecture", "refactor", "write a program",
    "write a function", "reasoning",
]

CODE_PATTERNS = [
    r"```",
    r"^\s*def \w+\(",
    r"^\s*class \w+",
    r"^\s*(import|from) \w+",
    r"#include\s*<",
    r"\bfunction\s*\w*\(",
    r"=>",
    r"\bselect\b.+\bfrom\b",
    r"[{};]\s*$",
]

MATH_KEYWORDS = ["calculate", "solve", "equation", "integral", "derivative",
                 "probability", "percent", "square root"]
MATH_EXPRESSION = re.compile(r"\d+(\.\d+)?\s*[\+\-\*/x×^%=]\s*\d+")


@dataclass
class RouteDecision:
    model: str
    reason: str


def has_code(prompt: str) -> bool:
    return any(
        re.search(p, prompt, flags=re.IGNORECASE | re.MULTILINE)
        for p in CODE_PATTERNS
    )


def has_hard_keyword(prompt: str) -> str | None:
    text = prompt.lower()
    for kw in HARD_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            return kw
    return None


def looks_like_math(prompt: str) -> bool:
    text = prompt.lower()
    if MATH_EXPRESSION.search(text):
        return True
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in MATH_KEYWORDS)


def route(prompt: str) -> RouteDecision:
    n = len(prompt)

    if n > LONG_PROMPT_CHARS:
        return RouteDecision(STRONG_MODEL, f"long prompt ({n} chars)")

    if has_code(prompt):
        return RouteDecision(STRONG_MODEL, "code detected")

    kw = has_hard_keyword(prompt)
    if kw:
        return RouteDecision(STRONG_MODEL, f"hard keyword: '{kw}'")

    if looks_like_math(prompt):
        return RouteDecision(STRONG_MODEL, "math detected")

    if n <= SHORT_PROMPT_CHARS:
        return RouteDecision(CHEAP_MODEL, f"short simple prompt ({n} chars)")

    return RouteDecision(STRONG_MODEL, f"medium prompt, unsure ({n} chars): default strong")