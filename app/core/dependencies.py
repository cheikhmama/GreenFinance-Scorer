"""Dépendances FastAPI transversales, non liées à un domaine métier précis.

get_current_user lit le jeton d'accès depuis le cookie httpOnly posé par
POST /auth/login (app/auth/router.py), le valide (app/auth/tokens.py) et
recharge l'Utilisateur correspondant. Toute route protégée le déclare via
Depends(get_current_user) — jamais de vérification de jeton dupliquée
ailleurs dans une route métier.
"""

import uuid

from fastapi import Cookie, Depends, Request
from sqlmodel import Session

from app.auth.models import Utilisateur
from app.auth.revocation import is_session_revoked
from app.auth.tokens import (
    API_V1_PREFIX,
    COOKIE_NAME,
    InvalidTokenError,
    decode_access_token,
)
from app.core.database import get_session
from app.core.exceptions import PermissionDeniedError, UnauthorizedError

__all__ = ["get_current_user", "get_session"]

# Routes accessibles même quand doit_changer_mot_de_passe est vrai (Phase 3 §3.3) : juste assez
# pour que le compte puisse changer son mot de passe et se déconnecter, jamais le reste de l'API
# métier tant que ce n'est pas fait. request.url.path conserve le préfixe de montage complet à
# l'intérieur d'api_app (voir API_V1_PREFIX, app/auth/tokens.py).
_ROUTES_AUTORISEES_AVANT_CHANGEMENT_MDP = {
    f"{API_V1_PREFIX}/auth/me",
    f"{API_V1_PREFIX}/auth/changer-mot-de-passe",
    f"{API_V1_PREFIX}/auth/logout",
}


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> Utilisateur:
    if access_token is None:
        raise UnauthorizedError("Authentification requise.", code="not_authenticated")

    try:
        payload = decode_access_token(access_token)
        user_id = uuid.UUID(payload["sub"])
        generation = int(payload["gen"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise UnauthorizedError("Jeton invalide ou expiré.", code="invalid_token") from exc

    if is_session_revoked(user_id, generation):
        raise UnauthorizedError("Session révoquée.", code="session_revoked")

    user = session.get(Utilisateur, user_id)
    if user is None or not user.actif:
        raise UnauthorizedError("Compte introuvable ou désactivé.", code="not_authenticated")

    if user.doit_changer_mot_de_passe and request.url.path not in _ROUTES_AUTORISEES_AVANT_CHANGEMENT_MDP:
        raise PermissionDeniedError(
            "Le mot de passe doit être changé avant de continuer.",
            code="password_change_required",
        )

    return user
