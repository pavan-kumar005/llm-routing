import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import GATEWAY_API_KEY, USE_MOCK
from app.db import init_db, log_request
from app.pricing import calculate_cost
from app.providers.groq_provider import ProviderError, call_groq
from app.providers.mock_provider import call_mock
from app.routing.policies import choose_model
from app.schemas import ChatRequest, ChatResponse


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


@app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(require_key)])
async def chat(req: ChatRequest):
    model, reason = choose_model(req.policy, req.prompt)

    start = time.perf_counter()
    try:
        result = await call_provider(model, req.prompt)
    except ProviderError as e:
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(req.policy, model, reason, 0, 0, latency_ms, 0.0, f"error: {e}"[:200])
        raise HTTPException(status_code=502, detail=str(e))
    latency_ms = (time.perf_counter() - start) * 1000

    cost = calculate_cost(model, result.input_tokens, result.output_tokens)
    log_request(req.policy, model, reason, result.input_tokens,
                result.output_tokens, latency_ms, cost, "success")

    return ChatResponse(
        answer=result.answer,
        model=model,
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