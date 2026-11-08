from fastapi.testclient import TestClient

from app import db, main

OWNER = {"Authorization": "Bearer owner-secret"}


def _prepare(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "owner-secret")
    main.cache.clear()
    main.limiter.clear()


def _customer(client, name):
    r = client.post("/admin/customers", json={"name": name}, headers=OWNER)
    return {"Authorization": f"Bearer {r.json()['api_key']}"}


def test_openai_response_shape(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    body = {"model": "auto",
            "messages": [{"role": "user", "content": "What is the capital of France?"}]}
    with TestClient(main.app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=OWNER)
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"]
    u = data["usage"]
    assert u["total_tokens"] == u["prompt_tokens"] + u["completion_tokens"]


def test_model_name_picks_policy(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    msg = [{"role": "user", "content": "hello there"}]
    with TestClient(main.app) as client:
        cheap = client.post("/v1/chat/completions",
                            json={"model": "cheap", "messages": msg}, headers=OWNER).json()
        strong = client.post("/v1/chat/completions",
                             json={"model": "strong", "messages": msg}, headers=OWNER).json()
    assert cheap["model"] == main.CHEAP_MODEL
    assert strong["model"] == main.STRONG_MODEL


def test_streaming_is_rejected(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    body = {"messages": [{"role": "user", "content": "hi"}], "stream": True}
    with TestClient(main.app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=OWNER)
    assert r.status_code == 400


def test_cache_is_per_customer(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    body = {"prompt": "same question", "policy": "always_cheap"}
    with TestClient(main.app) as client:
        a = _customer(client, "a")
        b = _customer(client, "b")
        assert client.post("/v1/chat", json=body, headers=a).json()["cached"] is False
        assert client.post("/v1/chat", json=body, headers=a).json()["cached"] is True
        assert client.post("/v1/chat", json=body, headers=b).json()["cached"] is False