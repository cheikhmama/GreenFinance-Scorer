import uuid
from unittest.mock import patch

import pytest
import redis

from app.company.import_rate_limit import MAX_IMPORTS, enforce_url_import_rate_limit
from app.core.exceptions import ServiceUnavailableError, TooManyRequestsError


class _FakeRedis:
    """Même double minimal que tests/unit/test_rate_limit.py::_FakeRedis -- reste vert sans
    dépendre d'un serveur Redis réel (ARCHITECTURE.md §7)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key: str, seconds: int) -> None:
        pass


class _BrokenRedis:
    def _boom(self, *_a: object, **_k: object) -> None:
        raise redis.ConnectionError("connexion Redis coupée")

    incr = _boom
    expire = _boom


@pytest.fixture()
def fake_redis():
    client = _FakeRedis()
    with patch("app.company.import_rate_limit.get_redis_client", return_value=client):
        yield client


@pytest.fixture()
def broken_redis():
    with patch("app.company.import_rate_limit.get_redis_client", return_value=_BrokenRedis()):
        yield


def test_enforce_url_import_rate_limit_allows_a_fresh_entreprise(fake_redis) -> None:
    enforce_url_import_rate_limit(uuid.uuid4())  # ne lève rien


def test_enforce_url_import_rate_limit_allows_up_to_the_threshold(fake_redis) -> None:
    entreprise_id = uuid.uuid4()
    for _ in range(MAX_IMPORTS):
        enforce_url_import_rate_limit(entreprise_id)  # ne lève rien jusqu'au seuil inclus


def test_enforce_url_import_rate_limit_raises_past_the_threshold(fake_redis) -> None:
    entreprise_id = uuid.uuid4()
    for _ in range(MAX_IMPORTS):
        enforce_url_import_rate_limit(entreprise_id)

    with pytest.raises(TooManyRequestsError) as exc_info:
        enforce_url_import_rate_limit(entreprise_id)
    assert exc_info.value.code == "import_url_limite_atteinte"


def test_enforce_url_import_rate_limit_is_scoped_per_entreprise(fake_redis) -> None:
    premiere = uuid.uuid4()
    seconde = uuid.uuid4()
    for _ in range(MAX_IMPORTS):
        enforce_url_import_rate_limit(premiere)

    enforce_url_import_rate_limit(seconde)  # ne lève rien, compteur distinct


def test_enforce_url_import_rate_limit_fails_closed_when_redis_is_unavailable(broken_redis) -> None:
    with pytest.raises(ServiceUnavailableError) as exc_info:
        enforce_url_import_rate_limit(uuid.uuid4())
    assert exc_info.value.code == "service_unavailable"
    assert exc_info.value.status_code == 503
