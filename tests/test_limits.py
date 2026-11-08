from fastapi.testclient import TestClient

from app import db, main


def test_prompt_too_long_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "owner-secret")
    monkeypatch.setattr(main, "MAX_PROMPT_CHARS", 10)
    with TestClient(main.app) as client:
        r = client.post("/v1/chat", json={"prompt": "x" * 11},
                        headers={"Authorization": "Bearer owner-secret"})
    assert r.status_code == 413


def test_rate_limit_blocks_third_request(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "owner-secret")
    monkeypatch.setattr(main, "RATE_LIMIT_PER_MINUTE", 2)
    main.limiter.clear()
    main.cache.clear()
    owner = {"Authorization": "Bearer owner-secret"}

    with TestClient(main.app) as client:
        r = client.post("/admin/customers", json={"name": "acme"}, headers=owner)
        cust = {"Authorization": f"Bearer {r.json()['api_key']}"}

        for i in range(2):
            ok = client.post("/v1/chat", json={"prompt": f"q{i}", "policy": "always_cheap"},
                             headers=cust)
            assert ok.status_code == 200

        blocked = client.post("/v1/chat", json={"prompt": "q3", "policy": "always_cheap"},
                              headers=cust)
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers