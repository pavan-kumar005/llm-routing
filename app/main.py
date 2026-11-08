import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

from app.cache import TTLCache
from app.config import (
    CACHE_ENABLED, CACHE_TTL_SECONDS, CHEAP_MODEL, GATEWAY_API_KEY,
    STRONG_MODEL, USE_MOCK,
)
from app.db import init_db, log_request
from app.pricing import calculate_cost
from app.providers.groq_provider import ProviderError, call_groq
from app.providers.mock_provider import call_mock
from app.routing.policies import choose_model
from app.schemas import ChatRequest, ChatResponse

cache = TTLCache(ttl=CACHE_TTL_SECONDS, max_items=1000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="LLM Router Gateway", lifespan=lifespan)


def require_key(authorization: str = Header(default="")):
    if not GATEWAY_API_KEY:
        return  # no key set: open (local development only)
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, GATEWAY_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def call_provider(model: str, prompt: str):
    if USE_MOCK:
        return await call_mock(model, prompt)
    return await call_groq(model, prompt)


async def call_with_fallback(model: str, prompt: str):
    """Try the chosen model; if it fails after retries, try the other one.
    Returns (result, model_that_answered, fallback_note_or_None)."""
    try:
        return await call_provider(model, prompt), model, None
    except ProviderError as first_error:
        backup = CHEAP_MODEL if model == STRONG_MODEL else STRONG_MODEL
        if backup == model:
            raise
        try:
            result = await call_provider(backup, prompt)
        except ProviderError:
            raise first_error
        return result, backup, f"fallback from {model} ({str(first_error)[:60]})"


@app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(require_key)])
async def chat(req: ChatRequest):
    model, reason = choose_model(req.policy, req.prompt)
    start = time.perf_counter()

    cache_key = cache.make_key(model, req.prompt)
    if CACHE_ENABLED:
        hit = cache.get(cache_key)
        if hit is not None:
            latency_ms = (time.perf_counter() - start) * 1000
            log_request(req.policy, model, reason, 0, 0, latency_ms, 0.0, "cache_hit")
            return ChatResponse(
                answer=hit.answer, model=model, route_reason=reason,
                input_tokens=0, output_tokens=0,
                latency_ms=round(latency_ms, 2), cost_usd=0.0, cached=True,
            )

    try:
        result, used_model, fallback_note = await call_with_fallback(model, req.prompt)
    except ProviderError as e:
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(req.policy, model, reason, 0, 0, latency_ms, 0.0, f"error: {e}"[:200])
        raise HTTPException(status_code=502, detail=str(e))
    latency_ms = (time.perf_counter() - start) * 1000

    if fallback_note:
        reason = f"{reason} | {fallback_note}"

    cost = calculate_cost(used_model, result.input_tokens, result.output_tokens)
    log_request(req.policy, used_model, reason, result.input_tokens,
                result.output_tokens, latency_ms, cost, "success")

    if CACHE_ENABLED:
        cache.set(cache_key, result)

    return ChatResponse(
        answer=result.answer,
        model=used_model,
        route_reason=reason,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=round(latency_ms, 2),
        cost_usd=cost,
    )


@app.get("/")
def home():
    return {
        "service": "LLM Router Gateway",
        "status": "ok",
        "docs": "/docs",
        "endpoint": "POST /v1/chat",
    }


@app.get("/health")
def health():
    return {"status": "ok"}