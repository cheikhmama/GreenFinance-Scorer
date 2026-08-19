"""Émission et validation des jetons JWT d'accès.

Portée volontairement réduite à cette passe de l'Étape 9 : un jeton
d'accès unique, sans rotation par rafraîchissement ni révocation
server-side — voir FRONTEND-ARCHITECTURE.md / ARCHITECTURE.md pour le
choix de débloquer le login d'abord et la MFA (app/core/config.py,
mfa_issuer_name) dans une passe ultérieure.

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

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(hours=12)
COOKIE_NAME = "access_token"


class InvalidTokenError(Exception):
    """Jeton absent, expiré, mal signé ou de forme inattendue."""


def create_access_token(user_id: uuid.UUID, role: Role) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role.value,
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
