import re
import string

_PUNCT = str.maketrans("", "", string.punctuation)
NUMBER = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


def normalize(text: str) -> str:
    return " ".join(text.lower().translate(_PUNCT).split())


def last_number(text: str):
    found = NUMBER.findall(text)
    if not found:
        return None
    return float(found[-1].replace(",", ""))


def score_number(output: str, expected, tol: float = 1e-6) -> bool:
    value = last_number(output)
    return value is not None and abs(value - float(expected)) <= tol


def score_contains(output: str, accepted: list[str]) -> bool:
    out = normalize(output)
    return any(normalize(a) in out for a in accepted)


def score_exact(output: str, accepted: list[str]) -> bool:
    out = normalize(output)
    return any(out == normalize(a) for a in accepted)


def score(item: dict, output: str) -> bool:
    kind = item["type"]
    if kind == "number":
        return score_number(output, item["answer"])
    if kind == "contains":
        return score_contains(output, item["answer"])
    if kind == "exact":
        return score_exact(output, item["answer"])
    raise ValueError(f"unknown scorer type: {kind}")