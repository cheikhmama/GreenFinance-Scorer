"""Limitation du débit de tentatives de connexion, par e-mail.

Empêche un brute-force ciblé sur un compte donné (fenêtre fixe en Redis).
Volontairement limité par e-mail, pas par IP : une limitation par IP fiable
suppose un en-tête posé par un reverse-proxy de confiance (X-Forwarded-For),
pas encore en place — à ajouter si le besoin se confirme après déploiement,
sans changer le contrat des fonctions ci-dessous.

Échec fermé si Redis est indisponible : une 503 explicite plutôt qu'un login
qui réussirait sans aucune limitation, ou qu'une 500 générique qui masquerait
la vraie cause. Le message journalisé est fixe — jamais str(exc) — pour ne
jamais risquer de journaliser un identifiant de connexion Redis, même si
redis-py ne semble pas l'exposer aujourd'hui (voir
tests/unit/test_rate_limit.py::test_service_unavailable_never_logs_a_secret,
même discipline que
tests/unit/test_logging.py::test_database_connection_error_never_leaks_the_password
côté base de données).
"""

from collections.abc import Callable
from typing import TypeVar

import redis
import structlog

from app.core.exceptions import ServiceUnavailableError, TooManyRequestsError
from app.core.redis import get_redis_client

logger = structlog.get_logger(__name__)

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60

T = TypeVar("T")


def _key(email: str) -> str:
    return f"login_attempts:{email.strip().lower()}"


def _guarded(operation: str, call: Callable[[], T]) -> T:
    try:
        return call()
    except redis.RedisError as exc:
        logger.error(
            "rate_limit_backend_unavailable", operation=operation, error_type=type(exc).__name__
        )
        raise ServiceUnavailableError(
            "Service de connexion temporairement indisponible. Réessayez plus tard."
        ) from exc


def enforce_login_rate_limit(email: str) -> None:
    """À appeler avant toute vérification d'identifiants — lève avant même
    de toucher la base si le seuil est déjà atteint."""
    attempts = _guarded("get", lambda: get_redis_client().get(_key(email)))
    if attempts is not None and int(attempts) >= MAX_ATTEMPTS:
        raise TooManyRequestsError(
            "Trop de tentatives de connexion pour ce compte. Réessayez plus tard."
        )


def register_failed_login_attempt(email: str) -> None:
    key = _key(email)

    def _incr_and_expire() -> int:
        client = get_redis_client()
        attempts = client.incr(key)
        if attempts == 1:
            client.expire(key, WINDOW_SECONDS)
        return attempts

    _guarded("incr", _incr_and_expire)


def clear_login_attempts(email: str) -> None:
    _guarded("delete", lambda: get_redis_client().delete(_key(email)))
