"""Limitation du débit d'import automatique par URL, par entreprise (fenêtre fixe en Redis).

Même patron que app/auth/rate_limit.py : échec fermé si Redis est indisponible (503 explicite
plutôt qu'un import sans aucune limitation), message journalisé fixe (jamais str(exc)).
Nécessaire ici spécifiquement parce que app/company/url_fetch.py fait du serveur un client HTTP
sortant sur une cible fournie par l'appelant — sans plafond, un compte Entreprise pourrait servir
de proxy pour marteler une cible tierce à volonté.
"""

import uuid
from collections.abc import Callable
from typing import TypeVar

import redis
import structlog

from app.core.exceptions import ServiceUnavailableError, TooManyRequestsError
from app.core.redis import get_redis_client

logger = structlog.get_logger(__name__)

MAX_IMPORTS = 10
WINDOW_SECONDS = 60 * 60

T = TypeVar("T")


def _key(entreprise_id: uuid.UUID) -> str:
    return f"url_imports:{entreprise_id}"


def _guarded(operation: str, call: Callable[[], T]) -> T:
    try:
        return call()
    except redis.RedisError as exc:
        logger.error(
            "import_rate_limit_backend_unavailable",
            operation=operation,
            error_type=type(exc).__name__,
        )
        raise ServiceUnavailableError(
            "Service d'import temporairement indisponible. Réessayez plus tard."
        ) from exc


def enforce_url_import_rate_limit(entreprise_id: uuid.UUID) -> None:
    """À appeler avant tout téléchargement — lève avant même de contacter l'URL cible si le
    seuil est déjà atteint pour cette entreprise."""
    key = _key(entreprise_id)

    def _incr_and_expire() -> int:
        client = get_redis_client()
        attempts = client.incr(key)
        if attempts == 1:
            client.expire(key, WINDOW_SECONDS)
        return attempts

    attempts = _guarded("incr", _incr_and_expire)
    if attempts > MAX_IMPORTS:
        raise TooManyRequestsError(
            "Trop d'imports automatiques pour cette entreprise. Réessayez plus tard.",
            code="import_url_limite_atteinte",
        )
