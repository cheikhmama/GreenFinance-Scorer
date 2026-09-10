"""Émission et validation des jetons JWT d'accès.

Un jeton embarque désormais la génération de session en vigueur à sa création (claim "gen",
voir app/auth/revocation.py) — c'est ce qui permet la révocation server-side alors que le jeton
lui-même reste, par nature, valide jusqu'à expiration une fois émis. La rotation par
rafraîchissement automatique reste hors périmètre (voir FRONTEND-ARCHITECTURE.md) : un jeton
expiré impose une reconnexion, pas un renouvellement silencieux.

Le jeton est transporté par un cookie httpOnly (voir app/auth/router.py) :
jamais lu ni écrit en JavaScript côté client, pour ne pas exposer le
jeton à un vol par XSS comme le ferait un stockage localStorage.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings
from app.core.enums import Role

# Défini ici (pas dans app/api/router.py, qui monte réellement ce préfixe) pour éviter un import
# circulaire : app/core/dependencies.py et app/auth/csrf.py en ont besoin pour comparer
# request.url.path — qui, à l'intérieur de la sous-application api_app montée par
# app.mount(API_V1_PREFIX, api_app) (voir app/main.py), conserve le préfixe complet plutôt que
# de le retirer (vérifié empiriquement, contrairement à l'intuition habituelle sur Mount).
API_V1_PREFIX = "/api/v1"

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(hours=12)
# Préfixe __Host- (Phase 3 §3.1) : le navigateur refuse de poser ce cookie sans Secure, Path=/ et
# sans attribut Domain — garantie structurelle qu'il ne peut jamais fuiter vers un sous-domaine
# ni être posé par une connexion non chiffrée, imposée par le navigateur lui-même, pas seulement
# par la configuration du serveur. Voir app/auth/router.py pour secure=True inconditionnel
# (nécessaire pour ce préfixe — fonctionne aussi en développement local via localhost).
COOKIE_NAME = "__Host-access_token"
CSRF_COOKIE_NAME = "__Host-csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


class InvalidTokenError(Exception):
    """Jeton absent, expiré, mal signé ou de forme inattendue."""


def create_access_token(user_id: uuid.UUID, role: Role, generation: int = 0) -> str:
    """generation : la génération de session en vigueur pour cet utilisateur au moment de
    l'émission (app/auth/revocation.py::current_generation, ou la valeur déjà renvoyée par
    revoke_all_sessions si ce jeton ré-ouvre une session juste après une révocation) — jamais
    0 par construction ailleurs que pour un utilisateur qui n'a encore jamais été révoqué."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "gen": generation,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
