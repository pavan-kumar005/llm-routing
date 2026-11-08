import hashlib
import json
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import db
from app.cache import TTLCache
from app.config import (
    CACHE_ENABLED, CACHE_TTL_SECONDS, CHEAP_MODEL, DEFAULT_MONTHLY_LIMIT,
    GATEWAY_API_KEY, MAX_PROMPT_CHARS, RATE_LIMIT_PER_MINUTE, STRONG_MODEL,
    USE_MOCK,
)
from app.pricing import calculate_cost
from app.providers.groq_provider import ProviderError, call_groq
from app.providers.mock_provider import call_mock
from app.ratelimit import RateLimiter
from app.routing.policies import choose_model
from app.schemas import ChatRequest, ChatResponse, CompletionRequest

cache = TTLCache(ttl=CACHE_TTL_SECONDS, max_items=1000)
limiter = RateLimiter(window=60.0)

LANDING = Path(__file__).parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="LLM Router Gateway", lifespan=lifespan)


@dataclass
class Caller:
    id: str
    limit: int | None  # None = unlimited


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def bearer(authorization: str) -> str:
    return authorization.removeprefix("Bearer ").strip()


def is_owner(token: str) -> bool:
    return bool(GATEWAY_API_KEY) and secrets.compare_digest(
        token.encode(), GATEWAY_API_KEY.encode()
    )


def authenticate(authorization: str = Header(default="")) -> Caller:
    if not GATEWAY_API_KEY:
        return Caller("local", None)  # no owner key set: open (local development only)
    token = bearer(authorization)
    if is_owner(token):
        return Caller("owner", None)
    customer = db.find_customer(hash_key(token)) if token else None
    if not customer or not customer["active"]:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return Caller(customer["id"], customer["limit"])


def require_admin(authorization: str = Header(default="")):
    if not GATEWAY_API_KEY:
        raise HTTPException(status_code=503, detail="Admin disabled: GATEWAY_API_KEY not set")
    if not is_owner(bearer(authorization)):
        raise HTTPException(status_code=403, detail="Admin only")


async def call_provider(model: str, prompt: str, **extra):
    if USE_MOCK:
        return await call_mock(model, prompt, **extra)
    return await call_groq(model, prompt, **extra)


async def call_with_fallback(model: str, prompt: str, **extra):
    """Try the chosen model; if it fails after retries, try the other one."""
    try:
        return await call_provider(model, prompt, **extra), model, None
    except ProviderError as first_error:
        backup = CHEAP_MODEL if model == STRONG_MODEL else STRONG_MODEL
        if backup == model:
            raise
        try:
            result = await call_provider(backup, prompt, **extra)
        except ProviderError:
            raise first_error
        return result, backup, f"fallback from {model} ({str(first_error)[:60]})"


def policy_for(model_name: str) -> str:
    m = model_name.lower()
    if m in ("cheap", "always_cheap"):
        return "always_cheap"
    if m in ("strong", "always_strong"):
        return "always_strong"
    return "router"  # "auto" and any other name (e.g. a model name from an existing app)


