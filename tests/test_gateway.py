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