from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_status_and_database_fields() -> None:
    response = client.get("/health")

    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ok", "error")
    assert body["database"] in ("connected", "unreachable")
