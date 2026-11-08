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


class Message(BaseModel):
    role: str
    content: str


class CompletionRequest(BaseModel):
    model: str = "auto"  # auto | cheap | strong (anything else is treated as auto)
    messages: list[Message] = Field(..., min_length=1)
    max_tokens: int | None = Field(None, ge=1, le=4096)
    temperature: float | None = None  # accepted but ignored (always 0)
    stream: bool = False