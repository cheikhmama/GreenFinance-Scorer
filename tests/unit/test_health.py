from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_status_and_database_fields() -> None:
    response = client.get("/health")

    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ok", "error")
    assert body["database"] in ("connected", "unreachable")


def test_health_never_exposes_the_database_error(monkeypatch) -> None:
    """Tâche 4.3 : la route est publique — le message d'exception (DSN, hôte, utilisateur) ne
    doit jamais y apparaître."""
    from app import main
    from app.core.database import DatabaseConnectionError

    def _panne() -> None:
        raise DatabaseConnectionError("connection to postgres@db-interne:5432 refused")

    monkeypatch.setattr(main, "check_database_connection", _panne)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}
    assert "db-interne" not in response.text
