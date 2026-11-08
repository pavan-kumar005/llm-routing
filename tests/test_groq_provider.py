import httpx
import pytest
import respx

from app.config import GROQ_BASE_URL, MAX_RETRIES
from app.providers import groq_provider
from app.providers.groq_provider import ProviderError, call_groq

URL = f"{GROQ_BASE_URL}/chat/completions"
OK = {
    "choices": [{"message": {"content": "Paris"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
}


@pytest.fixture(autouse=True)
def fast_and_keyed(monkeypatch):
    monkeypatch.setattr(groq_provider, "BACKOFF_BASE", 0)   # no real waiting
    monkeypatch.setattr(groq_provider, "GROQ_API_KEY", "test-key")


@pytest.mark.asyncio
async def test_success():
    with respx.mock:
        respx.post(URL).mock(return_value=httpx.Response(200, json=OK))
        r = await call_groq("m", "capital of France?")
    assert r.answer == "Paris"
    assert (r.input_tokens, r.output_tokens) == (10, 2)


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds():
    with respx.mock:
        route = respx.post(URL).mock(side_effect=[
            httpx.Response(429), httpx.Response(200, json=OK)])
        r = await call_groq("m", "hi")
    assert r.answer == "Paris"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_gives_up_after_max_retries():
    with respx.mock:
        route = respx.post(URL).mock(return_value=httpx.Response(500))
        with pytest.raises(ProviderError):
            await call_groq("m", "hi")
    assert route.call_count == MAX_RETRIES + 1


@pytest.mark.asyncio
async def test_does_not_retry_bad_request():
    with respx.mock:
        route = respx.post(URL).mock(return_value=httpx.Response(400, text="bad"))
        with pytest.raises(ProviderError):
            await call_groq("m", "hi")
    assert route.call_count == 1