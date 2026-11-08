from fastapi.testclient import TestClient

from app import db, main


def test_customer_key_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")  # throwaway database
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "owner-secret")
    main.cache.clear()
    owner = {"Authorization": "Bearer owner-secret"}

    with TestClient(main.app) as client:
        r = client.post("/admin/customers", json={"name": "acme", "monthly_limit": 2}, headers=owner)
        assert r.status_code == 200
        cust = {"Authorization": f"Bearer {r.json()['api_key']}"}

        for i in range(2):
            ok = client.post("/v1/chat", json={"prompt": f"q{i}", "policy": "always_cheap"}, headers=cust)
            assert ok.status_code == 200

        over = client.post("/v1/chat", json={"prompt": "q3", "policy": "always_cheap"}, headers=cust)
        assert over.status_code == 429

        assert client.get("/v1/usage", headers=cust).json()["requests_this_month"] == 2
        assert client.post("/admin/customers", json={"name": "x"}, headers=cust).status_code == 403
        assert client.get("/admin/usage", headers=owner).status_code == 200


def test_unknown_key_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "USE_MOCK", True)
    monkeypatch.setattr(main, "GATEWAY_API_KEY", "owner-secret")
    with TestClient(main.app) as client:
        r = client.post("/v1/chat", json={"prompt": "hi"},
                        headers={"Authorization": "Bearer gw_notreal"})
        assert r.status_code == 401