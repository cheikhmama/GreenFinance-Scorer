import json

import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from structlog.testing import capture_logs

from app.core.database import DatabaseConnectionError, check_database_connection
from app.core.exceptions import NotFoundError, register_exception_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)

    @app.get("/ok")
    def ok() -> dict[str, str]:
        structlog.get_logger("test").info("handling_ok_request")
        return {"status": "ok"}

    @app.get("/fail")
    def fail() -> None:
        structlog.get_logger("test").info("about_to_fail")
        raise NotFoundError("introuvable")

    return app


client = TestClient(_build_test_app(), raise_server_exceptions=False)


def test_successive_requests_get_different_correlation_ids() -> None:
    configure_logging("development")

    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs1:
        client.get("/ok")
    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs2:
        client.get("/ok")

    id1 = logs1[0]["correlation_id"]
    id2 = logs2[0]["correlation_id"]
    assert id1 != id2


def test_correlation_id_matches_between_logs_and_error_response() -> None:
    configure_logging("development")

    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
        response = client.get("/fail")

    body_correlation_id = response.json()["error"]["correlation_id"]
    log_correlation_ids = {entry.get("correlation_id") for entry in logs}
    assert body_correlation_id in log_correlation_ids


def test_development_output_is_human_readable_not_json(capsys) -> None:
    configure_logging("development")

    structlog.get_logger("test").info("hello_dev", foo="bar")
    captured = capsys.readouterr()

    last_line = captured.out.strip().splitlines()[-1]
    assert "hello_dev" in last_line
    try:
        json.loads(last_line)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("la sortie développement ne devrait pas être du JSON strict")


def test_production_output_is_json(capsys) -> None:
    configure_logging("production")

    structlog.get_logger("test").info("hello_prod", foo="bar")
    captured = capsys.readouterr()

    last_line = captured.out.strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload["event"] == "hello_prod"
    assert payload["foo"] == "bar"


def test_database_connection_error_never_leaks_the_password() -> None:
    configure_logging("development")
    secret = "super-secret-pw-x7z"
    broken_engine = create_engine(
        f"postgresql+psycopg://greenfinance:{secret}@localhost:1/nonexistent",
        connect_args={"connect_timeout": 2},
    )

    with capture_logs() as logs:
        try:
            check_database_connection(engine_=broken_engine)
        except DatabaseConnectionError as exc:
            structlog.get_logger("test").error("startup_db_check_failed", error=str(exc))

    assert logs, "un log aurait dû être émis"
    for entry in logs:
        assert secret not in str(entry)
