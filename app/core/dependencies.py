"""Dépendances FastAPI transversales, non liées à un domaine métier précis.

get_current_user lit le jeton d'accès depuis le cookie httpOnly posé par
POST /auth/login (app/auth/router.py), le valide (app/auth/tokens.py) et
recharge l'Utilisateur correspondant. Toute route protégée le déclare via
Depends(get_current_user) — jamais de vérification de jeton dupliquée
ailleurs dans une route métier.
"""

import uuid

from fastapi import Cookie, Depends
from sqlmodel import Session

from app.auth.models import Utilisateur
from app.auth.tokens import COOKIE_NAME, InvalidTokenError, decode_access_token
from app.core.database import get_session
from app.core.exceptions import UnauthorizedError

__all__ = ["get_current_user", "get_session"]


def get_current_user(
    session: Session = Depends(get_session),
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> Utilisateur:
    if access_token is None:
        raise UnauthorizedError("Authentification requise.", code="not_authenticated")

    try:
        payload = decode_access_token(access_token)
        user_id = uuid.UUID(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Jeton invalide ou expiré.", code="invalid_token") from exc

    user = session.get(Utilisateur, user_id)
    if user is None or not user.actif:
        raise UnauthorizedError("Compte introuvable ou désactivé.", code="not_authenticated")
    return user
