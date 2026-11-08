import pytest
from app.providers.base import ProviderResult
from app.providers.groq_provider import ProviderError
from fastapi.testclient import TestClient

from app import main


def test_chat_returns_answer(monkeypatch):
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "")
    with TestClient(main.app) as client:
        r = client.post("/v1/chat", json={"prompt": "What is 2+2?", "policy": "always_cheap"})
        assert r.status_code == 200
        body = r.json()
        assert "answer" in body
        assert body["route_reason"] == "policy=always_cheap"


def test_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "secret")
    with TestClient(main.app) as client:
        r = client.post("/v1/chat", json={"prompt": "hi"})
        assert r.status_code == 401
        r = client.post("/v1/chat", json={"prompt": "hi"},
                        headers={"Authorization": "Bearer secret"})
        assert r.status_code == 200

@pytest.fixture(autouse=True)
def clean_cache():
    main.cache.clear()
    yield
    main.cache.clear()


def test_second_identical_request_is_cached(monkeypatch):
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "")
    body = {"prompt": "cache me please", "policy": "always_cheap"}
    with TestClient(main.app) as client:
        first = client.post("/v1/chat", json=body).json()
        second = client.post("/v1/chat", json=body).json()
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["cost_usd"] == 0.0


def test_falls_back_when_strong_model_fails(monkeypatch):
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "")

    async def fake_call(model, prompt):
        if model == main.STRONG_MODEL:
            raise ProviderError("provider down")
        return ProviderResult(answer="ok", model=model, input_tokens=5, output_tokens=2)

    monkeypatch.setattr(main, "call_provider", fake_call)
    with TestClient(main.app) as client:
        r = client.post("/v1/chat", json={"prompt": "fallback test", "policy": "always_strong"})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == main.CHEAP_MODEL
    assert "fallback" in body["route_reason"]