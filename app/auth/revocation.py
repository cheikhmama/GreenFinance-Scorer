"""Révocation de session côté serveur (Phase 3 §3.1).

Un JWT reste par nature valide jusqu'à son expiration une fois émis — la seule façon de
l'invalider avant terme est de vérifier, à chaque requête authentifiée, qu'il n'a pas été
révoqué depuis. Choix délibéré : un compteur de génération par utilisateur (le jeton embarque
la génération en vigueur à sa création ; révoquer incrémente le compteur ; tout jeton portant
une génération inférieure à la valeur courante est invalide), pas un horodatage de coupure —
un compteur entier reste correct quelle que soit la précision temporelle réellement disponible
(la granularité à la seconde d'un iat JWT ne suffit pas à distinguer de façon fiable « une
session légitimement antérieure, mais émise la même seconde » d'« une session tout juste
ré-ouverte après cette révocation même » — un compteur discret n'a pas ce problème).

Échec fermé si Redis est indisponible, même discipline que app/auth/rate_limit.py : une 503
explicite plutôt qu'un accès qui réussirait sans que la révocation ait pu être vérifiée.
"""

import uuid
from collections.abc import Callable
from typing import TypeVar

import redis
import structlog

from app.core.exceptions import ServiceUnavailableError
from app.core.redis import get_redis_client, incrementer, lire_entier

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def _key(user_id: uuid.UUID) -> str:
    return f"session_generation:{user_id}"


def _guarded(operation: str, call: Callable[[], T]) -> T:
    try:
        return call()
    except redis.RedisError as exc:
        logger.error(
            "revocation_backend_unavailable", operation=operation, error_type=type(exc).__name__
        )
        raise ServiceUnavailableError(
            "Service de session temporairement indisponible. Réessayez plus tard."
        ) from exc


def current_generation(user_id: uuid.UUID) -> int:
    """Génération en vigueur pour cet utilisateur — 0 si jamais révoqué. À intégrer dans le
    jeton d'accès à sa création (voir app/auth/router.py::_ouvrir_session)."""
    valeur = _guarded("get", lambda: lire_entier(get_redis_client(), _key(user_id)))
    return valeur if valeur is not None else 0


def revoke_all_sessions(user_id: uuid.UUID) -> int:
    """Invalide tout jeton déjà émis pour cet utilisateur. À appeler à la déconnexion, après un
    changement de mot de passe et après un changement de rôle.

    Renvoie la nouvelle génération : pour ré-ouvrir immédiatement une nouvelle session après cet
    appel (changement de mot de passe/rôle), l'utiliser directement comme génération du nouveau
    jeton — jamais considérée comme révoquée par sa propre révocation, la comparaison portant
    sur une génération strictement inférieure, jamais égale."""
    return _guarded("incr", lambda: incrementer(get_redis_client(), _key(user_id)))


def is_session_revoked(user_id: uuid.UUID, token_generation: int) -> bool:
    """True si un jeton portant cette génération a été révoqué depuis son émission."""
    return token_generation < current_generation(user_id)
