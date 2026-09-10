import uuid
from unittest.mock import patch

import pytest
import redis

from app.auth.revocation import (
    current_generation,
    is_session_revoked,
    revoke_all_sessions,
)
from app.core.exceptions import ServiceUnavailableError


class _FakeRedis:
    """Double minimal — reproduit juste le sous-ensemble get/incr utilisé par
    app/auth/revocation.py, sans dépendre d'un serveur Redis réel (voir
    ARCHITECTURE.md §7)."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return str(self._store[key]) if key in self._store else None

    def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]


class _BrokenRedis:
    """Simule une panne Redis — même discipline que test_rate_limit.py::_BrokenRedis."""

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def _boom(self, *_args: object, **_kwargs: object) -> None:
        raise redis.ConnectionError(f"Error connecting with credentials pw={self._secret}")

    get = _boom
    incr = _boom


@pytest.fixture()
def fake_redis():
    client = _FakeRedis()
    with patch("app.auth.revocation.get_redis_client", return_value=client):
        yield client


@pytest.fixture()
def broken_redis():
    secret = "leak-me-not-x7z"
    client = _BrokenRedis(secret)
    with patch("app.auth.revocation.get_redis_client", return_value=client):
        yield secret


def test_an_untouched_user_is_at_generation_zero(fake_redis) -> None:
    assert current_generation(uuid.uuid4()) == 0


def test_a_token_from_an_earlier_generation_is_revoked(fake_redis) -> None:
    user_id = uuid.uuid4()
    token_generation = current_generation(user_id)  # 0, avant toute révocation

    revoke_all_sessions(user_id)

    assert is_session_revoked(user_id, token_generation) is True


def test_a_token_issued_at_the_post_revocation_generation_is_not_revoked(fake_redis) -> None:
    """Cas réel : changer de mot de passe révoque puis ré-ouvre une session sur la génération
    résultante (app/auth/router.py::changer_mot_de_passe) — la nouvelle session ne doit jamais
    se trouver invalidée par sa propre révocation, y compris exécutée dans la même seconde
    qu'une requête précédente (un compteur discret n'a pas ce problème, contrairement à un
    horodatage à la granularité de la seconde)."""
    user_id = uuid.uuid4()

    nouvelle_generation = revoke_all_sessions(user_id)

    assert is_session_revoked(user_id, nouvelle_generation) is False


def test_revoking_twice_invalidates_a_session_from_the_first_revocation(fake_redis) -> None:
    user_id = uuid.uuid4()

    premiere_generation = revoke_all_sessions(user_id)
    revoke_all_sessions(user_id)

    assert is_session_revoked(user_id, premiere_generation) is True


def test_revocation_is_scoped_to_the_user(fake_redis) -> None:
    revoked_user = uuid.uuid4()
    other_user = uuid.uuid4()

    revoke_all_sessions(revoked_user)

    assert is_session_revoked(other_user, 0) is False


def test_revoke_all_sessions_fails_closed_when_redis_is_unavailable(broken_redis) -> None:
    with pytest.raises(ServiceUnavailableError) as exc_info:
        revoke_all_sessions(uuid.uuid4())

    assert exc_info.value.status_code == 503


def test_is_session_revoked_fails_closed_when_redis_is_unavailable(broken_redis) -> None:
    with pytest.raises(ServiceUnavailableError):
        is_session_revoked(uuid.uuid4(), 0)


def test_service_unavailable_never_logs_a_secret(broken_redis, capsys) -> None:
    from app.core.logging import configure_logging

    configure_logging("development")
    secret = broken_redis

    with pytest.raises(ServiceUnavailableError) as exc_info:
        revoke_all_sessions(uuid.uuid4())

    captured = capsys.readouterr()
    assert "revocation_backend_unavailable" in captured.out
    assert secret not in captured.out
    assert secret not in exc_info.value.message
