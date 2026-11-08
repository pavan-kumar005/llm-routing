from fastapi.testclient import TestClient

from app import db, main


def test_landing_page(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(main.app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "/v1/chat/completions" in r.text