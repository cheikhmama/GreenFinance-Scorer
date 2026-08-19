from unittest.mock import patch

import pytest
import redis

from app.auth.rate_limit import (
    MAX_ATTEMPTS,
    clear_login_attempts,
    enforce_login_rate_limit,
    register_failed_login_attempt,
)
from app.core.exceptions import ServiceUnavailableError, TooManyRequestsError
from app.core.logging import configure_logging


class _FakeRedis:
    """Double minimal — reproduit juste le sous-ensemble get/incr/expire/delete
    utilisé par app/auth/rate_limit.py, sans dépendre d'un serveur Redis réel
    (voir ARCHITECTURE.md §7 : un test unitaire reste vert sans infrastructure)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return str(self._counts[key]) if key in self._counts else None

    def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key: str, seconds: int) -> None:
        pass  # la fenêtre temporelle n'est pas testée ici, juste le comptage

    def delete(self, key: str) -> None:
        self._counts.pop(key, None)


class _BrokenRedis:
    """Simule une panne Redis (connexion coupée, timeout…) sur chaque appel —
    le message d'exception embarque volontairement un secret factice, pour
    prouver que rate_limit.py ne le journalise jamais (voir _guarded)."""

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def _boom(self, *_args: object, **_kwargs: object) -> None:
        raise redis.ConnectionError(f"Error connecting with credentials pw={self._secret}")

    get = _boom
    incr = _boom
    expire = _boom
    delete = _boom


@pytest.fixture()
def fake_redis():
    client = _FakeRedis()
    with patch("app.auth.rate_limit.get_redis_client", return_value=client):
        yield client


@pytest.fixture()
def broken_redis():
    secret = "leak-me-not-x7z"
    client = _BrokenRedis(secret)
    with patch("app.auth.rate_limit.get_redis_client", return_value=client):
        yield secret


def test_enforce_login_rate_limit_allows_a_fresh_email(fake_redis) -> None:
    enforce_login_rate_limit("nouveau@example.com")  # ne lève rien


def test_enforce_login_rate_limit_raises_once_the_threshold_is_reached(fake_redis) -> None:
    email = "cible@example.com"
    for _ in range(MAX_ATTEMPTS):
        register_failed_login_attempt(email)

    with pytest.raises(TooManyRequestsError):
        enforce_login_rate_limit(email)


def test_enforce_login_rate_limit_allows_attempts_below_the_threshold(fake_redis) -> None:
    email = "presque@example.com"
    for _ in range(MAX_ATTEMPTS - 1):
        register_failed_login_attempt(email)

    enforce_login_rate_limit(email)  # ne lève rien, encore une tentative permise


def test_clear_login_attempts_resets_the_counter(fake_redis) -> None:
    email = "reussite@example.com"
    for _ in range(MAX_ATTEMPTS):
        register_failed_login_attempt(email)

    clear_login_attempts(email)

    enforce_login_rate_limit(email)  # ne lève plus rien après la remise à zéro


def test_rate_limit_is_case_and_whitespace_insensitive_on_the_email(fake_redis) -> None:
    for _ in range(MAX_ATTEMPTS):
        register_failed_login_attempt("Cible@Example.com")

    with pytest.raises(TooManyRequestsError):
        enforce_login_rate_limit("  cible@example.com  ")


def test_enforce_login_rate_limit_fails_closed_when_redis_is_unavailable(broken_redis) -> None:
    with pytest.raises(ServiceUnavailableError) as exc_info:
        enforce_login_rate_limit("qui-que-ce-soit@example.com")

    assert exc_info.value.code == "service_unavailable"
    assert exc_info.value.status_code == 503


def test_register_failed_login_attempt_fails_closed_when_redis_is_unavailable(broken_redis) -> None:
    with pytest.raises(ServiceUnavailableError):
        register_failed_login_attempt("qui-que-ce-soit@example.com")


def test_clear_login_attempts_fails_closed_when_redis_is_unavailable(broken_redis) -> None:
    with pytest.raises(ServiceUnavailableError):
        clear_login_attempts("qui-que-ce-soit@example.com")


def test_service_unavailable_never_logs_a_secret(broken_redis, capsys) -> None:
    """Même discipline que
    test_logging.py::test_database_connection_error_never_leaks_the_password :
    le message de l'exception Redis embarque un secret factice (broken_redis),
    _guarded ne doit jamais le faire passer dans un log ni dans le message
    exposé au client.

    Capture le vrai stdout (comme test_logging.py::test_production_output_is_json)
    plutôt que structlog.testing.capture_logs() : ce module a un logger créé une
    seule fois à l'import (cache_logger_on_first_use=True côté configure_logging),
    et capture_logs() n'intercepte plus fiablement un logger déjà mis en cache par
    un test antérieur d'un autre fichier — capsys observe la sortie réellement
    émise, indépendamment de cet état partagé."""
    configure_logging("development")
    secret = broken_redis

    with pytest.raises(ServiceUnavailableError) as exc_info:
        enforce_login_rate_limit("qui-que-ce-soit@example.com")

    captured = capsys.readouterr()
    assert "rate_limit_backend_unavailable" in captured.out, "un log aurait dû être émis"
    assert secret not in captured.out
    assert secret not in exc_info.value.message
