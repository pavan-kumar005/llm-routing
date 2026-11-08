import asyncio
import random

import httpx

from app.config import (
    GROQ_API_KEY, GROQ_BASE_URL, MAX_RETRIES, REQUEST_TIMEOUT, BACKOFF_BASE,
)
from app.providers.base import ProviderResult

RETRY_STATUS = {429, 500, 502, 503, 504}  # worth retrying
MAX_WAIT = 20.0


class ProviderError(Exception):
    """Raised when the provider fails after all retries."""


def _wait_time(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), MAX_WAIT)
        except ValueError:
            pass
    return min(BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.25), MAX_WAIT)


async def call_groq(model: str, prompt: str) -> ProviderResult:
    if not GROQ_API_KEY:
        raise ProviderError("GROQ_API_KEY is not set")

    url = f"{GROQ_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    last_error = "unknown error"
    for attempt in range(MAX_RETRIES + 1):
        retry_after = None
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                r = await client.post(url, headers=headers, json=payload)

            if r.status_code == 200:
                data = r.json()
                usage = data.get("usage", {})
                return ProviderResult(
                    answer=data["choices"][0]["message"]["content"] or "",
                    model=model,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                )

            if r.status_code not in RETRY_STATUS:
                # 400, 401, 404 etc: retrying will not help
                raise ProviderError(f"HTTP {r.status_code}: {r.text[:200]}")

            last_error = f"HTTP {r.status_code}"
            retry_after = r.headers.get("retry-after")

        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_error = f"{type(e).__name__}: {e}"

        if attempt < MAX_RETRIES:
            await asyncio.sleep(_wait_time(attempt, retry_after))

    raise ProviderError(f"Failed after {MAX_RETRIES + 1} attempts: {last_error}")