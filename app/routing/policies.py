from app.config import CHEAP_MODEL, STRONG_MODEL
from app.routing.rules import route


def choose_model(policy: str, prompt: str) -> tuple[str, str]:
    """Returns (model, reason)."""
    if policy == "always_cheap":
        return CHEAP_MODEL, "policy=always_cheap"
    if policy == "always_strong":
        return STRONG_MODEL, "policy=always_strong"
    decision = route(prompt)
    return decision.model, f"router: {decision.reason}"