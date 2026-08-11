from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.database import DatabaseConnectionError, check_database_connection
from app.main import app

client = TestClient(app)


def test_health_reports_database_connected() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_health_reflects_unreachable_database_without_crashing() -> None:
    with patch(
        "app.main.check_database_connection",
        side_effect=DatabaseConnectionError("db down"),
    ):
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "unreachable"


def test_check_database_connection_raises_explicit_error_on_bad_engine() -> None:
    broken_engine = create_engine(
        "postgresql+psycopg://baduser:badpass@localhost:1/nonexistent",
        connect_args={"connect_timeout": 2},
    )

    with pytest.raises(DatabaseConnectionError):
        check_database_connection(engine_=broken_engine)
