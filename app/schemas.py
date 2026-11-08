from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    policy: str = "router"  # always_cheap | always_strong | router


class ChatResponse(BaseModel):
    answer: str
    model: str
    route_reason: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    cached: bool = False