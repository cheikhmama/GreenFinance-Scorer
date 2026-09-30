"""Limitation du débit des tentatives de connexion : par e-mail ET par adresse IP.

- Par e-mail (MAX_ATTEMPTS) : empêche un brute-force ciblé sur un compte donné.
- Par IP (MAX_ATTEMPTS_PAR_IP, seuil plus large) : empêche la pulvérisation d'un même mot de
  passe courant sur de nombreux comptes, que la seule limite par e-mail ne voit pas.

L'IP est celle que fournit le serveur ASGI (request.client.host), jamais un en-tête lu
directement : derrière un reverse-proxy, uvicorn ne la réécrit depuis X-Forwarded-For que pour
les proxys listés dans FORWARDED_ALLOW_IPS (voir docs/ARCHITECTURE.md §8). Même règle que
app/contact/router.py.

Échec fermé si Redis est indisponible : une 503 explicite plutôt qu'un login qui réussirait sans
aucune limitation, ou qu'une 500 générique qui masquerait la vraie cause. Le message journalisé
est fixe — jamais str(exc) — pour ne jamais risquer de journaliser un identifiant de connexion
Redis (voir tests/unit/test_rate_limit.py::test_service_unavailable_never_logs_a_secret).
"""

import hashlib
from collections.abc import Callable
from typing import TypeVar

import redis
import structlog

from app.core.exceptions import ServiceUnavailableError, TooManyRequestsError
from app.core.redis import get_redis_client, incrementer_fenetre, lire_entier

logger = structlog.get_logger(__name__)

MAX_ATTEMPTS = 5
MAX_ATTEMPTS_PAR_IP = 30
WINDOW_SECONDS = 15 * 60

T = TypeVar("T")


def _key(email: str) -> str:
    return f"login_attempts:{email.strip().lower()}"


def _key_ip(adresse_ip: str) -> str:
    # Empreinte plutôt que l'IP en clair dans Redis — même choix que app/contact/router.py.
    return f"login_attempts_ip:{hashlib.sha256(adresse_ip.encode()).hexdigest()}"


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


def enforce_login_rate_limit(email: str, adresse_ip: str | None = None) -> None:
    """À appeler avant toute vérification d'identifiants — lève avant même de toucher la base si
    un des seuils est déjà atteint. `adresse_ip` est omise pour les vérifications d'un compte déjà
    connecté (verifier/changer mot de passe), où seul le compte compte."""
    attempts = _guarded("get", lambda: lire_entier(get_redis_client(), _key(email)))
    if attempts is not None and attempts >= MAX_ATTEMPTS:
        raise TooManyRequestsError(
            "Trop de tentatives de connexion pour ce compte. Réessayez plus tard."
        )
    if adresse_ip is not None:
        par_ip = _guarded("get", lambda: lire_entier(get_redis_client(), _key_ip(adresse_ip)))
        if par_ip is not None and par_ip >= MAX_ATTEMPTS_PAR_IP:
            raise TooManyRequestsError(
                "Trop de tentatives de connexion depuis cette adresse. Réessayez plus tard."
            )


def register_failed_login_attempt(email: str, adresse_ip: str | None = None) -> None:
    client = get_redis_client()
    _guarded("incr", lambda: incrementer_fenetre(client, _key(email), WINDOW_SECONDS))
    if adresse_ip is not None:
        _guarded("incr", lambda: incrementer_fenetre(client, _key_ip(adresse_ip), WINDOW_SECONDS))


def clear_login_attempts(email: str) -> None:
    """Réinitialise seulement le compteur du compte : le compteur par IP continue de compter
    jusqu'à la fin de sa fenêtre — un succès sur UN compte ne doit jamais blanchir une IP qui
    pulvérise des mots de passe sur les autres."""
    _guarded("delete", lambda: get_redis_client().delete(_key(email)))