async def run_chat(caller: Caller, policy: str, prompt: str,
                   messages=None, max_tokens=None) -> ChatResponse:
    """Shared by /v1/chat and /v1/chat/completions."""
    if len(prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Prompt too long: {len(prompt)} characters (maximum {MAX_PROMPT_CHARS}).",
        )

    if caller.id not in ("owner", "local"):
        wait = limiter.check(caller.id, RATE_LIMIT_PER_MINUTE)
        if wait:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({RATE_LIMIT_PER_MINUTE} requests per minute). "
                       f"Retry in {wait} seconds.",
                headers={"Retry-After": str(wait)},
            )

    if caller.limit is not None and db.count_month(caller.id) >= caller.limit:
        raise HTTPException(status_code=429, detail="Monthly request limit reached")

    model, reason = choose_model(policy, prompt)
    start = time.perf_counter()

    extra = {}
    if messages is not None:
        extra["messages"] = messages
    if max_tokens is not None:
        extra["max_tokens"] = max_tokens

    # the key includes the caller, so customers never share cached answers
    cache_key = cache.make_key(
        caller.id, model, prompt, json.dumps(messages) if messages else "", max_tokens
    )
    if CACHE_ENABLED:
        hit = cache.get(cache_key)
        if hit is not None:
            latency_ms = (time.perf_counter() - start) * 1000
            db.log_request(policy, model, reason, 0, 0, latency_ms, 0.0,
                           "cache_hit", caller.id)
            return ChatResponse(
                answer=hit.answer, model=model, route_reason=reason,
                input_tokens=0, output_tokens=0,
                latency_ms=round(latency_ms, 2), cost_usd=0.0, cached=True,
            )

    try:
        result, used_model, fallback_note = await call_with_fallback(model, prompt, **extra)
    except ProviderError as e:
        latency_ms = (time.perf_counter() - start) * 1000
        db.log_request(policy, model, reason, 0, 0, latency_ms, 0.0,
                       f"error: {e}"[:200], caller.id)
        # the real error is in your logs; customers get a generic message
        raise HTTPException(
            status_code=502,
            detail="The model provider is temporarily unavailable. Please try again shortly.",
        )
    latency_ms = (time.perf_counter() - start) * 1000

    if fallback_note:
        reason = f"{reason} | {fallback_note}"

    cost = calculate_cost(used_model, result.input_tokens, result.output_tokens)
    db.log_request(policy, used_model, reason, result.input_tokens,
                   result.output_tokens, latency_ms, cost, "success", caller.id)

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


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, caller: Caller = Depends(authenticate)):
    return await run_chat(caller, req.policy, req.prompt)


@app.post("/v1/chat/completions")
async def chat_completions(req: CompletionRequest, caller: Caller = Depends(authenticate)):
    if req.stream:
        raise HTTPException(status_code=400, detail="Streaming is not supported yet. Use stream=false.")

    messages = [m.model_dump() for m in req.messages]
    prompt = "\n".join(m["content"] for m in messages)
    r = await run_chat(caller, policy_for(req.model), prompt, messages, req.max_tokens)

    return {
        "id": "chatcmpl-" + secrets.token_hex(12),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": r.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": r.answer},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": r.input_tokens,
            "completion_tokens": r.output_tokens,
            "total_tokens": r.input_tokens + r.output_tokens,
        },
        "gateway": {
            "route_reason": r.route_reason,
            "cost_usd": r.cost_usd,
            "cached": r.cached,
            "latency_ms": r.latency_ms,
        },
    }


@app.get("/v1/usage")
def my_usage(caller: Caller = Depends(authenticate)):
    data = db.usage_for(caller.id)
    data["monthly_limit"] = caller.limit
    return data


class NewCustomer(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    monthly_limit: int = Field(DEFAULT_MONTHLY_LIMIT, ge=1)


@app.post("/admin/customers", dependencies=[Depends(require_admin)])
def create_customer(body: NewCustomer):
    key = "gw_" + secrets.token_urlsafe(24)
    customer_id = db.create_customer(body.name, hash_key(key), body.monthly_limit)
    return {
        "customer_id": customer_id,
        "name": body.name,
        "monthly_limit": body.monthly_limit,
        "api_key": key,
        "note": "Save this key now. It is not stored and cannot be shown again.",
    }


@app.post("/admin/customers/{customer_id}/deactivate", dependencies=[Depends(require_admin)])
def deactivate_customer(customer_id: int):
    db.set_active(customer_id, False)
    return {"customer_id": customer_id, "active": False}


@app.get("/admin/usage", dependencies=[Depends(require_admin)])
def all_usage():
    return db.usage_all()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(LANDING, media_type="text/html")


@app.get("/health")
def health():
    return {"status": "ok"}